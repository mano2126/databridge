"""
ai_conversion_orchestrator.py — Phase E-4 (2026-04-24)

AI 기반 SQL 오브젝트 변환을 오케스트레이션하는 중앙 모듈.

기존 문제:
  - 재시도 로직이 MSSQL 타겟 TRIGGER 에만 국한됨
  - 실패 시 같은 실수 반복 (AI 가 자기 실수 기억 못 함)
  - 실패 패턴이 KB 에 자동 축적 안 됨

이 모듈의 역할:
  1. AI 변환 요청을 받아서:
     - Pre-flight validator 로 사전 검증
     - 스키마 규칙 자동 주입 + 사후 정규화
     - JSON 파싱 견고화 (ai_response_parser)
  2. 실패 시 재시도:
     - 이전 실패의 구체적 원인을 프롬프트에 힌트로 주입
     - 최대 N 회 (기본 2회)
     - 같은 패턴 반복 시 rule-based fallback 으로 강제 전환
  3. 성공/실패 모두 KB 에 축적:
     - error_cases.txt (이미 존재하는 형식 유지)
     - 다음 변환 시 "알려진 위험 패턴" 으로 프롬프트에 주입

사용:
    from app.core.ai_conversion_orchestrator import convert_with_retry
    
    result = convert_with_retry(
        src_ddl=...,
        obj_type="PROCEDURE",
        obj_name="sp_test",
        src_db="mssql",
        tgt_db="mysql",
        job_id="...",
        max_retries=2,
        schema_strategy="underscore",
        executor_fn=lambda stmts: ...  # DB 실행 함수 (테스트용)
    )
"""

from __future__ import annotations
import os
import re
import json
import logging
import datetime
from typing import Callable, Optional

_log = logging.getLogger("databridge.ai_orchestrator")

# 실패 케이스 축적 파일 (기존 135줄에 이어서 추가됨)
ERROR_CASES_FILE = "prompts/mssql_to_mysql/error_cases.txt"


# ════════════════════════════════════════════════════════════════════════════
# 중앙 오케스트레이터
# ════════════════════════════════════════════════════════════════════════════

