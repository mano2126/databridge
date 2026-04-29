
import os as _os
import pathlib as _pathlib

_PROMPT_DIR = _pathlib.Path(__file__).parent.parent.parent / "prompts"


def _load_prompt_file(src_db: str, tgt_db: str, filename: str) -> str:
    """프롬프트 파일 로드. 없으면 빈 문자열 반환."""
    key = f"{src_db.lower()}_to_{tgt_db.lower()}"
    path = _PROMPT_DIR / key / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _build_prompt(src_db: str, tgt_db: str, obj_type: str, obj_name: str,
                  ddl: str, error_hint: str = "") -> str:
    """DB 조합 + 오브젝트 타입에 맞는 프롬프트 파일들을 조합하여 반환."""
    src_name = {"mssql":"SQL Server","mysql":"MySQL","mariadb":"MariaDB",
                "postgresql":"PostgreSQL","aurora":"Aurora MySQL"}.get(src_db.lower(), src_db)
    tgt_name = {"mssql":"SQL Server","mysql":"MySQL","mariadb":"MariaDB",
                "postgresql":"PostgreSQL","aurora":"Aurora MySQL"}.get(tgt_db.lower(), tgt_db)

    # 오류 섹션
    error_section = ""
    if error_hint:
        # ════════════════════════════════════════════════════════════════
        # v90.68 (2026-04-28): 흔한 오류 코드별 자동 강화 hint
        #   AI 가 일반 prompt 만 받고 어떻게 fix 할지 모름 → 오류 코드별
        #   구체적 처방 hint 를 자동으로 추가하여 AI 의 fix 정확도 향상.
        # v90.71 (2026-04-28): 환경 특정 객체명/파라미터명 제거 — 일반화
        # ════════════════════════════════════════════════════════════════
        _enhanced_hint = ""
        _h_lower = error_hint.lower()
        
        # 1406: Data too long for column → VARCHAR 길이 늘리기
        if "1406" in error_hint or "data too long" in _h_lower:
            _enhanced_hint += (
                "\n\n★★★★★ [1406 오류 강제 fix 룰] ★★★★★\n"
                "이 오류는 VARCHAR 파라미터 또는 컬럼 길이가 입력값보다 짧아서 발생.\n"
                "  ✅ 해결 1순위: 해당 VARCHAR 길이를 원본 그대로 유지 (절대 줄이지 말 것)\n"
                "  ✅ 해결 2순위: 의심스러우면 길이를 +50% 늘림 (예: VARCHAR(N) → VARCHAR(N*1.5))\n"
                "  ❌ 절대 금지: VARCHAR 를 DATE 로 바꾸기 (호출자가 문자열 넘기면 깨짐)\n"
                "  ❌ 절대 금지: VARCHAR(N) 의 N 을 줄이기\n"
                "오류 메시지에서 컬럼/파라미터 이름을 추출해 해당 항목의 길이만 조정하세요.\n"
            )
        
        # 1270: Illegal mix of collations → COLLATE 명시
        if "1270" in error_hint or "illegal mix of collations" in _h_lower or "collation" in _h_lower:
            _enhanced_hint += (
                "\n\n★★★★★ [1270 오류 강제 fix 룰] ★★★★★\n"
                "이 오류는 서버 collation(utf8mb4_unicode_ci) 과 테이블 컬럼 collation 충돌.\n"
                "  ✅ 해결: VARCHAR 파라미터를 테이블 컬럼과 비교 시 COLLATE 명시\n"
                "    예) WHERE col = p_val COLLATE utf8mb4_unicode_ci\n"
                "  ✅ 또는 DECLARE 시 명시: \n"
                "    DECLARE v_val VARCHAR(8) CHARSET utf8mb4 COLLATE utf8mb4_0900_ai_ci;\n"
                "    SET v_val = p_val;\n"
                "    WHERE col = v_val   -- 같은 collation 으로 비교\n"
            )
        
        # 1305: PROCEDURE does not exist → 객체 이름 확인 (대소문자/언더스코어)
        if "1305" in error_hint or "does not exist" in _h_lower:
            _enhanced_hint += (
                "\n\n★★★★★ [1305 오류 강제 fix 룰] ★★★★★\n"
                "객체가 타겟 DB에 없거나 이름이 다름.\n"
                "  ✅ 변환 후 객체 이름은 'schema_ObjectName' 형태 (언더스코어 평탄화)\n"
                "  ✅ MSSQL 의 dbo.sp_Foo → MySQL 의 dbo_sp_Foo 또는 sp_Foo\n"
                "  ❌ 'dbo.sp_Foo' 같이 점 표기 절대 안 됨\n"
            )
        
        # 1064: SQL syntax → 9대 패턴 참조
        if "1064" in error_hint or "sql syntax" in _h_lower:
            _enhanced_hint += (
                "\n\n★★★ [1064 오류 강제 fix 룰] ★★★\n"
                "system.txt 의 9대 패턴 (RETURN CASE;, SET ...; WHERE 등) 모두 검토 후 변환!\n"
            )
        
        error_section = (
            f"\n\n【최우선 수정 과제 — 아래 오류를 반드시 해결】\n"
            f"{error_hint[:600]}\n"
            "위 오류가 발생하지 않도록 변환된 DDL을 작성하세요."
            f"{_enhanced_hint}"
        )

    # 시스템 프롬프트 로드
    system = _load_prompt_file(src_db, tgt_db, "system.txt")
    if system:
        system = system.format(
            obj_type=obj_type, obj_name=obj_name,
            error_section=error_section
        )
    else:
        # 폴백: 기본 프롬프트
        system = (
            f"당신은 {src_name} → {tgt_name} 마이그레이션 전문가입니다.\n"
            f"{src_name} {obj_type} [{obj_name}] DDL을 {tgt_name} 8.0용으로 변환하세요.\n"
            f"{error_section}"
        )

    # 오브젝트 타입별 추가 규칙 로드
    type_file = {
        "FUNCTION":  "function.txt",
        "PROCEDURE": "procedure.txt",
        "SP":        "procedure.txt",
        "VIEW":      "view_trigger.txt",
        "TRIGGER":   "view_trigger.txt",
    }.get(obj_type.upper(), "")
    type_rules = _load_prompt_file(src_db, tgt_db, type_file) if type_file else ""

    # 오류 케이스 로드 (최근 10줄만)
    error_cases_raw = _load_prompt_file(src_db, tgt_db, "error_cases.txt")
    error_cases = ""
    if error_cases_raw:
        lines = [l for l in error_cases_raw.split("\n") if l.strip() and not l.startswith("#")]
        error_cases = "\n【과거 오류 패턴 — 반드시 참고】\n" + "\n".join(lines[-20:])

    prompt = f"{system}\n\n"
    if type_rules:
        prompt += f"{type_rules}\n\n"
    prompt += f"{error_cases}\n\n" if error_cases else ""
    prompt += (
        f"원본 {src_name} DDL:\n{ddl[:6000]}\n\n"
        "【응답 형식 — 엄수 필수】\n"
        "아래 JSON 한 줄만 반환. 마크다운 블록(```) 이나 설명문 금지.\n"
        "JSON 문법 규칙:\n"
        "  - DDL 안의 줄바꿈은 반드시 \\n 으로 이스케이프\n"
        "  - DDL 안의 따옴표(\") 는 반드시 \\\" 로 이스케이프\n"
        "  - DDL 안의 백슬래시(\\) 는 반드시 \\\\ 로 이스케이프\n"
        "  - 컨텐츠 전체가 단일 JSON 객체여야 함 (중간 끊김 없이)\n\n"
        '{"converted_ddl":"DDL전체(이스케이프 필수)","changes":["변경사항"],"warnings":["주의사항"]}'
    )
    return prompt

"""
obj_executor.py — MSSQL→MySQL 오브젝트 변환 및 배포 공통 모듈

위저드(jobs.py)와 오브젝트 탐색기(schema.py) 모두 이 모듈을 사용.
로직을 한 곳에서만 관리하여 중복/불일치 방지.
"""
import re
import logging
import json
import urllib.request
import urllib.error

logger = logging.getLogger("databridge.obj_executor")


