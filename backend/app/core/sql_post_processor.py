"""
SQL Post Processor - 자기학습 SQL 사후 보정 시스템 (v90.34)

본부장님 모토: "지금은 발생해도 앞으로 똑같은건 발생 시키지 않는다"

3단계 자기학습 사이클:
    [1] 보정 룰 (POSTPROCESS_RULES) - 알려진 패턴 자동 수정
    [2] 잘림 검출 (validate_ddl_complete) - 미완성 DDL 사전 차단
    [3] KB 자동 등록 (log_failure_to_kb) - 다음 변환 prompt 에 포함

본부장님 캐피탈사 현장 발견 패턴 (2026-04-26):
    - SP_SET_TABLE_COMMENT: AI 응답 statements 분리 시 [DROP, ";", CREATE]
                            → 빈 ; statement 가 1064 야기
    - sp_Softphone_UpdateRecord: AI 응답 max_tokens 잘림
                                  → BEGIN 만 있고 END 없는 DDL → 1064
"""

import re
import logging
from datetime import datetime
from pathlib import Path

_log = logging.getLogger("databridge.sql_postproc")

# ─────────────────────────────────────────────────────────────────
# 보정 룰 - 본부장님 모토: 똑같은 건 다시 안 발생!
# ─────────────────────────────────────────────────────────────────

POSTPROCESS_RULES = [
    {
        "id": "R-001",
        "name": "빈 세미콜론 statement 제거",
        "pattern": r"(?:^|\n)\s*;\s*(?=\n|$)",
        "replacement": "\n",
        "description": "AI 응답 분리 시 생기는 단독 ; 제거 (1064 방지)",
        "case": "SP_SET_TABLE_COMMENT (2026-04-26)",
    },
    {
        "id": "R-002",
        "name": "DDL 시작의 빈 ;",
        "pattern": r"^\s*;\s*\n",
        "replacement": "",
        "description": "statement 첫 줄이 ; 만 있는 경우 제거",
    },
    {
        "id": "R-003",
        "name": "이중 세미콜론 단일화",
        "pattern": r";\s*;",
        "replacement": ";",
        "description": ";; → ; (AI 가 종종 만드는 실수)",
    },
    {
        "id": "R-004",
        "name": "BEGIN 다음 빈 ;",
        "pattern": r"(BEGIN\s*\n)\s*;\s*\n",
        "replacement": r"\1",
        "description": "BEGIN 직후의 빈 statement 제거",
    },
    {
        "id": "R-005",
        "name": "END 직전 빈 ;",
        "pattern": r"\n\s*;\s*(\n\s*END\b)",
        "replacement": r"\1",
        "description": "END 직전 빈 ; 제거",
    },
    # ════════════════════════════════════════════════════════════════
    # v90.51 추가 룰 (본부장님 결정 2026-04-27 — 4건 1064 잡기)
    # ════════════════════════════════════════════════════════════════
    {
        "id": "R-006",
        "name": "UPDATE SET ... ; WHERE 잘못된 세미콜론",
        # SET col=X; WHERE → SET col=X WHERE
        # SET col=X;\n WHERE → SET col=X\n WHERE
        # 단순 라인 끝 세미콜론 + 공백 + WHERE
        "pattern": r"(SET\s+[^;]+?)\s*;\s*(\n\s*)(WHERE\b)",
        "replacement": r"\1\2\3",
        "description": "UPDATE/MERGE 의 SET 절 끝 세미콜론 (sp_assign_collector 케이스)",
        "case": "v90.51 sp_assign_collector",
    },
    {
        "id": "R-007",
        "name": "SET 'value',; 콤마+세미콜론",
        # SET col1='X',;\n  col2=Y → SET col1='X',\n  col2=Y
        "pattern": r"(=\s*[^,;]+,)\s*;\s*(\n)",
        "replacement": r"\1\2",
        "description": "AI가 콤마 뒤 세미콜론 잘못 추가 (sp_approve_application 케이스)",
        "case": "v90.51 sp_approve_application",
    },
    {
        "id": "R-008",
        "name": "INSERT/UPDATE 끝 LIMIT 잘못",
        # ); LIMIT 1; → );    (INSERT는 LIMIT 사용 불가)
        # \n\tLIMIT N; \n  END 패턴
        "pattern": r"(\)\s*;)\s*\n\s*LIMIT\s+\d+\s*;\s*(\n)",
        "replacement": r"\1\2",
        "description": "INSERT/UPDATE/DELETE 끝의 의미 없는 LIMIT N 제거 (sp_mark_delinquent)",
        "case": "v90.51 sp_mark_delinquent",
    },
    {
        "id": "R-009",
        "name": "RETURN CASE; 잘못된 세미콜론",
        # RETURN CASE;\n  WHEN ... → RETURN CASE\n  WHEN ...
        "pattern": r"(\bRETURN\s+CASE)\s*;\s*(\n)",
        "replacement": r"\1\2",
        "description": "CASE 표현식 시작 직후 잘못된 세미콜론 (fn_delinq_stage)",
        "case": "v90.51 fn_delinq_stage",
    },
    {
        "id": "R-010",
        "name": "CASE/WHEN/THEN 직후 잘못된 세미콜론 (v90.54 정밀화)",
        # CASE; → CASE
        # WHEN x;\n THEN → WHEN x THEN
        # ELSE 'X';\n END → ELSE 'X' END (단, 다른 statement 가 따라오는 일반 케이스 영향 없도록 좁게)
        #
        # v90.54 변경: [^;]+ → [^;\n]+ 로 줄바꿈 차단.
        # 기존 정규식이 줄바꿈 포함 greedy 매칭으로 정상 SQL 의 END; 까지 손상시킴.
        # 
        # 본부장님 환경 fn_delinq_stage 케이스:
        #   AI 정상 출력: ELSE 'WRITEOFF' / END;\n END
        #   기존 R-010 손상: ELSE 'WRITEOFF' / END\n END  (CASE 종료 ; 손실 → 1064)
        #   v90.54 R-010: 정상 SQL 그대로 유지.
        "pattern": r"\b(CASE|WHEN\s+[^;\n]+|THEN\s+[^;\n]+|ELSE\s+[^;\n]+)\s*;\s*(\n\s*(?:WHEN|THEN|ELSE|END)\b)",
        "replacement": r"\1\2",
        "description": "CASE 표현식 안에 잘못 들어간 세미콜론 (보조 룰, R-009 보완)",
    },
]


