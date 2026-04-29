"""
ai_response_parser.py — Phase E-1 (2026-04-24)

AI (Claude/GPT) 응답에서 JSON 을 견고하게 추출하는 파서.

배경:
  기존 _ai_convert_ddl() 는 json.loads() 를 엄격하게 사용하여
  아래 같은 실패가 빈번했음:
    - "Extra data: line 3 column 1 (char 506)"
    - AI 가 JSON 뒤에 설명 텍스트 붙임
    - 응답 시작에 ```json 펜스, 끝에 설명
    - trailing comma, 싱글쿼트, 주석 등

  이 모듈은 여러 fallback 전략으로 JSON 을 "최대한 긁어내는" 것이 목표.

사용법:
    from app.core.ai_response_parser import extract_json_robust
    result = extract_json_robust(ai_text)
    # result = {"statements": [...], "notes": "..."} 또는 {"statements": [], "notes": "파싱실패: ..."}
"""

from __future__ import annotations
import json
import re
import logging
from typing import Optional

_log = logging.getLogger("databridge.ai_parser")

# ════════════════════════════════════════════════════════════════════════════
# 공개 API
# ════════════════════════════════════════════════════════════════════════════

def extract_json_robust(text: str) -> dict:
    """
    AI 응답에서 JSON 객체를 최대한 견고하게 추출.
    
    Returns:
        {"statements": [...], "notes": "..."}  — 파싱 성공
        {"statements": [], "notes": "파싱 실패: ..."}  — 실패
    """
    if not text or not text.strip():
        return _fail("빈 응답")

    # 단계별 시도 — 각 단계가 실패하면 다음 단계로
    strategies = [
        ("원본 그대로", _strategy_raw),
        ("코드 펜스 제거", _strategy_remove_fences),
        ("첫 JSON 객체 추출", _strategy_first_json_object),
        ("statements 배열 직접 추출", _strategy_statements_array),
        ("공격적 정규식 수리", _strategy_aggressive_repair),
    ]

    errors = []
    for name, strategy in strategies:
        try:
            result = strategy(text)
            if result is not None and _is_valid(result):
                if errors:
                    _log.info("[AI 파서] '%s' 전략으로 복구 성공 (이전 %d 회 실패)", name, len(errors))
                return _normalize(result)
        except Exception as e:
            errors.append(f"{name}: {e}")
            continue

    # 모두 실패 — 디버깅 정보 포함해서 반환
    _log.warning("[AI 파서] 모든 전략 실패. 응답 첫 200자: %s", text[:200])
    return _fail(f"모든 파싱 전략 실패 ({len(errors)}회): {errors[0] if errors else 'unknown'}")


# ════════════════════════════════════════════════════════════════════════════
# 개별 전략 (순서 중요: 보수적 → 공격적)
# ════════════════════════════════════════════════════════════════════════════

def _strategy_raw(text: str) -> Optional[dict]:
    """전략 1: 원본 그대로 json.loads"""
    return json.loads(text.strip())


def _strategy_remove_fences(text: str) -> Optional[dict]:
    """전략 2: ```json ... ``` 펜스 및 설명 텍스트 제거"""
    cleaned = text.strip()
    
    # 시작 펜스 제거 (```json, ```JSON, ``` 등)
    cleaned = re.sub(r'^```(?:json|JSON)?\s*\n?', '', cleaned)
    # 끝 펜스 제거
    cleaned = re.sub(r'\n?```\s*$', '', cleaned)
    
    # 시작이 { 가 아니면, 첫 { 위치로 이동
    if not cleaned.startswith('{'):
        brace_idx = cleaned.find('{')
        if brace_idx > 0:
            cleaned = cleaned[brace_idx:]
    
    # 끝이 } 이후에 텍스트가 있으면 제거 ("Extra data" 에러 방지)
    # 중괄호 깊이를 세서 최상위 } 까지만 사용
    depth = 0
    in_string = False
    escape_next = False
    last_close = -1
    
    for i, ch in enumerate(cleaned):
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                last_close = i
                break
    
    if last_close > 0:
        cleaned = cleaned[:last_close + 1]
    
    return json.loads(cleaned)


def _strategy_first_json_object(text: str) -> Optional[dict]:
    """전략 3: 텍스트 어디든 있는 첫 JSON 객체 찾기 (statements 필드 포함)
    
    v90.33: ReDoS 안전화 - 정규식 catastrophic backtracking 위험 제거
        본부장님 케이스 진단: AI 응답 수신 후 시스템 hang
        원인: re.findall(r'\\{[^{}]*\\}', text, re.DOTALL) 같은 패턴이
              중첩 brace 가진 큰 응답에서 무한 백트래킹
        해결: 정규식 대신 단순 brace counting (O(n) 보장)
    """
    # "statements" 키워드 인덱스 찾기 (안전한 단순 검색)
    idx = text.find('"statements"')
    if idx < 0:
        return None
    
    # 그 앞으로 가서 시작 brace { 찾기
    start = text.rfind('{', 0, idx)
    if start < 0:
        return None
    
    # brace counting 으로 매칭하는 닫는 } 찾기 (O(n))
    depth = 0
    in_str = False
    escape = False
    for i in range(start, min(start + 100000, len(text))):  # 최대 100KB 보호
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                # 매칭하는 } 찾음
                json_str = text[start:i+1]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    return None
    return None