# ── 1. MSSQL→MySQL 규칙 변환 ─────────────────────────────────────
def mssql_to_mysql_ddl(ddl: str, obj_type: str) -> tuple[str, list[str]]:
    """
    MSSQL DDL을 MySQL DDL로 규칙 기반 변환.
    Returns: (converted_ddl, warnings)
    """
    s = ddl
    warnings = []

    # ── SELECT @var = col FROM 변환 (@ 치환 이전에 먼저) ──────────
    def _fix_top_assign(m):
        top_n = m.group(1); var = m.group(2); col = m.group(3)
        rest  = m.group(4).rstrip()
        return f"SELECT {col} INTO p_{var}\n\t{rest}\n\tLIMIT {top_n}\n"

    s = re.sub(
        r"SELECT\s+TOP\s+(\d+)\s+@(\w+)\s*=\s*(\w+)[ \t]+(FROM\b[^\n]+(?:\n[ \t]+[^\n]+)*)",
        _fix_top_assign, s, flags=re.IGNORECASE
    )
    s = re.sub(
        r"SELECT\s+@(\w+)\s*=\s*(\w+)\s+(FROM\b)",
        lambda m: f"SELECT {m.group(2)} INTO p_{m.group(1)} {m.group(3)}",
        s, flags=re.IGNORECASE
    )

    # ── 식별자 변환 ───────────────────────────────────────────────
    s = re.sub(r"\[dbo\]\.\[(\w+)\]", r"`\1`", s)
    s = re.sub(r"\[dbo\]\.(\w+)",     r"`\1`", s)
    s = re.sub(r"\[(\w+)\]",          r"`\1`", s)
    s = re.sub(r"\bdbo\.",            "",      s, flags=re.IGNORECASE)

    # ── @param → p_param ─────────────────────────────────────────
    s = re.sub(r"(?<![\w`])@(\w+)(?=\s+[\w(]+)", r"p_\1", s)
    s = re.sub(r"(?<![\w`])@(\w+)",               r"p_\1", s)

    # ── 헤더 변환 ─────────────────────────────────────────────────
    # v90.61: 객체 이름 추출 정규식 강화.
    #   기존: r"CREATE\s+(?:OR\s+ALTER\s+)?PROCEDURE\s+`?(\w+)`?"
    #         → `schema`.name 형태일 때 \w+ 가 schema 만 잡아서 DROP 망가짐
    #   v90.61: schema 부분 optional 캡처 후, 둘 다 있으면 schema_name 으로 평탄화
    #
    #   지원 패턴:
    #     CREATE FUNCTION name              → 'name'
    #     CREATE FUNCTION `name`            → 'name'
    #     CREATE FUNCTION schema.name       → 'schema_name'
    #     CREATE FUNCTION `schema`.name     → 'schema_name'    (★ 본부장님 환경 핵심)
    #     CREATE FUNCTION schema.`name`     → 'schema_name'
    #     CREATE FUNCTION `schema`.`name`   → 'schema_name'
    #     CREATE FUNCTION [schema].[name]   → 'schema_name'    (MSSQL 잔재)
    def _extract_obj_name(text: str, kw: str) -> tuple[str, str]:
        """
        CREATE {kw} ... 에서 객체 이름 추출.
        Returns: (flattened_name, original_match) — flattened 는 schema_name 또는 name.
        """
        # schema.name 변종 모두 (대괄호도 포함)
        m = re.search(
            rf"CREATE\s+(?:OR\s+ALTER\s+)?{kw}\s+"
            r"(?:[`\[]?(\w+)[`\]]?\s*\.\s*)?"   # schema 부분 (optional)
            r"[`\[]?(\w+)[`\]]?",               # 이름 부분 (필수)
            text, re.IGNORECASE
        )
        if not m:
            return ("", "")
        sch_part = m.group(1)
        name_part = m.group(2)
        # 매치 전체 텍스트
        original = m.group(0)
        if sch_part:
            return (f"{sch_part}_{name_part}", original)
        return (name_part, original)
    
    otype = obj_type.upper()
    if otype in ("PROCEDURE", "SP"):
        nm, original = _extract_obj_name(s, "PROCEDURE")
        if not nm:
            nm = "proc"
        # 헤더 통째 교체 — schema.name 도 정확히 잡아서 평탄화
        s = re.sub(
            rf"CREATE\s+(?:OR\s+ALTER\s+)?PROCEDURE\s+"
            r"(?:[`\[]?\w+[`\]]?\s*\.\s*)?"
            r"[`\[]?\w+[`\]]?",
            f"DROP PROCEDURE IF EXISTS `{nm}`;\nCREATE PROCEDURE `{nm}`",
            s, count=1, flags=re.IGNORECASE
        )
        s = re.sub(r"\bAS\s*\n\s*BEGIN\b", "BEGIN", s, flags=re.IGNORECASE)
        s = re.sub(r"\bAS\s+BEGIN\b",      "BEGIN", s, flags=re.IGNORECASE)

    elif otype == "FUNCTION":
        nm, original = _extract_obj_name(s, "FUNCTION")
        if not nm:
            nm = "func"
        s = re.sub(
            rf"CREATE\s+(?:OR\s+ALTER\s+)?FUNCTION\s+"
            r"(?:[`\[]?\w+[`\]]?\s*\.\s*)?"
            r"[`\[]?\w+[`\]]?",
            f"DROP FUNCTION IF EXISTS `{nm}`;\nCREATE FUNCTION `{nm}`",
            s, count=1, flags=re.IGNORECASE
        )
        s = re.sub(r"\bRETURNS\s+(\S+)\s+AS\s*\n\s*BEGIN\b",
                   r"RETURNS \1\nDETERMINISTIC\nBEGIN", s, flags=re.IGNORECASE)
        s = re.sub(r"\bRETURNS\s+(\S+)\s+AS\s+BEGIN\b",
                   r"RETURNS \1 DETERMINISTIC BEGIN", s, flags=re.IGNORECASE)
        s = re.sub(r"\bAS\s*\n\s*BEGIN\b", "BEGIN", s, flags=re.IGNORECASE)
        s = re.sub(r"\bAS\s+BEGIN\b",      "BEGIN", s, flags=re.IGNORECASE)

    elif otype == "VIEW":
        nm, original = _extract_obj_name(s, "VIEW")
        if not nm:
            nm = "vw"
        s = re.sub(
            rf"CREATE\s+(?:OR\s+ALTER\s+)?VIEW\s+"
            r"(?:[`\[]?\w+[`\]]?\s*\.\s*)?"
            r"[`\[]?\w+[`\]]?",
            f"CREATE OR REPLACE VIEW `{nm}`",
            s, count=1, flags=re.IGNORECASE
        )

    elif otype == "TRIGGER":
        s = re.sub(r"WITH\s+EXEC(?:UTE)?\s+AS\s+\w+", "", s, flags=re.IGNORECASE)
        # v90.61: TRIGGER 도 schema.name 패턴 평탄화
        nm, original = _extract_obj_name(s, "TRIGGER")
        if nm and original:
            # schema.name 형태였으면 평탄화된 이름으로 재작성
            s = re.sub(
                rf"CREATE\s+(?:OR\s+ALTER\s+)?TRIGGER\s+"
                r"(?:[`\[]?\w+[`\]]?\s*\.\s*)?"
                r"[`\[]?\w+[`\]]?",
                f"CREATE TRIGGER `{nm}`",
                s, count=1, flags=re.IGNORECASE
            )

    # ── 공통 함수/구문 변환 ──────────────────────────────────────
    s = re.sub(r"\bGETDATE\(\)",         "NOW()",           s, flags=re.IGNORECASE)
    s = re.sub(r"\bGETUTCDATE\(\)",      "UTC_TIMESTAMP()", s, flags=re.IGNORECASE)
    s = re.sub(r"\bISNULL\s*\(",         "IFNULL(",         s, flags=re.IGNORECASE)
    s = re.sub(r"\bNVL\s*\(",            "IFNULL(",         s, flags=re.IGNORECASE)
    s = re.sub(r"\bLEN\s*\(",            "LENGTH(",         s, flags=re.IGNORECASE)
    s = re.sub(r"\bNVARCHAR\s*\(MAX\)",  "LONGTEXT",        s, flags=re.IGNORECASE)
    s = re.sub(r"\bNVARCHAR\s*\((\d+)\)",r"VARCHAR(\1)",   s, flags=re.IGNORECASE)
    s = re.sub(r"\bNVARCHAR\b",          "VARCHAR(255)",    s, flags=re.IGNORECASE)
    s = re.sub(r"\bSET\s+NOCOUNT\s+ON\s*;?", "",           s, flags=re.IGNORECASE)
    s = re.sub(r"WITH\s*\(NOLOCK\)",     "",                s, flags=re.IGNORECASE)
    s = re.sub(r"\bSELECT\s+TOP\s+(\d+)\b", "SELECT",      s, flags=re.IGNORECASE)
    s = re.sub(r"\bSTUFF\s*\(",          "INSERT(",         s, flags=re.IGNORECASE)
    s = re.sub(r"\bCHARINDEX\s*\(([^,]+),([^,)]+)\)", r"LOCATE(\1,\2)", s, flags=re.IGNORECASE)
    s = re.sub(r"\bPATINDEX\s*\(([^,]+),([^)]+)\)",   r"LOCATE(\1,\2)", s, flags=re.IGNORECASE)
    s = re.sub(r"\bCONVERT\s*\(\s*VARCHAR\s*\(\d+\)\s*,([^,)]+)(?:,\d+)?\s*\)",
               r"CAST(\1 AS CHAR)", s, flags=re.IGNORECASE)
    s = re.sub(r"\bRAISERROR\s*\([^)]+\)", "SIGNAL SQLSTATE '45000'", s, flags=re.IGNORECASE)
    s = re.sub(r"\bPRINT\s+[^\n;]+",    "-- PRINT removed", s, flags=re.IGNORECASE)

    # ════════════════════════════════════════════════════════════════════
    # v90.61 (2026-04-28): 본부장님 환경 41개 SP/FN/VW/TR 1064 케이스 후처리 보강
    # ════════════════════════════════════════════════════════════════════
    # 본부장님 backend.log 분석 결과:
    #   - DATETIME2 가 그대로 남아 있음 (AI 가 누락) — 1064 발생
    #   - IF condition RETURN value;  → MySQL 미지원 (THEN/END IF 필요)
    #   - DECLARE x TYPE = value;     → MySQL 미지원 (DECLARE 후 SET 분리)
    #   - 문자열 + 결합              → MySQL 미지원 (CONCAT)
    #   - DATEDIFF(year, ...)         → MySQL DATEDIFF 는 인자 2개만
    #   - DATEPART(weekday, ...)      → MySQL 의 DAYOFWEEK
    #   - DATEADD(day, ...)           → MySQL 의 DATE_ADD
    #   - SUBSTRING + 음수 시작 위치 → MySQL 도 OK 지만 PATTERN 다름
    
    # DATETIME2(n) → DATETIME(6), DATETIME2 → DATETIME(6)
    s = re.sub(r"\bDATETIME2\s*\(\s*\d+\s*\)", "DATETIME(6)", s, flags=re.IGNORECASE)
    s = re.sub(r"\bDATETIME2\b",                "DATETIME(6)", s, flags=re.IGNORECASE)
    # SMALLDATETIME → DATETIME (system.txt 도 명시했으나 누락 케이스 보강)
    s = re.sub(r"\bSMALLDATETIME\b",            "DATETIME",    s, flags=re.IGNORECASE)
    
    # IF condition RETURN value;  →  IF condition THEN RETURN value; END IF;
    # 본부장님 환경: fn_calc_monthly_payment 의 'IF p_r = 0 RETURN p_principal / p_months;'
    s = re.sub(
        r"\bIF\s+([^\n]+?)\s+RETURN\s+([^;\n]+?);",
        r"IF \1 THEN RETURN \2; END IF;",
        s, flags=re.IGNORECASE
    )
    
    # DECLARE x TYPE = value;  →  DECLARE x TYPE; SET x = value;
    # 본부장님 환경: DECLARE p_r DECIMAL(18,10) = p_rate / 12;
    s = re.sub(
        r"\bDECLARE\s+(\w+)\s+([\w\s,()]+?)\s*=\s*([^;\n]+);",
        r"DECLARE \1 \2;\n    SET \1 = \3;",
        s, flags=re.IGNORECASE
    )
    
    # DATEDIFF(year, a, b)  →  TIMESTAMPDIFF(YEAR, a, b)
    # MySQL DATEDIFF 는 인자 2개라 unit 명시 안 됨. 같은 의미는 TIMESTAMPDIFF.
    s = re.sub(
        r"\bDATEDIFF\s*\(\s*(year|month|day|hour|minute|second)\b\s*,",
        lambda m: f"TIMESTAMPDIFF({m.group(1).upper()},",
        s, flags=re.IGNORECASE
    )
    
    # DATEPART(weekday, x)  →  DAYOFWEEK(x)  (MySQL 1=일요일, MSSQL 1=월요일 — 의미 살짝 다름 경고)
    s = re.sub(
        r"\bDATEPART\s*\(\s*weekday\s*,\s*([^)]+)\)",
        r"DAYOFWEEK(\1)",
        s, flags=re.IGNORECASE
    )
    s = re.sub(
        r"\bDATEPART\s*\(\s*(year|month|day|hour|minute|second)\s*,\s*([^)]+)\)",
        lambda m: f"{m.group(1).upper()}({m.group(2)})",
        s, flags=re.IGNORECASE
    )
    
    # DATEADD(day, n, date)  →  DATE_ADD(date, INTERVAL n DAY)
    s = re.sub(
        r"\bDATEADD\s*\(\s*(year|month|day|hour|minute|second)\s*,\s*([^,]+)\s*,\s*([^)]+)\)",
        lambda m: f"DATE_ADD({m.group(3).strip()}, INTERVAL {m.group(2).strip()} {m.group(1).upper()})",
        s, flags=re.IGNORECASE
    )
    
    # 문자열 + 결합 → CONCAT 변환
    # 본부장님 환경: REPLACE(p_rrn, '-', '') + '-' + ... → CONCAT(...)
    # 안전한 변환을 위해 'string' + identifier 와 identifier + 'string' 패턴만 처리.
    # 양쪽이 다 숫자 식이면 그대로 두고, 한쪽이 string literal 이면 CONCAT 으로.
    # 단, JOIN ON / WHERE / SET 같은 곳에 + 가 산술로 쓰일 수 있어 너무 공격적이지 않게.
    # 가장 안전: 'literal' + ident 또는 ident + 'literal' 케이스만.
    def _replace_string_concat(text: str) -> str:
        # 'X' + ident → CONCAT('X', ident)
        text = re.sub(
            r"('(?:[^']|'')*')\s*\+\s*([\w_.`]+(?:\([^)]*\))?)",
            r"CONCAT(\1, \2)",
            text
        )
        # ident + 'X' → CONCAT(ident, 'X')
        text = re.sub(
            r"([\w_.`]+(?:\([^)]*\))?)\s*\+\s*('(?:[^']|'')*')",
            r"CONCAT(\1, \2)",
            text
        )
        # 'X' + 'Y' → CONCAT('X', 'Y')
        text = re.sub(
            r"('(?:[^']|'')*')\s*\+\s*('(?:[^']|'')*')",
            r"CONCAT(\1, \2)",
            text
        )
        return text
    s = _replace_string_concat(s)
    
    # RETURNS TABLE AS RETURN(...) — MSSQL TVF, MySQL 미지원 → 경고 + 가능하면 PROCEDURE 변환
    # AI 가 처리할 영역이지만 후처리가 잡으면 명확한 경고 추가.
    if re.search(r"\bRETURNS\s+TABLE\s+AS\s+RETURN\s*\(", s, re.IGNORECASE):
        warnings.append(
            "★ TVF (RETURNS TABLE AS RETURN(...)) 는 MySQL 미지원 — "
            "PROCEDURE + 임시 테이블 또는 VIEW 로 수동 재설계 필요"
        )

    # ════════════════════════════════════════════════════════════════════
    # 끝 — v90.61 신규 변환 규칙
    # ════════════════════════════════════════════════════════════════════

    # ════════════════════════════════════════════════════════════════════
    # v90.63 (2026-04-28): AI 가 만든 raw SQL 의 1064 패턴 강제 fix
    # ════════════════════════════════════════════════════════════════════
    # 본부장님 backend.log 13:11~13:13 retry 분석:
    #   AI 가 자기 잘못 인정 ("이전 구문 오류 수정 완료") 했지만 또 같은 패턴 반복.
    #   prompt 강화 + 후처리 동시 처방 필요.
    #
    # 4가지 1064 패턴 (실제 backend.log 에서 추출):
    #
    # P1: RETURN CASE; (CASE 다음 잘못된 ;)
    #     fn_delinq_stage:
    #       RETURN CASE;          ← RETURN 의 CASE 표현식 끝나기 전 ;
    #         WHEN ... THEN ...
    #       END;
    #
    # P2: UPDATE...SET col = val;\n WHERE ... (SET 뒤 잘못된 ;)
    #     sp_assign_collector, sp_close_branch:
    #       UPDATE tbl SET col = val;     ← UPDATE 한 문장으로 끝나야 하는데 ;로 끊김
    #       WHERE id = p_id;              ← 여기는 별도 문장으로 인식 → 1064
    #
    # P3: UPDATE...SET col = 'X',;\n... (첫 컬럼 끝 잘못된 ,;)
    #     sp_approve_application, sp_close_contract, sp_merge_customer:
    #       UPDATE tbl SET col1 = 'X',;   ← 콤마 다음 ; (양쪽 다 잘못)
    #             col2 = ...
    #
    # P4: RETURN expr (끝에 ; 누락)
    #     fn_calc_monthly_payment:
    #       IF v_r = 0 THEN
    #         RETURN CAST(...AS DECIMAL)   ← ; 없음
    #       END IF;
    
    # ─── P1: RETURN CASE; → RETURN CASE (CASE 직후 ; 제거) ───────────
    # 정확히 'RETURN CASE;' 또는 'RETURN CASE\n;' 형태만 잡아서 ; 제거.
    # 다른 RETURN 문엔 영향 없음.
    s = re.sub(r"\bRETURN\s+CASE\s*;", "RETURN CASE", s, flags=re.IGNORECASE)
    
    # ─── P2: UPDATE/SET 한 줄에 ; 잘못 들어간 케이스 fix ──────────────
    # 패턴: SET col = val[ COLLATE x];\n[\s]*WHERE
    # → SET col = val[ COLLATE x]\n[\s]*WHERE  (; 제거)
    # SET 행과 WHERE 행 사이의 잘못된 ; 만 정확히 매치
    s = re.sub(
        r"(\bSET\s+\w+\s*=\s*[^;\n]+?);(\s*\n\s*WHERE\b)",
        r"\1\2",
        s, flags=re.IGNORECASE
    )
    # 변종: SET col = val\n;\n WHERE (드물지만 가능)
    s = re.sub(
        r"(\bSET\s+\w+\s*=\s*[^;\n]+)\n\s*;\s*\n(\s*WHERE\b)",
        r"\1\n\2",
        s, flags=re.IGNORECASE
    )
    
    # ─── P3: SET col = 'X',; 형태 (콤마 + 잘못된 ;) fix ──────────────
    # 패턴: ',;' 또는 ', ;' (콤마 다음 ; — UPDATE SET 다중 컬럼 케이스)
    # ;를 제거하고 콤마만 유지
    s = re.sub(r",\s*;\s*\n", ",\n", s)
    
    # ─── P4: RETURN expr 끝에 ; 보장 (CASE/IF 같은 키워드 제외) ──────
    # 'RETURN <expr>' 다음에 줄바꿈만 있고 ; 가 없는 케이스.
    # 단, 'RETURN CASE' (다중 줄 CASE 표현식) 는 제외 — END; 가 끝맺으니까.
    # 단, 'RETURN' 단독 (PROCEDURE 의 빈 RETURN) 도 제외.
    # 안전하게 — RETURN 으로 시작하고 같은 줄에 표현식 + 줄바꿈으로 끝나면 ; 추가.
    # 매치 조건 (negative lookahead 로 CASE 등 제외):
    s = re.sub(
        r"(\bRETURN\s+(?!CASE\b|SELECT\b|\(\s*SELECT\b)[^;\n]+?)(?<![;])(\s*\n)",
        r"\1;\2",
        s, flags=re.IGNORECASE
    )
    # 특수: RETURN CAST(...) 같이 닫는 ) 다음에 줄바꿈
    s = re.sub(
        r"(\bRETURN\s+CAST\s*\([^)]*\)(?:\s+AS\s+\w+(?:\([^)]*\))?)?)(?<![;])(\s*\n)",
        r"\1;\2",
        s, flags=re.IGNORECASE
    )
    
    # ════════════════════════════════════════════════════════════════════
    # 끝 — v90.63 신규 후처리 규칙
    # ════════════════════════════════════════════════════════════════════

    # ── 잔류 경고 ─────────────────────────────────────────────────
    if re.search(r"DECLARE\s+p_\w+\s+TABLE", s, re.IGNORECASE):
        warnings.append("테이블 변수(@TABLE) → MySQL 임시 테이블로 수동 변환 필요")
    if re.search(r"\bCURSOR\b", s, re.IGNORECASE):
        warnings.append("CURSOR → MySQL CURSOR 문법 수동 검토 필요")

    return s.strip(), warnings