def convert_with_retry(
    src_ddl: str,
    obj_type: str,
    obj_name: str,
    src_db: str,
    tgt_db: str,
    job_id: str = "",
    max_retries: int = 2,
    schema_strategy: str = "underscore",
    known_schemas: Optional[list] = None,
    ai_convert_fn: Optional[Callable] = None,
    executor_fn: Optional[Callable] = None,
) -> dict:
    """
    AI 변환을 재시도 + 검증 + KB 축적과 함께 수행.
    
    Args:
        ai_convert_fn: (src_ddl, obj_type, obj_name, src_db, tgt_db, error_hint, job_id) -> dict
                       실제 AI 호출 함수 (schema._ai_convert_ddl 를 주입 가능)
        executor_fn:   (statements: list) -> (success: bool, error: str)
                       DB 실행 함수 (실전 사용 시)
    
    Returns:
        {
            "success": bool,
            "statements": [...],
            "notes": "...",
            "retries_used": int,
            "final_error": "..." | None,
            "preflight_fixes": [...],  # 자동 수정 내역
        }
    """
    from app.core.ai_response_parser import extract_json_robust
    from app.core.schema_conversion_policy import (
        build_schema_rule_prompt,
        enforce_schema_strategy,
    )
    from app.core.sql_preflight_validator import preflight_check, build_retry_hint
    
    # 재시도 누적 정보
    attempt_log = []
    accumulated_hint = ""
    kb_hint = _load_kb_hint(obj_type)  # 기존 KB 에서 교훈 추출
    
    for attempt in range(max_retries + 1):
        # ── 1) AI 호출 ──────────────────────────────
        full_hint = (kb_hint + "\n" + accumulated_hint).strip()
        
        if ai_convert_fn is None:
            return _fail("ai_convert_fn 이 제공되지 않음")
        
        try:
            ai_result = ai_convert_fn(
                src_ddl=src_ddl,
                obj_type=obj_type,
                obj_name=obj_name,
                src_db=src_db,
                tgt_db=tgt_db,
                error_hint=full_hint,
                job_id=job_id,
            )
        except Exception as e:
            _log.warning("[%s] AI 호출 실패 (attempt %d): %s", obj_name, attempt + 1, e)
            attempt_log.append({"attempt": attempt + 1, "error": f"AI 호출 실패: {e}"})
            if attempt < max_retries:
                accumulated_hint = f"Previous attempt failed at AI call stage: {e}"
                continue
            return _fail(f"AI 호출 실패 (재시도 소진): {e}", attempt_log)
        
        # ── 2) JSON 파싱 견고화 ──────────────────────
        # ai_result 가 이미 dict 면 그대로, 아니면 text 에서 추출
        if isinstance(ai_result, dict) and "statements" in ai_result:
            parsed = ai_result
        elif isinstance(ai_result, str):
            parsed = extract_json_robust(ai_result)
        else:
            parsed = {"statements": [], "notes": "invalid ai_result type"}
        
        statements = parsed.get("statements", [])
        if not statements:
            _log.warning("[%s] statements 비어있음 (attempt %d)", obj_name, attempt + 1)
            attempt_log.append({"attempt": attempt + 1, "error": "statements 비어있음"})
            if attempt < max_retries:
                accumulated_hint = (
                    "Previous response had no 'statements' array. "
                    "Return JSON strictly: {\"statements\":[\"...\"], \"notes\":\"...\"}"
                )
                continue
            return _fail("statements 파싱 실패 (재시도 소진)", attempt_log)
        
        # ── 3) 스키마 규칙 사후 정규화 ────────────────
        fixed_statements = []
        schema_fixes_total = []
        for stmt in statements:
            fixed_stmt, fixes = enforce_schema_strategy(
                stmt, schema_strategy, known_schemas
            )
            fixed_statements.append(fixed_stmt)
            schema_fixes_total.extend(fixes)
        
        if schema_fixes_total:
            _log.info("[%s] 스키마 정규화: %s", obj_name, schema_fixes_total)
        
        # ── 4) Pre-flight syntax validation ──────────
        all_issues = []
        preflight_fixes = []
        checked_statements = []
        
        for stmt in fixed_statements:
            pf = preflight_check(stmt, obj_type)
            if pf["issues"]:
                all_issues.extend(pf["issues"])
            if pf["auto_fixed_sql"] != stmt:
                preflight_fixes.append(f"[{obj_name}] preflight 자동 수정 적용")
                checked_statements.append(pf["auto_fixed_sql"])
            else:
                checked_statements.append(stmt)
        
        # fail 레벨 이슈 있으면 재시도 (자동 수정 안 됨)
        fail_issues = [i for i in all_issues if i.get("severity") == "fail"]
        if fail_issues and attempt < max_retries:
            retry_hint = build_retry_hint({"issues": fail_issues})
            accumulated_hint = retry_hint
            attempt_log.append({
                "attempt": attempt + 1,
                "error": "preflight fail",
                "issues": [i["rule"] for i in fail_issues],
            })
            continue
        
        # ── 5) 실행 시도 ──────────────────────────────
        if executor_fn is None:
            # executor_fn 없으면 검증만 하고 반환
            return {
                "success": True,
                "statements": checked_statements,
                "notes": parsed.get("notes", ""),
                "retries_used": attempt,
                "final_error": None,
                "preflight_fixes": preflight_fixes + schema_fixes_total,
                "warnings": [i for i in all_issues if i.get("severity") == "warn"],
            }
        
        exec_ok, exec_err = executor_fn(checked_statements)
        
        if exec_ok:
            # 성공 — KB 에 성공 케이스는 기록 안 함 (용량 문제)
            return {
                "success": True,
                "statements": checked_statements,
                "notes": parsed.get("notes", ""),
                "retries_used": attempt,
                "final_error": None,
                "preflight_fixes": preflight_fixes + schema_fixes_total,
            }
        
        # 실행 실패 — KB 에 누적 + 재시도
        _accumulate_error_case(
            obj_name=obj_name,
            obj_type=obj_type,
            error=exec_err,
            failed_sql=checked_statements[0] if checked_statements else "",
        )
        
        attempt_log.append({
            "attempt": attempt + 1,
            "error": exec_err,
        })
        
        if attempt < max_retries:
            # 다음 시도에 오류 메시지 힌트로
            accumulated_hint = (
                f"\nPrevious attempt failed at DB execution with error:\n{exec_err[:500]}\n"
                "This was the faulty SQL (first 500 chars):\n"
                f"{(checked_statements[0] if checked_statements else '')[:500]}\n"
                "Analyze the specific error and fix it in this retry."
            )
            continue
        
        # 최종 실패
        return _fail(
            f"DB 실행 실패 (재시도 소진): {exec_err}",
            attempt_log,
            statements=checked_statements,
        )
    
    return _fail("재시도 루프 종료 - 예상치 못한 경로", attempt_log)


# ════════════════════════════════════════════════════════════════════════════
# KB (실패 지식 베이스) 관리
# ════════════════════════════════════════════════════════════════════════════

