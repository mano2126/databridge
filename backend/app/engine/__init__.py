"""
app/engine
DataBridge 이관 엔진 모듈.

외부(라우터 등)에서는 이 패키지를 통해서만 엔진을 사용한다:

    from app.engine import MigrationEngine, run_migration, new_job
    from app.engine.security import (
        encrypt_job_passwords, decrypt_job_for_engine, mask_job_response,
        MASK_TOKEN,
    )

내부 구조(분리 후):
  security.py         — 비밀번호 암호화/복호화/마스킹 (기존 _encrypt/_decrypt/_mask)
  job_factory.py      — Job dict 생성 (_new_job)
  migration_engine.py — MigrationEngine 클래스
  runner.py           — _run_migration 백그라운드 실행 래퍼
"""
from app.engine.security import (
    encrypt_job_passwords,
    decrypt_job_for_engine,
    mask_job_response,
    MASK_TOKEN,
)
from app.engine.job_factory import new_job
from app.engine.migration_engine import MigrationEngine
from app.engine.runner import run_migration

__all__ = [
    "encrypt_job_passwords",
    "decrypt_job_for_engine",
    "mask_job_response",
    "MASK_TOKEN",
    "new_job",
    "MigrationEngine",
    "run_migration",
]