# ── v73: AI 응답 파싱 헬퍼 (방어적) ─────────────────────────────
def _parse_ai_response(raw_text: str, obj_type: str, obj_name: str) -> dict:
    """
    AI 응답 텍스트를 파싱하여 {"converted_ddl", "changes", "warnings"} dict 반환.

    AI 응답 형식이 다양해서 여러 케이스 방어:
      케이스 A: 정상 JSON — {"converted_ddl":"...","changes":[...],"warnings":[...]}
      케이스 B: 마크다운 코드블록 감싸진 JSON — ```json\n{...}\n```
      케이스 C: JSON 이스케이프 깨짐 (DDL 안의 줄바꿈/따옴표가 JSON 문법 위반)
      케이스 D: AI 가 JSON 대신 평문 DDL 을 반환
      케이스 E: 응답이 잘림 (max_tokens 에 걸려 마지막 괄호 없음)

    정상 결과가 안 나오면 raise → 호출자(ai_convert_ddl) 에서 재시도 트리거.
    """
    import re as _re

    if not raw_text:
        raise ValueError("AI 응답이 빈 문자열")

    text = raw_text.strip()

    # 1) 접두/접미 마크다운 블록 제거
    text = text.lstrip("```json").lstrip("```").rstrip("```").strip()

    # 케이스 A/B: 표준 JSON 파싱 시도
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and parsed.get("converted_ddl"):
            return _validate_parsed(parsed, obj_type, obj_name)
    except (json.JSONDecodeError, ValueError):
        pass  # 다음 케이스로

    # 케이스 C: 이스케이프 깨진 JSON — converted_ddl 필드만 정규식으로 추출
    #   패턴: "converted_ddl":"...DDL본문..."
    #   DDL 안에 " 나 \n 이 제대로 이스케이프 안 됐어도 최대한 잡아냄.
    #   DOTALL 로 줄바꿈 포함, non-greedy 로 최단.
    #   끝 매칭 힌트: ," 다음에 changes/warnings 키가 나오거나, 마지막 "}
    m = _re.search(
        r'"converted_ddl"\s*:\s*"(.+?)"\s*,\s*"(?:changes|warnings)"',
        text, _re.DOTALL
    )
    if not m:
        # 끝이 잘렸을 때: changes/warnings 키 없이 }로 바로 끝날 수도
        m = _re.search(
            r'"converted_ddl"\s*:\s*"(.+?)"\s*\}?\s*$',
            text, _re.DOTALL
        )
    if m:
        ddl_raw = m.group(1)
        # JSON 이스케이프 디코딩 시도 — \n, \", \\ 변환
        try:
            # 가짜 JSON 문자열로 감싸서 파싱 → 제대로 언이스케이프
            ddl_decoded = json.loads(f'"{ddl_raw}"')
        except json.JSONDecodeError:
            # 실패 시 수동 치환 (부분 복구)
            ddl_decoded = (ddl_raw
                           .replace('\\n', '\n')
                           .replace('\\"', '"')
                           .replace('\\\\', '\\'))
        logger.warning("ai_convert_ddl [%s] %s — JSON 파싱 실패, 정규식으로 복구 성공 (%d자)",
                       obj_type, obj_name, len(ddl_decoded))
        return _validate_parsed({
            "converted_ddl": ddl_decoded,
            "changes": ["JSON 파싱 실패 — 정규식 복구"],
            "warnings": ["AI 응답 JSON 이스케이프 불완전"],
        }, obj_type, obj_name)

    # 케이스 D: 평문 DDL — text 자체가 CREATE 로 시작하면 전체를 DDL 로 간주
    text_upper = text.lstrip().upper()
    if text_upper.startswith("CREATE") or text_upper.startswith("DROP"):
        logger.warning("ai_convert_ddl [%s] %s — 평문 DDL 응답 감지 (JSON 형식 아님)",
                       obj_type, obj_name)
        return _validate_parsed({
            "converted_ddl": text,
            "changes": ["AI 가 JSON 이 아닌 평문 DDL 반환"],
            "warnings": [],
        }, obj_type, obj_name)

    # 모든 방어 레이어 실패
    raise ValueError(
        f"AI 응답 파싱 실패 — 인식 가능한 포맷 아님. "
        f"응답 앞부분: {text[:200]}..."
    )


