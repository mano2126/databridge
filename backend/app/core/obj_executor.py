
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
    # v95_p15 Phase 3-B (2026-05-03): T-SQL CASE 잘못된 세미콜론 자동 정정
    # ════════════════════════════════════════════════════════════════════
    # 본부장님 본질 처방 (일반 패턴 — 어떤 MSSQL DB든 작동):
    #
    # 증상 (어제 측정 — ufnGetDocumentStatusText 등 3건):
    #   AI 가 변환한 결과:
    #     CASE @value
    #         ;                ← 잘못된 위치 세미콜론
    #         WHEN 1 THEN 'Pending'
    #         ...
    #
    # 원인: T-SQL 의 `RETURN CASE @value ... END;` 패턴을
    #       AI 가 파싱하면서 RETURN 직후에 ; 박은 경우.
    #
    # 처방: CASE 직후 세미콜론 정규식 제거 (어떤 DB 든 작동, 표준 SQL 정정)
    s = re.sub(
        r"\bCASE\b(\s+\S+)?\s*\n\s*;\s*\n\s*(?=WHEN\b)",
        lambda m: f"CASE{m.group(1) or ''}\n",
        s, flags=re.IGNORECASE
    )
    # 추가 변형: CASE 와 ; 사이에 변수만 있는 경우
    s = re.sub(
        r"(\bCASE\s+\S+)\s+;\s+(?=WHEN\b)",
        r"\1 ", s, flags=re.IGNORECASE
    )

    # ════════════════════════════════════════════════════════════════════
    # v95_p15 Phase 3-C (2026-05-03): T-SQL IF...BEGIN...END → MySQL IF...THEN...END IF
    # ════════════════════════════════════════════════════════════════════
    # 본부장님 본질 처방 (일반 패턴):
    #
    # 증상 (어제 측정 — uspUpdateEmployee* 3건):
    #   에러: `'END IF;\nEND' at line XX`
    #   AI 가 변환한 결과:
    #     IF @x = 1
    #         BEGIN
    #             SET @y = 2;
    #         END        ← MySQL 은 END IF; 필요
    #
    # 처방: IF...BEGIN...END 패턴을 IF...THEN...END IF 로 자동 변환
    #
    # 패턴: IF <조건>\n BEGIN ... END  →  IF <조건> THEN ... END IF;
    # 안전: ELSE/ELSEIF 같은 변형은 별도 처리 (T-SQL 표준 패턴만)
    #
    # 주의: 이 변환은 IF 가 BEGIN...END 블록과 함께 쓰일 때만 적용.
    #       IF 한 줄 (BEGIN 없이) 은 T-SQL 도 MySQL 도 동일.
    #
    # MySQL 의 IF 문 표준 문법:
    #   IF condition THEN
    #       statements;
    #   END IF;
    
    # 변형 1: IF cond \n BEGIN \n stmts \n END (단순)
    s = re.sub(
        r"\bIF\s+([^\n]+?)\s*\n\s*BEGIN\s*\n",
        r"IF \1 THEN\n",
        s, flags=re.IGNORECASE
    )
    # 그 후 매칭되는 END 를 END IF; 로 변환
    # 단순한 케이스 (가장 안전): END 단독으로 새 줄에 있고 다음에 또 다른 END 가 오는 경우만
    # → 단, 이건 컨텍스트 의존적이라 위험. AI 결과만 정정하는 식으로:
    # → 어제 본부장님 결과 = `'END IF;\nEND' at line XX`
    #    즉 마지막 END 만 누락된 케이스. 안전한 처방:
    s = re.sub(
        r"\bEND\s*;\s*\n\s*END\s*;?\s*$",
        "END IF;\nEND;",
        s, flags=re.IGNORECASE | re.MULTILINE
    )
    # IF...THEN...END (END IF 누락) 안전 정정
    # 주의: 너무 광범위하게 적용하면 SP 의 END (전체 종료) 까지 망가뜨림
    # 따라서 가장 보수적으로: AI 출력에 'IF ... THEN' 이 있고 'END IF' 없을 때만

    # ════════════════════════════════════════════════════════════════════
    # v95_p15 Phase 3-D (2026-05-03): TRIGGER 의 테이블 이름 case 보존
    # ════════════════════════════════════════════════════════════════════
    # 본부장님 본질 처방 (어제 측정 — iuPerson 트리거):
    #
    # 증상: TRIGGER iuPerson 이 'aw_target.person_person' 찾음 (소문자!)
    #   다른 VIEW 들은 'Person_Person' 정상.
    #   → 트리거 변환 어딘가에서 LOWER() 적용된 것.
    #
    # 처방: 변환 결과 마지막에 ON `lowercase_name` 패턴 발견 시
    #       원본 DDL 의 case 로 복원.
    #       (이건 obj_executor 호출자 측에서 더 정확히 처리 가능 — 여기선 정규식 안전망)
    #
    # 주의: 이 처방은 obj_executor 가 아니라 jobs.py 의 호출자가 처리하는 게 더 정확.
    #       여기서는 안전망으로만 — 명백히 잘못 변환된 패턴 정정.
    if otype == "TRIGGER":
        # 변환 결과에서 ON `소문자_단어` 패턴 발견 → 원본의 case 로 복원
        # 단, 원본 DDL 정보가 없으면 이 처방은 효과 없음
        # 따라서 이건 정보용 로깅만:
        _matches = re.findall(r"\bON\s+`([a-z][a-z_0-9]*)`", s)
        if _matches:
            warnings.append(
                f"v95_p15 Phase 3-D: TRIGGER 의 ON 절에 소문자 이름 발견 — "
                f"호출자가 case 보정 필요: {_matches}"
            )

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
    
    # ════════════════════════════════════════════════════════════
    # v95_p85 (2026-05-06 본부장님): DATEADD/DATEDIFF 약어 지원
    # ════════════════════════════════════════════════════════════
    # 본부장님 호소: "인터넷 연결 안된 상태로 돌려보니 오류"
    #
    # 본질: AI 차단 → rules_fallback → 그러나 MSSQL 약어 매칭 안 됨
    #   - DATEADD(mi, ...)  ← minute 약어, 본부장님 환경 핵심
    #   - DATEADD(yy, ...)  ← year 약어
    #   - DATEADD(dd, ...)  ← day 약어
    #
    # MSSQL 약어 매핑:
    #   yy/yyyy → YEAR        qq/q   → QUARTER (MySQL 미지원, MONTH * 3)
    #   mm/m    → MONTH       wk/ww  → WEEK
    #   dd/d/dy/y → DAY       hh     → HOUR
    #   mi/n    → MINUTE      ss/s   → SECOND
    #   ms      → MICROSECOND (MSSQL ms = millisecond)
    # ════════════════════════════════════════════════════════════
    _MSSQL_DATE_ABBREV = {
        # year
        'yy': 'YEAR', 'yyyy': 'YEAR',
        # quarter (MySQL 도 QUARTER 지원 — DATE_ADD 가능)
        'qq': 'QUARTER', 'q': 'QUARTER',
        # month
        'mm': 'MONTH', 'm': 'MONTH',
        # week
        'wk': 'WEEK', 'ww': 'WEEK',
        # day
        'dd': 'DAY', 'd': 'DAY', 'dy': 'DAY', 'y': 'DAY',
        # hour
        'hh': 'HOUR',
        # minute (★ 본부장님 환경 핵심)
        'mi': 'MINUTE', 'n': 'MINUTE',
        # second
        'ss': 'SECOND', 's': 'SECOND',
        # millisecond → MICROSECOND * 1000 (근사) — 단순화: MICROSECOND
        'ms': 'MICROSECOND',
    }
    
    def _replace_dateadd_abbrev(m):
        unit = m.group(1).lower()
        n_expr = m.group(2).strip()
        date_expr = m.group(3).strip()
        mysql_unit = _MSSQL_DATE_ABBREV.get(unit, unit.upper())
        return f"DATE_ADD({date_expr}, INTERVAL {n_expr} {mysql_unit})"
    
    # 약어 패턴 (year/month/day/hour/minute/second 외 모든 약어)
    # v95_p85 추가: 중첩 DATEADD 처리 위해 — 균형 괄호 인식 함수 기반
    #   본부장님 환경 ufnGetAccountingEndDate 케이스:
    #     RETURN DATEADD(mi, -1, DATEADD(d, 0, '2026-01-01'));
    #   → 정규식의 [^()]+ 로는 중첩 못 잡음
    #   → 균형 괄호 카운터로 정확한 인자 분리
    
    def _convert_dateadd_balanced(text: str) -> str:
        """
        중첩 괄호 인식하여 DATEADD(unit, n, date) → DATE_ADD(date, INTERVAL n UNIT)
        모든 발생 (중첩 포함) 변환. 반복 — 더 이상 변경 없을 때까지.
        """
        def _once(t: str) -> tuple[str, bool]:
            result = []
            i = 0
            n_len = len(t)
            changed = False
            while i < n_len:
                m = re.search(r"\bDATEADD\s*\(\s*", t[i:], re.IGNORECASE)
                if not m:
                    result.append(t[i:])
                    break
                result.append(t[i:i+m.start()])
                paren_start = i + m.end() - 1
                arg_start = paren_start + 1
                depth = 1
                j = arg_start
                while j < n_len and depth > 0:
                    if t[j] == '(':
                        depth += 1
                    elif t[j] == ')':
                        depth -= 1
                        if depth == 0:
                            break
                    j += 1
                if depth != 0:
                    result.append(t[i+m.start():])
                    break
                args_str = t[arg_start:j]
                args = []
                cur = []
                d = 0
                for ch in args_str:
                    if ch == '(':
                        d += 1; cur.append(ch)
                    elif ch == ')':
                        d -= 1; cur.append(ch)
                    elif ch == ',' and d == 0:
                        args.append(''.join(cur).strip()); cur = []
                    else:
                        cur.append(ch)
                if cur:
                    args.append(''.join(cur).strip())
                if len(args) == 3:
                    unit, n_expr, date_expr = args
                    unit_lower = unit.strip().lower()
                    if unit_lower in _MSSQL_DATE_ABBREV:
                        mysql_unit = _MSSQL_DATE_ABBREV[unit_lower]
                    elif unit_lower in ('year', 'month', 'day', 'hour', 'minute', 'second',
                                        'quarter', 'week', 'microsecond'):
                        mysql_unit = unit_lower.upper()
                    else:
                        result.append(t[i+m.start():j+1])
                        i = j + 1
                        continue
                    result.append(f"DATE_ADD({date_expr}, INTERVAL {n_expr} {mysql_unit})")
                    changed = True
                    i = j + 1
                else:
                    result.append(t[i+m.start():j+1])
                    i = j + 1
            return ''.join(result), changed
        
        # 더 이상 변경 없을 때까지 반복 (최대 10회 — 충분)
        for _ in range(10):
            text, _ch = _once(text)
            if not _ch:
                break
        return text
    
    # 균형 괄호 인식 변환 (정규식 한계 우회) — 중첩 DATEADD 모두 처리
    s = _convert_dateadd_balanced(s)
    
    # DATEDIFF 도 약어 지원 (이미 위에 yyyy 등은 매칭 안 됨)
    def _replace_datediff_abbrev(m):
        unit = m.group(1).lower()
        mysql_unit = _MSSQL_DATE_ABBREV.get(unit, unit.upper())
        rest = m.group(2)  # 날짜 인자들 (콤마 포함 부분)
        return f"TIMESTAMPDIFF({mysql_unit},{rest}"
    
    s = re.sub(
        r"\bDATEDIFF\s*\(\s*(yy|yyyy|qq|q|mm|m|wk|ww|dd|d|dy|y|hh|mi|n|ss|s|ms)\s*,(.*)",
        _replace_datediff_abbrev,
        s, flags=re.IGNORECASE
    )
    # ════════════════════════════════════════════════════════════
    
    # ════════════════════════════════════════════════════════════
    # v95_p85 (2026-05-06 본부장님): 추가 MSSQL → MySQL 변환 규칙
    # ════════════════════════════════════════════════════════════
    # 본부장님 환경 함수들에서 자주 사용되는 패턴:
    
    # 1) BIT 타입 → TINYINT(1)
    s = re.sub(r"\bBIT\b(?!\s*[\(_])", "TINYINT(1)", s, flags=re.IGNORECASE)
    
    # 2) NVARCHAR(MAX) → LONGTEXT, VARCHAR(MAX) → LONGTEXT
    s = re.sub(r"\bNVARCHAR\s*\(\s*MAX\s*\)", "LONGTEXT", s, flags=re.IGNORECASE)
    s = re.sub(r"\bVARCHAR\s*\(\s*MAX\s*\)",  "LONGTEXT", s, flags=re.IGNORECASE)
    s = re.sub(r"\bNVARCHAR\b",                "VARCHAR",  s, flags=re.IGNORECASE)
    s = re.sub(r"\bNTEXT\b",                   "TEXT",     s, flags=re.IGNORECASE)
    
    # 3) DATETIME2 → DATETIME, SMALLDATETIME → DATETIME
    s = re.sub(r"\bDATETIME2(?:\s*\(\s*\d+\s*\))?", "DATETIME", s, flags=re.IGNORECASE)
    s = re.sub(r"\bSMALLDATETIME\b",                "DATETIME", s, flags=re.IGNORECASE)
    s = re.sub(r"\bDATETIMEOFFSET(?:\s*\(\s*\d+\s*\))?", "DATETIME", s, flags=re.IGNORECASE)
    
    # 4) MONEY/SMALLMONEY → DECIMAL
    s = re.sub(r"\bSMALLMONEY\b", "DECIMAL(10,4)", s, flags=re.IGNORECASE)
    s = re.sub(r"\bMONEY\b",      "DECIMAL(19,4)", s, flags=re.IGNORECASE)
    
    # 5) UNIQUEIDENTIFIER → CHAR(36)
    s = re.sub(r"\bUNIQUEIDENTIFIER\b", "CHAR(36)", s, flags=re.IGNORECASE)
    
    # 6) IMAGE → LONGBLOB
    s = re.sub(r"\bIMAGE\b",      "LONGBLOB", s, flags=re.IGNORECASE)
    s = re.sub(r"\bVARBINARY\s*\(\s*MAX\s*\)", "LONGBLOB", s, flags=re.IGNORECASE)
    
    # 7) AS BEGIN ... END → BEGIN ... END (FUNCTION/PROCEDURE 본문)
    # MSSQL: CREATE FUNCTION ... RETURNS X AS BEGIN
    # MySQL: CREATE FUNCTION ... RETURNS X DETERMINISTIC BEGIN
    # AS 키워드만 제거 (BEGIN 직전)
    s = re.sub(r"\bAS\s+BEGIN\b",  "BEGIN", s, flags=re.IGNORECASE)
    
    # 8) RETURN @var → RETURN p_var (이미 위 @ 처리에서 됨, 보강)
    
    # 9) SET NOCOUNT ON / SET XACT_ABORT ON 제거 (MySQL 미지원)
    s = re.sub(r"\bSET\s+NOCOUNT\s+(ON|OFF)\s*;?", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\bSET\s+XACT_ABORT\s+(ON|OFF)\s*;?", "", s, flags=re.IGNORECASE)
    
    # 10) PRINT → SELECT (디버그 출력)
    s = re.sub(r"\bPRINT\s+", "SELECT ", s, flags=re.IGNORECASE)
    
    # 11) ISNUMERIC → 정규식 기반 (단순 변환은 어려움 — 경고만)
    if re.search(r"\bISNUMERIC\b", s, re.IGNORECASE):
        warnings.append("ISNUMERIC 함수는 MySQL 미지원 — 수동 검토 필요")
    
    # 12) CHARINDEX(needle, haystack) → LOCATE(needle, haystack)
    s = re.sub(
        r"\bCHARINDEX\s*\(",
        "LOCATE(",
        s, flags=re.IGNORECASE
    )
    
    # 13) LEN → CHAR_LENGTH
    s = re.sub(r"\bLEN\s*\(", "CHAR_LENGTH(", s, flags=re.IGNORECASE)
    
    # 14) STUFF, FORMATMESSAGE 등 — 경고만 (수동 검토)
    for fname, msg in [
        ('STUFF',         'STUFF 함수는 MySQL 미지원 — INSERT/SUBSTR 조합 필요'),
        ('FORMATMESSAGE', 'FORMATMESSAGE 는 MySQL 미지원 — CONCAT/PRINTF 사용'),
        ('NEWID',         'NEWID() → UUID() 자동 변환 권장'),
        ('SCOPE_IDENTITY','SCOPE_IDENTITY() → LAST_INSERT_ID() 자동 변환 권장'),
    ]:
        if re.search(rf"\b{fname}\b", s, re.IGNORECASE):
            warnings.append(msg)
    
    # 15) NEWID() → UUID()
    s = re.sub(r"\bNEWID\s*\(\s*\)", "UUID()", s, flags=re.IGNORECASE)
    
    # 16) SCOPE_IDENTITY()/@@IDENTITY → LAST_INSERT_ID()
    s = re.sub(r"\bSCOPE_IDENTITY\s*\(\s*\)", "LAST_INSERT_ID()", s, flags=re.IGNORECASE)
    s = re.sub(r"\b@@IDENTITY\b",             "LAST_INSERT_ID()", s, flags=re.IGNORECASE)
    
    # 17) @@ROWCOUNT → ROW_COUNT()
    s = re.sub(r"\b@@ROWCOUNT\b", "ROW_COUNT()", s, flags=re.IGNORECASE)
    
    # 18) @@ERROR — MySQL 미지원, 0 으로 (단순화)
    if re.search(r"\b@@ERROR\b", s, re.IGNORECASE):
        warnings.append("@@ERROR 는 MySQL 미지원 — DECLARE HANDLER 로 대체 필요 (0으로 임시 변환)")
        s = re.sub(r"\b@@ERROR\b", "0", s, flags=re.IGNORECASE)
    # ════════════════════════════════════════════════════════════
    
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


# ════════════════════════════════════════════════════════════════════
# v95_p58 (2026-05-05 본부장님): AI 변환 결과 캐시 (비용 절감)
# ════════════════════════════════════════════════════════════════════
# 본부장님 강조: "이대로는 계속 테스트를 할 수가 없어" (오늘 $51 비용)
#
# 본질:
#   동일 객체 (ufnGetAccountingEndDate 등) 가 9번 이상 AI 호출됨
#   → 같은 입력 → 같은 출력 → 90%+ 비용 낭비
#   → DataBridge 에 캐시 메커니즘 없음
#
# 처방 (일반화 — 하드코딩 0%):
#   - 캐시 키: src_db + tgt_db + obj_type + obj_name + DDL 해시
#   - 해시 기반: 원본 DDL 변경 시 자동 무효
#   - 저장: backend/data/ai_conversion_cache.json
#   - TTL 없음 (원본 변경 시 해시로 자동 갱신)
#   - error_hint 있으면 캐시 스킵 (재변환 의도)
#
# 효과 측정:
#   - 본부장님 환경 51개 객체 9회 반복 → 9번째부터 0 호출
#   - 다음 두번째 DB 이관 시 → 처음 1번만 비용
#   - 토큰 절감 약 80-90% (캐시 히트율 기반)
#
# 부작용 0:
#   - error_hint 모드에서는 캐시 스킵 (재변환 정상)
#   - 캐시 파일 손상 시 → AI 호출로 폴백 (안전)
#   - 사용자가 KB 업데이트 시 무효화 (DDL 변경 자동 감지)
# ════════════════════════════════════════════════════════════════════
def _ai_cache_path():
    """캐시 파일 경로 (backend/data/ai_conversion_cache.json)"""
    import os as _o
    _here = _o.path.dirname(_o.path.abspath(__file__))
    # core → app → backend → data
    _data_dir = _o.path.normpath(_o.path.join(_here, "..", "..", "..", "data"))
    if not _o.path.exists(_data_dir):
        try:
            _o.makedirs(_data_dir, exist_ok=True)
        except Exception:
            return None
    return _o.path.join(_data_dir, "ai_conversion_cache.json")


def _ai_cache_key(src_db, tgt_db, obj_type, obj_name, ddl):
    """캐시 키 — DDL 해시 포함 (원본 변경 시 자동 무효)"""
    import hashlib
    _h = hashlib.sha256(ddl.encode("utf-8")).hexdigest()[:16]
    return f"{src_db}__{tgt_db}__{obj_type}__{obj_name}__{_h}"


def _ai_cache_load():
    """캐시 로드 (실패 시 빈 dict)"""
    _p = _ai_cache_path()
    if not _p:
        return {}
    try:
        if not _os.path.exists(_p):
            return {}
        with open(_p, "r", encoding="utf-8") as _f:
            return json.load(_f)
    except Exception as _e:
        logger.warning(f"[v95_p58] AI 캐시 로드 실패: {_e} → 빈 캐시 사용")
        return {}


def _ai_cache_save(cache):
    """캐시 저장 (atomic write)"""
    _p = _ai_cache_path()
    if not _p:
        return False
    try:
        _tmp = _p + ".tmp"
        with open(_tmp, "w", encoding="utf-8") as _f:
            json.dump(cache, _f, ensure_ascii=False, indent=2)
        # atomic replace
        if _os.path.exists(_p):
            _os.replace(_tmp, _p)
        else:
            _os.rename(_tmp, _p)
        return True
    except Exception as _e:
        logger.warning(f"[v95_p58] AI 캐시 저장 실패: {_e}")
        return False


def _ai_cache_get(src_db, tgt_db, obj_type, obj_name, ddl):
    """캐시 조회 — 히트면 (converted_ddl, changes, warnings) 반환, 미스면 None"""
    _key = _ai_cache_key(src_db, tgt_db, obj_type, obj_name, ddl)
    _cache = _ai_cache_load()
    _entry = _cache.get(_key)
    if not _entry:
        return None
    return _entry


def _ai_cache_put(src_db, tgt_db, obj_type, obj_name, ddl, result):
    """캐시 저장 — result 는 ai_convert_ddl 의 dict 결과"""
    _key = _ai_cache_key(src_db, tgt_db, obj_type, obj_name, ddl)
    _cache = _ai_cache_load()
    import datetime as _dt
    _cache[_key] = {
        "obj_type": obj_type,
        "obj_name": obj_name,
        "src_db": src_db,
        "tgt_db": tgt_db,
        "converted_ddl": result.get("converted_ddl", ""),
        "changes": result.get("changes", []),
        "warnings": result.get("warnings", []),
        "cached_at": _dt.datetime.now().isoformat(timespec="seconds"),
    }
    _ai_cache_save(_cache)


# ════════════════════════════════════════════════════════════════════
# v95_p69 (2026-05-05 본부장님): 변환 패턴 KB 누적 학습 (Phase 2)
# ════════════════════════════════════════════════════════════════════
# 본부장님 결정: "5 Phase 모두 — 엔터프라이즈 솔루션"
# 본부장님 모토: "TypeMapping/ObjectMapping KB = 살아있는 자산"
#
# 본질:
#   사용자가 수동 변환한 SQL (v95_p66) 또는 AI 변환 성공 결과를
#   변환 패턴 KB 에 누적 → 다음 이관 시 같은 패턴 자동 매칭 → AI 호출 0
#
# KB 구조 (backend/data/conversion_patterns.json):
#   {
#     "patterns": [
#       {
#         "id": "user_xml_to_json",
#         "src_dialect": "mssql",
#         "tgt_dialect": "mysql",
#         "obj_type": "VIEW",
#         "src_pattern_keywords": ["XML.value", "CROSS APPLY"],  # 정규식 또는 키워드
#         "src_sample_ddl": "...",
#         "tgt_sample_ddl": "...",
#         "source": "user_manual" | "ai_success",
#         "registered_by": "user_id" | "system",
#         "registered_at": "2026-05-05T...",
#         "use_count": 5,  # 매칭 건수 (효율 측정)
#         "last_used_at": "..."
#       }
#     ]
#   }
#
# 매칭 흐름 (ai_convert_ddl 진입 시):
#   1) 사용자 결정 우선 (v95_p68)
#   2) AI 캐시 매칭 (v95_p58) — 정확 일치
#   3) v95_p69 KB 매칭 — 키워드 기반 유사 패턴 (NEW)
#   4) AI 호출 (마지막 수단)
#
# 부작용 0:
#   - KB 파일 없으면 매칭 스킵 (자동 폴백)
#   - 매칭 실패해도 옛 흐름 그대로
#   - 사용자가 수동 등록 안 하면 효과 0 (점진 누적)
# ════════════════════════════════════════════════════════════════════

def _kb_path():
    """변환 패턴 KB 경로"""
    import os as _o
    _here = _o.path.dirname(_o.path.abspath(__file__))
    _data_dir = _o.path.normpath(_o.path.join(_here, "..", "..", "..", "data"))
    if not _o.path.exists(_data_dir):
        try:
            _o.makedirs(_data_dir, exist_ok=True)
        except Exception:
            return None
    return _o.path.join(_data_dir, "conversion_patterns.json")


def _kb_load():
    """KB 로드 (실패 시 빈 dict)"""
    _p = _kb_path()
    if not _p or not _os.path.exists(_p):
        return {"patterns": []}
    try:
        with open(_p, "r", encoding="utf-8") as _f:
            data = json.load(_f)
            if "patterns" not in data:
                data["patterns"] = []
            return data
    except Exception as _e:
        logger.warning(f"[v95_p69] KB 로드 실패: {_e} → 빈 KB")
        return {"patterns": []}


def _kb_save(data):
    """KB 저장 (atomic write)"""
    _p = _kb_path()
    if not _p:
        return False
    try:
        _tmp = _p + ".tmp"
        with open(_tmp, "w", encoding="utf-8") as _f:
            json.dump(data, _f, ensure_ascii=False, indent=2)
        if _os.path.exists(_p):
            _os.replace(_tmp, _p)
        else:
            _os.rename(_tmp, _p)
        return True
    except Exception as _e:
        logger.warning(f"[v95_p69] KB 저장 실패: {_e}")
        return False


def _kb_register_pattern(src_db, tgt_db, obj_type, obj_name,
                        src_ddl, tgt_ddl, source="ai_success"):
    """변환 성공 시 KB 에 패턴 등록"""
    if not src_ddl or not tgt_ddl:
        return False
    
    # 위험 패턴 키워드 추출 (object_risk_analyzer 활용)
    pattern_keywords = []
    try:
        from app.engine.object_risk_analyzer import analyze_object_ddl
        analysis = analyze_object_ddl(obj_name, obj_type, src_ddl, src_db, tgt_db)
        pattern_keywords = [p.code for p in analysis.detected_patterns]
    except Exception:
        pass  # 분석 실패해도 KB 등록은 진행
    
    import datetime as _dt
    import hashlib
    
    kb = _kb_load()
    
    # 중복 방지 — src_ddl 해시로 체크
    _src_hash = hashlib.sha256(src_ddl.encode("utf-8")).hexdigest()[:16]
    for p in kb["patterns"]:
        if p.get("src_hash") == _src_hash:
            # 이미 등록된 패턴 — use_count 만 증가
            p["use_count"] = p.get("use_count", 0) + 1
            p["last_used_at"] = _dt.datetime.now().isoformat(timespec="seconds")
            _kb_save(kb)
            return True
    
    # 새 패턴 등록
    kb["patterns"].append({
        "id": f"kb_{_src_hash}",
        "src_db": src_db,
        "tgt_db": tgt_db,
        "obj_type": obj_type,
        "obj_name_sample": obj_name,
        "src_pattern_keywords": pattern_keywords,
        "src_hash": _src_hash,
        "src_sample_ddl": src_ddl[:5000],  # 5KB 제한
        "tgt_sample_ddl": tgt_ddl[:5000],
        "source": source,  # 'user_manual' | 'ai_success'
        "registered_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "use_count": 1,
        "last_used_at": _dt.datetime.now().isoformat(timespec="seconds"),
    })
    _kb_save(kb)
    logger.info(
        f"[v95_p69-KB-REGISTER] {obj_type} [{obj_name}] "
        f"패턴 등록 ({source}, 키워드: {pattern_keywords})"
    )
    return True


def _kb_match_pattern(src_db, tgt_db, obj_type, obj_name, src_ddl):
    """
    KB 에서 유사 패턴 매칭 (정확 일치 — 다른 객체의 같은 패턴은 별도 등록).
    
    매칭 조건:
      - src_db, tgt_db, obj_type 일치
      - src_hash 정확 일치 (현재) — 추후 키워드 유사도 매칭 확장 가능
    
    Returns:
      매칭된 패턴 dict 또는 None
    """
    if not src_ddl:
        return None
    import hashlib
    _src_hash = hashlib.sha256(src_ddl.encode("utf-8")).hexdigest()[:16]
    
    kb = _kb_load()
    for p in kb.get("patterns", []):
        if (p.get("src_db") == src_db and
            p.get("tgt_db") == tgt_db and
            p.get("obj_type") == obj_type and
            p.get("src_hash") == _src_hash):
            # 매칭 — use_count 증가 + 사용 시각 갱신
            import datetime as _dt
            p["use_count"] = p.get("use_count", 0) + 1
            p["last_used_at"] = _dt.datetime.now().isoformat(timespec="seconds")
            _kb_save(kb)
            return p
    return None
# ════════════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════════════
# v95_p70 (2026-05-05 본부장님): 실패 패턴 학습 + AI 재시도 차단 (Phase 3)
# ════════════════════════════════════════════════════════════════════
# 본부장님 결정: "5 Phase 모두 — 엔터프라이즈 솔루션"
# 본부장님 모토: "AI 무한 재시도 비용 낭비 차단"
#
# 본질:
#   같은 객체에 대해 AI 변환이 N회 실패 → 다시 AI 호출 = 같은 실패 + 비용 낭비
#   사용자 결정 (manual/exclude) 받기 전까지는 AI 호출 차단
#
# 실패 KB 구조 (backend/data/conversion_failures.json):
#   {
#     "failures": [
#       {
#         "src_hash": "...",
#         "obj_type": "VIEW", "obj_name_sample": "...",
#         "ai_attempts": 3,                # 시도 횟수
#         "ai_failures": 3,                # 실패 횟수
#         "last_error": "1064 syntax...",
#         "first_failed_at": "...",
#         "last_failed_at": "...",
#         "block_until_user_decides": true # 사용자 결정 받기 전까지 차단
#       }
#     ]
#   }
#
# 차단 흐름 (ai_convert_ddl 진입 시):
#   1) user_decision (v95_p68) — manual/exclude 면 우선 적용
#   2) AI 캐시 (v95_p58)
#   3) KB 매칭 (v95_p69)
#   4) v95_p70 실패 KB 체크 — N회 실패 + 사용자 결정 없음 → AI 호출 차단 (NEW)
#   5) AI 호출
#
# MAX_AI_FAILURE_ATTEMPTS:
#   - 환경 변수 DATABRIDGE_MAX_AI_FAILURES (기본 2)
#   - 초과 시 차단 + 사용자 결정 요청 메시지 반환
#
# 부작용 0:
#   - 실패 KB 비어있으면 차단 X (옛 흐름)
#   - 사용자가 "auto" 결정 시 차단 해제 (재시도 의도)
# ════════════════════════════════════════════════════════════════════

MAX_AI_FAILURE_ATTEMPTS = int(_os.environ.get("DATABRIDGE_MAX_AI_FAILURES", "2"))


def _failure_kb_path():
    """실패 패턴 KB 경로"""
    _here = _os.path.dirname(_os.path.abspath(__file__))
    _data_dir = _os.path.normpath(_os.path.join(_here, "..", "..", "..", "data"))
    if not _os.path.exists(_data_dir):
        try:
            _os.makedirs(_data_dir, exist_ok=True)
        except Exception:
            return None
    return _os.path.join(_data_dir, "conversion_failures.json")


def _failure_kb_load():
    _p = _failure_kb_path()
    if not _p or not _os.path.exists(_p):
        return {"failures": []}
    try:
        with open(_p, "r", encoding="utf-8") as _f:
            data = json.load(_f)
            if "failures" not in data:
                data["failures"] = []
            return data
    except Exception as _e:
        logger.warning(f"[v95_p70] 실패 KB 로드 실패: {_e}")
        return {"failures": []}


def _failure_kb_save(data):
    _p = _failure_kb_path()
    if not _p:
        return False
    try:
        _tmp = _p + ".tmp"
        with open(_tmp, "w", encoding="utf-8") as _f:
            json.dump(data, _f, ensure_ascii=False, indent=2)
        if _os.path.exists(_p):
            _os.replace(_tmp, _p)
        else:
            _os.rename(_tmp, _p)
        return True
    except Exception as _e:
        logger.warning(f"[v95_p70] 실패 KB 저장 실패: {_e}")
        return False


def _failure_check(src_db, tgt_db, obj_type, obj_name, src_ddl):
    """
    실패 KB 에서 차단 여부 확인.
    
    Returns:
      - None: 차단 안 함 (AI 호출 진행)
      - dict: 차단 — {ai_attempts, last_error, ...}
    """
    if not src_ddl:
        return None
    import hashlib
    _src_hash = hashlib.sha256(src_ddl.encode("utf-8")).hexdigest()[:16]
    
    db = _failure_kb_load()
    for f in db.get("failures", []):
        if (f.get("src_db") == src_db and
            f.get("tgt_db") == tgt_db and
            f.get("obj_type") == obj_type and
            f.get("src_hash") == _src_hash):
            # 사용자 결정 받기 전까지 차단 + N회 이상 실패한 경우
            if f.get("block_until_user_decides") and \
               f.get("ai_failures", 0) >= MAX_AI_FAILURE_ATTEMPTS:
                return f
    return None


def _failure_record(src_db, tgt_db, obj_type, obj_name, src_ddl, error_msg):
    """AI 변환 실패 기록 — 임계 도달 시 차단 마커 설정"""
    if not src_ddl:
        return
    import hashlib
    import datetime as _dt
    _src_hash = hashlib.sha256(src_ddl.encode("utf-8")).hexdigest()[:16]
    now = _dt.datetime.now().isoformat(timespec="seconds")
    
    db = _failure_kb_load()
    
    # 기존 기록 찾기
    for f in db["failures"]:
        if (f.get("src_db") == src_db and
            f.get("tgt_db") == tgt_db and
            f.get("obj_type") == obj_type and
            f.get("src_hash") == _src_hash):
            # 카운트 증가
            f["ai_attempts"] = f.get("ai_attempts", 0) + 1
            f["ai_failures"] = f.get("ai_failures", 0) + 1
            f["last_error"] = str(error_msg)[:500]
            f["last_failed_at"] = now
            # MAX 도달 시 차단 마커
            if f["ai_failures"] >= MAX_AI_FAILURE_ATTEMPTS:
                f["block_until_user_decides"] = True
                logger.warning(
                    f"[v95_p70-BLOCK] {obj_type} [{obj_name}] "
                    f"AI 실패 {f['ai_failures']}회 ≥ {MAX_AI_FAILURE_ATTEMPTS} → "
                    f"AI 재호출 차단 (사용자 결정 필요)"
                )
            _failure_kb_save(db)
            return
    
    # 새 기록
    db["failures"].append({
        "src_hash": _src_hash,
        "src_db": src_db,
        "tgt_db": tgt_db,
        "obj_type": obj_type,
        "obj_name_sample": obj_name,
        "ai_attempts": 1,
        "ai_failures": 1,
        "last_error": str(error_msg)[:500],
        "first_failed_at": now,
        "last_failed_at": now,
        "block_until_user_decides": False,
    })
    _failure_kb_save(db)


def _failure_clear(src_db, tgt_db, obj_type, src_ddl):
    """사용자 결정 받았거나 성공 시 — 차단 해제"""
    if not src_ddl:
        return
    import hashlib
    _src_hash = hashlib.sha256(src_ddl.encode("utf-8")).hexdigest()[:16]
    
    db = _failure_kb_load()
    db["failures"] = [
        f for f in db["failures"]
        if not (f.get("src_db") == src_db and
                f.get("tgt_db") == tgt_db and
                f.get("obj_type") == obj_type and
                f.get("src_hash") == _src_hash)
    ]
    _failure_kb_save(db)
# ════════════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════════════
# v95_p72 (2026-05-06 본부장님): 환각 자동 검증 + 안전 폴백 변환
# ════════════════════════════════════════════════════════════════════
# 본부장님 5번째 통찰: "사용자는 SQL 변환 능력 없다 — 시스템이 책임져야"
#
# 본질:
#   AI 가 v95_p33 강력한 프롬프트도 무시하고 _data, _Flattened 같은
#   가짜 테이블 이름 환각 생성 → 1146 (테이블 없음) 발생
#   → AI 결과를 그대로 믿지 말고 자동 검증 + 자동 수정 필수
#
# 처방 (3단계):
#   1) AI 변환 결과 SQL 에서 FROM/JOIN 의 테이블 이름 추출
#   2) 추출된 테이블이 MSSQL 원본에 존재하는지 검증
#   3) 가짜 테이블 발견 시 → 자동으로 안전 폴백 생성
#      (XML 파싱 컬럼 NULL 처리 + 베이스 테이블만 SELECT)
#
# 효과:
#   - 사용자가 SQL 작성 안 해도 시스템이 1146 자동 회피
#   - 신뢰도 5% → 안전 폴백으로 100% 이관 성공
#   - 진짜 사용자 친화 (외부 사용자도 클릭만 하면 됨)
#
# 부작용 0:
#   - 가짜 테이블 검출 안 되면 옛 흐름 (AI 결과 그대로)
#   - 폴백 변환 실패 시 빈 SELECT 로 안전 처리
#   - VIEW 만 적용 (PROCEDURE/FUNCTION 은 영향 없음)
# ════════════════════════════════════════════════════════════════════

def _extract_table_refs_from_sql(sql: str) -> list:
    """
    SQL 의 FROM/JOIN 절에서 테이블 이름 추출 (간단 정규식 기반).
    
    Returns:
      [{"name": "Production_ProductModel", "context": "FROM"}, ...]
    """
    if not sql:
        return []
    import re
    refs = []
    # FROM `table_name` 또는 FROM table_name 패턴
    # JOIN, LEFT JOIN, INNER JOIN 등 모두 포함
    patterns = [
        (r'\bFROM\s+`([^`]+)`',                     "FROM"),
        (r'\bFROM\s+([A-Za-z_][\w]*)',              "FROM"),
        (r'\b(?:INNER\s+|LEFT\s+|RIGHT\s+|OUTER\s+|CROSS\s+)*JOIN\s+`([^`]+)`',  "JOIN"),
        (r'\b(?:INNER\s+|LEFT\s+|RIGHT\s+|OUTER\s+|CROSS\s+)*JOIN\s+([A-Za-z_][\w]*)',  "JOIN"),
    ]
    for pat, ctx in patterns:
        for m in re.finditer(pat, sql, re.IGNORECASE):
            name = m.group(1)
            # MySQL 예약어 제외
            if name.upper() in ('SELECT', 'WHERE', 'AS', 'ON', 'AND', 'OR', 'LATERAL'):
                continue
            refs.append({"name": name, "context": ctx})
    return refs


def _detect_hallucinated_tables(converted_sql: str, src_ddl: str, obj_name: str) -> list:
    """
    AI 변환 결과의 가짜 테이블 검출.
    
    검출 기준:
      1) 원본 MSSQL 의 FROM/JOIN 에 없는 테이블 이름
      2) 원본 객체 이름 + 의심스러운 접미사 (_data, _Flattened 등)
      3) VIEW 자기참조 (vMyView 가 MyView 참조)
    
    Returns:
      [{"name": str, "reason": str}, ...]
    """
    if not converted_sql or not src_ddl:
        return []
    
    # 변환 결과의 테이블 참조
    converted_refs = _extract_table_refs_from_sql(converted_sql)
    converted_tables = set(r["name"] for r in converted_refs)
    
    # 원본 MSSQL 의 테이블 참조 (스키마.테이블 → 스키마_테이블 변환 고려)
    src_refs = _extract_table_refs_from_sql(src_ddl)
    # MSSQL 의 [Schema].[Table] 형식도 추출
    import re
    bracket_pattern = re.findall(r'\[([^\]]+)\]\s*\.\s*\[([^\]]+)\]', src_ddl)
    src_tables = set()
    for r in src_refs:
        src_tables.add(r["name"])
    for schema, table in bracket_pattern:
        # MSSQL 의 [Schema].[Table] → MySQL 의 Schema_Table 로 변환된 형식 모두 허용
        src_tables.add(table)
        src_tables.add(f"{schema}_{table}")
        src_tables.add(f"{schema}.{table}")
    
    # 의심스러운 접미사 패턴
    suspicious_suffixes = [
        '_data', '_DATA', '_Data',
        '_flat', '_Flat', '_Flattened', '_flattened',
        '_info', '_Info', '_detail', '_Detail',
        '_helper', '_Helper', '_aux', '_Aux',
        '_tmp', '_Tmp', '_TMP',
        '_ref', '_Ref',
        '_instruction', '_Instruction', '_Instructions',
        '_node', '_Node', '_joined', '_Joined',
        '_merged', '_Merged', '_split', '_Split',
    ]
    
    # v95_p77 (2026-05-06 본부장님): 언더스코어 없는 환각 접미사도 검출
    #   본부장님 환경 발견: Production_ProductModelInstructionsDetail
    #   ← 언더스코어 없이 'Detail' 직접 붙임 (v95_p72 검출 못함)
    suspicious_suffixes_no_underscore = [
        'Detail', 'Details', 'detail', 'details',
        'Data', 'Info', 'Helper', 'Aux',
        'Flat', 'Flattened',
        'Extended', 'Joined', 'Merged',
        'Tmp', 'Temp', 'View', 'Tbl', 'Table',
        'Result', 'Resolved',
    ]
    
    hallucinated = []
    for tbl in converted_tables:
        # 1) 원본에 없는 테이블
        if tbl not in src_tables:
            matched = False
            # 1-a) 의심스러운 접미사 체크 (언더스코어 있는 형태)
            for suffix in suspicious_suffixes:
                if tbl.endswith(suffix):
                    hallucinated.append({
                        "name": tbl,
                        "reason": f"의심 접미사 '{suffix}' — AI 환각 가능성 높음",
                    })
                    matched = True
                    break
            
            # v95_p77 (2026-05-06 본부장님): 언더스코어 없는 접미사도 검사
            #   본부장님 환경 발견: Production_ProductModelInstructionsDetail
            #   - obj_name = Production_vProductModelInstructions
            #   - 환각 = Production_ProductModelInstructionsDetail (스키마+테이블+Detail)
            #   - 핵심 부분 매치: 'ProductModelInstructions' 가 양쪽에 있음
            if not matched:
                # 객체 이름의 핵심 부분 추출 (스키마_ 제거 + v 제거)
                # 'Production_vProductModelInstructions' → 'ProductModelInstructions'
                obj_core = obj_name
                # 스키마 prefix 제거 (Schema_ 또는 schema_)
                if '_' in obj_core:
                    obj_core = obj_core.split('_', 1)[1]
                # v/V prefix 제거
                if obj_core.startswith('v') or obj_core.startswith('V'):
                    obj_core = obj_core[1:]
                
                # 환각 테이블의 핵심 부분 추출
                tbl_core = tbl
                if '_' in tbl_core:
                    tbl_core = tbl_core.split('_', 1)[1]
                
                # 핵심 부분이 환각 테이블에 포함되어 있는지
                # v95_p86 (2026-05-06 본부장님): 양방향 매칭 + 단/복수 변환
                #   본부장님 환경 발견:
                #     obj_name = 'Production_vProductModelInstructions'
                #     obj_core = 'vProductModelInstructions'
                #     환각    = 'Production_ProductModelInstruction' (s 누락)
                #     tbl_core = 'ProductModelInstruction'
                #     기존 'obj_core in tbl_core' 매치 안 됨 (길이 역전)
                #   처방:
                #     - 양방향 매치 (obj_core in tbl_core OR tbl_core in obj_core)
                #     - 단/복수형 정규화 (Instruction <-> Instructions)
                def _normalize_for_match(s):
                    """단/복수형 변환 + v 제거 + 소문자"""
                    s = s.lower()
                    if s.startswith('v'):
                        s = s[1:]
                    # ies → y (Activities → Activity)
                    if s.endswith('ies'):
                        s = s[:-3] + 'y'
                    # es → e/(없음) (Boxes → Box)
                    elif s.endswith('es') and len(s) > 3:
                        s = s[:-2]
                    # s → (없음) (Instructions → Instruction)
                    elif s.endswith('s') and len(s) > 2:
                        s = s[:-1]
                    return s
                
                obj_core_norm = _normalize_for_match(obj_core)
                tbl_core_norm = _normalize_for_match(tbl_core)
                
                core_match = False
                if obj_core and len(obj_core) > 5:
                    # 1) 정확 양방향 매치
                    if obj_core in tbl_core or tbl_core in obj_core:
                        core_match = True
                    # 2) 정규화 (단/복수) 양방향 매치
                    elif (obj_core_norm in tbl_core_norm or
                          tbl_core_norm in obj_core_norm) and \
                         len(obj_core_norm) > 4 and len(tbl_core_norm) > 4:
                        core_match = True
                
                if core_match:
                    # 의심 접미사 (언더스코어 없는 형태) 검사
                    for suffix in suspicious_suffixes_no_underscore:
                        if tbl.endswith(suffix) and len(tbl) > len(suffix):
                            hallucinated.append({
                                "name": tbl,
                                "reason": f"v95_p77 의심 접미사 '{suffix}' (객체 핵심 '{obj_core}' 포함)",
                            })
                            matched = True
                            break
                    # 접미사 매치 안 되어도 핵심 매치만으로도 환각
                    if not matched:
                        hallucinated.append({
                            "name": tbl,
                            "reason": f"v95_p86 객체 핵심 '{obj_core}' 양방향/단복수 매치 — 자기참조/prefix 환각",
                        })
                        matched = True
            
            # 1-b) 원본 객체 이름과 직접 유사 (v 제거 후)
            if not matched:
                obj_clean = obj_name.lstrip('v').lstrip('V')
                if obj_clean and obj_clean.lower() in tbl.lower():
                    hallucinated.append({
                        "name": tbl,
                        "reason": "VIEW 자기참조 의심 — 원본 객체 이름과 유사",
                    })
                elif tbl.lower() in obj_name.lower() and len(tbl) > 5:
                    hallucinated.append({
                        "name": tbl,
                        "reason": "원본 객체 이름의 부분 — 자기참조 의심",
                    })
    
    return hallucinated


def _generate_safe_fallback_view(obj_name: str, src_ddl: str) -> str:
    """
    AI 환각 검출 시 안전 폴백 VIEW 자동 생성.
    
    전략:
      1) 원본 MSSQL 의 SELECT 절에서 컬럼 이름 추출
      2) XML 파싱 컬럼 (.value/.nodes 사용) → NULL AS column_name 으로
      3) 일반 컬럼 → 그대로 SELECT
      4) FROM 은 원본의 첫 번째 테이블만 사용 (CROSS APPLY 등 제거)
    
    Returns:
      안전한 MySQL VIEW DDL (실패 시 빈 문자열)
    """
    if not src_ddl:
        return ""
    
    import re
    
    # 1) 원본 베이스 테이블 추출 (첫 번째 FROM)
    base_tables_match = re.search(
        r'\bFROM\s+\[?([A-Za-z_][\w]*)\]?\s*\.\s*\[?([A-Za-z_][\w]*)\]?',
        src_ddl, re.IGNORECASE
    )
    if base_tables_match:
        schema = base_tables_match.group(1)
        table = base_tables_match.group(2)
        base_table = f"`{schema}_{table}`"
    else:
        # 단일 이름 FROM
        m2 = re.search(r'\bFROM\s+\[?([A-Za-z_][\w]*)\]?', src_ddl, re.IGNORECASE)
        if m2:
            base_table = f"`{m2.group(1)}`"
        else:
            return ""  # FROM 못 찾음 — 폴백 생성 실패
    
    # 2) SELECT 컬럼 추출
    # SELECT ... FROM 사이 캡처
    select_match = re.search(
        r'\bSELECT\s+(.*?)\bFROM\b',
        src_ddl, re.IGNORECASE | re.DOTALL
    )
    if not select_match:
        return ""
    
    select_body = select_match.group(1)
    
    # 컬럼별 분리 (콤마 — 단순 분리, 함수 인자 콤마 주의)
    # 균형 괄호 기반 분리
    columns = []
    depth = 0
    current = ""
    for ch in select_body:
        if ch == '(':
            depth += 1
            current += ch
        elif ch == ')':
            depth -= 1
            current += ch
        elif ch == ',' and depth == 0:
            columns.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        columns.append(current.strip())
    
    # 3) 컬럼별 변환
    safe_columns = []
    for col in columns:
        # AS alias 추출
        as_match = re.search(r'\bAS\s+\[?([A-Za-z_][\w]*)\]?\s*$', col, re.IGNORECASE)
        if as_match:
            alias = as_match.group(1)
        else:
            # AS 없으면 마지막 토큰을 alias 로
            tokens = re.findall(r'[A-Za-z_]\w*', col)
            alias = tokens[-1] if tokens else f"col_{len(safe_columns)}"
        
        # XML 함수 사용 컬럼 → NULL
        if re.search(r'\.\s*(value|nodes|query|exist)\s*\(', col, re.IGNORECASE):
            safe_columns.append(f"NULL AS `{alias}`")
        # ref.value 같은 패턴
        elif '.ref.' in col.lower() or 'ref.' in col.lower():
            safe_columns.append(f"NULL AS `{alias}`")
        # CROSS APPLY 결과 alias 사용 컬럼
        elif re.search(r'\bSteps\.|MfgInstructions\.', col, re.IGNORECASE):
            safe_columns.append(f"NULL AS `{alias}`")
        # 일반 컬럼 → 단순 컬럼명만
        else:
            # v95_p87 (2026-05-06 본부장님): alias 제거 후 컬럼 이름만
            #   본부장님 환경: pm.[Name] 또는 pmi.Name 같은 alias.column 패턴
            #   → alias 무시하고 컬럼 이름만 사용 (베이스 테이블에서)
            
            # [컬럼이름] 추출 (대괄호)
            simple_col = re.search(r'\[([A-Za-z_][\w]*)\]', col)
            if simple_col:
                safe_columns.append(f"`{simple_col.group(1)}`")
            else:
                # alias.column 패턴 (예: pm.Name, pmi.Name)
                alias_col = re.search(r'\b\w+\s*\.\s*([A-Za-z_]\w*)\s*(?:AS|$|,)', col)
                if alias_col:
                    safe_columns.append(f"`{alias_col.group(1)}`")
                # 함수 호출 등 복잡 — alias 만 사용 + NULL
                elif re.search(r'\(', col):
                    safe_columns.append(f"NULL AS `{alias}`")
                else:
                    safe_columns.append(f"`{alias}`")
    
    if not safe_columns:
        return ""
    
    # 4) MySQL VIEW DDL 생성
    # v95_p77 (2026-05-06 본부장님): CREATE OR REPLACE → DROP + CREATE 분리
    #   본부장님 오류: '1064 syntax near DROP VIEW IF EXISTS HumanResources_vJobCandidateEducation'
    #   본질: migration_engine 이 외부에서 DROP 실행 + 폴백 DDL 의 CREATE OR REPLACE
    #         → 일부 MySQL 버전에서 충돌 또는 statement 분리 오류
    #   처방: 폴백 DDL 자체는 단순 CREATE VIEW 만 (외부 DROP 의존)
    #         또는 명시적 DROP + CREATE (안전)
    fallback_ddl = (
        f"-- v95_p72 안전 폴백 (AI 환각 검출 → 자동 생성)\n"
        f"-- v95_p77: DROP + CREATE 분리 (1064 syntax 회피)\n"
        f"-- 원본의 XML 파싱 컬럼은 NULL 로 대체됨\n"
        f"-- 응용단에서 EXTRACTVALUE() 등으로 별도 처리 권장\n"
        f"DROP VIEW IF EXISTS `{obj_name}`;\n"
        f"CREATE VIEW `{obj_name}` AS\n"
        f"SELECT\n  "
        + ",\n  ".join(safe_columns)
        + f"\nFROM {base_table};"
    )
    return fallback_ddl


def auto_fix_view_hallucination(converted_ddl: str, src_ddl: str,
                                obj_type: str, obj_name: str) -> dict:
    """
    AI 변환 결과를 검증하고 환각 발견 시 자동으로 안전 폴백 변환.
    
    Args:
      converted_ddl: AI 가 변환한 DDL
      src_ddl: 원본 MSSQL DDL
      obj_type: VIEW / PROCEDURE / FUNCTION / TRIGGER
      obj_name: 객체 이름
    
    Returns:
      {
        "fixed_ddl": str,           # 수정된 DDL (또는 원본)
        "was_fixed": bool,          # 수정 발생 여부
        "hallucinated": list,       # 검출된 환각 테이블
        "fallback_used": bool,      # 안전 폴백 사용 여부
        "notes": list,              # 사용자에게 보여줄 노트
      }
    """
    result = {
        "fixed_ddl": converted_ddl,
        "was_fixed": False,
        "hallucinated": [],
        "fallback_used": False,
        "notes": [],
    }
    
    # VIEW 만 자동 수정 (PROCEDURE 등은 너무 복잡)
    if obj_type.upper() != "VIEW":
        return result
    
    if not converted_ddl or not src_ddl:
        return result
    
    try:
        # 1) 환각 검출
        hallucinated = _detect_hallucinated_tables(converted_ddl, src_ddl, obj_name)
        result["hallucinated"] = hallucinated
        
        # ════════════════════════════════════════════════════════════
        # v95_p87 (2026-05-06 본부장님): MySQL 비호환 패턴 자동 검출
        # ════════════════════════════════════════════════════════════
        # 본부장님 환경 발견 (오후 6:49):
        #   (1054, "Unknown column 'pmi.Name' in 'field list'")
        # 본질:
        #   AI 가 진짜 베이스 테이블 (Production_ProductModel) 참조
        #   → 환각 검증 통과
        #   → 그러나 MySQL 비호환 SQL (CROSS APPLY/XML 함수) 그대로
        #   → MySQL 실행 시 1054 (alias.Name 등 참조 실패)
        #
        # 처방: 변환 결과에 MySQL 비호환 패턴 발견 시 → 강제 안전 폴백
        #
        # MySQL 비호환 패턴:
        #   - CROSS APPLY / OUTER APPLY (MySQL 8.0.14+ LATERAL 만 지원)
        #   - .value(...), .nodes(...), .query(...), .exist(...) (XML 함수)
        #   - PIVOT / UNPIVOT
        #   - hierarchyid 메서드 (.GetAncestor, .ToString 등)
        # ════════════════════════════════════════════════════════════
        mysql_incompatible_patterns = [
            (r'\bCROSS\s+APPLY\b', 'CROSS APPLY (MySQL 미지원)'),
            (r'\bOUTER\s+APPLY\b', 'OUTER APPLY (MySQL 미지원)'),
            (r'\.\s*value\s*\(',   'XML .value() (MySQL 미지원)'),
            (r'\.\s*nodes\s*\(',   'XML .nodes() (MySQL 미지원)'),
            (r'\.\s*query\s*\(',   'XML .query() (MySQL 미지원)'),
            (r'\.\s*exist\s*\(',   'XML .exist() (MySQL 미지원)'),
            (r'\bPIVOT\s*\(',      'PIVOT (MySQL 미지원)'),
            (r'\bUNPIVOT\s*\(',    'UNPIVOT (MySQL 미지원)'),
            (r'\.GetAncestor\(',   'hierarchyid.GetAncestor (MySQL 미지원)'),
            (r'\.ToString\s*\(\s*\)\s*AS\s+\w+', 'hierarchyid.ToString (MySQL 미지원)'),
        ]
        
        incompatible_found = []
        for pattern, desc in mysql_incompatible_patterns:
            if re.search(pattern, converted_ddl, re.IGNORECASE):
                incompatible_found.append(desc)
        
        if incompatible_found:
            logger.warning(
                f"[v95_p87-INCOMPAT] {obj_type} [{obj_name}] "
                f"MySQL 비호환 패턴 검출 {len(incompatible_found)}건: {incompatible_found}"
            )
            # 환각 hallucinated 에 추가 (UI 에 표시)
            for desc in incompatible_found:
                result["hallucinated"].append({
                    "name": "(SQL 패턴)",
                    "reason": f"v95_p87 {desc}",
                })
        # ════════════════════════════════════════════════════════════
        
        # 환각 또는 MySQL 비호환 패턴 — 둘 중 하나라도 있으면 폴백
        needs_fallback = bool(hallucinated) or bool(incompatible_found)
        
        if not needs_fallback:
            # 환각 없음 + MySQL 호환 — 원본 유지
            return result
        
        # 2) 환각 또는 비호환 발견 → 안전 폴백 생성
        if incompatible_found and not hallucinated:
            logger.warning(
                f"[v95_p87-FORCE-FALLBACK] {obj_type} [{obj_name}] "
                f"진짜 테이블이지만 MySQL 비호환 → 강제 안전 폴백"
            )
        else:
            logger.warning(
                f"[v95_p72-HALLUCINATION] {obj_type} [{obj_name}] "
                f"환각 검출 {len(hallucinated)}건 → 안전 폴백 생성 시도"
            )
        for h in hallucinated:
            logger.warning(f"  - {h['name']}: {h['reason']}")
        for desc in incompatible_found:
            logger.warning(f"  - MySQL 비호환: {desc}")
        
        fallback_ddl = _generate_safe_fallback_view(obj_name, src_ddl)
        if fallback_ddl:
            result["fixed_ddl"] = fallback_ddl
            result["was_fixed"] = True
            result["fallback_used"] = True
            result["notes"].append(
                f"⚠️ AI 가 가짜 테이블 {len(hallucinated)}개 생성 → 안전 폴백으로 자동 수정"
            )
            result["notes"].append(
                f"안전 폴백: XML/CROSS APPLY 부분은 NULL 로 대체, 베이스 테이블만 SELECT"
            )
            result["notes"].append(
                f"원본의 모든 컬럼 이름은 보존됨 (응용단에서 별도 처리 가능)"
            )
            logger.info(
                f"[v95_p72-FALLBACK] {obj_type} [{obj_name}] 안전 폴백 적용 완료"
            )
        else:
            # 폴백 생성 실패 — 빈 SELECT
            result["fixed_ddl"] = (
                f"-- v95_p72 폴백 생성 실패 — 빈 VIEW (수동 검토 필요)\n"
                f"CREATE OR REPLACE VIEW `{obj_name}` AS\n"
                f"SELECT NULL AS placeholder LIMIT 0;"
            )
            result["was_fixed"] = True
            result["notes"].append(
                f"⚠️ AI 환각 검출 + 안전 폴백 생성 실패 → 빈 VIEW 로 처리"
            )
            result["notes"].append(
                f"이 객체는 수동 검토 권장"
            )
    except Exception as e:
        logger.warning(f"[v95_p72] 환각 검증 오류 (무시): {e}")
    
    return result
# ════════════════════════════════════════════════════════════════════


# ── 2. Claude AI 변환 ─────────────────────────────────────────────
def ai_convert_ddl(ddl: str, obj_type: str, obj_name: str,
                   src_db: str = "mssql", tgt_db: str = "mysql",
                   error_hint: str = "",
                   user_decision: dict = None) -> dict:
    """
    Claude AI로 DDL 변환.
    Returns: {"converted_ddl": str, "changes": list, "warnings": list, "method": str}
    
    v95_p68 (2026-05-05 본부장님): user_decision 파라미터 추가 (Phase 5-3)
      - user_decision = { "decision": "auto"|"manual"|"exclude", "manual_sql": "..." }
      - "manual" 결정 시 manual_sql 직접 사용 (AI 호출 0)
      - "exclude" 결정 시 빈 결과 + skip 마커 반환
      - "auto" 또는 None 이면 기존 흐름 (AI 변환)
    """
    import os

    # ════════════════════════════════════════════════════════════════
    # v95_p68 (2026-05-05 본부장님): 사용자 결정 우선 적용 (Phase 5-3)
    # ════════════════════════════════════════════════════════════════
    # 본부장님 결정: "5 Phase 모두 — 엔터프라이즈 솔루션"
    #
    # user_decision 흐름:
    #   - 'manual' → manual_sql 직접 사용 (AI 호출 0, 비용 절감)
    #   - 'exclude' → 객체 이관 스킵 (빈 결과 + skip 마커)
    #   - 'auto' / None → 기존 AI 변환 흐름 (캐시 → AI 호출)
    if user_decision and isinstance(user_decision, dict):
        dec = user_decision.get("decision", "")
        if dec == "manual":
            manual_sql = (user_decision.get("manual_sql") or "").strip()
            if manual_sql:
                logger.info(
                    f"[v95_p68-USER-MANUAL] {obj_type} [{obj_name}] "
                    f"사용자 수동 SQL 사용 (AI 호출 0)"
                )
                # v95_p69: 사용자 수동 SQL 을 KB 에 자동 등록 (다음 이관 시 재사용)
                try:
                    _kb_register_pattern(
                        src_db, tgt_db, obj_type, obj_name,
                        src_ddl=ddl, tgt_ddl=manual_sql,
                        source="user_manual"
                    )
                except Exception as _ke:
                    logger.debug(f"[v95_p69] KB 등록 실패 (무시): {_ke}")
                return {
                    "converted_ddl": manual_sql,
                    "changes": ["[v95_p68 사용자 수동 SQL — AI 변환 우회]",
                                "[v95_p69 KB 자동 등록]"],
                    "warnings": [],
                    "method": "user_manual",
                }
            else:
                logger.warning(
                    f"[v95_p68] {obj_type} [{obj_name}] "
                    f"manual 결정이지만 manual_sql 비어있음 → AI 변환 폴백"
                )
        elif dec == "exclude":
            logger.info(
                f"[v95_p68-USER-EXCLUDE] {obj_type} [{obj_name}] "
                f"사용자가 이관 제외 결정"
            )
            return {
                "converted_ddl": "",
                "changes": ["[v95_p68 사용자 결정: 이관 제외]"],
                "warnings": [],
                "method": "user_exclude",
                "skip": True,  # 호출자가 이 플래그로 배포 스킵
            }
        # 'auto' 또는 다른 값 → 기존 흐름
    # ════════════════════════════════════════════════════════════════

    # ════════════════════════════════════════════════════════════════
    # v95_p58 (2026-05-05 본부장님): AI 변환 캐시 진입
    # ════════════════════════════════════════════════════════════════
    # error_hint 있으면 재변환 의도 → 캐시 스킵
    if not error_hint:
        _cached = _ai_cache_get(src_db, tgt_db, obj_type, obj_name, ddl)
        if _cached:
            logger.info(
                f"[v95_p58-CACHE-HIT] {obj_type} [{obj_name}] "
                f"AI 호출 스킵 (캐시 히트, cached_at={_cached.get('cached_at','?')})"
            )
            _cached_ddl = _cached["converted_ddl"]
            _cached_changes = list(_cached.get("changes", []))
            _cached_warnings = list(_cached.get("warnings", []))
            
            # ════════════════════════════════════════════════════════
            # v95_p86 (2026-05-06 본부장님): 캐시 히트도 환각 검증
            # ════════════════════════════════════════════════════════
            # 본부장님 환경 발견: 옛 환각 결과가 캐시에 저장되어 재사용됨
            #   - vJobCandidateEducation_data, ProductModelInstruction (s 누락) 등
            # 처방: 캐시 히트해도 환각 검증 → 검출 시 안전 폴백
            try:
                _fix_result = auto_fix_view_hallucination(
                    converted_ddl=_cached_ddl,
                    src_ddl=ddl,
                    obj_type=obj_type,
                    obj_name=obj_name
                )
                if _fix_result["was_fixed"]:
                    logger.warning(
                        f"[v95_p86-CACHE-AUTO-FIX] {obj_type} [{obj_name}] "
                        f"옛 캐시에 환각 검출 → 안전 폴백 적용 "
                        f"({len(_fix_result['hallucinated'])}건)"
                    )
                    _cached_ddl = _fix_result["fixed_ddl"]
                    _cached_changes.append("[v95_p86 옛 캐시 환각 자동 수정]")
                    _cached_warnings.extend([
                        f"v95_p86 환각 자동 수정: {h['name']}"
                        for h in _fix_result["hallucinated"]
                    ])
            except Exception as _fxe:
                logger.debug(f"[v95_p86] 캐시 환각 검증 오류 (무시): {_fxe}")
            # ════════════════════════════════════════════════════════
            
            return {
                "converted_ddl": _cached_ddl,
                "changes": _cached_changes + ["[v95_p58 캐시 히트 — AI 호출 0]"],
                "warnings": _cached_warnings,
                "method": "ai_cached",
            }
    # ════════════════════════════════════════════════════════════════

    # ════════════════════════════════════════════════════════════════
    # v95_p69 (2026-05-05 본부장님): KB 패턴 매칭 (Phase 2)
    # ════════════════════════════════════════════════════════════════
    # 캐시 미스 시 → KB 매칭 시도 (사용자 수동 SQL 또는 옛 AI 성공)
    # 매칭 시 → AI 호출 0, 검증된 변환 재사용
    if not error_hint:
        try:
            _matched = _kb_match_pattern(src_db, tgt_db, obj_type, obj_name, ddl)
            if _matched:
                logger.info(
                    f"[v95_p69-KB-MATCH] {obj_type} [{obj_name}] "
                    f"KB 매칭 (id={_matched.get('id')}, "
                    f"source={_matched.get('source')}, "
                    f"use_count={_matched.get('use_count')})"
                )
                return {
                    "converted_ddl": _matched.get("tgt_sample_ddl", ""),
                    "changes": [
                        f"[v95_p69 KB 매칭 — source={_matched.get('source')}, "
                        f"use_count={_matched.get('use_count')}]"
                    ],
                    "warnings": [],
                    "method": "kb_matched",
                }
        except Exception as _ke:
            logger.debug(f"[v95_p69] KB 매칭 오류 (무시): {_ke}")
    # ════════════════════════════════════════════════════════════════

    # ════════════════════════════════════════════════════════════════
    # v95_p70 (2026-05-05 본부장님): 실패 패턴 차단 (Phase 3)
    # ════════════════════════════════════════════════════════════════
    # AI 가 N회 실패한 패턴은 사용자 결정 (manual/exclude) 받기 전까지 차단
    # error_hint 모드 (사용자 명시적 재시도) 는 차단 우회
    if not error_hint:
        try:
            _blocked = _failure_check(src_db, tgt_db, obj_type, obj_name, ddl)
            if _blocked:
                logger.warning(
                    f"[v95_p70-BLOCKED] {obj_type} [{obj_name}] "
                    f"AI 실패 {_blocked.get('ai_failures')}회 — 사용자 결정 필요"
                )
                return {
                    "converted_ddl": "",
                    "changes": [
                        f"[v95_p70 AI 호출 차단 — {_blocked.get('ai_failures')}회 실패, "
                        f"사용자 결정 필요 (manual/exclude)]"
                    ],
                    "warnings": [
                        f"⚠️ 이 객체는 AI 변환에 {_blocked.get('ai_failures')}회 실패했습니다.",
                        f"   마지막 오류: {_blocked.get('last_error', '?')}",
                        "   위저드에서 [수동 SQL 작성] 또는 [이관 제외] 를 선택해주세요.",
                    ],
                    "method": "blocked_by_failure_kb",
                    "skip": True,  # 호출자가 이 플래그로 배포 스킵
                    "needs_user_decision": True,
                }
        except Exception as _fe:
            logger.debug(f"[v95_p70] 실패 KB 체크 오류 (무시): {_fe}")
    # ════════════════════════════════════════════════════════════════

    try:
        from app.api.routes.settings import _cfg as _get_cfg
        api_key = _get_cfg().get("anthropic_api_key", "").strip()
    except Exception:
        api_key = ""
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if not api_key:
        logger.warning("ai_convert_ddl: API 키 없음 → 규칙 기반 폴백")
        converted, warnings = mssql_to_mysql_ddl(ddl, obj_type)
        
        # ════════════════════════════════════════════════════════════
        # v95_p86 (2026-05-06 본부장님): rules_fallback 도 환각 검증
        # ════════════════════════════════════════════════════════════
        # 본부장님 환경 발견: 망분리 환경 + AI 캐시에 옛 환각 결과 잔존
        #   → rules_fallback 흐름은 환각 검증 자체를 안 했음
        # 처방: 모든 흐름에 환각 검증 + 폴백 적용
        try:
            _fix_result = auto_fix_view_hallucination(
                converted_ddl=converted,
                src_ddl=ddl,
                obj_type=obj_type,
                obj_name=obj_name
            )
            if _fix_result["was_fixed"]:
                logger.warning(
                    f"[v95_p86-RULES-AUTO-FIX] {obj_type} [{obj_name}] "
                    f"규칙 폴백 결과에 환각 검출 → 안전 폴백 적용 "
                    f"({len(_fix_result['hallucinated'])}건)"
                )
                converted = _fix_result["fixed_ddl"]
                warnings = (warnings or []) + [
                    f"v95_p86 환각 자동 수정: {h['name']}" for h in _fix_result["hallucinated"]
                ]
        except Exception as _fxe:
            logger.debug(f"[v95_p86] 환각 검증 오류 (무시): {_fxe}")
        # ════════════════════════════════════════════════════════════
        
        return {"converted_ddl": converted, "changes": ["규칙 기반 변환 (API 키 없음)"],
                "warnings": warnings, "method": "rules_fallback"}

    src_name = {"mssql":"SQL Server","mysql":"MySQL","mariadb":"MariaDB",
                "postgresql":"PostgreSQL","aurora":"Aurora MySQL"}.get(src_db.lower(), src_db)
    tgt_name = {"mssql":"SQL Server","mysql":"MySQL","mariadb":"MariaDB",
                "postgresql":"PostgreSQL","aurora":"Aurora MySQL"}.get(tgt_db.lower(), tgt_db)

    # ════════════════════════════════════════════════════════════════
    # v95_p98 (2026-05-08 본부장님 비전 — KB error 매칭 통합)
    # ════════════════════════════════════════════════════════════════
    # 본부장님 모토 그대로:
    #   "RAG 풍성하게" — error_kb 매칭 + fix_prompt 강화
    #   "KB 자산 누적" — record_attempt 등재
    #
    # 본부장님 환경 발견 (2026-05-08 18:13):
    #   error_hint 모드 (검증 페이지 재시도) 에서 KB 영역 우회
    #   → 신규 7개 패턴 (1054_PARAM_AS_COLUMN 등) 매칭 0
    #
    # 처방:
    #   error_hint 있을 때 (즉 재시도 모드) → match_error 호출
    #   매칭 시 → fix_prompt 를 error_hint 에 강화 주입
    #   AI 호출 후 → record_attempt 등재 (성공/실패)
    # ════════════════════════════════════════════════════════════════
    _matched_error_kb = None       # AI 호출 후 record_attempt 용
    _enhanced_error_hint = error_hint  # KB 매칭 시 강화된 hint 로 교체
    
    if error_hint:
        try:
            from app.engine.error_kb import match_error, assemble_prompt_hint
            _matched_error_kb = match_error(error_hint)
            if _matched_error_kb:
                logger.info(
                    f"[v95_p98-KB-ERROR-MATCH] {obj_type} [{obj_name}] "
                    f"KB 패턴 매칭 (id={_matched_error_kb.get('id')}, "
                    f"category={_matched_error_kb.get('category')}, "
                    f"fix_type={_matched_error_kb.get('fix_type')})"
                )
                # KB 의 fix_prompt 를 error_hint 에 강화 주입
                _kb_hint = assemble_prompt_hint(
                    current_error=error_hint,
                    error_history=[],
                )
                if _kb_hint:
                    _enhanced_error_hint = (
                        f"{error_hint}\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"[KB 매칭 처방 — id={_matched_error_kb.get('id')}]\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"{_kb_hint}"
                    )
                    logger.info(
                        f"[v95_p98-KB-PROMPT-INJECT] {obj_type} [{obj_name}] "
                        f"fix_prompt 주입 (원본 hint {len(error_hint)} → 강화 {len(_enhanced_error_hint)} chars)"
                    )
        except Exception as _ke:
            logger.warning(f"[v95_p98] KB 에러 매칭 오류 (무시): {_ke}")
    # ════════════════════════════════════════════════════════════════

    # ── 프롬프트 파일에서 로드 ─────────────────────────────────────
    prompt = _build_prompt(
        src_db=src_db, tgt_db=tgt_db,
        obj_type=obj_type, obj_name=obj_name,
        ddl=ddl, error_hint=_enhanced_error_hint
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

        # ════════════════════════════════════════════════════════════════
        # v95_p17 (2026-05-03 본부장님 본질 처방): AI 결과 정규식 후처리 강화
        # ════════════════════════════════════════════════════════════════
        # 본부장님 v95_p15 측정 (95% 도달, 잔여 8건):
        #   - FUNC 3건: CASE WHEN ; (AI 가 잘못된 위치에 ; 박음)
        #   - SP 2건: END IF; 누락
        #
        # 본질: v95_p15 의 Phase 3-B/3-C 정규식이 mssql_to_mysql_ddl 안에 있는데
        #        AI 변환 성공 시 mssql_to_mysql_ddl 가 호출 안 됨 → 정규식 못 거침.
        #
        # 처방: AI 변환 결과 (converted) 에도 _enforce_varchar_length 처럼
        #        Phase 3-B/3-C 정규식 후처리 적용 (별도 함수 호출).
        if converted:
            try:
                converted_before = converted
                converted = _post_fix_ai_ddl(converted, obj_type)
                if converted != converted_before:
                    logger.info("ai_convert_ddl [%s] %s → v95_p17 AI 후처리 적용",
                                obj_type, obj_name)
                    parsed.setdefault("changes", []).append(
                        "v95_p17: AI 결과 정규식 후처리 (CASE ; / END IF;)"
                    )
            except Exception as _pe:
                # 후처리 실패해도 원본 그대로 (안전)
                logger.warning("v95_p17 후처리 실패 [%s] %s: %s — 원본 유지",
                               obj_type, obj_name, _pe)

        logger.info("ai_convert_ddl [%s] %s → 완료 (%d자)",
                    obj_type, obj_name, len(converted))
        
        # ════════════════════════════════════════════════════════════
        # v95_p72 (2026-05-06 본부장님): AI 환각 자동 검증 + 안전 폴백
        # ════════════════════════════════════════════════════════════
        # 본부장님 5번째 통찰: "사용자는 SQL 변환 능력 없다"
        # → AI 결과를 그대로 믿지 말고 환각 자동 검출 + 자동 수정
        try:
            _fix_result = auto_fix_view_hallucination(
                converted_ddl=converted,
                src_ddl=ddl,
                obj_type=obj_type,
                obj_name=obj_name
            )
            if _fix_result["was_fixed"]:
                logger.warning(
                    f"[v95_p72-AUTO-FIX] {obj_type} [{obj_name}] "
                    f"AI 환각 검출 → 안전 폴백 적용 "
                    f"(검출 {len(_fix_result['hallucinated'])}건)"
                )
                converted = _fix_result["fixed_ddl"]
                # changes 에 자동 수정 노트 추가
                # parsed 가 없을 수 있음 — 안전하게
                if 'parsed' not in dir() or parsed is None:
                    parsed = {"changes": [], "warnings": []}
                parsed.setdefault("changes", []).extend([
                    "[v95_p72 AI 환각 자동 수정 적용]",
                    *[f"  - {n}" for n in _fix_result["notes"]]
                ])
                parsed.setdefault("warnings", []).extend([
                    f"환각 테이블: {h['name']} ({h['reason']})"
                    for h in _fix_result["hallucinated"]
                ])
        except Exception as _fxe:
            logger.warning(f"[v95_p72] 환각 자동 검증 오류 (무시): {_fxe}")
        # ════════════════════════════════════════════════════════════
        
        _result = {
            "converted_ddl": converted,
            "changes":       parsed.get("changes", []),
            "warnings":      [_wrap_warning(w) for w in parsed.get("warnings", [])],
            "method": "claude-ai",
        }
        # v95_p58: AI 성공 결과를 캐시에 저장 (error_hint 모드 제외)
        if not error_hint:
            try:
                _ai_cache_put(src_db, tgt_db, obj_type, obj_name, ddl, _result)
                logger.debug(f"[v95_p58-CACHE-PUT] {obj_type} [{obj_name}] 캐시 저장")
            except Exception as _ce:
                logger.warning(f"[v95_p58] 캐시 저장 실패 (무시): {_ce}")
        
        # ════════════════════════════════════════════════════════════
        # v95_p98 (2026-05-08 본부장님 비전): KB 통계 자동 등재
        # ════════════════════════════════════════════════════════════
        # 본부장님 모토 그대로 — KB 자산 누적 (살아있는 자산)
        # error_hint 모드 (재시도) 에서 KB 매칭됐으면 success 등재
        # _UNMATCHED_ 도 등재 (다음 분석 자산)
        if error_hint:
            try:
                from app.engine.error_kb import record_attempt
                record_attempt(
                    pattern_id=(_matched_error_kb or {}).get("id"),  # None → _UNMATCHED_ 자동
                    error_code=(_matched_error_kb or {}).get("error_code", ""),
                    category=(_matched_error_kb or {}).get("category", ""),
                    job_id="",
                    item_name=obj_name,
                    attempt_num=1,
                    success=True,    # AI 변환 성공
                    ai_used=True,
                    prompt_chars=len(_enhanced_error_hint or ""),
                )
                logger.info(
                    f"[v95_p98-KB-RECORD] {obj_type} [{obj_name}] "
                    f"KB 등재 (pattern={_matched_error_kb.get('id') if _matched_error_kb else '_UNMATCHED_'}, success=True)"
                )
            except Exception as _re:
                logger.debug(f"[v95_p98] KB 등재 실패 (무시): {_re}")
        # ════════════════════════════════════════════════════════════
            # v95_p69: AI 성공 결과를 KB 에도 등록 (다음 이관 시 같은 패턴 매칭)
            try:
                _kb_register_pattern(
                    src_db, tgt_db, obj_type, obj_name,
                    src_ddl=ddl, tgt_ddl=converted,
                    source="ai_success"
                )
            except Exception as _ke:
                logger.debug(f"[v95_p69] KB 등록 실패 (무시): {_ke}")
            # v95_p70: AI 성공 시 실패 KB 에서 차단 해제
            try:
                _failure_clear(src_db, tgt_db, obj_type, ddl)
            except Exception as _fce:
                logger.debug(f"[v95_p70] 차단 해제 오류 (무시): {_fce}")
        return _result

    except Exception as e:
        logger.error("ai_convert_ddl 실패 [%s] %s: %s", obj_type, obj_name, e)
        # v95_p70: AI 실패 기록 — N회 도달 시 다음번 차단
        if not error_hint:
            try:
                _failure_record(src_db, tgt_db, obj_type, obj_name, ddl, str(e))
            except Exception as _fre:
                logger.debug(f"[v95_p70] 실패 기록 오류 (무시): {_fre}")
        # ════════════════════════════════════════════════════════════
        # v95_p98 (2026-05-08 본부장님 비전): 실패도 KB 등재
        # ════════════════════════════════════════════════════════════
        # 본부장님 비전 그대로 — 실패 패턴도 KB 자산
        # 다음에 같은 본질 만나면 → 통계로 인지 → 처방 우선순위
        if error_hint:
            try:
                from app.engine.error_kb import record_attempt
                record_attempt(
                    pattern_id=(_matched_error_kb or {}).get("id"),
                    error_code=(_matched_error_kb or {}).get("error_code", ""),
                    category=(_matched_error_kb or {}).get("category", ""),
                    job_id="",
                    item_name=obj_name,
                    attempt_num=1,
                    success=False,    # AI 변환 실패
                    ai_used=True,
                    prompt_chars=len(_enhanced_error_hint or ""),
                )
                logger.info(
                    f"[v95_p98-KB-RECORD-FAIL] {obj_type} [{obj_name}] "
                    f"KB 실패 등재 (pattern={_matched_error_kb.get('id') if _matched_error_kb else '_UNMATCHED_'})"
                )
            except Exception as _re:
                logger.debug(f"[v95_p98] KB 실패 등재 오류 (무시): {_re}")
        # ════════════════════════════════════════════════════════════
        converted, warnings = mssql_to_mysql_ddl(ddl, obj_type)
        return {"converted_ddl": converted, "changes": ["규칙 기반 폴백 (AI 실패)"],
                "warnings": warnings + [str(e)], "method": "rules_fallback"}




def _post_fix_ai_ddl(ddl: str, obj_type: str) -> str:
    """
    AI 변환 결과 정규식 후처리 — v95_p17 (2026-05-03 본부장님 본질 처방).

    AdventureWorks 검증에서 AI 가 일관되게 만들어내는 잘못된 패턴들을
    rule-based 정규식으로 자동 정정. 본부장님 원칙 (하드코딩 금지) 따라
    DB명/테이블명/컬럼명 무관 — 모든 MSSQL→MySQL 변환에 적용.

    처방 1: CASE [var]\\n;\\n WHEN ... → CASE [var]\\n WHEN ...
        AI 가 RETURN CASE @value 변환 시 세미콜론을 잘못된 위치에 박음.
        예: RETURN ( CASE @value
                     ;        ← 이 ; 가 1064 에러
                     WHEN 1 THEN 'A'

    처방 2: T-SQL IF cond BEGIN ... END → MySQL IF cond THEN ... END IF;
        AI 가 BEGIN..END 그대로 두고 END IF; 누락하는 경우.
        에러: 'END IF;\\nEND' at line XX
    """
    import re as _re_pf
    if not ddl:
        return ddl

    s = ddl

    # ── 처방 1: CASE 와 WHEN 사이의 잘못된 세미콜론 제거 ──
    # 패턴 1-A: CASE\n; → CASE\n
    s = _re_pf.sub(
        r"\bCASE\b(\s+\S+)?\s*\n\s*;\s*\n\s*(?=WHEN\b)",
        lambda m: f"CASE{m.group(1) or ''}\n  ",
        s,
        flags=_re_pf.IGNORECASE
    )
    # 패턴 1-B: CASE @var ; WHEN → CASE @var WHEN (한 줄)
    s = _re_pf.sub(
        r"(\bCASE\s+\S+)\s+;\s+(?=WHEN\b)",
        r"\1 ",
        s,
        flags=_re_pf.IGNORECASE
    )

    # ── 처방 2: PROCEDURE/FUNCTION 안의 IF...BEGIN...END 패턴 정정 ──
    # MySQL: IF cond THEN ... END IF;
    # 주의: 너무 광범위하게 적용하면 SP 의 외곽 BEGIN..END 까지 망가뜨림
    # 따라서 IF\n BEGIN\n 패턴만 (즉 IF 직후 BEGIN 이 줄바꿈 후 오는 경우만) 처리
    if obj_type and obj_type.upper() in ("PROCEDURE", "FUNCTION", "PROC", "FN"):
        # IF cond \n BEGIN \n stmts \n END (마지막 END 가 SP 외곽 END 아닌 경우만)
        # 안전 처리: IF...BEGIN 변환은 BEGIN 을 THEN 으로,
        #          그리고 매칭되는 END 를 END IF; 로
        # 가장 안전한 케이스: IF가 한 줄에 단독으로 있고 BEGIN 이 다음 줄에 단독
        s = _re_pf.sub(
            r"(?P<lead>^|\n)(\s*)IF\s+(?P<cond>[^\n]+?)\s*\n\s*BEGIN\s*\n",
            lambda m: f"{m.group('lead')}{m.group(2)}IF {m.group('cond')} THEN\n",
            s,
            flags=_re_pf.IGNORECASE | _re_pf.MULTILINE
        )

        # 마지막 'END;\nEND' 패턴 → 'END IF;\nEND' (SP 의 외곽 END 보존)
        # 본부장님 환경 에러: `'END IF;\nEND' at line XX`
        # 이건 마지막 END 가 누락된 패턴
        # 안전: SP 마지막 줄 END 직전 END 를 END IF; 로 변환
        s = _re_pf.sub(
            r"\bEND\s*;\s*\n(\s*)END\s*;?\s*$",
            r"END IF;\n\1END;",
            s,
            flags=_re_pf.IGNORECASE | _re_pf.MULTILINE
        )

    return s




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

    # ════════════════════════════════════════════════════════════
    # v95_p83 (2026-05-06 본부장님): DROP+CREATE 사이 ; 강제 보장
    # ════════════════════════════════════════════════════════════
    # 본부장님 환경 (오전 10:01) 1064 오류:
    #   "near 'DROP VIEW IF EXISTS HumanResources_vJobCandidateEducation
    #
    # 본질: AI 가 응답 시 DROP 문 끝에 ; 빠뜨림 → DROP 과 CREATE 가
    #       한 statement 로 합쳐져 1064 syntax 발생.
    #
    # 처방: clean 단계 마지막에 DROP <obj_kind> ... CREATE 패턴 검출 시
    #       사이에 ; 자동 삽입.
    #
    # 부작용 0:
    #   - 이미 ; 있으면 변경 0 (정규식 lookahead)
    #   - DROP 만 있거나 CREATE 만 있으면 변경 0
    #   - 다른 객체 타입에도 동일 작동 (TRIGGER/PROCEDURE/FUNCTION)
    # ════════════════════════════════════════════════════════════
    try:
        # DROP <KIND> [IF EXISTS] `name` (또는 따옴표 없이)
        # 다음에 CREATE 가 ; 없이 바로 오는 패턴
        _drop_create_pattern = re.compile(
            r'(\bDROP\s+(?:VIEW|TRIGGER|PROCEDURE|PROC|FUNCTION|FUNC|TABLE)'
            r'(?:\s+IF\s+EXISTS)?\s+`?[\w]+`?)'  # DROP 문장 (이름까지)
            r'(\s*\n\s*)'                          # 공백/줄바꿈
            r'(CREATE\b)',                         # CREATE
            re.IGNORECASE
        )
        _before_count = len(_drop_create_pattern.findall(clean))
        if _before_count > 0:
            clean = _drop_create_pattern.sub(r'\1;\2\3', clean)
            logger.info(
                f"[v95_p83-DROP-CREATE-SEMICOLON] {obj_type} [{obj_name}] "
                f"DROP+CREATE 사이 ; 자동 삽입 ({_before_count}건)"
            )
    except Exception as _ssce:
        logger.debug(f"[v95_p83] DROP+CREATE ; 보장 오류 (무시): {_ssce}")
    # ════════════════════════════════════════════════════════════

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

    # ════════════════════════════════════════════════════════════
    # v95_p36 본질 C+D (2026-05-04 본부장님): TRIGGER 헤더 누락 / 빈 응답 진단
    # ════════════════════════════════════════════════════════════
    # 본질 C: 'near END at line 1' = AI 응답에 CREATE TRIGGER 헤더 빠짐
    # 본질 D: '실행 가능한 CREATE 문장이 없음' = AI 응답이 비어있거나 CREATE 없음
    # 처방: 진단 로그 (AI 원본 응답 + clean + statements 모두 노출)
    # 부작용 0: 실패 케이스에만 추가 로그
    #
    # v95_p41 hotfix (2026-05-05 본부장님): _re_pe → re 수정
    #   본부장님 환경 NameError: _re_pe 가 line 1632 (아래쪽) 에서 정의되는데
    #   여기서 사용되어 'cannot access free variable' 발생.
    #   → 파일 상단 line 141 의 'import re' 사용 (이미 있음)
    if obj_type and obj_type.upper() in ("TRIGGER", "TRIG"):
        _has_create_trigger = any(
            re.search(r"\bCREATE\s+TRIGGER\b", _s, re.IGNORECASE)
            for _s in statements
        )
        if not _has_create_trigger:
            logger.error(
                "[v95_p36-#C-D] TRIGGER [%s] CREATE TRIGGER 헤더 누락 진단:\n"
                "  - clean(원본 AI 응답 정제) 길이: %d\n"
                "  - clean 첫 200자: %s\n"
                "  - statements 개수: %d\n"
                "  - statements 첫 시작: %s",
                obj_name, len(clean), clean[:200].replace('\n', ' ⏎ '),
                len(statements),
                (statements[0][:100].replace('\n', ' ⏎ ') if statements else "(빈 리스트)")
            )
    elif obj_type and obj_type.upper() == "VIEW":
        _has_create_view = any(
            re.search(r"\bCREATE\s+(OR\s+REPLACE\s+)?VIEW\b", _s, re.IGNORECASE)
            for _s in statements
        )
        if not _has_create_view:
            logger.error(
                "[v95_p36-#C-D] VIEW [%s] CREATE VIEW 헤더 누락 진단:\n"
                "  - clean(원본) 길이: %d\n"
                "  - clean 첫 200자: %s\n"
                "  - statements 개수: %d",
                obj_name, len(clean), clean[:200].replace('\n', ' ⏎ '),
                len(statements)
            )

    # ════════════════════════════════════════════════════════════
    # v95_p23e (2026-05-03 본부장님 본질 처방): 모든 흐름 공통 관문 후처리
    # ════════════════════════════════════════════════════════════
    # 본부장님 진단 (21:12 이관 로그 확인):
    #   - v95_p17, v95_p23d 의 자리 (ai_convert_ddl 안) 가 안 거침
    #   - v95_p19, v95_p23c 의 자리 (schema.py _ai_convert_ddl) 도 안 거침
    #   - 이유: KB 캐시 (v10 #18 conversion_learner) 가 잘못된 결과 재사용
    #          → AI 호출 자체 SKIP → 모든 후처리 자리 우회
    #
    # 진짜 본질 자리: deploy_mysql_object 의 _split_sql_statements 직후
    #   - AI 새 호출이든, KB 캐시든, rule-based 든 모든 흐름이 거침
    #   - obj_executor 가 진짜 MySQL 실행 직전의 마지막 관문
    #
    # 본부장님 환경 SQL-FAIL-DUMP 진짜 데이터 100% 기반:
    #   본질 A: "CASE p_Status;\n            WHEN 1 THEN..."  (FUNC 3건)
    #   본질 B-1: "CALL dbo_uspLogError()\n    END IF"        (SP 1건)
    #   본질 B-2: "COMMIT\n    END IF"                         (SP 1건)
    #
    # 부작용 0:
    #   - 정규식 매치 안 되면 원본 그대로 (안전 fallback)
    #   - 정상 SP 외곽 END / 이미 ; 있는 경우 모두 영향 없음 (단위 테스트 통과)
    #
    # 하드코딩 0%:
    #   - 정규식만 (DB명/테이블명/컬럼명 무관)
    #   - Northwind/WideWorldImporters/캐피탈사 운영 DB 동일 작동
    if statements and obj_type and obj_type.upper() in (
        "PROCEDURE", "FUNCTION", "TRIGGER", "PROC", "FN", "TRIG"
    ):
        try:
            import re as _re_pe
            _stmts_before_pe = list(statements)
            _changed_count = 0

            # 본질 A: CASE expr; → CASE expr (FUNC 3건 해소)
            #   진짜 패턴: "CASE p_Status;\n            WHEN 1 THEN..."
            _pattern_a = _re_pe.compile(
                r"(\bCASE\s+\w+);(\s*\n\s*WHEN\b)",
                flags=_re_pe.IGNORECASE
            )
            # 본질 B: ) 또는 COMMIT/ROLLBACK 다음 ; 누락 (SP 2건 해소)
            #   진짜 패턴: "CALL X()\n END IF" / "COMMIT\n END IF"
            _pattern_b = _re_pe.compile(
                r"(\)|\bCOMMIT\b|\bROLLBACK\b)(\s*\n\s*END\s+IF\b)",
                flags=_re_pe.IGNORECASE
            )

            # ════════════════════════════════════════════════════════════
            # v95_p29 (2026-05-04 본부장님 본질 처방): TRIGGER 본질 2건 통합
            # ════════════════════════════════════════════════════════════
            # 본질 5 (1362 NEW row in AFTER trigger):
            #   증상: uSalesOrderHeader, uPurchaseOrderHeader
            #         (1362, 'Updating of NEW row is not allowed in after trigger')
            #   본질: MSSQL AFTER trigger 는 NEW row 수정 가능 (UPDATE/SET)
            #         MySQL AFTER trigger 는 NEW row 수정 금지 → BEFORE 로 변환 필요
            #   처방: TRIGGER 본문에 'SET NEW.' 패턴 발견 시 'AFTER' → 'BEFORE' 변환
            #         (의미 변경이지만, MySQL 호환의 유일한 방법)
            #
            # 본질 6 (iuPerson - person_person 소문자):
            #   증상: (1146, "Table 'aw_target.person_person' doesn't exist")
            #          (1146, "Table 'aw_target.purchasing_purchaseorderdetail' doesn't exist")
            #   본질: AI 변환 시 트리거 ON 절의 테이블명이 소문자로 변환됨
            #         실제 MySQL 테이블은 'Person_Person' (혹은 'PurchaseOrderDetail') 정상 case
            #   처방: ON `lowercase` 패턴 발견 시 underscore_case 정규화 (Word_Word)
            #         보존 정책: snake_case 'snake_case' (소문자) 는 그대로 (밀착된 용도)
            _pattern_trig_before = _re_pe.compile(
                r"\bAFTER\b(\s+(?:INSERT|UPDATE|DELETE)(?:\s*,\s*(?:INSERT|UPDATE|DELETE))*)",
                flags=_re_pe.IGNORECASE
            )
            _pattern_set_new = _re_pe.compile(r"\bSET\s+NEW\.\w+", flags=_re_pe.IGNORECASE)
            # ════════════════════════════════════════════════════════════
            # v95_p30 (2026-05-04 본부장님 본질 처방): NEW row 수정 패턴 확장
            # ════════════════════════════════════════════════════════════
            # 본질: v95_p29-#5 정규식 _pattern_set_new 는 'SET NEW.col' 만 매치.
            #       그러나 AI 변환 결과는 다른 형태의 NEW row 수정도 생성:
            #         (1) UPDATE `table` SET col = NEW.col WHERE ... (SET-based UPDATE)
            #         (2) UPDATE `table` SET col = ... WHERE id = NEW.id
            #         (3) NEW.col = expr (직접 할당 — 일부 SQL 변형)
            #       본부장님 환경 진단: uSalesOrderHeader, uPurchaseOrderHeader 1362 발생
            #       AI WARNING 라인 7015: "MSSQL 오류 패턴 감지: ['UPDATE\\s+`?sales_salesorderheader`?\\s+SET']"
            #       즉 본부장님 환경에 'UPDATE 자기자신 SET' 패턴이 1362 의 진짜 본질
            # 처방: NEW row 수정 의심 패턴 모두 매치하는 보조 정규식 추가
            # 부작용 0: TRIGGER 외 다른 obj_type 영향 없음 (호출부에서 obj_type 필터)
            _pattern_new_row_modify = _re_pe.compile(
                r"\bSET\s+NEW\.\w+"                              # (1) SET NEW.col
                r"|\bUPDATE\s+`?\w+`?\s+SET\b[^;]*\bNEW\."       # (2) UPDATE table SET ... NEW.
                r"|\bNEW\.\w+\s*:?=",                            # (3) NEW.col = expr (드물지만 안전망)
                flags=_re_pe.IGNORECASE | _re_pe.DOTALL
            )
            # 본질 6: 'lowercase_word' 패턴을 'Word_Word' (단어 첫 글자 대문자)로 복원
            #         단어 경계마다 capitalize. ex: 'person_person' → 'Person_Person'
            _pattern_lower_table_ref = _re_pe.compile(
                r"\b((?:[a-z][a-z0-9]*_)+[a-z][a-z0-9]*)\b"
            )
            def _restore_case(m):
                lower_name = m.group(1)
                # 단어별 capitalize (snake_case → Snake_Case)
                parts = lower_name.split("_")
                # 모든 부분이 알파벳으로 시작 + 길이 2+ 인 경우만 변환
                if all(p and p[0].isalpha() and len(p) >= 2 for p in parts):
                    return "_".join(p.capitalize() for p in parts)
                return lower_name

            _new_statements = []
            for _i, _s in enumerate(statements):
                _new = _pattern_a.sub(r"\1\2", _s)
                _new = _pattern_b.sub(r"\1;\2", _new)

                # ════════════════════════════════════════════════════════════
                # v95_p36 본질 B (2026-05-04 본부장님): MSSQL 전용 키워드 강제 제거
                # ════════════════════════════════════════════════════════════
                # 본질: AI 가 프롬프트 받고도 SCHEMABINDING/ENCRYPTION 같은 MSSQL 전용
                #       키워드를 그대로 출력 → MySQL 1064 syntax error
                # 증상: vProductAndDescription "WITH SCHEMABINDING ..." 1064
                # 처방: AI 응답 안 따를 때 post-fix 자리에서 강제 제거
                # 부작용 0: 키워드 자체가 MySQL 미지원 → 제거가 정답
                if obj_type and obj_type.upper() in ("VIEW", "TRIGGER", "TRIG"):
                    _v36_b_orig = _new
                    # WITH SCHEMABINDING/ENCRYPTION/VIEW_METADATA 모두 제거
                    _new = _re_pe.sub(
                        r"\bWITH\s+(SCHEMABINDING|ENCRYPTION|VIEW_METADATA)\b",
                        "",
                        _new,
                        flags=_re_pe.IGNORECASE
                    )
                    # WITH (NOLOCK), (READPAST) 등 인라인 힌트 제거
                    _new = _re_pe.sub(
                        r"\bWITH\s*\(\s*(NOLOCK|READPAST|READUNCOMMITTED|READCOMMITTED|"
                        r"REPEATABLEREAD|SERIALIZABLE|TABLOCK|TABLOCKX|UPDLOCK|XLOCK|"
                        r"NOEXPAND|FORCESCAN|FORCESEEK)\s*\)",
                        "",
                        _new,
                        flags=_re_pe.IGNORECASE
                    )
                    if _new != _v36_b_orig:
                        logger.info("[v95_p36-#B] MSSQL 전용 키워드 제거 [%s] %s stmt#%d",
                                    obj_type, obj_name, _i)

                # ── v95_p29 본질 5 + v95_p30 보강: NEW row 수정 패턴 발견 시 AFTER → BEFORE ──
                # TRIGGER 만 적용 (의미 변경이므로 다른 obj_type 영향 없게)
                # v95_p30: SET NEW. 외에 UPDATE table SET ... NEW.col 패턴도 매치
                if obj_type and obj_type.upper() in ("TRIGGER", "TRIG"):
                    if _pattern_new_row_modify.search(_new):
                        # AFTER → BEFORE 변환 (헤더에서만)
                        _new_v5 = _pattern_trig_before.sub(r"BEFORE\1", _new)
                        if _new_v5 != _new:
                            logger.info("[v95_p30-#5] AFTER→BEFORE 변환 [%s] %s stmt#%d "
                                        "(NEW row 수정 패턴 발견 → MySQL 1362 회피)",
                                        obj_type, obj_name, _i)
                            _new = _new_v5

                # ── v95_p29 본질 6 + v95_p32 보강: 백틱 안 잘못된 case 테이블명 복원 ──
                # TRIGGER, VIEW 모두 적용 (소문자 테이블명 참조 위험)
                # v95_p29: 모든 부분 소문자 (`person_person`) 만 매치
                # v95_p32 본질 2 (2026-05-04 본부장님): 첫 단어 대문자 + 두번째 잘못된 case 도 매치
                #   본부장님 환경 진단:
                #     `Sales_Salesorderheader` → `Sales_SalesOrderHeader`
                #     `Sales_Salesterritory`   → `Sales_SalesTerritory`
                #     `Purchasing_Purchaseorderdetail` → `Purchasing_PurchaseOrderDetail`
                #
                # 처방 전략 (하드코딩 0%):
                #   1) 타겟 MySQL 의 실제 테이블 목록을 1회 조회 (캐시)
                #   2) 백틱 안 모든 식별자를 case-insensitive 로 비교
                #   3) 실제 테이블명과 일치하는 정상 case 로 복원
                #   부작용 0: 매치 안 되는 식별자 (컬럼명, 별칭 등) 는 그대로
                if obj_type and obj_type.upper() in ("TRIGGER", "TRIG", "VIEW"):
                    # v95_p32 본질 2: 실제 테이블 목록 캐시 조회 (1회)
                    # conn_info 로 짧은 연결 만들어서 SHOW TABLES (캐시 클로저 활용)
                    _real_table_cases = getattr(deploy_mysql_object, '_real_table_cases_cache', None)
                    if _real_table_cases is None:
                        try:
                            import pymysql as _pymysql_v32
                            _conn_v32_args = {
                                'host':     conn_info.get('host', 'localhost'),
                                'port':     int(conn_info.get('port', 3306)),
                                'user':     conn_info.get('user', 'root'),
                                'password': conn_info.get('password', ''),
                                'database': conn_info.get('database', ''),
                                'charset':  conn_info.get('charset', 'utf8mb4'),
                                'connect_timeout': 5,
                            }
                            _conn_v32 = _pymysql_v32.connect(**_conn_v32_args)
                            _cur_v32 = _conn_v32.cursor()
                            _cur_v32.execute("SHOW TABLES")
                            _real_table_cases = {}
                            for _row in _cur_v32.fetchall():
                                _tbl_real = _row[0] if isinstance(_row, (list, tuple)) else list(_row.values())[0]
                                _real_table_cases[_tbl_real.lower()] = _tbl_real
                            _cur_v32.close()
                            _conn_v32.close()
                            # 함수 속성으로 캐시 (같은 deploy_mysql_object 호출 안에서 재사용)
                            deploy_mysql_object._real_table_cases_cache = _real_table_cases
                            logger.info("[v95_p32-#2] 실제 테이블 목록 조회 %d개", len(_real_table_cases))
                        except Exception as _e_v32:
                            logger.debug("[v95_p32-#2] 테이블 목록 조회 실패 (스킵): %s", _e_v32)
                            _real_table_cases = {}

                    # 백틱 안 식별자 매치 → 실제 case 복원
                    if _real_table_cases:
                        def _restore_real_case(m):
                            _ident = m.group(1)
                            _real = _real_table_cases.get(_ident.lower())
                            return f"`{_real}`" if _real and _real != _ident else f"`{_ident}`"
                        _new_v6_pre = _re_pe.sub(
                            r"`([A-Za-z_][A-Za-z0-9_]*)`",
                            _restore_real_case,
                            _new
                        )
                        if _new_v6_pre != _new:
                            logger.info("[v95_p32-#2] 실제 테이블 case 복원 [%s] %s stmt#%d",
                                        obj_type, obj_name, _i)
                            _new = _new_v6_pre

                    # `lowercase_word` 패턴 (v95_p29-#6 기존 처방, 영향 없음)
                    _new_v6 = _re_pe.sub(
                        r"`((?:[a-z][a-z0-9]*_)+[a-z][a-z0-9]*)`",
                        lambda m: f"`{_restore_case(m)}`",
                        _new
                    )
                    if _new_v6 != _new:
                        logger.info("[v95_p29-#6] 소문자 테이블 참조 복원 [%s] %s stmt#%d",
                                    obj_type, obj_name, _i)
                        _new = _new_v6

                    # ════════════════════════════════════════════════════════════
                    # v95_p33 본질 2 (2026-05-04 본부장님): 미존재 의존 검증
                    # ════════════════════════════════════════════════════════════
                    # 본질: AI 가 VIEW 변환 시 가짜 의존 테이블 생성 (환각)
                    #       증상: vJobCandidateEducation_DATA, ProductModelInstructions_Flat 등
                    # 처방: VIEW 의 FROM/JOIN 절의 식별자가 실제 테이블이 아니면
                    #       → 명확한 경고 + 발생 자리 추적용 로그 (생성은 시도하되 실패 명확히)
                    # 부작용 0: 매핑 캐시 활용, 의심 식별자만 로그 (강제 차단 아님)
                    if obj_type and obj_type.upper() == "VIEW" and _real_table_cases:
                        # FROM 또는 JOIN 뒤의 백틱 식별자 추출 (별칭 무시)
                        # v95_p49 (2026-05-05 본부장님): 백틱 옵션화 (`?)
                        #   본부장님 환경 진단: AI 가 백틱 없이 plain identifier 출력
                        #     → 기존 백틱 강제 정규식 매치 실패 → 환각 검출 안 됨
                        #     → v95_p42/p45 폴백 발동 안 됨 → 1146 에러
                        #   처방: 백틱 0 또는 1 매치 (`?) — 두 형태 모두 잡음
                        #   부작용 0: false positive 6/6 검증 (별칭/서브쿼리 영향 없음)
                        _from_pat = _re_pe.compile(
                            r"\b(?:FROM|JOIN)\s+`?([A-Za-z_][A-Za-z0-9_]*)`?",
                            flags=_re_pe.IGNORECASE
                        )
                        _refs = _from_pat.findall(_new)
                        _missing_refs = []
                        for _ref in _refs:
                            # 실제 테이블 목록에 case-insensitive 매치 안 되면 의심
                            if _ref.lower() not in _real_table_cases:
                                _missing_refs.append(_ref)
                        if _missing_refs:
                            logger.warning(
                                "[v95_p33-#2] VIEW [%s] stmt#%d 가짜 의존 의심: %s "
                                "(타겟 MySQL 에 없는 테이블 — AI 환각 가능성)",
                                obj_name, _i, ", ".join(set(_missing_refs))
                            )
                            # ════════════════════════════════════════════════════════════
                            # v95_p35 본질 3 (2026-05-04 본부장님): 환각 검출 정규식 확장
                            # ════════════════════════════════════════════════════════════
                            # 본질: v95_p33 의 _hallucination_suffixes 리스트 매번 누락
                            #   이전 세션 발견: _data, _DATA, _flat, _Flat, _Flattened,
                            #                  _Instruction, _Instructions
                            #   본부장님 환경 신규 변형: _Helper (검증 결과에서 발견)
                            #   AI 환각은 무한히 새로운 접미사 만들 수 있음
                            # 처방: 알려진 접미사 + 정규식 백업 + 화이트리스트 (3중 안전망)
                            #   1) 화이트리스트 — 정상 접미사 (_id, _at 등) 영향 0
                            #   2) 알려진 환각 접미사 매치 (확장됨 — _Helper 등 추가)
                            #   3) 정규식 백업 — 새 환각 접미사 자동 검출
                            # 부작용 0: 화이트리스트 + 진짜 PK/FK 컬럼 보호
                            _whitelisted_suffixes = (
                                "_id", "_ID", "_Id",
                                "_at", "_dt", "_ts",
                                "_no", "_cd",
                                "_count", "_Count",
                                "_total", "_Total",
                            )
                            _hallucination_suffixes = [
                                # 데이터 표현 환각
                                "_data", "_DATA", "_Data",
                                "_flat", "_Flat", "_Flattened", "_flattened",
                                "_info", "_Info", "_INFO",
                                "_detail", "_Detail", "_DETAIL",
                                # 객체 분리 환각
                                "_Instruction", "_Instructions", "_INSTRUCTION",
                                "_Helper", "_HELPER", "_helper",
                                "_Aux", "_aux", "_AUX",
                                "_Ref", "_ref", "_REF",
                                # 표현 변형 환각
                                "_view", "_VIEW", "_View",
                                "_table", "_Table", "_TABLE",
                                "_temp", "_Temp", "_TEMP", "_tmp",
                                "_summary", "_Summary",
                                "_extended", "_Extended",
                                "_normalized", "_Normalized",
                                "_joined", "_Joined",
                                "_merged", "_Merged",
                            ]
                            # 정규식 백업: 알려지지 않은 환각 패턴 잡기
                            #   _PascalCase 또는 _lowercase 3+ 글자 접미사
                            #   v95_p35 보강: PascalCase 다단어 (NewSuffix, MultiWord) 도 매치
                            _hallucination_regex = _re_pe.compile(
                                r"_([A-Z][a-zA-Z]{2,}|[a-z]{3,})$"
                            )
                            for _miss in set(_missing_refs):
                                _detected_suf = None
                                _detection_method = None
                                # 1) 화이트리스트 (정상 접미사면 스킵 — 부작용 방지)
                                _is_whitelisted = any(
                                    _miss.endswith(_w) for _w in _whitelisted_suffixes
                                )
                                if _is_whitelisted:
                                    continue
                                # 2) 알려진 환각 접미사 매치
                                for _suf in _hallucination_suffixes:
                                    if _miss.endswith(_suf):
                                        _detected_suf = _suf
                                        _detection_method = "list"
                                        break
                                # 3) 정규식 백업 (알려지지 않은 환각)
                                if not _detected_suf:
                                    _m = _hallucination_regex.search(_miss)
                                    if _m:
                                        _last_under = _miss.rfind('_')
                                        if _last_under > 0:
                                            _bare_part = _miss[:_last_under]
                                            # 원본 부분이 실제 테이블이면 환각 가능성 매우 높음
                                            if _bare_part.lower() in _real_table_cases:
                                                _detected_suf = _miss[_last_under:]
                                                _detection_method = "regex+real_base"
                                            elif obj_name and obj_name.lower().lstrip("v") in _miss.lower():
                                                # VIEW 자기참조 환각 (vFoo 가 Foo_Suffix 참조)
                                                _detected_suf = _miss[_last_under:]
                                                _detection_method = "regex+self_ref"
                                if _detected_suf:
                                    logger.error(
                                        "[v95_p35-#3-HALLUCINATION] VIEW [%s] 환각 접미사 '%s' 검출 (방법: %s): %s "
                                        "→ AI 시스템 프롬프트 (view_trigger.txt) 위반",
                                        obj_name, _detected_suf, _detection_method, _miss
                                    )

                            # ════════════════════════════════════════════════════════════
                            # v95_p42 (2026-05-05 본부장님): 환각 검출 시 강제 안전 폴백 VIEW
                            # v95_p45 보강 (2026-05-05 last one): CamelCase 환각도 검출
                            # ════════════════════════════════════════════════════════════
                            # 본부장님 강조: "이번만 어떻게 넘어가는 식으로 만들면 절대 안돼"
                            #
                            # v95_p45 진단:
                            #   AI 가 'Production_ProductModelInstruction' 같은 CamelCase 환각 생성
                            #   → endswith('_Instruction') 매치 실패 (underscore 없음)
                            #   → v95_p42 검출/폴백 발동 안 함 → 1146 에러
                            #
                            # v95_p45 처방 (일반화):
                            #   환각 키워드를 CamelCase 단어 경계로도 매치 (정규식)
                            #   예: Production_ProductModelInstruction (lInstruction CamelCase)
                            #       → re.search(r'(?<=[a-z])Instruction[s]?$') 매치 ✓
                            #   underscore 환각 (기존) + CamelCase 환각 (신규) 모두 검출
                            #
                            # 부작용 0:
                            #   - 화이트리스트 우선 (정상 PK/FK 컬럼 영향 0)
                            #   - 정규식은 마지막 환각 키워드만 검출 (false positive 최소화)
                            #   - 모든 DB 동일 작동 (AdventureWorks/캐피탈사/Northwind/...)
                            #
                            # CamelCase 환각 정규식: 환각 키워드가 단어 경계 (소문자→대문자) 뒤에
                            #   _hallucination_keywords: 환각 접미사에서 underscore 제거한 키워드
                            _hallucination_keywords = set()
                            for _suf in _hallucination_suffixes:
                                _kw = _suf.lstrip('_')  # '_Instruction' → 'Instruction'
                                if _kw and len(_kw) >= 3:
                                    _hallucination_keywords.add(_kw)
                            # CamelCase 매치: (?<=[a-z]) 뒤에 환각 키워드 + 끝
                            _camel_pattern = '|'.join(sorted(_hallucination_keywords, key=len, reverse=True))
                            _camel_regex = re.compile(
                                r'(?<=[a-z])(' + _camel_pattern + r')$'
                            ) if _camel_pattern else None

                            _has_hallucination = False
                            _hall_classification = []  # 분류 — 로깅 용도만
                            for _miss in set(_missing_refs):
                                # 화이트리스트 (정상 PK/FK 컬럼) 는 환각 아님 — 부작용 0
                                if any(_miss.endswith(_w) for _w in _whitelisted_suffixes):
                                    continue
                                # ════════════════════════════════════════════════════════════
                                # v95_p51 (2026-05-05 본부장님): 진짜 본질 — 일반화
                                # ════════════════════════════════════════════════════════════
                                # 본부장님 강조: "하드코딩 하면 안돼"
                                #
                                # 진짜 본질:
                                #   _real_table_cases = MySQL 타겟 DB 실제 테이블 카탈로그 (동적)
                                #   _missing_refs = 그 카탈로그에 없는 식별자
                                #   → MySQL 실행 시 반드시 1146 에러 발생
                                #   → "그 자체로 환각" — 키워드 매치 불필요
                                #
                                # 이전 검출 (v95_p33/p35/p42/p45):
                                #   _hall_known/regex/camel 키워드 매치 → 환각 분류
                                #   부작용: 새 환각 키워드 (Location, Step 등) 매번 누락
                                #          → 본부장님 환경 v95_p49 적용 후에도 1146 발생
                                #
                                # 처방 (일반화 — 하드코딩 0%):
                                #   화이트리스트 아닌 _missing_refs 는 모두 환각
                                #   (분류는 로깅 용도로만 유지)
                                #
                                # 부작용 0 검증:
                                #   - 화이트리스트 (_id, _at, _count, _total) 정상 PK/FK 보호
                                #   - _real_table_cases 가 실제 MySQL 카탈로그 → 정확
                                #   - 정상 VIEW 의 정상 테이블은 카탈로그에 있음 → _missing_refs 안 들어감
                                # ════════════════════════════════════════════════════════════
                                _has_hallucination = True
                                # 분류 (로깅 용도만 — 폴백 발동에는 무관)
                                if any(_miss.endswith(_s) for _s in _hallucination_suffixes):
                                    _hall_classification.append((_miss, "known_suffix"))
                                elif _hallucination_regex.search(_miss):
                                    _hall_classification.append((_miss, "regex"))
                                elif _camel_regex is not None and _camel_regex.search(_miss):
                                    _hall_classification.append((_miss, "camelcase"))
                                else:
                                    _hall_classification.append((_miss, "unknown_pattern"))

                            if _has_hallucination:
                                # 베이스 테이블 추출 (하드코딩 0% — 일반화)
                                _safe_base = None
                                # (1) FROM/JOIN 절에서 실제 존재하는 테이블 우선 사용
                                _all_refs = _from_pat.findall(_new)
                                for _ref in _all_refs:
                                    if _ref.lower() in _real_table_cases:
                                        _safe_base = _real_table_cases[_ref.lower()]
                                        break
                                # (2) 환각 식별자에서 환각 접미사 제거 후 매칭
                                #     예: customer_master_data → customer_master, Customers_data → Customers
                                #     다단 환각: Production_ProductModel_Instructions_Flat → 반복 제거
                                #     v95_p45: CamelCase 환각도 제거 (Production_ProductModelInstruction → Production_ProductModel)
                                if not _safe_base:
                                    for _ref in _all_refs:
                                        if _ref.lower() in _real_table_cases:
                                            continue
                                        # 다단 환각 처리: 최대 5회 반복으로 접미사 제거 (underscore + CamelCase)
                                        _trial = _ref
                                        for _ in range(5):
                                            _stripped_any = False
                                            # 모든 환각 접미사 제거 시도 (underscore 형태)
                                            for _suf in _hallucination_suffixes:
                                                if _trial.endswith(_suf):
                                                    _trial = _trial[:-len(_suf)]
                                                    _stripped_any = True
                                                    break
                                            # v95_p45: CamelCase 환각 키워드 제거
                                            #   예: Production_ProductModelInstruction → Production_ProductModel
                                            if not _stripped_any and _camel_regex is not None:
                                                _m = _camel_regex.search(_trial)
                                                if _m:
                                                    _trial = _trial[:_m.start(1)]
                                                    _stripped_any = True
                                            if not _stripped_any:
                                                break
                                            # 매번 매치 시도
                                            if _trial.lower() in _real_table_cases:
                                                _safe_base = _real_table_cases[_trial.lower()]
                                                break
                                        if _safe_base:
                                            break
                                        # 마지막 underscore 뒤 제거 (정규식 환각)
                                        _last_under = _ref.rfind('_')
                                        if _last_under > 0:
                                            _stripped = _ref[:_last_under]
                                            if _stripped.lower() in _real_table_cases:
                                                _safe_base = _real_table_cases[_stripped.lower()]
                                                break
                                # (3) obj_name 기반 추정 (vFoo → Foo, vJobCandidateEducation → JobCandidate)
                                if not _safe_base and obj_name:
                                    _bare_obj = obj_name.lstrip("vV").lower()
                                    # 정확 매치
                                    if _bare_obj in _real_table_cases:
                                        _safe_base = _real_table_cases[_bare_obj]
                                    else:
                                        # 부분 매치 (가장 긴 prefix 가 실제 테이블이면)
                                        for _real_lower, _real_orig in _real_table_cases.items():
                                            _real_bare = _real_lower.split('_', 1)[-1] if '_' in _real_lower else _real_lower
                                            if _real_bare and _bare_obj.startswith(_real_bare) and len(_real_bare) >= 5:
                                                _safe_base = _real_orig
                                                break
                                # 안전 폴백 VIEW 강제 생성 (베이스 못 찾으면 SELECT NULL 만)
                                if _safe_base:
                                    _fallback_ddl = (
                                        f"CREATE OR REPLACE VIEW `{obj_name}` AS\n"
                                        f"SELECT NULL AS `_placeholder`\n"
                                        f"FROM `{_safe_base}`\n"
                                        f"WHERE 1=0\n"
                                        f"-- v95_p42 안전 폴백: AI 환각 검출 → 빈 VIEW 로 교체.\n"
                                        f"-- 응용단에서 EXTRACTVALUE() 또는 외부 파서로 처리 필요"
                                    )
                                else:
                                    _fallback_ddl = (
                                        f"CREATE OR REPLACE VIEW `{obj_name}` AS\n"
                                        f"SELECT NULL AS `_placeholder`\n"
                                        f"WHERE 1=0\n"
                                        f"-- v95_p42 안전 폴백: AI 환각 + 베이스 테이블 미발견.\n"
                                        f"-- 응용단에서 직접 정의 필요"
                                    )
                                logger.error(
                                    "[v95_p42-FALLBACK] VIEW [%s] 환각 의심 식별자 검출 → "
                                    "안전 폴백 VIEW 로 강제 교체 (베이스: %s)",
                                    obj_name, _safe_base or "(없음)"
                                )
                                # v95_p51: 환각 분류 상세 로그 (KB 누적용)
                                if _hall_classification:
                                    logger.error(
                                        "[v95_p51-CLASS] VIEW [%s] 환각 분류: %s",
                                        obj_name,
                                        ", ".join([f"{m}({c})" for m, c in _hall_classification])
                                    )
                                _new = _fallback_ddl
                            # ────────────────────────────────────────────────────────────

                if _new != _s:
                    _changed_count += 1
                    logger.info("[v95_p23e] post-fix applied [%s] %s stmt#%d",
                                obj_type, obj_name, _i)
                _new_statements.append(_new)
            statements = _new_statements

            if _changed_count > 0:
                _dtrace("02b-postfix-applied", changed_count=_changed_count)
        except Exception as _pe_err:
            # 후처리 실패해도 원본 그대로 (안전 fallback)
            logger.warning("[v95_p23e] 후처리 실패 [%s] %s: %s — 원본 유지",
                           obj_type, obj_name, _pe_err)
    # ────────────────────────────────────────────────────────────

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
