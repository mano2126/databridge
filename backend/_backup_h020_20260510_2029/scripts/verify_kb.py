#!/usr/bin/env python3
"""
v95_p107 hotfix_014 — 기존 KB 검증 스크립트

본부장님 환경에서 직접 실행:
  python3 scripts/verify_kb.py

기능:
  - data/conversion_patterns.json 의 모든 패턴을 hotfix_014 게이트로 검증
  - 오염 항목 리포트 출력 (어떤 게이트에서 거부됐는지)
  - 자동 삭제 안 함 — 본부장님이 cleanup_kb.py 별도 실행 필요
"""
import json
import os
import re
import sys


def _kb_quality_gate(converted_ddl, src_ddl=""):
    """hotfix_014 게이트 5종 — schema.py 의 _kb_quality_gate_p107 와 동일 로직"""
    body = (converted_ddl or "").strip()
    if not body:
        return False, "변환 결과 비어있음"
    open_p = body.count("(")
    close_p = body.count(")")
    if open_p != close_p:
        return False, f"괄호 불일치 ( {open_p} vs ) {close_p}"
    begins = len(re.findall(r'\bBEGIN\b', body, re.IGNORECASE))
    end_ifs = len(re.findall(r'\bEND\s+IF\b', body, re.IGNORECASE))
    end_loops = len(re.findall(r'\bEND\s+(?:LOOP|WHILE|CASE|REPEAT)\b', body, re.IGNORECASE))
    all_ends = len(re.findall(r'\bEND\b', body, re.IGNORECASE))
    pure_ends = all_ends - end_ifs - end_loops
    if begins > pure_ends:
        return False, f"BEGIN 미종결 (BEGIN={begins} > pure_END={pure_ends})"
    suspicious_patterns = [
        (r'\b\w*(?:Entity|ID|Name|Date|Status|Amount|Count|Value|Price|Rate)\s+NULL\s+(?:AND|OR)\b',
         "컬럼 비교문 잘림 (예: BusinessEntity NULL AND)"),
        (r'\bWHERE\s*$', "WHERE 절로 끝남"),
        (r'=\s*$', "= 로 끝남"),
        (r'\bAND\s*$', "AND 로 끝남"),
        (r'\bOR\s*$', "OR 로 끝남"),
        (r'\bSELECT\s*$', "SELECT 로 끝남"),
        (r'\bFROM\s*$', "FROM 으로 끝남"),
        (r'\bINTO\s+\w+\s*$', "INSERT INTO 다음 누락"),
        (r',\s*\)\s*$', ", 후 ) 로 끝남"),
    ]
    for pat, desc in suspicious_patterns:
        if re.search(pat, body, re.MULTILINE | re.IGNORECASE):
            return False, f"미완성 SQL: {desc}"
    if_exists_blocks = re.findall(r'IF\s+EXISTS\s*\([^)]{40,300}\)', body, re.IGNORECASE)
    seen = set()
    for block in if_exists_blocks:
        if block in seen:
            return False, "동일 IF EXISTS 블록 중복 (재생성 흔적)"
        seen.add(block)
    if src_ddl and len(src_ddl) > 100:
        ratio = len(body) / len(src_ddl)
        if ratio < 0.3:
            return False, f"변환 결과 너무 짧음 (ratio={ratio:.2f}, 원본 대비 30% 미만)"

    # ─── 게이트 7 (hotfix_014_002): MSSQL 잔재 검출 ───
    mssql_remnants = [
        (r'\bSELECT\s+[v_@]\w+\s*=\s*[\w\.]+\s+FROM\b',
         "MSSQL 'SELECT @var = col FROM' 잔재"),
        (r'\bDECLARE\s+@\w+\s+(?:INT|VARCHAR|NVARCHAR|DECIMAL|DATETIME|MONEY|BIT|BIGINT)',
         "MSSQL DECLARE @var 타입선언 잔재"),
        (r'\bSET\s+@\w+\s*=', "MSSQL SET @var 잔재"),
        (r"\bOBJECT_ID\s*\(\s*N?'\[", "MSSQL OBJECT_ID 잔재"),
        (r'\[(?:dbo|HumanResources|Sales|Person|Production|Purchasing)\]\.\[',
         "MSSQL [schema].[obj] 잔재"),
        (r"\bN'[^']{2,}'", "MSSQL N'string' 유니코드 리터럴"),
        (r"\bCONVERT\s*\(\s*(?:datetime|nvarchar|varchar|int)\s*,", "MSSQL CONVERT() 잔재"),
        (r'\bISNULL\s*\(', "MSSQL ISNULL() 잔재 (MySQL: IFNULL)"),
        (r'\bIF\s+OBJECT_ID\b', "MSSQL IF OBJECT_ID 트리거 헤더 잔재"),
        (r'\bGETDATE\s*\(\s*\)', "MSSQL GETDATE() 잔재 (MySQL: NOW())"),
    ]
    for pat, desc in mssql_remnants:
        if re.search(pat, body, re.IGNORECASE):
            return False, f"MSSQL 잔재: {desc}"

    return True, "OK"


def main():
    # 스크립트 위치 기준으로 KB 경로 자동 탐색
    here = os.path.abspath(os.path.dirname(__file__))
    candidates = [
        os.path.join(here, "..", "data", "conversion_patterns.json"),
        os.path.expanduser("~/project/databridge_full/data/conversion_patterns.json"),
        "/Users/choimanho/project/databridge_full/data/conversion_patterns.json",
    ]
    kb_path = None
    for c in candidates:
        if os.path.exists(c):
            kb_path = os.path.abspath(c)
            break

    if not kb_path:
        print("❌ KB 파일을 찾지 못했습니다.")
        print(f"   탐색한 경로:")
        for c in candidates:
            print(f"     - {c}")
        sys.exit(1)

    print(f"📂 KB 파일: {kb_path}")
    with open(kb_path, encoding="utf-8") as f:
        kb = json.load(f)

    patterns = kb.get("patterns", [])
    print(f"📊 총 패턴 수: {len(patterns)}건")
    print()
    print("=" * 75)

    ok_list = []
    ng_list = []
    for p in patterns:
        tgt = p.get("tgt_sample_ddl", "")
        src = p.get("src_sample_ddl", "")
        safe, reason = _kb_quality_gate(tgt, src)
        if safe:
            ok_list.append(p)
        else:
            ng_list.append((p, reason))

    print(f"✅ 정상 (KB 유지 권장): {len(ok_list)}건")
    print(f"🔴 오염 (KB 제거 권장): {len(ng_list)}건")

    if ng_list:
        print()
        print("=" * 75)
        print("🔴 오염 항목 상세:")
        print("=" * 75)
        for p, reason in ng_list:
            print(f"  - {p.get('obj_type', '?')} [{p.get('obj_name_sample', '?')}]")
            print(f"      id: {p.get('id', '?')}")
            print(f"      use_count: {p.get('use_count', 0)}")
            print(f"      거부 사유: {reason}")
            print()

    print("=" * 75)
    print("다음 단계:")
    if ng_list:
        print(f"  - 오염 {len(ng_list)}건 제거하려면: python3 scripts/cleanup_kb.py")
        print("  - (백업 자동 생성됨)")
    else:
        print("  - 오염 항목 없음. KB 깨끗합니다 ✨")
    print("=" * 75)


if __name__ == "__main__":
    main()
