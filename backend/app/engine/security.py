"""
app/engine/security.py
Job 엔트리의 비밀번호 필드 암호화/복호화/마스킹 헬퍼.

분리 배경:
  기존에는 jobs.py 상단에 _encrypt_job_passwords 등이 있었지만,
  이 로직은 라우터가 아니라 엔진 계약의 일부다. 외부 라우터 코드가
  Job dict를 넘기거나 받을 때 반드시 이 함수들을 사용해야 하므로
  명시적인 공개 API로 분리했다.

원칙:
  - 디스크/저장소에 들어가는 값은 반드시 암호화된 상태 (enc:: prefix)
  - 엔진(pymysql/pyodbc 드라이버)에 넘기기 직전에만 복호화
  - API 응답으로 나가는 값은 마스킹 (MASK_TOKEN)
"""
from __future__ import annotations
import copy
from typing import Any

from app.core.crypto import (
    encrypt as _enc,
    decrypt as _dec,
    is_encrypted as _is_enc,
)


# API 응답에서 비밀번호 자리에 들어가는 문자열.
# 프론트가 편집 모드에서 이 값을 그대로 다시 보내면 "변경 없음"으로 해석됨
# (connector.py의 _preserve_masked_passwords 가 동일 토큰 사용).
MASK_TOKEN = "●●●●●●●●"


def encrypt_job_passwords(job: dict) -> dict:
    """
    Job dict의 src_password / tgt_password 를 암호화.
    Store.set() 으로 저장하기 직전에 호출한다.

    멱등성: 이미 암호화된 값(enc::)은 재암호화하지 않는다.

    Args:
        job: in-place 수정 가능한 Job 딕셔너리
    Returns:
        동일한 dict 객체 (편의용 체이닝)
    """
    for k in ("src_password", "tgt_password"):
        v = job.get(k, "")
        if v and not _is_enc(v):
            job[k] = _enc(v)
    return job


def decrypt_job_for_engine(job: dict) -> dict:
    """
    엔진에 넘길 Job의 복호화된 사본을 반환.
    원본 dict는 건드리지 않는다 → 저장소의 암호문은 그대로 유지.

    사용 위치:
        MigrationEngine 인스턴스화 직전
        (runner.py._run_migration 참조)

    Returns:
        복호화된 사본. src_password/tgt_password가 평문인 새 dict.
    """
    out = copy.deepcopy(job)
    for k in ("src_password", "tgt_password"):
        v = out.get(k, "")
        if _is_enc(v):
            out[k] = _dec(v)
    return out


def mask_job_response(job: dict) -> Any:
    """
    API 응답용 Job dict — 비밀번호 마스킹.
    원본은 건드리지 않는다.

    Note:
      현재 None/list/dict 어떤 입력도 수용하도록 타입 느슨하게 처리.
      단순히 dict가 아니면 그대로 반환.
    """
    if not isinstance(job, dict):
        return job
    out = copy.deepcopy(job)
    for k in ("src_password", "tgt_password"):
        if out.get(k):
            out[k] = MASK_TOKEN
    return out