def post_process_sql(sql: str, obj_name: str = "", verbose: bool = True) -> tuple[str, list[str]]:
    """SQL 사후 보정 - 알려진 패턴 자동 수정."""
    if not sql or not sql.strip():
        return sql, []
    
    applied = []
    for rule in POSTPROCESS_RULES:
        try:
            new_sql, count = re.subn(
                rule["pattern"], rule["replacement"], sql, flags=re.MULTILINE
            )
            if count > 0:
                applied.append(f"{rule['id']} x{count}")
                if verbose:
                    _log.info("[SQL-PostProc] [%s] %s 적용: %d회",
                              obj_name or "?", rule["id"], count)
                sql = new_sql
        except re.error as e:
            _log.warning("[SQL-PostProc] %s 정규식 오류: %s", rule["id"], e)
    
    return sql, applied


def post_process_statements(statements: list, obj_name: str = "") -> tuple[list, list]:
    """Statement 리스트 단위 보정 + 빈 statement 제거."""
    if not statements:
        return statements, []
    
    cleaned = []
    all_fixes = []
    removed_empty = 0
    
    for stmt in statements:
        stmt = stmt.strip() if stmt else ""
        # 빈 statement 또는 ; 만 있는 것 제거
        if not stmt or re.fullmatch(r"\s*;?\s*", stmt):
            removed_empty += 1
            continue
        new_stmt, fixes = post_process_sql(stmt, obj_name, verbose=False)
        cleaned.append(new_stmt)
        all_fixes.extend(fixes)
    
    if removed_empty > 0:
        all_fixes.append(f"R-EMPTY x{removed_empty}")
        _log.info("[SQL-PostProc] [%s] 빈 statement %d개 제거", obj_name, removed_empty)
    
    return cleaned, all_fixes


