#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════════════════
# kb_curator.py — DataBridge KB 수작업 큐레이션 도구 (2026-05-07)
#
# 본부장님 비전:
#   "내가 KB를 수작업으로 더 쌓을 수 있는 방법 없을까?"
#
# 본부장님 모토 부합:
#   - 본질에 충실: 본부장님이 빨간불 보면서 패턴 짚으시는 순간 → 즉시 KB 등록
#   - 신중하게: dry-run 미리보기 + 사용자 확인 후에만 저장
#   - 한방에: 1개 도구로 yml + auto_learned + error_cases 모두 누적
#   - 부작용 0: 백업 자동, 잘못 등록 시 복구 가능
#
# 사용법:
#   cd ~/project/databridge_full/backend
#   source venv/bin/activate
#   python3 scripts/kb_curator.py            # 대화형 모드 (메뉴)
#   python3 scripts/kb_curator.py --add      # 단일 패턴 직접 추가
#   python3 scripts/kb_curator.py --import-job-id 14   # 실패 Job 에서 자동 분석
#   python3 scripts/kb_curator.py --list     # 현재 KB 패턴 목록
#   python3 scripts/kb_curator.py --search "hierarchyid"  # KB 검색
#
# 본부장님 사용 예시 (오늘 빨간불 누적):
#   $ python3 scripts/kb_curator.py
#   [메뉴]
#     1) 빨간불 패턴 KB 등록 (대화형) ← 본부장님 핵심
#     2) 실패 Job 에서 자동 분석 + 시드 추출
#     3) KB 검색 / 검토
#     4) 통계 대시보드
#     5) 종료
# ════════════════════════════════════════════════════════════════════════════

import os
import re
import sys
import json
import time
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict

try:
    import yaml
except ImportError:
    print("❌ PyYAML 필요: pip install --break-system-packages PyYAML")
    sys.exit(1)


# ─── 경로 ────────────────────────────────────────────────────
DATABRIDGE_ROOT = Path(os.environ.get(
    "DATABRIDGE_ROOT",
    Path(__file__).resolve().parent.parent.parent.parent  # backend/scripts/ 기준
))
if not (DATABRIDGE_ROOT / "backend" / "app").exists():
    # 사용자가 backend 디렉토리에서 실행한 경우
    DATABRIDGE_ROOT = Path.home() / "project" / "databridge_full"

KB_YML       = DATABRIDGE_ROOT / "backend" / "app" / "engine" / "error_kb.yml"
AUTO_LEARNED = DATABRIDGE_ROOT / "backend" / "prompts" / "mssql_to_mysql" / "auto_learned_rules.json"
ERROR_CASES  = DATABRIDGE_ROOT / "backend" / "prompts" / "mssql_to_mysql" / "error_cases.txt"
KB_STATS_DB  = DATABRIDGE_ROOT / "backend" / "data" / "kb_stats.db"
DATABRIDGE_DB= DATABRIDGE_ROOT / "backend" / "data" / "databridge.db"


# ─── ANSI 색상 (터미널 친화) ─────────────────────────────────
def _supports_color():
    return sys.stdout.isatty() and os.environ.get("TERM") != "dumb"

USE_COLOR = _supports_color()
def C_R(t): return f"\033[31m{t}\033[0m" if USE_COLOR else t  # red
def C_G(t): return f"\033[32m{t}\033[0m" if USE_COLOR else t  # green
def C_Y(t): return f"\033[33m{t}\033[0m" if USE_COLOR else t  # yellow
def C_B(t): return f"\033[34m{t}\033[0m" if USE_COLOR else t  # blue
def C_M(t): return f"\033[35m{t}\033[0m" if USE_COLOR else t  # magenta
def C_C(t): return f"\033[36m{t}\033[0m" if USE_COLOR else t  # cyan
def C_BOLD(t): return f"\033[1m{t}\033[0m" if USE_COLOR else t


# ════════════════════════════════════════════════════════════════
# KB 로드/저장
# ════════════════════════════════════════════════════════════════
def load_kb_yml() -> dict:
    if not KB_YML.exists():
        return {"version": "1.0", "patterns": {}}
    with open(KB_YML, encoding="utf-8") as f:
        return yaml.safe_load(f) or {"patterns": {}}