def _strategy_statements_array(text: str) -> Optional[dict]:
    """전략 4: statements 배열만이라도 추출
    
    v90.33: ReDoS 안전화
        기존: re.search(r'"statements"\\s*:\\s*(\\[[^\\]]*(?:\\][^\\]]*)*\\])', ...)
              중첩 array 시 catastrophic backtracking 발생 가능
        해결: 단순 bracket counting
    """
    idx = text.find('"statements"')
    if idx < 0:
        return _extract_sql_blocks(text)
    
    # "statements" 다음의 [ 찾기 (콜론과 공백 건너뜀)
    bracket_start = text.find('[', idx)
    if bracket_start < 0 or bracket_start - idx > 20:  # 너무 멀면 다른 키
        return _extract_sql_blocks(text)
    
    # bracket counting (문자열 내부 [/] 무시)
    depth = 0
    in_str = False
    escape = False
    for i in range(bracket_start, min(bracket_start + 200000, len(text))):  # 최대 200KB
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                arr_str = text[bracket_start:i+1]
                try:
                    statements = json.loads(arr_str)
                    if isinstance(statements, list):
                        return {"statements": statements, "notes": "통계: statements 배열만 복구"}
                except json.JSONDecodeError:
                    pass
                break
    
    return _extract_sql_blocks(text)


def _strategy_aggressive_repair(text: str) -> Optional[dict]:
    """전략 5: 공격적 수리 — trailing comma, 싱글쿼트, 주석 등"""
    cleaned = text.strip()
    
    # 펜스 제거
    cleaned = re.sub(r'^```(?:json|JSON)?\s*\n?', '', cleaned)
    cleaned = re.sub(r'\n?```\s*$', '', cleaned)
    
    # 첫 { 부터 마지막 } 까지
    first = cleaned.find('{')
    last = cleaned.rfind('}')
    if first < 0 or last < first:
        return None
    cleaned = cleaned[first:last + 1]
    
    # trailing comma 제거: ,\s*} 또는 ,\s*]
    cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)
    
    # JSON 내 한줄 주석 제거 // ...
    cleaned = re.sub(r'(?<!:)//[^\n]*', '', cleaned)
    
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # 마지막 수단: SQL 블록 직접 추출
        return _extract_sql_blocks(text)


# ════════════════════════════════════════════════════════════════════════════
# 유틸리티
# ════════════════════════════════════════════════════════════════════════════

def _extract_sql_blocks(text: str) -> Optional[dict]:
    """
    응답에서 CREATE/DROP SQL 문장을 직접 추출.
    JSON 파싱 완전 실패 시 최후 수단.
    """
    statements = []
    
    # DROP ... ; 패턴
    for m in re.finditer(
        r'(?i)(DROP\s+(?:PROCEDURE|FUNCTION|TRIGGER|VIEW|TABLE|INDEX)[^;]*?);',
        text
    ):
        statements.append(m.group(1).strip())
    
    # CREATE ... END; 패턴 (프로시저/함수)
    for m in re.finditer(
        r'(?is)(CREATE\s+(?:OR\s+ALTER\s+)?'
        r'(?:PROCEDURE|FUNCTION|TRIGGER|VIEW)'
        r'.*?END\s*;?)',
        text
    ):
        stmt = m.group(1).strip()
        # 끝에 ; 없으면 추가
        if not stmt.endswith(';'):
            stmt += ';'
        statements.append(stmt)
    
    # CREATE VIEW ... ; 패턴 (END 없는 단순 VIEW)
    for m in re.finditer(
        r'(?is)(CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+[^;]+?);',
        text
    ):
        stmt = m.group(1).strip() + ';'
        if stmt not in statements:
            statements.append(stmt)
    
    if statements:
        return {
            "statements": statements,
            "notes": f"SQL 블록 직접 추출 ({len(statements)}개 발견)",
        }
    return None


def _is_valid(d: dict) -> bool:
    """결과가 유효한지 검증"""
    if not isinstance(d, dict):
        return False
    stmts = d.get("statements")
    if not isinstance(stmts, list):
        return False
    # 최소 1개 이상의 non-empty 문장
    return any(isinstance(s, str) and s.strip() for s in stmts)


def _normalize(d: dict) -> dict:
    """결과 정규화"""
    stmts = d.get("statements", [])
    # 빈 문자열 제거, strip
    stmts = [s.strip() for s in stmts if isinstance(s, str) and s.strip()]
    notes = d.get("notes", "") or ""
    return {"statements": stmts, "notes": str(notes)[:500]}  # notes 길이 제한


def _fail(reason: str) -> dict:
    """실패 결과 생성"""
    return {"statements": [], "notes": f"AI 응답 파싱 실패: {reason}"}