def validate_ddl_complete(ddl: str, obj_type: str = "PROCEDURE", obj_name: str = "") -> tuple[bool, str]:
    """
    DDL 완성도 검증 (AI 응답 잘림 사전 차단).
    본부장님 캐피탈사 케이스: sp_Softphone_UpdateRecord 가 max_tokens 잘림 → BEGIN..END 짝 안 맞음
    
    Returns: (is_complete, reason)
    """
    if not ddl or not ddl.strip():
        return False, "DDL 비어있음"
    
    ddl_upper = ddl.upper()
    
    # CREATE PROCEDURE/FUNCTION 인 경우
    if obj_type.upper() in ("PROCEDURE", "FUNCTION", "TRIGGER"):
        if "BEGIN" in ddl_upper:
            # BEGIN 개수와 END 개수가 같아야 함 (CASE..END, IF..END IF 등 제외)
            # 단순히 단어 경계의 BEGIN/END 만 비교
            
            # BEGIN 이후 본문 추출
            begin_idx = ddl_upper.find("BEGIN")
            body = ddl_upper[begin_idx:]
            
            # 마지막 줄이 END; 또는 END 로 끝나야 함
            body_stripped = body.rstrip().rstrip(';').rstrip()
            if not body_stripped.endswith("END"):
                # 혹시 라인 잘림 (마지막 줄이 한 줄 안 끝남)
                last_line = ddl.strip().split('\n')[-1].strip()
                if len(last_line) > 0 and not last_line.endswith((';', 'END', 'end')):
                    return False, f"DDL 미완성 - 마지막: '{last_line[-60:]}'"
                return False, f"DDL 끝이 END 가 아님 (잘림 의심)"
            
            # BEGIN/END 카운트 균형 체크 (단어 경계로)
            begin_count = len(re.findall(r'\bBEGIN\b', ddl_upper))
            # END 는 END IF, END WHILE, END LOOP, END CASE, END REPEAT, END HANDLER 별도 카운트
            total_end = len(re.findall(r'\bEND\b', ddl_upper))
            inner_end = len(re.findall(r'\bEND\s+(IF|WHILE|LOOP|CASE|REPEAT|HANDLER)\b', ddl_upper))
            block_end = total_end - inner_end
            
            if block_end < begin_count:
                return False, f"BEGIN/END 짝 불일치 (BEGIN {begin_count}개 / END {block_end}개)"
    
    return True, ""


def log_failure_to_kb(
    obj_name: str,
    obj_type: str,
    src_db: str,
    tgt_db: str,
    error_msg: str,
    failed_ddl: str = "",
    kb_path: str = "",
):
    """
    실패 케이스를 KB 에 자동 등록.
    다음 AI 변환 시 prompt 에 포함되어 재발 방지.
    """
    if not kb_path:
        kb_path = f"prompts/{src_db.lower()}_to_{tgt_db.lower()}/error_cases.txt"
    
    try:
        kb_file = Path(kb_path)
        if not kb_file.is_absolute():
            base = Path(__file__).parent.parent.parent
            kb_file = base / kb_path
        
        kb_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 에러 코드 + near 패턴 추출
        err_match = re.search(r'\((\d{4}),', error_msg)
        err_code = err_match.group(1) if err_match else "?"
        line_match = re.search(r"near '([^']{0,60})'\s*at line\s*(\d+)", error_msg)
        near_pattern = line_match.group(1) if line_match else ""
        line_no = line_match.group(2) if line_match else ""
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        entry = f"""
[{date_str}] {obj_name} | ({err_code}) {error_msg[:120]}
  타입: {obj_type}
  near: {near_pattern!r} (line {line_no})
  자동 등록 (v90.34 self-learning)
  TODO: 패턴 분석 후 sql_post_processor.POSTPROCESS_RULES 에 룰 추가 → 영구 해결
"""
        with open(kb_file, 'a', encoding='utf-8') as f:
            f.write(entry)
        
        _log.info("[SQL-PostProc] KB 자동 등록: %s → %s", obj_name, kb_file.name)
        return True
    except Exception as e:
        _log.warning("[SQL-PostProc] KB 등록 실패: %s", e)
        return False


def get_kb_summary(src_db: str = "mssql", tgt_db: str = "mysql", max_entries: int = 30) -> str:
    """AI prompt 에 포함시킬 KB 요약 (최근 실패 패턴 + 해결책)."""
    kb_path = f"prompts/{src_db.lower()}_to_{tgt_db.lower()}/error_cases.txt"
    base = Path(__file__).parent.parent.parent
    kb_file = base / kb_path
    
    if not kb_file.exists():
        return ""
    
    try:
        with open(kb_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 항목 분리 (날짜로 시작하는 줄 기준)
        entries = re.split(r'\n(?=\[\d{4}-\d{2}-\d{2}\])', content)
        # 가장 최근 N 개
        recent = entries[-max_entries:] if len(entries) > max_entries else entries
        return "\n".join(recent).strip()
    except Exception as e:
        _log.warning("[SQL-PostProc] KB 읽기 실패: %s", e)
        return ""


def build_prompt_kb_section(src_db: str = "mssql", tgt_db: str = "mysql") -> str:
    """
    AI prompt 에 포함시킬 KB 섹션 (포맷 완성).
    
    본부장님 모토 적용:
        한 번 발생한 패턴은 prompt 에 포함 → AI 가 그 패턴 회피
    """
    kb_text = get_kb_summary(src_db, tgt_db)
    if not kb_text:
        return ""
    
    return f"""
=== 과거 발생 오류 회피 가이드 (절대 발생시키지 마세요) ===
다음 패턴들은 과거 실제로 변환 실패를 야기한 것들입니다.
이 패턴을 절대 만들지 마세요:

{kb_text}

=== 가이드 끝 ===
"""