def save_kb_yml(doc: dict, backup: bool = True):
    if backup and KB_YML.exists():
        backup_path = KB_YML.with_suffix(f".yml.before_curator_{int(time.time())}")
        shutil.copy2(KB_YML, backup_path)
        print(f"  💾 백업: {backup_path.name}")
    
    doc["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    
    with open(KB_YML, "w", encoding="utf-8") as f:
        yaml.dump(doc, f, allow_unicode=True, default_flow_style=False,
                  sort_keys=False, width=100)
    print(f"  ✅ 저장: {KB_YML}")


def load_auto_learned() -> dict:
    if not AUTO_LEARNED.exists():
        return {"version": "v90.52", "updated_at": "", "patterns": []}
    with open(AUTO_LEARNED, encoding="utf-8") as f:
        return json.load(f)

def save_auto_learned(doc: dict, backup: bool = True):
    if backup and AUTO_LEARNED.exists():
        shutil.copy2(AUTO_LEARNED, AUTO_LEARNED.with_suffix(f".json.before_curator_{int(time.time())}"))
    doc["updated_at"] = datetime.now().isoformat(timespec="seconds")
    with open(AUTO_LEARNED, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)


def append_error_case(obj_name: str, obj_type: str, errno: str, full_error: str, near: str = ""):
    """error_cases.txt 에 1건 추가"""
    ERROR_CASES.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d")
    entry = (
        f"\n[{ts}] {obj_name} | ({errno}) {full_error[:300]}\n"
        f"  타입: {obj_type}\n"
        f"  near: '{near}' (line ?)\n"
        f"  수작업 등록 (kb_curator)\n"
        f"  TODO: 패턴 검증 후 error_kb.yml 정식 등록\n"
    )
    with open(ERROR_CASES, "a", encoding="utf-8") as f:
        f.write(entry)


# ════════════════════════════════════════════════════════════════
# 입력 헬퍼
# ════════════════════════════════════════════════════════════════
def prompt(label: str, default: str = "", required: bool = False) -> str:
    """대화형 입력. 빈 입력 시 default 반환."""
    suffix = f" [{default}]" if default else ""
    while True:
        try:
            val = input(f"  {C_C(label)}{suffix}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n취소됨.")
            sys.exit(0)
        if val:
            return val
        if default:
            return default
        if not required:
            return ""
        print(f"    {C_Y('이 항목은 필수입니다.')}")

def prompt_choice(label: str, choices: list, default_idx: int = 0) -> str:
    """선택지 메뉴"""
    print(f"  {C_C(label)}:")
    for i, c in enumerate(choices, 1):
        marker = "▶" if i - 1 == default_idx else " "
        print(f"    {marker} {i}) {c}")
    while True:
        try:
            v = input(f"    선택 [1-{len(choices)}, 기본={default_idx+1}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            sys.exit(0)
        if not v:
            return choices[default_idx]
        try:
            idx = int(v) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        except ValueError:
            pass
        print(f"    {C_Y('잘못된 입력')}")

def prompt_yn(label: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    try:
        v = input(f"  {C_C(label)} {suffix}: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        sys.exit(0)
    if not v:
        return default
    return v.startswith("y") or v in ("ㅇ", "예")

def prompt_multiline(label: str, end_marker: str = "===END===") -> str:
    """여러 줄 입력 (===END=== 로 종료)"""
    print(f"  {C_C(label)} ({C_Y(end_marker)} 만 적힌 줄로 종료):")
    lines = []
    while True:
        try:
            ln = input("    | ")
        except (EOFError, KeyboardInterrupt):
            sys.exit(0)
        if ln.strip() == end_marker:
            break
        lines.append(ln)
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════
# 메뉴 1: 대화형 패턴 등록 (본부장님 핵심)
# ════════════════════════════════════════════════════════════════
def menu_add_pattern_interactive():
    print()
    print(C_BOLD(C_M("════════════════════════════════════════════════════════════")))
    print(C_BOLD(C_M("  메뉴 1 — 빨간불 패턴 KB 등록 (대화형)")))
    print(C_BOLD(C_M("════════════════════════════════════════════════════════════")))
    print()
    print(C_C("본부장님이 빨간불에서 발견하신 패턴을 KB 에 영구 등록합니다."))
    print(C_C("등록 후 다음 변환부터 사전 처방으로 자동 주입 → 같은 에러 회피."))
    print()
    
    # ─── 1. 패턴 ID ────────────────────────────────────────
    print(C_BOLD("[1/8] 패턴 ID"))
    print(C_Y("       명명 규칙: {OBJ}_{ISSUE}_{N3}  예: TRIG_NEW_UPDATE_001"))
    pid_obj = prompt_choice("객체 카테고리", 
        ["FUNC", "PROC", "TRIG", "VIEW", "TYPE", "TUNE", "ANY"], 0)
    pid_issue = prompt("이슈 키워드 (대문자, _ 구분, 예: NEW_UPDATE_NOT_ALLOWED)", required=True)
    
    # 자동 시퀀스 결정 (기존 yml 의 같은 prefix 카운트 + 1)
    doc = load_kb_yml()
    patterns = doc.get("patterns", {})
    prefix = f"{pid_obj}_{pid_issue}_"
    existing_seq = []
    for k in patterns:
        if k.startswith(prefix):
            m = re.search(r"_(\d{3})$", k)
            if m:
                existing_seq.append(int(m.group(1)))
    next_seq = max(existing_seq) + 1 if existing_seq else 1
    seq_str = prompt(f"시퀀스 번호 (3자리)", default=f"{next_seq:03d}")
    pattern_id = f"{pid_obj}_{pid_issue}_{seq_str.zfill(3)}"
    
    if pattern_id in patterns:
        if not prompt_yn(f"⚠️  '{pattern_id}' 이미 존재 — 덮어쓸까요?", False):
            print("취소됨.")
            return
    
    print(f"   {C_G('패턴 ID:')} {C_BOLD(pattern_id)}")
    
    # ─── 2. error_code ──────────────────────────────────────
    print()
    print(C_BOLD("[2/8] MySQL 에러 코드"))
    err_code = prompt("에러 코드 (예: 1064, 1049, 1146, 1054, * 또는 N/A)", default="1064")
    try:
        err_code_val = int(err_code) if err_code.isdigit() else err_code
    except:
        err_code_val = err_code
    
    # ─── 3. 카테고리 ──────────────────────────────────────
    print()
    print(C_BOLD("[3/8] 카테고리"))
    category = prompt_choice("카테고리",
        ["FUNCTION", "PROCEDURE", "TRIGGER", "VIEW", "QUERY", "TYPE", "ALL"], 0)
    
    # ─── 4. applies_to ──────────────────────────────────────
    print()
    print(C_BOLD("[4/8] 적용 대상 (applies_to)"))
    print(C_Y("       콤마로 구분, 예: PROCEDURE,FUNCTION,TRIGGER"))
    applies_str = prompt("적용 대상", default=category, required=True)
    applies_to = [s.strip().upper() for s in applies_str.split(",") if s.strip()]
    
    # ─── 5. 정규식 ──────────────────────────────────────
    print()
    print(C_BOLD("[5/8] 정규식 (사후 매칭용)"))
    print(C_Y("       에러 메시지에서 이 패턴 검출용. 빈 값도 OK."))
    print(C_Y("       예: \"near\\\\s*'`(int|datetime|money)`\""))
    regex = prompt("정규식 (옵션)", default="")
    
    # ─── 6. 원인 ──────────────────────────────────────
    print()
    print(C_BOLD("[6/8] 원인 (cause)"))
    print(C_Y("       한 줄로 요약. 예: 'AI 가 MySQL 타입에 백틱 잘못 붙임'"))
    cause = prompt("원인", required=True)
    
    # ─── 7. 사전 처방 (fix_prompt) ──────────────────────
    print()
    print(C_BOLD("[7/8] 사전 처방 (fix_prompt) — KB 핵심"))
    print(C_Y("       AI 에 주입될 처방 텍스트. 보통 ❌/✅ 예시 + 변환 룰 포함."))
    fix_prompt = prompt_multiline("사전 처방 본문")
    if not fix_prompt.strip():
        print(f"   {C_Y('처방이 비어있음 — 등록 취소')}")
        return
    
    # ─── 8. 시드 출처 ──────────────────────────────────
    print()
    print(C_BOLD("[8/8] 시드 출처 (seed_source)"))
    today = datetime.now().strftime("%Y-%m-%d")
    seed_source = prompt("시드 출처", default=f"{today} 본부장님 수작업 등록")
    
    # ─── 미리보기 ──────────────────────────────────────
    print()
    print(C_BOLD(C_C("━━━ 미리보기 ━━━")))
    new_entry = {
        "error_code": err_code_val,
        "category": category,
        "applies_to": applies_to,
        "regex": regex,
        "severity": "high",
        "cause": cause,
        "fix_type": "prompt_injection",
        "fix_prompt": fix_prompt,
        "seed_source": seed_source,
    }
    print(yaml.dump({pattern_id: new_entry}, allow_unicode=True, default_flow_style=False,
                    sort_keys=False, width=100))
    
    if prompt_yn("이 패턴을 등록하시겠습니까?", True):
        # 백업 + 저장
        if "patterns" not in doc:
            doc["patterns"] = {}
        doc["patterns"][pattern_id] = new_entry
        save_kb_yml(doc)
        print()
        print(f"  {C_G('✅ 패턴 등록 완료:')} {pattern_id}")
        print(f"  {C_C('다음 변환부터 자동 사전 주입 (백엔드 재기동 또는 KB 재로드 시).')}")
    else:
        print(f"  {C_Y('취소됨.')}")


# ════════════════════════════════════════════════════════════════
# 메뉴 2: 실패 Job 에서 자동 분석 → 시드 추출
# ════════════════════════════════════════════════════════════════
def menu_import_from_job():
    print()
    print(C_BOLD(C_M("════════════════════════════════════════════════════════════")))
    print(C_BOLD(C_M("  메뉴 2 — 실패 Job 에서 자동 분석 + 시드 추출")))
    print(C_BOLD(C_M("════════════════════════════════════════════════════════════")))
    print()
    
    if not DATABRIDGE_DB.exists():
        print(f"  {C_R('❌ databridge.db 없음:')} {DATABRIDGE_DB}")
        return
    
    # SQLite 직접 조회 (sqlite3 stdlib)
    import sqlite3
    conn = sqlite3.connect(DATABRIDGE_DB)
    cur = conn.cursor()
    
    # 최근 실패 Job 목록
    try:
        cur.execute("""
            SELECT job_id, status, started_at, finished_at,
                   (SELECT COUNT(*) FROM job_objects WHERE job_id=j.job_id AND status='error') as err_cnt,
                   (SELECT COUNT(*) FROM job_objects WHERE job_id=j.job_id) as total
            FROM jobs j
            ORDER BY started_at DESC LIMIT 10
        """)
        jobs = cur.fetchall()
    except Exception as e:
        print(f"  {C_R('DB 스키마 차이로 조회 실패:')} {e}")
        print(f"  {C_Y('수동으로 Job ID 입력 후 진행 (--import-job-id N)')}")
        conn.close()
        return
    
    if not jobs:
        print(f"  {C_Y('실패 Job 없음.')}")
        conn.close()
        return
    
    print(C_BOLD("최근 Job 10건:"))
    print(f"  {'ID':<5} {'상태':<10} {'시작':<20} {'에러/전체':<10}")
    for j in jobs:
        jid, st, sa, fa, ec, tot = j
        print(f"  {jid:<5} {st:<10} {(sa or '')[:19]:<20} {ec or 0}/{tot or 0}")
    
    job_id_str = prompt("\n분석할 Job ID", required=True)
    try:
        job_id = int(job_id_str)
    except ValueError:
        print(f"  {C_R('잘못된 ID')}")
        conn.close()
        return
    
    # 해당 Job 의 에러 객체들
    cur.execute("""
        SELECT obj_name, obj_type, error_message
        FROM job_objects
        WHERE job_id = ? AND status = 'error'
        ORDER BY obj_type, obj_name
    """, (job_id,))
    errors = cur.fetchall()
    conn.close()
    
    if not errors:
        print(f"  {C_Y(f'Job {job_id} 에 에러 없음.')}")
        return
    
    print()
    print(C_BOLD(f"Job {job_id} 의 실패 객체: {len(errors)}건"))
    
    # 에러 패턴 분류
    pattern_groups = defaultdict(list)
    pattern_rules = [
        # (정규식, 패턴키, 설명)
        (r"near '`(int|bigint|datetime|date|tinyint|smallint|float|decimal|money)`", "TYPE_BACKTICK", "타입 백틱"),
        (r"near '`(varchar|char|nvarchar)\(", "TYPE_LENGTH_BACKTICK", "타입 길이 백틱"),
        (r"RETURNS `(money|smallmoney)`", "MONEY_TYPE", "MONEY 미매핑"),
        (r"RETURNS \w+\s*\n?\s*AS\s*\n?\s*BEGIN", "AS_BEGIN", "FUNCTION AS BEGIN"),
        (r"OUTPUT", "OUTPUT_KEYWORD", "PROCEDURE OUTPUT"),
        (r"Unknown database '(\w+)'", "UNKNOWN_DB", "VIEW Unknown DB"),
        (r"NOT FOR REPLICATION", "NOT_FOR_REPL", "TRIGGER NOT FOR REPL"),
        (r"INSTEAD OF", "INSTEAD_OF", "TRIGGER INSTEAD OF"),
        (r"WITH SCHEMABINDING", "SCHEMABINDING", "VIEW SCHEMABINDING"),
        (r"PIVOT", "PIVOT", "VIEW PIVOT"),
        (r"\.value\(N'declare", "XML_FUNC", "VIEW XML 함수"),
        (r"hierarchyid", "HIERARCHYID", "HIERARCHYID 미지원"),
        (r"ERROR_(MESSAGE|SEVERITY|NUMBER)\(", "ERROR_FUNCTIONS", "ERROR_*() 함수"),
        (r"NEW row is not allowed", "TRIGGER_NEW_UPDATE", "AFTER trigger 의 NEW UPDATE 금지"),
        (r"near 'END' at line 1", "DDL_TRUNCATED", "DDL 잘림"),
    ]
    
    unmatched = []
    for obj_name, obj_type, err_msg in errors:
        matched = False
        err_msg = err_msg or ""
        for regex, key, desc in pattern_rules:
            if re.search(regex, err_msg, re.IGNORECASE):
                pattern_groups[(key, desc)].append((obj_name, obj_type, err_msg))
                matched = True
                break
        if not matched:
            unmatched.append((obj_name, obj_type, err_msg))
    
    print()
    print(C_BOLD(C_C("━━━ 패턴별 분류 ━━━")))
    for (key, desc), items in sorted(pattern_groups.items(), key=lambda x: -len(x[1])):
        print(f"  {C_G(key):<40} {C_Y(str(len(items))+'건'):<8} {desc}")
        for obj_name, obj_type, _ in items[:3]:
            print(f"    - {obj_type:<6} {obj_name}")
        if len(items) > 3:
            print(f"    ... 외 {len(items)-3}건")
    
    if unmatched:
        print()
        print(f"  {C_R('미분류:')} {len(unmatched)}건")
        for obj_name, obj_type, err in unmatched[:5]:
            print(f"    - {obj_type} {obj_name}: {(err or '')[:80]}")
    
    # error_cases.txt 에 자동 누적 옵션
    print()
    if prompt_yn(f"이 {len(errors)}건을 error_cases.txt 에 누적할까요?", True):
        for obj_name, obj_type, err_msg in errors:
            err_msg = err_msg or ""
            errno_m = re.search(r"\((\d{4})", err_msg)
            errno = errno_m.group(1) if errno_m else "?"
            near_m = re.search(r"near\s+'([^']+)'", err_msg)
            near = near_m.group(1)[:80] if near_m else ""
            append_error_case(obj_name, obj_type or "?", errno, err_msg, near)
        print(f"  {C_G('✅ error_cases.txt 에')} {len(errors)}건 누적됨")


# ════════════════════════════════════════════════════════════════
# 메뉴 3: KB 검색 / 검토
# ════════════════════════════════════════════════════════════════
def menu_search_kb():
    print()
    print(C_BOLD(C_M("════════════════════════════════════════════════════════════")))
    print(C_BOLD(C_M("  메뉴 3 — KB 검색 / 검토")))
    print(C_BOLD(C_M("════════════════════════════════════════════════════════════")))
    
    doc = load_kb_yml()
    patterns = doc.get("patterns", {})
    print(f"\n  현재 KB 패턴 수: {C_BOLD(str(len(patterns)))}개")
    
    keyword = prompt("\n검색어 (빈 입력 → 전체 목록)", default="")
    
    matched = []
    for pid, p in patterns.items():
        if not keyword:
            matched.append((pid, p))
            continue
        kw = keyword.lower()
        searchable = (
            pid + " " + str(p.get("category", "")) + " " + str(p.get("cause", "")) +
            " " + str(p.get("fix_prompt", "")) + " " + str(p.get("regex", ""))
        ).lower()
        if kw in searchable:
            matched.append((pid, p))
    
    print(f"\n  {C_C('매칭:')} {len(matched)}건")
    for i, (pid, p) in enumerate(matched, 1):
        print()
        print(f"  {C_BOLD(C_G(str(i)+'.'))} {C_BOLD(pid)}")
        print(f"     카테고리: {p.get('category', '?')}  |  err_code: {p.get('error_code', '?')}")
        print(f"     원인: {p.get('cause', '')[:100]}")
        if i % 5 == 0 and i < len(matched):
            if not prompt_yn(f"\n  계속 보기? ({i}/{len(matched)})", True):
                break


# ════════════════════════════════════════════════════════════════
# 메뉴 4: 통계 대시보드 (간단한 카운트)
# ════════════════════════════════════════════════════════════════
def menu_stats():
    print()
    print(C_BOLD(C_M("════════════════════════════════════════════════════════════")))
    print(C_BOLD(C_M("  메뉴 4 — KB 통계 대시보드")))
    print(C_BOLD(C_M("════════════════════════════════════════════════════════════")))
    
    doc = load_kb_yml()
    patterns = doc.get("patterns", {})
    
    print(f"\n  {C_BOLD('전체 패턴 수:')} {len(patterns)}")
    
    # 카테고리별
    cat_count = Counter(p.get("category", "?") for p in patterns.values())
    print(f"\n  {C_BOLD('카테고리별 분포:')}")
    for cat, cnt in cat_count.most_common():
        bar = "█" * cnt
        print(f"    {cat:<12} {cnt:>3}  {C_C(bar)}")
    
    # 에러 코드별
    err_count = Counter(str(p.get("error_code", "?")) for p in patterns.values())
    print(f"\n  {C_BOLD('에러 코드별 분포:')}")
    for ec, cnt in err_count.most_common(10):
        print(f"    {ec:<10} {cnt:>3}건")


# ════════════════════════════════════════════════════════════════
# 메뉴 5 (v95_p89_dashboard 2026-05-07 본부장님): KB 성장 대시보드
# ════════════════════════════════════════════════════════════════
# 본부장님 질문: "Gemma 반복 돌리면 KB 가 단단해지는가? 확인 가능?"
#
# 본부장님 환경의 3가지 누적 자산을 한눈에:
#   1) error_kb.yml         — 정식 KB (RAG 사전 주입 활성화)
#   2) error_cases.txt      — 자동 누적 케이스 (5542 lines)
#   3) auto_learned_rules   — 자동 학습 룰 (occurrence 카운트)
#
# 표시 정보:
#   - 자산별 크기 + 최근 추가 (얼마나 자라고 있는지)
#   - 자동 누적 vs 수동 등록 (RAG 활성화 여부)
#   - 패턴별 발생 횟수 Top 10
#   - "다음 변환 시 사전 주입될 패턴" (yml 에서 매칭 가능한 것)
# ════════════════════════════════════════════════════════════════
def menu_growth_dashboard():
    print()
    print(C_BOLD(C_M("════════════════════════════════════════════════════════════")))
    print(C_BOLD(C_M("  메뉴 5 — KB 성장 대시보드 (본부장님 자산 가시화)")))
    print(C_BOLD(C_M("════════════════════════════════════════════════════════════")))
    print()
    print(f"  {C_C('본부장님 비전: KB = 살아있는 자산')}")
    print(f"  {C_C('이 화면이 본부장님 자산이 자라는 모습입니다 ❤️')}")

    # ─── 1. error_kb.yml (정식 KB — RAG 활성화) ───
    print()
    print(C_BOLD(C_G("━━━ [1/3] error_kb.yml — 정식 KB (RAG 사전 주입 활성화) ━━━")))
    doc = load_kb_yml()
    patterns = doc.get("patterns", {})
    print(f"  ✓ 등록된 패턴: {C_BOLD(str(len(patterns)))}개  ← 다음 변환 시 사전 주입 활성")
    print(f"  ✓ 파일 크기: {KB_YML.stat().st_size:,} bytes")
    print(f"  ✓ 최종 수정: {datetime.fromtimestamp(KB_YML.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 시드 출처별 카운트
    seed_count = Counter()
    for p in patterns.values():
        src = (p.get("seed_source", "") or "기타").split("—")[0].strip()[:50]
        if not src: src = "기타"
        seed_count[src] += 1
    print(f"\n  {C_BOLD('패턴 시드 출처 (자산이 어디서 왔나):')}")
    for src, cnt in seed_count.most_common(5):
        bar = "█" * min(cnt, 30)
        print(f"    {cnt:>3}건  {C_C(bar)} {src}")

    # ─── 2. error_cases.txt (자동 누적 케이스) ───
    print()
    print(C_BOLD(C_Y("━━━ [2/3] error_cases.txt — 자동 누적 케이스 ━━━")))
    if ERROR_CASES.exists():
        size = ERROR_CASES.stat().st_size
        line_cnt = sum(1 for _ in open(ERROR_CASES, encoding="utf-8", errors="ignore"))
        print(f"  ✓ 누적 라인: {C_BOLD(str(line_cnt))} 줄 ({size:,} bytes)")
        print(f"  ✓ 최종 추가: {datetime.fromtimestamp(ERROR_CASES.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 최근 7일 추가 패턴 분석
        try:
            from datetime import timedelta
            today = datetime.now().strftime("%Y-%m-%d")
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            
            today_count = 0
            yest_count = 0
            week_count = 0
            obj_types = Counter()
            err_codes = Counter()
            with open(ERROR_CASES, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.startswith("[20"):
                        if today in line: today_count += 1
                        if yesterday in line: yest_count += 1
                        # 객체 타입 추출
                        if "타입:" in line: pass  # 다음 줄
                    if "  타입:" in line:
                        ot = line.split(":", 1)[1].strip()
                        obj_types[ot] += 1
                    # 에러 코드
                    import re as _re
                    m = _re.search(r"\((\d{4})", line)
                    if m: err_codes[m.group(1)] += 1
            
            print(f"\n  {C_BOLD('성장 추이:')}")
            print(f"    오늘 추가:  {C_G(str(today_count))} 건")
            print(f"    어제 추가:  {yest_count} 건")
            
            if obj_types:
                print(f"\n  {C_BOLD('누적된 객체 타입 분포 (Top 5):')}")
                for ot, cnt in obj_types.most_common(5):
                    bar = "█" * min(cnt // 2, 30)
                    print(f"    {ot:<10} {cnt:>4}건  {C_C(bar)}")
            
            if err_codes:
                print(f"\n  {C_BOLD('누적된 에러 코드 분포 (Top 10):')}")
                for ec, cnt in err_codes.most_common(10):
                    bar = "█" * min(cnt // 5, 30)
                    print(f"    {ec:<6} {cnt:>4}회  {C_C(bar)}")
        except Exception as _e:
            print(f"    {C_Y('분석 일부 실패: ' + str(_e)[:50])}")
    else:
        print(f"  {C_Y('파일 없음 — 아직 누적된 에러 없음')}")

    # ─── 3. auto_learned_rules.json ───
    print()
    print(C_BOLD(C_B("━━━ [3/3] auto_learned_rules.json — 자동 학습 룰 (occurrence) ━━━")))
    if AUTO_LEARNED.exists():
        try:
            al = load_auto_learned()
            al_patterns = al.get("patterns", [])
            print(f"  ✓ 자동 학습 룰: {C_BOLD(str(len(al_patterns)))}개")
            print(f"  ✓ 버전: {al.get('version', '?')}")
            print(f"  ✓ 최종 갱신: {al.get('updated_at', '?')}")
            
            # occurrence 정렬
            al_patterns_sorted = sorted(al_patterns, 
                key=lambda x: x.get("occurrence", 0), reverse=True)
            
            if al_patterns_sorted:
                print(f"\n  {C_BOLD('자주 발생한 패턴 Top 5 (이게 바로 KB 등록 후보!):')}")
                for i, p in enumerate(al_patterns_sorted[:5], 1):
                    rid = p.get("rule_id", "?")
                    occ = p.get("occurrence", 0)
                    obj_type = p.get("obj_type", "?")
                    msg = (p.get("issue_msg", "") or "")[:70]
                    print(f"    {i}. {C_BOLD(rid)} ({obj_type}) — {C_Y(str(occ)+'회 발생')}")
                    print(f"       {msg}")
            
        except Exception as e:
            print(f"  {C_Y(f'로드 실패: {e}')}")
    else:
        print(f"  {C_Y('파일 없음')}")

    # ─── 4. 본부장님 핵심 답변 ───
    print()
    print(C_BOLD(C_M("━━━ 본부장님 질문에 대한 답 ━━━")))
    print(f"  {C_BOLD('Q: Gemma 반복하면 KB 가 단단해지나?')}")
    print(f"     A: ✅ 자동 누적은 됨 (error_cases.txt + auto_learned)")
    print(f"        ⚠️  하지만 RAG 사전 주입에 활용되려면 yml 등록 필요")
    print(f"           → 메뉴 1 (대화형) 또는 메뉴 2 (Job 자동 분석) 사용")
    print()
    print(f"  {C_BOLD('Q: 프롬프트가 풍성해지나?')}")
    print(f"     A: ✅ yml 의 {len(patterns)}개 패턴이 사전 주입됨")
    print(f"        패턴이 늘수록 Gemma 컨텍스트 풍성해짐")
    print()
    print(f"  {C_BOLD('Q: 내가 확인 가능?')}")
    print(f"     A: ✅ 이 대시보드 (메뉴 5) — 언제든 다시 보기")
    print(f"        ✅ 메뉴 3 (KB 검색) — 특정 패턴 등록됐는지")
    print(f"        ✅ 백엔드 로그: grep '01b-preflight-applied' (사전 주입 작동 증명)")
    
    print()
    if al_patterns_sorted := al_patterns_sorted if AUTO_LEARNED.exists() else []:
        print(C_BOLD(C_G("💡 다음 액션 권장:")))
        print(f"   auto_learned 의 Top 패턴 ({len(al_patterns_sorted)}개) 중 발생 빈도 높은 것을")
        print(f"   메뉴 1 (대화형 등록) 으로 yml 에 정식 등록하시면 — 즉시 RAG 활성화!")
    print()
    print(C_BOLD(C_M("════════════════════════════════════════════════════════════")))
    print(C_BOLD(C_M("  메뉴 4 — KB 통계 대시보드")))
    print(C_BOLD(C_M("════════════════════════════════════════════════════════════")))
    
    doc = load_kb_yml()
    patterns = doc.get("patterns", {})
    
    print(f"\n  {C_BOLD('전체 패턴 수:')} {len(patterns)}")
    
    # 카테고리별
    cat_count = Counter(p.get("category", "?") for p in patterns.values())
    print(f"\n  {C_BOLD('카테고리별 분포:')}")
    for cat, cnt in cat_count.most_common():
        bar = "█" * cnt
        print(f"    {cat:<12} {cnt:>3}  {C_C(bar)}")
    
    # 에러 코드별
    err_count = Counter(str(p.get("error_code", "?")) for p in patterns.values())
    print(f"\n  {C_BOLD('에러 코드별 분포:')}")
    for ec, cnt in err_count.most_common(10):
        print(f"    {ec:<10} {cnt:>3}건")
    
    # 시드 출처별
    seed_count = Counter()
    for p in patterns.values():
        src = (p.get("seed_source", "") or "기타").split("—")[0].strip()[:60]
        seed_count[src] += 1
    print(f"\n  {C_BOLD('시드 출처 (Top 5):')}")
    for src, cnt in seed_count.most_common(5):
        print(f"    {cnt:>3}건  {src}")
    
    # auto_learned
    if AUTO_LEARNED.exists():
        try:
            al = load_auto_learned()
            print(f"\n  {C_BOLD('auto_learned_rules.json:')}")
            print(f"    버전: {al.get('version', '?')}")
            print(f"    패턴: {len(al.get('patterns', []))}개")
            for p in al.get("patterns", [])[:5]:
                print(f"      - {p.get('rule_id')}: {p.get('issue_msg', '')[:80]}")
        except Exception as e:
            print(f"    {C_Y(f'로드 실패: {e}')}")
    
    # error_cases.txt 라인 수
    if ERROR_CASES.exists():
        line_cnt = sum(1 for _ in open(ERROR_CASES, encoding="utf-8", errors="ignore"))
        print(f"\n  {C_BOLD('error_cases.txt:')} {line_cnt} lines")


# ════════════════════════════════════════════════════════════════
# 메뉴 루프
# ════════════════════════════════════════════════════════════════
def main_menu():
    while True:
        print()
        print(C_BOLD(C_M("╔══════════════════════════════════════════════════════════╗")))
        print(C_BOLD(C_M("║   DataBridge KB Curator — 본부장님 KB 큐레이션 도구      ║")))
        print(C_BOLD(C_M("╚══════════════════════════════════════════════════════════╝")))
        print()
        print(f"  KB 위치: {C_C(str(KB_YML))}")
        try:
            doc = load_kb_yml()
            print(f"  현재 패턴 수: {C_BOLD(str(len(doc.get('patterns', {}))))}개")
        except Exception as e:
            print(f"  {C_R(f'KB 로드 에러: {e}')}")
        
        print()
        print("  1) 빨간불 패턴 KB 등록 (대화형)  ← 본부장님 핵심")
        print("  2) 실패 Job 에서 자동 분석 + 시드 추출")
        print("  3) KB 검색 / 검토")
        print("  4) 통계 대시보드")
        print(f"  5) {C_G('KB 성장 대시보드')}  ← {C_BOLD('자산이 자라는 모습 ❤️')}")
        print("  6) 종료")
        print()
        
        try:
            choice = input(f"  {C_C('선택')} [1-6]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료.")
            break
        
        if choice == "1":
            menu_add_pattern_interactive()
        elif choice == "2":
            menu_import_from_job()
        elif choice == "3":
            menu_search_kb()
        elif choice == "4":
            menu_stats()
        elif choice == "5":
            menu_growth_dashboard()
        elif choice == "6":
            print(f"  {C_G('수고하셨습니다, 본부장님 ❤️')}")
            break
        else:
            print(f"  {C_Y('잘못된 선택')}")


# ════════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════════
def main():
    p = argparse.ArgumentParser(
        description="DataBridge KB Curator — 본부장님 수작업 KB 큐레이션 도구")
    p.add_argument("--add", action="store_true", help="대화형 패턴 추가")
    p.add_argument("--list", action="store_true", help="KB 패턴 목록")
    p.add_argument("--search", metavar="KEYWORD", help="KB 검색")
    p.add_argument("--stats", action="store_true", help="통계 대시보드")
    p.add_argument("--dashboard", action="store_true",
                   help="KB 성장 대시보드 (본부장님 자산 가시화)")
    p.add_argument("--import-job-id", type=int, help="Job 에서 자동 분석")
    args = p.parse_args()
    
    # 환경 검증
    if not KB_YML.exists():
        print(f"  {C_R('❌ error_kb.yml 없음:')} {KB_YML}")
        print(f"  {C_Y('DataBridge 설치 확인 또는 DATABRIDGE_ROOT 환경변수 설정')}")
        sys.exit(1)
    
    if args.add:
        menu_add_pattern_interactive()
    elif args.list:
        doc = load_kb_yml()
        for pid in sorted(doc.get("patterns", {})):
            p_obj = doc["patterns"][pid]
            print(f"  {pid:<40} {p_obj.get('category', '?'):<10} {(p_obj.get('cause', '') or '')[:60]}")
    elif args.search:
        # 키워드 직접 검색
        doc = load_kb_yml()
        kw = args.search.lower()
        for pid, p_obj in doc.get("patterns", {}).items():
            searchable = (pid + " " + str(p_obj.get("cause", "")) + " " +
                          str(p_obj.get("fix_prompt", ""))).lower()
            if kw in searchable:
                print(f"\n  {C_BOLD(pid)}")
                print(f"     {p_obj.get('cause', '')[:100]}")
    elif args.stats:
        menu_stats()
    elif args.dashboard:
        menu_growth_dashboard()
    elif getattr(args, "import_job_id", None):
        menu_import_from_job()
    else:
        # 기본: 대화형 메뉴
        main_menu()


if __name__ == "__main__":
    main()