def _validate_parsed(parsed: dict, obj_type: str, obj_name: str) -> dict:
    """파싱 결과가 최소 요건을 만족하는지 검증."""
    ddl = parsed.get("converted_ddl", "").strip()

    # 너무 짧으면 불완전한 응답
    #   실제로 실패했던 tvf_daily_trx(550자), tvf_delinq_ranking(763자) 는 이 선 넘었지만
    #   파싱 자체가 깨졌던 게 진짜 원인. 여기선 명백히 잘린 응답만 잡음.
    MIN_LEN = {
        "FUNCTION": 80,    # CREATE FUNCTION x() RETURNS INT DETERMINISTIC BEGIN RETURN 1; END
        "PROCEDURE": 80,
        "VIEW": 40,
        "TRIGGER": 80,
    }.get(obj_type.upper(), 60)

    if len(ddl) < MIN_LEN:
        raise ValueError(
            f"AI 응답 DDL 이 너무 짧음 ({len(ddl)}자, 최소 {MIN_LEN}자 필요). "
            f"불완전한 응답일 가능성. 처음 100자: {ddl[:100]}"
        )

    # CREATE 또는 DROP 으로 시작해야 함 (앞에 공백/주석은 허용)
    import re as _re
    stripped = _re.sub(r'^(\s*--[^\n]*\n)*\s*', '', ddl)
    if not _re.match(r'(CREATE|DROP)\b', stripped, _re.IGNORECASE):
        raise ValueError(
            f"AI 응답 DDL 이 CREATE/DROP 으로 시작하지 않음. "
            f"처음 100자: {ddl[:100]}"
        )

    return {
        "converted_ddl": ddl,
        "changes": parsed.get("changes", []),
        "warnings": parsed.get("warnings", []),
    }


# ════════════════════════════════════════════════════════════════════════
# v90.73 (2026-04-28): VARCHAR 길이 코드 레벨 강제 보정
# ════════════════════════════════════════════════════════════════════════
def _enforce_varchar_length(src_ddl: str, tgt_ddl: str, obj_name: str = "") -> tuple:
    """
    AI 변환 결과의 VARCHAR(M) 이 원본 VARCHAR(N) 보다 짧으면 M = N 으로 보정.
    
    원리:
      1. 원본 (MSSQL) 의 모든 VARCHAR(N) 파라미터/컬럼 길이 추출
      2. 변환 결과 (MySQL) 의 같은 이름 파라미터/컬럼의 VARCHAR(M) 비교
      3. M < N 이면 → 변환 결과 강제 보정 (M = N)
      4. AI 가 DATE 로 바꾼 경우 → VARCHAR(N) 으로 복원 (호출자 호환성)
    
    Args:
      src_ddl: 원본 MSSQL DDL
      tgt_ddl: AI 가 변환한 MySQL DDL
      obj_name: 객체 이름 (로깅용)
    
    Returns:
      (corrected_ddl, changes): 보정된 DDL + 변경 이력 리스트
    """
    changes = []
    
    if not src_ddl or not tgt_ddl:
        return tgt_ddl, changes
    
    # ── Step 1: 원본 DDL 에서 파라미터/컬럼별 VARCHAR 길이 추출 ──
    # MSSQL 파라미터: @name VARCHAR(N) 또는 @name NVARCHAR(N)
    # MSSQL 컬럼:    [name] VARCHAR(N) 또는 name VARCHAR(N)
    src_lengths = {}  # {param_name_normalized: length}
    
    # @name [N]VARCHAR(N) 패턴 — MSSQL 파라미터
    for m in re.finditer(
        r"@(\w+)\s+(?:N?VARCHAR|N?CHAR)\s*\(\s*(\d+)\s*\)",
        src_ddl, re.IGNORECASE
    ):
        param_name = m.group(1).lower()
        length = int(m.group(2))
        # 키 정규화: 'rec_sdate' (소스) ↔ 'p_rec_sdate' (타겟) 매칭용
        src_lengths[param_name] = length
        # p_ 접두사 변형도 추가 (AI 가 p_ 붙이는 경우 대비)
        src_lengths[f"p_{param_name}"] = length
    
    if not src_lengths:
        return tgt_ddl, changes  # 원본에 VARCHAR 파라미터 없음 → 보정할 것 없음
    
    # ── Step 2: 변환 결과의 VARCHAR(M) 검사 ──
    # MySQL 파라미터: IN p_name VARCHAR(M) 또는 OUT/INOUT
    # 또는 컬럼: name VARCHAR(M)
    corrected = tgt_ddl
    
    # Pattern A: [IN/OUT/INOUT] name [N]VARCHAR(M)
    # AI 가 줄인 길이 → 원본으로 복원
    def _fix_varchar(match):
        prefix = match.group(1) or ""  # IN / OUT / INOUT (옵션)
        name = match.group(2)
        var_type = match.group(3)
        length_str = match.group(4)
        m_length = int(length_str)
        
        # 매칭 시도: 정확한 이름, p_ 접두사 변형
        n_length = None
        name_lower = name.lower()
        if name_lower in src_lengths:
            n_length = src_lengths[name_lower]
        else:
            # p_ 접두사 제거하고 시도
            stripped = re.sub(r"^p_", "", name_lower)
            if stripped in src_lengths:
                n_length = src_lengths[stripped]
        
        if n_length is None or m_length >= n_length:
            return match.group(0)  # 매칭 안 되거나 충분한 길이 → 그대로
        
        # 길이 줄어듦 → 강제 보정
        new_segment = f"{prefix}{name} {var_type}({n_length})"
        changes.append(
            f"★ VARCHAR 길이 강제 보정 [{name}]: VARCHAR({m_length}) → VARCHAR({n_length}) "
            f"(원본 길이 보존, 1406 회피)"
        )
        return new_segment
    
    # 정규식 패턴:
    #   group 1: IN/OUT/INOUT (있으면)
    #   group 2: 파라미터/컬럼 이름
    #   group 3: VARCHAR 또는 CHAR
    #   group 4: 숫자
    corrected = re.sub(
        r"((?:\bIN\s+|\bOUT\s+|\bINOUT\s+)?)(\w+)\s+(VARCHAR|CHAR)\s*\(\s*(\d+)\s*\)",
        _fix_varchar,
        corrected,
        flags=re.IGNORECASE
    )
    
    # ── Step 3: AI 가 DATE 로 바꾼 경우 → VARCHAR 로 복원 ──
    # MySQL 의 'IN p_name DATE' 인데 원본이 VARCHAR(N) 이면 → VARCHAR(N) 으로 복원
    def _fix_date(match):
        prefix = match.group(1) or ""
        name = match.group(2)
        date_type = match.group(3)
        
        # 매칭 시도
        n_length = None
        name_lower = name.lower()
        if name_lower in src_lengths:
            n_length = src_lengths[name_lower]
        else:
            stripped = re.sub(r"^p_", "", name_lower)
            if stripped in src_lengths:
                n_length = src_lengths[stripped]
        
        if n_length is None:
            return match.group(0)  # 원본에 VARCHAR 아니면 DATE 유지
        
        # 원본이 VARCHAR(N) 인데 AI 가 DATE 로 바꿈 → 복원
        new_segment = f"{prefix}{name} VARCHAR({n_length})"
        changes.append(
            f"★ DATE 강제 복원 [{name}]: {date_type} → VARCHAR({n_length}) "
            f"(원본 호환성, 호출자가 문자열 보냄)"
        )
        return new_segment
    
    corrected = re.sub(
        r"((?:\bIN\s+|\bOUT\s+|\bINOUT\s+)?)(\w+)\s+(DATE|DATETIME)\b(?!\s*\()",
        _fix_date,
        corrected,
        flags=re.IGNORECASE
    )
    
    return corrected, changes