def _load_kb_hint(obj_type: str) -> str:
    """
    error_cases.txt 에서 해당 obj_type 에 관련된 최근 교훈을 추출하여
    AI 프롬프트용 힌트로 변환.
    
    전체가 아닌 최근 N 개만 (프롬프트 길이 제약).
    """
    try:
        # backend 디렉토리 기준 상대 경로
        candidates = [
            ERROR_CASES_FILE,
            os.path.join(os.path.dirname(__file__), "..", "..", ERROR_CASES_FILE),
            os.path.join(os.getcwd(), ERROR_CASES_FILE),
        ]
        
        content = None
        for path in candidates:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                break
        
        if not content:
            return ""
        
        # 최근 20 케이스만 추출 (각 케이스는 [날짜] 로 시작)
        cases = re.split(r'\n\[(\d{4}-\d{2}-\d{2})\]', content)
        # cases[0] 은 헤더, 이후 [날짜, 본문] 쌍으로
        recent = []
        for i in range(1, min(len(cases), 41), 2):  # 최근 20개
            date = cases[i] if i < len(cases) else ""
            body = cases[i + 1] if i + 1 < len(cases) else ""
            if body:
                # obj_type 필터 (PROCEDURE/FUNCTION/VIEW/TRIGGER)
                if obj_type.upper() in body.upper() or obj_type.lower() in body.lower() or not obj_type:
                    recent.append(f"[{date}]{body}")
        
        if not recent:
            return ""
        
        # 최근 10개만 힌트로 (프롬프트 과부화 방지)
        hint_cases = recent[-10:]
        return (
            "\n[KNOWN RISKY PATTERNS from past conversions — AVOID these mistakes]\n"
            + "\n".join(hint_cases[:5])  # 5개로 더 줄임 (토큰 절약)
            + "\n[END OF KNOWN PATTERNS]\n"
        )
    
    except Exception as e:
        _log.warning("[KB] 힌트 로드 실패: %s", e)
        return ""


def _accumulate_error_case(obj_name: str, obj_type: str, error: str, failed_sql: str):
    """
    실패 케이스를 error_cases.txt 에 추가.
    기존 135줄 포맷 유지:
        [날짜] 오브젝트명 | 오류
          원인: ...
          해결: ...
    """
    try:
        candidates = [
            ERROR_CASES_FILE,
            os.path.join(os.path.dirname(__file__), "..", "..", ERROR_CASES_FILE),
            os.path.join(os.getcwd(), ERROR_CASES_FILE),
        ]
        
        target_path = None
        for path in candidates:
            parent = os.path.dirname(path) or "."
            if os.path.exists(parent):
                target_path = path
                break
        
        if not target_path:
            return  # KB 디렉토리 없음 — 조용히 skip
        
        date = datetime.datetime.now().strftime("%Y-%m-%d")
        error_brief = error[:200].replace("\n", " ")
        sql_brief = failed_sql[:300].replace("\n", " ")
        
        # 추정 원인/해결 (MySQL 에러 코드 기반)
        cause, solution = _guess_cause_and_solution(error)
        
        entry = (
            f"\n[{date}] {obj_name} ({obj_type}) | {error_brief}\n"
            f"  원인: {cause}\n"
            f"  해결: {solution}\n"
            f"  실패 SQL: {sql_brief}\n"
        )
        
        with open(target_path, "a", encoding="utf-8") as f:
            f.write(entry)
        
        _log.info("[KB] 실패 케이스 축적: %s (%s)", obj_name, error_brief[:80])
    
    except Exception as e:
        _log.warning("[KB] 축적 실패: %s", e)


def _guess_cause_and_solution(error: str) -> tuple[str, str]:
    """
    MySQL 에러 메시지에서 원인과 해결책을 휴리스틱으로 추정.
    """
    err_lower = error.lower()
    
    if "1064" in error:
        if "update" in err_lower and "where" in err_lower:
            return (
                "UPDATE SET 절에서 WHERE 전 세미콜론 찍힘",
                "SET col=X, col2=Y WHERE ... — 세미콜론 없이 WHERE 로 이어가기",
            )
        if "create procedure" in err_lower or "create function" in err_lower:
            return (
                "프로시저/함수 DELIMITER 없이 BEGIN-END 내 세미콜론 때문",
                "cur.execute() 로 단일 실행 + MULTI_STATEMENTS 비활성화 필요",
            )
        return ("문법 오류 (1064)", "에러 메시지의 'near' 부분 확인 후 재변환")
    
    if "1146" in error:
        return (
            "참조 테이블이 존재하지 않음",
            "스키마 변환 규칙 불일치 (schema.table → 변환 방식 확인). "
            "schema_conversion_policy 적용 권장",
        )
    
    if "1049" in error:
        return (
            "Unknown database — 스키마를 별도 database 로 해석함",
            "`schema`.`table` 대신 schema_table 또는 schema 제거 필요",
        )
    
    if "1406" in error:
        return (
            "데이터 길이 초과",
            "파라미터/컬럼 타입 길이 원본 유지 (VARCHAR(8) → 10 등 확장 금지)",
        )
    
    if "already exists" in err_lower:
        return ("동일 이름 객체 존재", "DROP IF EXISTS 를 CREATE 앞에 추가")
    
    return ("실행 실패", "에러 메시지 분석 후 재시도")


def _fail(reason: str, attempt_log: Optional[list] = None, statements: Optional[list] = None) -> dict:
    return {
        "success": False,
        "statements": statements or [],
        "notes": "",
        "retries_used": len(attempt_log) if attempt_log else 0,
        "final_error": reason,
        "attempt_log": attempt_log or [],
    }
