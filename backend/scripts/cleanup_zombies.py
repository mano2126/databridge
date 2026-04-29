"""좀비 Job 수동 정리 스크립트.

기동 시 자동 정리 훅 (v10 #3) 이 추가되었지만,
서버를 끌 수 없을 때 수동으로 정리가 필요한 경우를 위한 스크립트.

사용법:
    cd D:\\project\\databridge_full\\backend
    python scripts\\cleanup_zombies.py
"""
import sqlite3
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# backend 디렉토리 기준으로 data/databridge.db 찾기
HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
DB_PATH = BACKEND / "data" / "databridge.db"

if not DB_PATH.exists():
    print(f"❌ SQLite DB 파일 없음: {DB_PATH}")
    print("   backend 폴더 안에서 실행하고 있는지 확인하세요")
    sys.exit(1)

conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 테이블 존재 확인
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='store_jobs'")
if not cur.fetchone():
    print("❌ store_jobs 테이블 없음 — 서버가 한 번도 기동하지 않았거나 Job 저장소 없음")
    sys.exit(1)

cur.execute("SELECT key, value FROM store_jobs")
zombies = []
total = 0
for row in cur.fetchall():
    total += 1
    try:
        j = json.loads(row["value"])
        if j.get("status") in ("running", "paused"):
            zombies.append((row["key"], j))
    except Exception as e:
        print(f"  [skip] {row['key']}: {e}")

print(f"\n전체 Job: {total}개")
print(f"running/paused (좀비 후보): {len(zombies)}개\n")

if not zombies:
    print("✅ 정리할 좀비 없음")
    sys.exit(0)

for key, j in zombies:
    print(f"  {key[:8]} | {j.get('name','?'):30s} | {j.get('status'):8s} | {j.get('started_at','')}")

print()
ans = input(f"위 {len(zombies)}개를 모두 'stopped'로 전환할까? (y/N): ").strip().lower()
if ans != "y":
    print("취소됨")
    sys.exit(0)

now = datetime.now().astimezone().isoformat()
for key, j in zombies:
    j["status"] = "stopped"
    j["stopped_at"] = now
    j["stop_reason"] = "manual cleanup (scripts/cleanup_zombies.py)"
    cur.execute(
        "UPDATE store_jobs SET value=?, updated_at=? WHERE key=?",
        (json.dumps(j, ensure_ascii=False), now, key),
    )
conn.commit()
print(f"\n✅ {len(zombies)}개 Job 좀비 → stopped 로 전환 완료")
print("   서버가 실행 중이면 재기동 권장 (메모리 _jobs 딕셔너리 동기화)")