# ── 2. Claude AI 변환 ─────────────────────────────────────────────
def ai_convert_ddl(ddl: str, obj_type: str, obj_name: str,
                   src_db: str = "mssql", tgt_db: str = "mysql",
                   error_hint: str = "") -> dict:
    """
    Claude AI로 DDL 변환.
    Returns: {"converted_ddl": str, "changes": list, "warnings": list, "method": str}
    """
    import os

    try:
        from app.api.routes.settings import _cfg as _get_cfg
        api_key = _get_cfg().get("anthropic_api_key", "").strip()
    except Exception:
        api_key = ""
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if not api_key:
        logger.warning("ai_convert_ddl: API 키 없음 → 규칙 기반 폴백")
        converted, warnings = mssql_to_mysql_ddl(ddl, obj_type)
        return {"converted_ddl": converted, "changes": ["규칙 기반 변환 (API 키 없음)"],
                "warnings": warnings, "method": "rules_fallback"}

    src_name = {"mssql":"SQL Server","mysql":"MySQL","mariadb":"MariaDB",
                "postgresql":"PostgreSQL","aurora":"Aurora MySQL"}.get(src_db.lower(), src_db)
    tgt_name = {"mssql":"SQL Server","mysql":"MySQL","mariadb":"MariaDB",
                "postgresql":"PostgreSQL","aurora":"Aurora MySQL"}.get(tgt_db.lower(), tgt_db)

    # ── 프롬프트 파일에서 로드 ─────────────────────────────────────
    prompt = _build_prompt(
        src_db=src_db, tgt_db=tgt_db,
        obj_type=obj_type, obj_name=obj_name,
        ddl=ddl, error_hint=error_hint
    )

    try:
        payload = json.dumps({
            "model": "claude-sonnet-4-6",
            # v73: 6000 → 8000. 복잡한 TVF/PROC 변환 시 JSON 포함해 길이 초과로 응답이 잘려
            #   "converted_ddl":"..." 중간에서 끝남 → JSON 파싱 실패의 원인 중 하나였음.
            "max_tokens": 8000,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())

        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text = block["text"].strip()
                break

        # v73: 방어적 파싱 — AI 응답 형식 다양성 대응
        #   문제 상황 (오늘 tvf_daily_trx, tvf_delinq_ranking 실패 원인):
        #     AI 가 JSON 안에 DDL 을 담을 때 세미콜론/따옴표/줄바꿈 이스케이프 불완전하거나,
        #     응답 중간에 마크다운 블록 혼재 시 json.loads 가 깨지거나 부분만 파싱.
        #     기존 코드는 예외 발생 시 규칙 기반 폴백으로 가서 v63 프롬프트 효과 무용지물.
        #   3단 방어:
        #     1) 정상 JSON 파싱 시도
        #     2) 실패 시 정규식으로 converted_ddl 본문 추출
        #     3) 둘 다 실패 또는 결과가 비정상 (짧거나 CREATE 로 시작 안 함) → raise
        parsed = _parse_ai_response(text, obj_type, obj_name)

        # 사용량 기록
        _record_usage(obj_name, obj_type, src_db, tgt_db, data.get("usage", {}))

        # ════════════════════════════════════════════════════════════════
        # v90.73 (2026-04-28): VARCHAR 길이 코드 레벨 강제 보정
        # 
        # 배경: prompt (system.txt 패턴 0 + obj_executor 의 1406 hint) 만으론
        #       AI 가 일관되게 따르지 않음. 본부장님 환경에서 v90.71 적용 후에도
        #       AI 가 VARCHAR 길이 줄여서 1406 재발.
        # 
        # 처방: AI 변환 결과를 DB 배포 전에 정규식으로 검사:
        #         원본 DDL 의 VARCHAR(N) 추출 → 변환 결과의 VARCHAR(M) 비교
        #         M < N 이면 M = N 으로 자동 교정 (prompt 무관 강제)
        # ════════════════════════════════════════════════════════════════
        converted = parsed.get("converted_ddl", "")
        if converted:
            converted, _vc_changes = _enforce_varchar_length(ddl, converted, obj_name)
            if _vc_changes:
                # 변경 이력 추가 (사용자에게 fix 적용 알림)
                parsed.setdefault("changes", []).extend(_vc_changes)
                logger.info("ai_convert_ddl [%s] %s → VARCHAR 길이 보정 %d건",
                            obj_type, obj_name, len(_vc_changes))

        logger.info("ai_convert_ddl [%s] %s → 완료 (%d자)",
                    obj_type, obj_name, len(converted))
        return {
            "converted_ddl": converted,
            "changes":       parsed.get("changes", []),
            "warnings":      [_wrap_warning(w) for w in parsed.get("warnings", [])],
            "method": "claude-ai",
        }

    except Exception as e:
        logger.error("ai_convert_ddl 실패 [%s] %s: %s", obj_type, obj_name, e)
        converted, warnings = mssql_to_mysql_ddl(ddl, obj_type)
        return {"converted_ddl": converted, "changes": ["규칙 기반 폴백 (AI 실패)"],
                "warnings": warnings + [str(e)], "method": "rules_fallback"}




def _record_error_case(src_db: str, tgt_db: str, obj_name: str, obj_type: str,
                        error_msg: str, cause: str = "", solution: str = ""):
    """배포 오류를 error_cases.txt에 자동 누적"""
    import datetime as _dt
    try:
        key = f"{src_db.lower()}_to_{tgt_db.lower()}"
        path = _PROMPT_DIR / key / "error_cases.txt"
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        
        today = _dt.date.today().strftime("%Y-%m-%d")
        # 중복 방지: 같은 오류 메시지 앞 80자가 이미 있으면 skip
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        err_key = error_msg[:80].replace("\n", " ")
        if err_key in existing:
            return

        entry = (
            f"\n[{today}] {obj_name} ({obj_type}) | {error_msg[:120]}\n"
            f"  원인: {cause or '자동 기록 — 원인 분석 필요'}\n"
            f"  해결: {solution or '재이관 시 오류 메시지를 AI에 전달하여 자동 수정'}\n"
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
        logger.info("[오류 누적] %s → %s", obj_name, path)
    except Exception as e:
        logger.warning("오류 누적 실패: %s", e)

def _record_usage(obj_name: str, obj_type: str, src_db: str, tgt_db: str, usage: dict):
    """Claude API 사용량 기록"""
    try:
        from app.core.store import Store
        import datetime as dt
        store = Store("claude_usage")
        prev = store.get("total") or {"calls":0,"input_tokens":0,"output_tokens":0,"objects":[]}
        prev["calls"]        += 1
        prev["input_tokens"] += usage.get("input_tokens", 0)
        prev["output_tokens"]+= usage.get("output_tokens", 0)
        prev.setdefault("objects", []).append({
            "name": obj_name, "type": f"OBJ_{obj_type}",
            "in":  usage.get("input_tokens", 0),
            "out": usage.get("output_tokens", 0),
            "ts":  dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "src": src_db, "tgt": tgt_db,
        })
        prev["objects"] = prev["objects"][-100:]
        store.set("total", prev)
    except Exception as e:
        logger.warning("사용량 기록 실패: %s", e)


# ── 3. MySQL 오브젝트 DDL 배포 ────────────────────────────────────
# ═══════════════════════════════════════════════════════════════
# v89 hotfix (2026-04-23): 오브젝트 배포 엔진 전면 재설계
# ═══════════════════════════════════════════════════════════════
# 기존 deploy_mysql_object 문제점:
#   1. BEGIN 키워드 존재 여부로만 compound 판정 → CASE...END 같은 0-depth
#      블록을 구분 못 하고 내부 세미콜론에서 자름 (fn_delinq_stage 실패)
#   2. AI 가 여러 DDL (DROP + CREATE + helper function) 을 한 번에 반환하면
#      전체를 한 execute() 에 던져 버려서 PyMySQL 단일 문장 제약 위반 (TVF 실패)
#   3. 실패 시 어느 문장이 실패했는지 진단 정보 없음
#
# 재설계 원칙:
#   A. 문장 분리는 엔진이 책임 — BEGIN/END depth + 문자열/주석 인식 tokenizer
#   B. 각 독립 문장은 개별 execute() 호출
#   C. DDL 종류별 분류 (DROP/CREATE/ALTER/SET/기타) 후 순서대로 실행
#   D. 실패 문장은 수집하여 진단 정보에 포함
#   E. BEGIN..END 본문이 있는 CREATE 는 "하나의 execute 대상" 으로 묶어 전달
#      (세미콜론을 statement terminator 가 아닌 block terminator 로 취급)
# ═══════════════════════════════════════════════════════════════

def _split_sql_statements(sql: str) -> list[str]:
    """
    SQL 문자열을 독립 문장 리스트로 분리.

    핵심 규칙:
      - BEGIN..END 블록 내부의 세미콜론은 statement terminator 가 아님
      - CASE..END 도 depth 증가로 취급 (CASE 표현식 종료의 END 가
        BEGIN..END 의 END 와 구분 안 되므로, 양쪽 모두 depth 카운트)
      - END IF / END WHILE / END LOOP / END REPEAT / END HANDLER 는
        내부 제어 구조 종료 — depth 변화 없음
      - 문자열 리터럴 '...'/"..." 안의 세미콜론 무시
      - 백틱 식별자 `...` 안의 세미콜론도 무시
      - 주석은 deploy_mysql_object 에서 미리 제거됨
    """
    if not sql or not sql.strip():
        return []

    statements: list[str] = []
    current: list[str] = []

    i = 0
    n = len(sql)
    depth = 0           # BEGIN..END / CASE..END 통합 depth
    in_string = None    # 현재 문자열 리터럴 종결 문자

    # END 뒤에 이 키워드가 오면 "END XXX" 로 내부 구조 종료 — depth 변화 없음
    END_INNER_KEYWORDS = ("IF", "WHILE", "LOOP", "REPEAT", "HANDLER")
    # 주의: "END CASE" 는 CASE 문장(statement) 종료인데 CASE 시작 시
    # 이미 depth +1 했으므로 END CASE 도 depth -1 해야 함.
    # 즉 END CASE 는 내부가 아닌 종료로 취급.

    def _peek_word(pos: int) -> str:
        j = pos
        while j < n and (sql[j].isalpha() or sql[j] == '_'):
            j += 1
        return sql[pos:j].upper()

    while i < n:
        ch = sql[i]

        # ── 문자열 리터럴 처리 ──
        if in_string:
            current.append(ch)
            if ch == '\\' and i + 1 < n:
                current.append(sql[i + 1])
                i += 2
                continue
            if ch == in_string:
                if i + 1 < n and sql[i + 1] == in_string and in_string == "'":
                    current.append(sql[i + 1])
                    i += 2
                    continue
                in_string = None
            i += 1
            continue

        if ch in ("'", '"', '`'):
            in_string = ch
            current.append(ch)
            i += 1
            continue

        # ── 키워드 인식 (단어 경계 위) ──
        is_word_start = (i == 0) or (not (sql[i - 1].isalnum() or sql[i - 1] == '_'))

        if is_word_start and ch.isalpha():
            word = _peek_word(i)

            if word == "BEGIN":
                # BEGIN TRANSACTION / BEGIN TRAN / BEGIN WORK 는 블록 아님
                next_i = i + len(word)
                after_ws = next_i
                while after_ws < n and sql[after_ws] in ' \t\n\r':
                    after_ws += 1
                after_word = _peek_word(after_ws)
                if after_word not in ("TRANSACTION", "TRAN", "WORK"):
                    depth += 1
                current.append(sql[i:next_i])
                i = next_i
                continue

            if word == "CASE":
                # CASE..END 도 depth +1 (종료의 END 가 BEGIN 짝 END 와 구분 안 됨)
                depth += 1
                current.append(sql[i:i + len(word)])
                i += len(word)
                continue

            if word == "END":
                # END 뒤에 IF/WHILE/LOOP/REPEAT/HANDLER 가 오면 내부 구조 종료
                # END CASE 는 CASE 짝 — depth 감소
                # 단독 END 는 BEGIN 또는 CASE 짝 — depth 감소
                next_i = i + len(word)
                after_ws = next_i
                while after_ws < n and sql[after_ws] in ' \t\n\r':
                    after_ws += 1
                after_word = _peek_word(after_ws)

                current.append(sql[i:next_i])
                i = next_i

                if after_word in END_INNER_KEYWORDS:
                    # END IF / END WHILE 등 — depth 변화 없음
                    pass
                else:
                    # 단독 END 또는 END CASE — depth 감소
                    if depth > 0:
                        depth -= 1
                continue

        # ── 세미콜론 처리 ──
        if ch == ';':
            current.append(ch)
            if depth == 0:
                stmt = ''.join(current).strip()
                if stmt and stmt != ';':
                    statements.append(stmt)
                current = []
            i += 1
            continue

        current.append(ch)
        i += 1

    # 마지막 남은 문장
    tail = ''.join(current).strip()
    if tail:
        statements.append(tail)

    return statements


def _classify_statement(stmt: str) -> str:
    """
    SQL 문장을 종류별로 분류.
    Returns: 'drop' | 'create' | 'alter' | 'set' | 'select' | 'other'
    """
    s = stmt.lstrip().upper()
    # 주석이 남아있을 수 있으므로 skip
    while s.startswith('/*') or s.startswith('--'):
        if s.startswith('/*'):
            end = s.find('*/')
            if end < 0:
                break
            s = s[end + 2:].lstrip()
        elif s.startswith('--'):
            nl = s.find('\n')
            if nl < 0:
                break
            s = s[nl + 1:].lstrip()
    # 앞 토큰 추출
    first = s.split(None, 1)[0] if s else ''
    if first == 'DROP':
        return 'drop'
    if first in ('CREATE', 'REPLACE'):
        return 'create'
    if first == 'ALTER':
        return 'alter'
    if first == 'SET':
        return 'set'
    if first == 'SELECT':
        return 'select'
    if first == 'DELIMITER':
        return 'delimiter'   # 이미 제거됐지만 방어적
    return 'other'


def _extract_object_name_from_create(stmt: str) -> str:
    """
    CREATE 문에서 대상 오브젝트 이름을 추출. 로그/진단용.
    예: CREATE PROCEDURE `usp_foo`(...) → 'usp_foo'
    """
    m = re.search(
        r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:PROCEDURE|FUNCTION|TRIGGER|VIEW|TABLE)\s+`?(\w+)`?",
        stmt, re.IGNORECASE
    )
    return m.group(1) if m else ""


def _strip_trailing_semicolons(stmt: str) -> str:
    """
    문장 끝의 세미콜론 및 공백 제거. PyMySQL 의 execute() 는 말미 세미콜론을
    싫어하는 경우가 있음 (특히 CREATE PROCEDURE 의 BEGIN..END 본문).
    단, 내부 세미콜론 (BEGIN..END 안쪽) 은 그대로 유지.
    """
    s = stmt.rstrip()
    while s.endswith(';'):
        s = s[:-1].rstrip()
    return s


def _drop_stmt_looks_safe(stmt: str) -> bool:
    """DROP 문이 IF EXISTS 를 포함해서 안전한지."""
    return bool(re.search(r"\bIF\s+EXISTS\b", stmt, re.IGNORECASE))


def deploy_mysql_object(ddl: str, conn_info: dict, obj_type: str, obj_name: str) -> dict:
    """
    MySQL 에 오브젝트 DDL 배포 — v89 재설계 버전.

    처리 흐름:
      1. DDL 정제 (DELIMITER/주석/공백)
      2. 독립 문장으로 분리 (_split_sql_statements, BEGIN..END 인식)
      3. 각 문장 분류 (DROP / CREATE / ALTER / 기타)
      4. DROP 먼저 일괄 실행 (실패 허용)
      5. CREATE/ALTER 순차 실행 (실패 시 수집)
      6. 결과 집계 + 진단 정보 반환

    conn_info: {host, port, username/user, password, database}
    Returns: {
        "success":   bool,
        "output":    str,              # 사용자용 요약 메시지
        "error":     str,              # 실패 요약 (성공 시 빈 문자열)
        "executed":  list[str],        # 성공 실행된 문장 head (진단용)
        "failures":  list[dict],       # [{stmt_head, error}]
        "stmt_count": int,
    }

    v90.40: [DEPLOY-TRACE] 단계별 진단 로그 추가 (freeze 시 마지막 마커가 발생 지점)
    """
    import pymysql
    import sys as _dpsys, time as _dptime

    # v90.40: DEPLOY-TRACE 헬퍼 (즉시 flush)
    _dp_t0 = _dptime.monotonic()
    def _dtrace(stage: str, **kv):
        _el = _dptime.monotonic() - _dp_t0
        _kv = " ".join(f"{k}={v}" for k, v in kv.items())
        logger.info("[DEPLOY-TRACE %s] [%s] (+%.2fs) %s", stage, obj_name, _el, _kv)
        for _h in logger.handlers:
            try: _h.flush()
            except Exception: pass
        try: _dpsys.stderr.flush()
        except Exception: pass

    _dtrace("01-enter", obj_type=obj_type, ddl_len=len(ddl or ""))

    # v90.41: PyMySQL CLIENT.MULTI_STATEMENTS 플래그 활성화
    #   본부장님 케이스: BEGIN..END 본문의 첫 ; 에서 PyMySQL/Workbench 클라이언트가
    #   SQL 을 잘라버려 1064 (near 'WHERE...' at line N) 발생.
    #   해결: MULTI_STATEMENTS 모드에서는 클라이언트가 ; 로 자르지 않고 통째로
    #         서버에 보냄 → MySQL 서버가 BEGIN..END 를 SP 컨텍스트로 인식하여 정상 파싱.
    #   부작용: 없음 - 단일 statement 도 정상 동작 (그냥 추가 ; 가 무시됨)
    try:
        from pymysql.constants import CLIENT as _PYMYSQL_CLIENT
        _client_flag = _PYMYSQL_CLIENT.MULTI_STATEMENTS
    except Exception:
        _client_flag = 0  # import 실패 시 비활성화 (호환성)

    conn_args = dict(
        host=conn_info["host"], port=int(conn_info["port"]),
        user=conn_info.get("username", conn_info.get("user", "")),
        password=conn_info.get("password", ""),
        database=conn_info["database"],
        charset="utf8mb4",
        connect_timeout=30,
        # v90.29: 무한 hang 방지 - 본부장님 보고 "트리거/SP 처리 중 시스템 멈춤"
        #   read_timeout: SELECT/EXECUTE 결과 대기 최대 (초)
        #   write_timeout: 쿼리 송신 대기 최대 (초)
        #   → DDL 실행이 무한 wait 안 됨, 5분 후 강제 timeout
        read_timeout=300,    # 5분
        write_timeout=60,    # 1분
        # v90.41: BEGIN..END 본문 1064 픽스 (위 주석 참조)
        client_flag=_client_flag,
    )

    # ── Phase 1: DDL 정제 ─────────────────────────────────────────
    clean = ddl or ""

    # DELIMITER 지시자 제거 (MySQL 클라이언트 전용, 드라이버는 불필요)
    clean = re.sub(r"(?im)^\s*DELIMITER\s+\S+\s*$", "", clean)
    # 연속 구분자 (//, $$, ;;) 단독 라인 제거
    clean = re.sub(r"(?m)^\s*[\$\/;]{2,}\s*$", "", clean)
    # /* */ 블록 주석 제거
    clean = re.sub(r"/\*[\s\S]*?\*/", "", clean)
    # 라인 주석 제거
    clean = re.sub(r"--[^\n]*", "", clean)
    # 줄 앞 홀로 있는 ; 를 이전 줄 끝에 붙임
    clean = re.sub(r"\n[ \t]*;", ";", clean)

    # AI 미변환 보정 — SELECT var = col FROM → SELECT col INTO var FROM
    clean = re.sub(
        r"SELECT\s+(\w+)\s*=\s*(\w+)\s+(FROM\b)",
        lambda m: f"SELECT {m.group(2)} INTO {m.group(1)} {m.group(3)}",
        clean, flags=re.IGNORECASE
    )

    # SELECT INTO 뒤 LIMIT 1 자동 추가
    def _add_limit(m):
        body = m.group(1).rstrip()
        return f"{body}\n\tLIMIT 1;\n\t{m.group(2)}"
    clean = re.sub(
        r"(SELECT\s+\w+\s+INTO\s+\w+\s+FROM\b(?:(?!\bLIMIT\b|\bRETURN\b|\bEND\b|\bIF\b).)*?)\n[ \t]*(RETURN\b|END\b)",
        _add_limit, clean, flags=re.IGNORECASE | re.DOTALL
    )
    clean = re.sub(r"(LIMIT\s+\d+)(RETURN|END|SET|DECLARE|IF)",
                   lambda m: m.group(1) + ";\n\t" + m.group(2),
                   clean, flags=re.IGNORECASE)
    clean = re.sub(r"(LIMIT\s+\d+)(?!\s*;)(?=\s*\n)", r"\1;", clean, flags=re.IGNORECASE)

    # 각 문장 끝 세미콜론 보완 (단, BEGIN 밖 개별 문장용)
    clean = re.sub(r"(DECLARE\s+\w+\s+[\w()]+)(?!\s*;)(?=\s*\n)", r"\1;", clean, flags=re.IGNORECASE)
    
    # ════════════════════════════════════════════════════════════════════
    # v90.64 (2026-04-28): 본부장님 환경 진짜 1064 원인 fix
    # ════════════════════════════════════════════════════════════════════
    # 진단 (backend.log Job#e7b829, 13:39~13:41):
    #   v90.63 의 mssql_to_mysql_ddl 후처리는 호출 안 되는 경로였고,
    #   진짜 망가뜨리는 코드는 deploy_mysql_object 의 clean 단계 라인 1027~1028.
    #
    # 기존 (WRONG):
    #   clean = re.sub(r"(SET\s+\w+\s*=\s*[^\n;]+)(?<!;)(?=\s*\n)", r"\1;", clean)
    #   → AI 가 정상으로 보낸 'SET col = val\n WHERE ...' 의 SET 라인 끝에 ; 추가
    #   → 'SET col = val;\n WHERE...' → 1064
    #
    #   clean = re.sub(r"(RETURN\s+\w+)(?!;)(?=\s*\n)", r"\1;", clean)
    #   → 'RETURN CASE\n WHEN...' 도 매치되어 'RETURN CASE;\n WHEN...' 만듦 → 1064
    #
    # v90.64 처방:
    #   1. SET 라인 자동 ; 추가는 다음 라인이 WHERE/JOIN/AND/OR 아닐 때만
    #   2. RETURN 자동 ; 추가는 CASE/SELECT/( 아닐 때만
    #   3. 잘못 추가된 ; 가 있어도 retroactive 로 fix (정규식 강제 수술)
    
    # SET 라인 ; 추가 — UPDATE...SET 다음 라인이 WHERE/JOIN 이면 추가 안 함
    clean = re.sub(
        r"(SET\s+\w+\s*=\s*[^\n;]+)(?<!;)(?=\s*\n\s*(?!WHERE\b|FROM\b|JOIN\b|AND\b|OR\b|,)\w)",
        r"\1;",
        clean, flags=re.IGNORECASE
    )
    
    # RETURN 라인 ; 추가 — CASE/SELECT/( 등 다중라인 표현식이면 추가 안 함
    clean = re.sub(
        r"(RETURN\s+(?!CASE\b|SELECT\b|\()\w+)(?!;)(?=\s*\n)",
        r"\1;",
        clean, flags=re.IGNORECASE
    )
    
    # ─── retroactive 강제 fix — 이미 깨진 패턴 강제 수술 ────────────────
    # P1: RETURN CASE; → RETURN CASE
    clean = re.sub(r"\bRETURN\s+CASE\s*;", "RETURN CASE", clean, flags=re.IGNORECASE)
    
    # P2: SET col = val; \n WHERE → SET col = val \n WHERE (; 제거)
    clean = re.sub(
        r"(\bSET\s+\w+\s*=\s*[^;\n]+?);(\s*\n\s*WHERE\b)",
        r"\1\2", clean, flags=re.IGNORECASE
    )
    # 다중 컬럼 SET 다음 ; 잘못 (SET col = val,\n   col2 = ... 사이의 ;)
    clean = re.sub(
        r"(\bSET\s+\w+\s*=\s*[^;\n]+?);(\s*\n\s*(?:AND\b|OR\b))",
        r"\1\2", clean, flags=re.IGNORECASE
    )
    
    # P3: ',;' → ',' (UPDATE 다중 컬럼 SET 의 콤마 다음 잘못된 ;)
    clean = re.sub(r",\s*;\s*\n", ",\n", clean)
    
    # P4: RETURN CAST(...) 또는 RETURN expr 끝에 ; 누락
    clean = re.sub(
        r"(\bRETURN\s+CAST\s*\([^)]*\)(?:\s+AS\s+\w+(?:\([^)]*\))?)?)(?<![;])(\s*\n)",
        r"\1;\2", clean, flags=re.IGNORECASE
    )
    # ════════════════════════════════════════════════════════════════════
    # 끝 — v90.64 진짜 1064 fix
    # ════════════════════════════════════════════════════════════════════
    
    # ════════════════════════════════════════════════════════════════════
    # v90.66 (2026-04-28): RETURN 다중라인 표현식 끝 ; 보장
    # ════════════════════════════════════════════════════════════════════
    # 본부장님 fn_age 케이스 — v90.64 가 못 잡은 잔여 P4 변종:
    #   RETURN (YEAR(NOW()) - YEAR(p_birth))
    #          - CASE WHEN ... THEN 1 ELSE 0 END   ← 마지막 END 다음에 ; 없음
    #   END                                          ← 함수 BEGIN..END 의 닫는 END
    # → 'near END at line 12' 1064 발생
    #
    # 처방:
    #   '<expression>END\n<whitespace>END' 패턴 (CASE 의 END 가 맨 끝 RETURN
    #    표현식의 일부) 에서 안쪽 END 다음에 ; 가 없으면 추가.
    #   단, 안쪽이 'END IF' / 'END LOOP' / 'END WHILE' 면 그대로.
    
    # Step 1: 라인 단위 처리로 안전하게.
    # 'END' 로 끝나는 라인 다음 줄에 'END' 만 (혹은 들여쓰기 + END) 있으면,
    # 첫 번째 END 가 CASE 의 END 일 가능성. ; 보장.
    def _fix_inner_end_terminator(text):
        lines = text.split('\n')
        for i in range(len(lines) - 1):
            cur = lines[i].rstrip()
            nxt = lines[i + 1].strip()
            
            # 다음 줄이 'END' (블록 끝) 인지 확인 — 단독 END 또는 'END;' 만 인정
            # (END IF, END LOOP, END WHILE 는 제외)
            if not re.match(r"^END\s*;?\s*$", nxt, re.IGNORECASE):
                continue
            
            # 현재 줄이 'END' 로 끝나면서 ';' 없는 경우 (CASE 의 END)
            # 단, 'END IF', 'END LOOP', 'END WHILE' 는 제외
            m = re.search(r"\bEND\s*$", cur, re.IGNORECASE)
            if not m:
                continue
            
            # 'END IF', 'END LOOP', 'END WHILE' 는 자체적으로 ; 가 필요.
            # 그러나 그 케이스는 cur 가 'END IF' 처럼 끝나야 함 — 위 m 매치는
            # 'END' 자체 매치라 IF/LOOP/WHILE 가 END 앞에 있는 경우는 제외 필요.
            # 'END IF' 는 'EF' 로 끝나니 m 가 매치 안 함 — 그냥 'END' 만 매치.
            # 안전하게 cur 끝 토큰이 단독 END 인지 한 번 더 확인.
            tokens = cur.split()
            if not tokens or tokens[-1].upper() != 'END':
                continue
            # 마지막에서 두 번째 토큰이 IF/LOOP/WHILE 면 'IF END' 같이 거꾸로 된 케이스
            # (드물지만) 회피
            if len(tokens) >= 2 and tokens[-2].upper() in ('IF', 'LOOP', 'WHILE'):
                continue
            
            # 안쪽 END 끝에 ; 추가
            lines[i] = cur + ';'
        return '\n'.join(lines)
    
    clean = _fix_inner_end_terminator(clean)
    
    # ════════════════════════════════════════════════════════════════════
    # 끝 — v90.66 RETURN 다중라인 표현식 ; 보장
    # ════════════════════════════════════════════════════════════════════
    
    clean = clean.strip()

    if not clean:
        return {
            "success": False, "output": "", "error": "DDL이 비어있습니다",
            "executed": [], "failures": [], "stmt_count": 0,
        }

    # ── Phase 2: 문장 분리 ──────────────────────────────────────
    _dtrace("02-clean-done", clean_len=len(clean))
    try:
        statements = _split_sql_statements(clean)
    except Exception as split_err:
        logger.error("SQL 문장 분리 실패: %s", split_err)
        # 폴백: 전체를 하나의 문장으로 간주
        statements = [clean]

    if not statements:
        _dtrace("99-no-stmt")
        return {
            "success": False, "output": "", "error": "파싱 후 실행 가능한 문장이 없음",
            "executed": [], "failures": [], "stmt_count": 0,
        }

    logger.info("  [%s] DDL 파싱: %d개 문장 분리", obj_name, len(statements))
    _dtrace("03-split-done", stmt_count=len(statements))

    # ── Phase 3: 분류 ────────────────────────────────────────────
    drops:    list[str] = []
    creates:  list[str] = []
    alters:   list[str] = []
    others:   list[str] = []

    for stmt in statements:
        kind = _classify_statement(stmt)
        if kind == 'drop':
            drops.append(stmt)
        elif kind == 'create':
            creates.append(stmt)
        elif kind == 'alter':
            alters.append(stmt)
        elif kind == 'delimiter':
            pass  # skip
        else:
            others.append(stmt)

    logger.info("  [%s] 분류: DROP=%d, CREATE=%d, ALTER=%d, OTHER=%d",
                obj_name, len(drops), len(creates), len(alters), len(others))
    _dtrace("04-classify-done", drops=len(drops), creates=len(creates),
            alters=len(alters), others=len(others))

    # ── Phase 4: DROP 먼저 실행 (실패 허용) ─────────────────────
    executed: list[str] = []
    failures: list[dict] = []

    def _stmt_head(s: str, limit: int = 120) -> str:
        """문장 앞부분을 한 줄로 요약 (로그/진단용)."""
        one = " ".join(s.split())
        return one[:limit] + ("..." if len(one) > limit else "")

    def _exec_one(sql_text: str, kind_label: str, allow_fail: bool) -> tuple[bool, str]:
        """하나의 SQL 을 독립 커넥션에서 실행. (성공여부, 에러문자열) 반환."""
        import time as _time
        # v90.40: _exec_one 내부 마이크로 TRACE — freeze 정확한 발생점 파악용
        _eo_t0 = _time.monotonic()
        def _eotrace(stage: str, **kv):
            _el = _time.monotonic() - _eo_t0
            _kv = " ".join(f"{k}={v}" for k, v in kv.items())
            logger.info("[EXEC-ONE %s] [%s/%s] (+%.2fs) %s",
                        stage, obj_name, kind_label, _el, _kv)
            for _h in logger.handlers:
                try: _h.flush()
                except Exception: pass

        _eotrace("E1-enter", sql_head=_stmt_head(sql_text, 60))
        try:
            _eotrace("E2-connect-enter", host=conn_args.get("host"),
                     port=conn_args.get("port"))
            conn = pymysql.connect(**conn_args)
            _conn_id = None
            try:
                # v90.40: 진단용 connection id (KILL 가능하게 기록)
                try:
                    _ck = conn.cursor()
                    _ck.execute("SELECT CONNECTION_ID()")
                    _row = _ck.fetchone()
                    _conn_id = _row[0] if _row else None
                    _ck.close()
                except Exception: pass
                _eotrace("E3-connected", conn_id=_conn_id)

                cur = conn.cursor()
                # v90.29: MySQL 세션 timeout 설정 (DDL 무한 hang 방지)
                #   max_execution_time 은 SELECT 만 제한, DDL 은 안 됨
                #   대신 read_timeout (connection 단위) 으로 강제됨
                #   추가로 lock_wait_timeout 으로 메타데이터 lock 대기 시간 제한
                try:
                    cur.execute("SET SESSION lock_wait_timeout = 60")  # 1분 메타 lock 대기
                except Exception:
                    pass
                
                # v90.29: 진단 로그 - 어디서 멈췄는지 파악용
                _t_start = _time.monotonic()
                logger.info("  ▶ %s 시작: %s", kind_label, _stmt_head(sql_text, 80))
                # v90.40: ★★★ freeze 가장 의심 지점 ★★★ — execute 직전/직후 마커
                _eotrace("E4-execute-enter", conn_id=_conn_id,
                         sql_len=len(sql_text))
                
                # v90.43: CREATE PROCEDURE/FUNCTION/TRIGGER 의 경우 raw bytes hex 로깅
                #   본부장님 환경: 진단 스크립트 깔끔한 SQL 은 통과, 백엔드 AI SQL 은 1064.
                #   진짜 원인이 invisible char (BOM/NBSP/zero-width 등) 일 가능성이 큼.
                #   다음 1064 발생 시 정확한 byte 파악을 위해 hex dump 남김.
                _is_routine_create = (
                    kind_label == "CREATE" and
                    any(kw in sql_text.upper()[:100] 
                        for kw in ("PROCEDURE", "FUNCTION", "TRIGGER"))
                )
                if _is_routine_create:
                    try:
                        _sql_bytes = sql_text.encode('utf-8', errors='replace')
                        _eotrace("E4-rawbytes-head",
                                 hex=_sql_bytes[:200].hex(),
                                 byte_len=len(_sql_bytes))
                        _eotrace("E4-rawbytes-tail",
                                 hex=_sql_bytes[-200:].hex())
                        # ASCII 가 아닌 바이트가 있는지 검사
                        _non_ascii = [(i, hex(b)) for i, b in enumerate(_sql_bytes)
                                      if b > 127][:20]
                        if _non_ascii:
                            _eotrace("E4-non-ascii-found",
                                     count=len(_non_ascii),
                                     samples=str(_non_ascii[:10]))
                        # 의심 문자 직접 검사 (BOM/NBSP/zero-width)
                        _suspects = []
                        if '\ufeff' in sql_text: _suspects.append("BOM")
                        if '\u00a0' in sql_text: _suspects.append("NBSP")
                        if '\u3000' in sql_text: _suspects.append("ideographic-space")
                        for c in '\u200b\u200c\u200d\u200e\u200f\u2028\u2029\u2060':
                            if c in sql_text:
                                _suspects.append(f"U+{ord(c):04X}")
                        if _suspects:
                            _eotrace("E4-suspect-chars-detected",
                                     chars=",".join(_suspects))
                    except Exception as _be:
                        _eotrace("E4-bytes-log-err", error=str(_be)[:60])
                
                cur.execute(sql_text)
                _t_elapsed = _time.monotonic() - _t_start
                _eotrace("E5-execute-done", elapsed=f"{_t_elapsed:.2f}s")

                # v90.41: MULTI_STATEMENTS 모드에서는 cur.execute() 가 여러 결과셋을
                #   반환할 수 있음. 모두 소비하지 않으면 다음 쿼리에서 "Commands out of
                #   sync" 오류 발생. nextset() 으로 잔여 결과셋 정리.
                _nextset_count = 0
                try:
                    while cur.nextset():
                        _nextset_count += 1
                        if _nextset_count > 10:  # 안전장치
                            break
                except Exception:
                    pass  # nextset 미지원 또는 정상 (단일 결과셋)
                if _nextset_count > 0:
                    _eotrace("E5b-nextset-drained", count=_nextset_count)

                _eotrace("E6-commit-enter")
                conn.commit()
                _eotrace("E7-commit-done")

                if _t_elapsed > 5.0:
                    logger.warning("  ⏱ %s 느림 (%.1fs): %s", kind_label, _t_elapsed, _stmt_head(sql_text, 60))
                _eotrace("E8-return-ok")
                return True, ""
            finally:
                _eotrace("E9-close-enter")
                try:
                    conn.close()
                    _eotrace("E10-close-done")
                except Exception as _ce:
                    _eotrace("E10-close-err", error=str(_ce)[:80])
        except Exception as e:
            err = str(e)
            if allow_fail:
                logger.warning("  ⚠ %s 실패(무시): %s | %s",
                               kind_label, _stmt_head(sql_text, 60), err[:160])
            else:
                logger.error("  ✗ %s 실패: %s | %s",
                             kind_label, _stmt_head(sql_text, 60), err[:300])
                # v90.43: 1064/1146 등 SQL 오류 시 전체 SQL + hex 덤프
                #   다음 1064 발생 시 어떤 invisible char/오타 인지 정확 파악용
                if "1064" in err or "syntax" in err.lower():
                    try:
                        _full_bytes = sql_text.encode('utf-8', errors='replace')
                        logger.error("  [SQL-FAIL-DUMP] full_repr=%r", sql_text)
                        logger.error("  [SQL-FAIL-DUMP] full_hex=%s", _full_bytes.hex())
                    except Exception:
                        pass
            _eotrace("E99-exception", error=err[:120])
            return False, err

    # DROP 문은 끝 세미콜론 제거 후 실행 (PyMySQL 호환)
    _dtrace("05-drops-enter", count=len(drops))
    for d in drops:
        d_exec = _strip_trailing_semicolons(d)
        ok, err = _exec_one(d_exec, "DROP", allow_fail=True)
        if ok:
            logger.info("  ✓ DROP: %s", _stmt_head(d_exec, 80))
            executed.append(d_exec)
        # DROP 실패는 failures 에 넣지 않음 (IF EXISTS 라서 테이블 없으면 발생 가능)
    _dtrace("06-drops-done", executed=len(executed))

    # ── Phase 5: CREATE/ALTER/OTHER 실행 ────────────────────────
    primary_created = False  # obj_name 과 일치하는 CREATE 가 성공했는가

    # CREATE 는 obj_name 매칭 것을 먼저 (주 대상 우선 배포)
    def _sort_primary_first(create_list: list[str]) -> list[str]:
        primary = []
        others_ = []
        for c in create_list:
            extracted = _extract_object_name_from_create(c)
            if extracted and extracted.lower() == obj_name.lower():
                primary.append(c)
            else:
                others_.append(c)
        return primary + others_

    sorted_creates = _sort_primary_first(creates)

    _dtrace("07-creates-enter", count=len(sorted_creates))
    for c in sorted_creates:
        c_exec = _strip_trailing_semicolons(c)
        extracted = _extract_object_name_from_create(c) or obj_name

        ok, err = _exec_one(c_exec, "CREATE", allow_fail=False)
        if ok:
            logger.info("  ✓ CREATE 완료: %s", extracted)
            executed.append(_stmt_head(c_exec, 100))
            if extracted.lower() == obj_name.lower():
                primary_created = True
        else:
            failures.append({
                "stmt_head": _stmt_head(c_exec, 150),
                "object_name": extracted,
                "error": err,
            })
    _dtrace("08-creates-done", primary_ok=primary_created,
            failures=len(failures))

    _dtrace("09-alters-enter", count=len(alters))
    for a in alters:
        a_exec = _strip_trailing_semicolons(a)
        ok, err = _exec_one(a_exec, "ALTER", allow_fail=False)
        if ok:
            logger.info("  ✓ ALTER 완료")
            executed.append(_stmt_head(a_exec, 100))
        else:
            failures.append({
                "stmt_head": _stmt_head(a_exec, 150),
                "object_name": obj_name,
                "error": err,
            })
    _dtrace("10-alters-done")

    for o in others:
        o_exec = _strip_trailing_semicolons(o)
        if not o_exec:
            continue
        ok, err = _exec_one(o_exec, "STMT", allow_fail=False)
        if ok:
            logger.info("  ✓ 문장 실행: %s", _stmt_head(o_exec, 80))
            executed.append(_stmt_head(o_exec, 100))
        else:
            failures.append({
                "stmt_head": _stmt_head(o_exec, 150),
                "object_name": obj_name,
                "error": err,
            })

    # ── Phase 6: 결과 집계 ───────────────────────────────────────
    # 성공 판정:
    #   - primary CREATE 가 성공했으면 success=True (helper function 일부 실패 허용)
    #   - primary CREATE 가 아예 없었으면 (예: ALTER 만 있는 경우) failures 가 비어야 성공
    #   - failures 가 있지만 primary 는 성공한 경우 → 경고 포함 성공
    has_primary_create = any(
        _extract_object_name_from_create(c).lower() == obj_name.lower()
        for c in creates
    )

    if has_primary_create:
        success = primary_created
    else:
        success = len(failures) == 0 and len(executed) > 0

    if success:
        # 경고 메시지 조립 (primary 성공했지만 부가 실패 있는 경우)
        warn_notes = []
        if failures:
            warn_notes.append(
                f"보조 문장 {len(failures)}개 실패 (주 오브젝트 생성은 성공)"
            )
        output = f"{obj_name} 배포 완료"
        if warn_notes:
            output += " — " + "; ".join(warn_notes)

        # v90.40: 정상 반환 직전 마커
        _dtrace("99-return-success", executed=len(executed),
                failures=len(failures), stmt_count=len(statements))
        return {
            "success": True, "output": output, "error": "",
            "executed": executed, "failures": failures,
            "stmt_count": len(statements),
        }
    else:
        # 실패 — 실패 원인을 명확히
        if failures:
            primary_fail = next(
                (f for f in failures
                 if f["object_name"].lower() == obj_name.lower()),
                failures[0]
            )
            err_msg = primary_fail["error"]
        else:
            err_msg = "실행 가능한 CREATE 문장이 없음 (AI 응답 파싱 확인 필요)"

        # v90.40: 실패 반환 직전 마커
        _dtrace("99-return-fail", err=err_msg[:80],
                failures=len(failures))
        return {
            "success": False, "output": "", "error": err_msg,
            "executed": executed, "failures": failures,
            "stmt_count": len(statements),
        }

def _wrap_warning(msg: str, width: int = 80) -> str:
    """긴 경고 메시지를 width 글자 단위로 줄바꿈"""
    if len(msg) <= width:
        return msg
    parts = []
    while len(msg) > width:
        # 구분자(/) 기준으로 자름
        cut = msg.rfind(" / ", 0, width)
        if cut < 0:
            cut = msg.rfind(" ", 0, width)
        if cut < 0:
            cut = width
        parts.append(msg[:cut].strip())
        msg = msg[cut:].lstrip(" /").strip()
    if msg:
        parts.append(msg)
    return "\n".join(parts)
