#!/usr/bin/env python3
"""
v95_p107 hotfix_014 — 기존 오염 KB 청소 스크립트

본부장님 환경에서 직접 실행:
  python3 scripts/cleanup_kb.py

기능:
  - 실행 전 KB 파일 자동 백업 (timestamp 포함)
  - hotfix_014 게이트로 검증해서 오염 항목 제거
  - 청소 결과 리포트 출력

안전:
  - 원본은 백업 후 보존 (data/conversion_patterns.json.bak_YYYYMMDD_HHMM)
  - 청소된 결과를 새 파일로 저장
  - 게이트 통과한 정상 항목만 유지
"""
import json
import os
import re
import shutil
import sys
from datetime import datetime


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
         "컬럼 비교문 잘림"),
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
            return False, "동일 IF EXISTS 블록 중복"
        seen.add(block)
    if src_ddl and len(src_ddl) > 100:
        ratio = len(body) / len(src_ddl)
        if ratio < 0.3:
            return False, f"변환 결과 너무 짧음 (ratio={ratio:.2f})"

    # ─── 게이트 7 (hotfix_014_002): MSSQL 잔재 검출 ───
    mssql_remnants = [
        (r'\bSELECT\s+[v_@]\w+\s*=\s*[\w\.]+\s+FROM\b',
         "MSSQL 'SELECT @var = col FROM' 잔재"),
        (r'\bDECLARE\s+@\w+\s+(?:INT|VARCHAR|NVARCHAR|DECIMAL|DATETIME|MONEY|BIT|BIGINT)',
         "MSSQL DECLARE @var 잔재"),
        (r'\bSET\s+@\w+\s*=', "MSSQL SET @var 잔재"),
        (r"\bOBJECT_ID\s*\(\s*N?'\[", "MSSQL OBJECT_ID 잔재"),
        (r'\[(?:dbo|HumanResources|Sales|Person|Production|Purchasing)\]\.\[',
         "MSSQL [schema].[obj] 잔재"),
        (r"\bN'[^']{2,}'", "MSSQL N'string' 잔재"),
        (r"\bCONVERT\s*\(\s*(?:datetime|nvarchar|varchar|int)\s*,", "MSSQL CONVERT() 잔재"),
        (r'\bISNULL\s*\(', "MSSQL ISNULL() 잔재"),
        (r'\bIF\s+OBJECT_ID\b', "MSSQL IF OBJECT_ID 잔재"),
        (r'\bGETDATE\s*\(\s*\)', "MSSQL GETDATE() 잔재"),
    ]
    for pat, desc in mssql_remnants:
        if re.search(pat, body, re.IGNORECASE):
            return False, f"MSSQL 잔재: {desc}"

    # ─── 게이트 8 (hotfix_020): 컬럼 정의 무결성 ───
    column_def_broken = [
        (r'\b(?:VARCHAR|CHAR|NVARCHAR|NCHAR|VARBINARY|BINARY|DECIMAL|NUMERIC|FLOAT|DOUBLE)\s*\(\s*\d+(?:\s*,\s*\d+)?\s+(?:NULL|NOT\s+NULL)\b',
         "컬럼 타입 괄호 안 NULL 침투"),
        (r'\bNULL\s+NOT\s+NULL\b', "NULL NOT NULL 충돌"),
        (r'\bNOT\s+NULL\s+NULL\b', "NOT NULL NULL 충돌"),
    ]
    for pat, desc in column_def_broken:
        if re.search(pat, body, re.IGNORECASE):
            return False, f"컬럼 정의 깨짐: {desc}"

    return True, "OK"


def main():
    here = os.path.abspath(os.path.dirname(__file__))
    candidates = [
        os.path.join(here, "..", "data", "conversion_patterns.json"),
        os.path.expanduser("~/project/databridge_full/data/conversion_patterns.json"),
    ]
    kb_path = None
    for c in candidates:
        if os.path.exists(c):
            kb_path = os.path.abspath(c)
            break

    if not kb_path:
        print("❌ KB 파일을 찾지 못했습니다.")
        sys.exit(1)

    print(f"📂 KB 파일: {kb_path}")

    # 1) 백업
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    backup_path = f"{kb_path}.bak_{ts}"
    shutil.copy2(kb_path, backup_path)
    print(f"💾 백업 생성: {backup_path}")

    # 2) 검증 + 분리
    with open(kb_path, encoding="utf-8") as f:
        kb = json.load(f)

    patterns = kb.get("patterns", [])
    cleaned = []
    rejected = []
    for p in patterns:
        tgt = p.get("tgt_sample_ddl", "")
        src = p.get("src_sample_ddl", "")
        safe, reason = _kb_quality_gate(tgt, src)
        if safe:
            cleaned.append(p)
        else:
            rejected.append((p, reason))

    print()
    print(f"📊 검증 결과:")
    print(f"   - 총 패턴: {len(patterns)}건")
    print(f"   - 유지: {len(cleaned)}건")
    print(f"   - 제거: {len(rejected)}건")

    if not rejected:
        print()
        print("✨ 오염 항목 없음. KB 그대로 유지합니다.")
        os.remove(backup_path)
        print(f"🗑  불필요한 백업 제거: {backup_path}")
        return

    # 3) 사용자 확인
    print()
    print("🔴 제거 대상:")
    for p, reason in rejected:
        print(f"   - [{p.get('obj_name_sample', '?')}] use_count={p.get('use_count', 0)} :: {reason}")
    print()
    confirm = input("위 항목을 제거하고 깨끗한 KB 로 저장하시겠습니까? [yes/N]: ").strip().lower()
    if confirm not in ("yes", "y"):
        print("취소했습니다. 백업은 유지됩니다.")
        return

    # 4) 청소된 KB 저장
    new_kb = dict(kb)  # 다른 메타데이터 보존
    new_kb["patterns"] = cleaned
    with open(kb_path, "w", encoding="utf-8") as f:
        json.dump(new_kb, f, ensure_ascii=False, indent=2)

    print()
    print(f"✅ KB 청소 완료: {kb_path}")
    print(f"   - 백업: {backup_path}")
    print(f"   - 유지된 패턴: {len(cleaned)}건")
    print(f"   - 제거된 패턴: {len(rejected)}건")


if __name__ == "__main__":
    main()
