"""
app/core/password_resolver.py
password 필드 해결(resolve) 헬퍼 — v9 패치 #4

프론트엔드가 비밀번호 입력 필드를 보낼 때 3가지 케이스가 있음:
  1. 평문      : "bridge1234"      → 그대로 사용
  2. 마스크    : "●●●●●●●●"        → 프로파일 저장된 암호문을 복호화해서 사용
  3. 암호문    : "enc::gAAA..."     → 복호화해서 사용 (드문 경우)

이 헬퍼의 핵심 역할:
  - 마스크 토큰을 받으면 → profile_id 기반으로 저장된 프로파일에서 꺼내 복호화
  - 암호문을 받으면 → 바로 복호화
  - 평문이면 → 그대로 반환

사용처:
  - /connectors/test (연결 테스트)
  - /jobs (Job 생성)
  - /schema/... (각종 스키마 조회 엔드포인트)
  - 그 외 DB 접속이 필요한 모든 곳

설계 원칙:
  - 프론트가 profile_id 를 함께 보내면 자동 해결 (가장 선호)
  - 안 보내면 host+username+database 조합으로 프로파일 검색 (fallback)
  - 해결 불가면 원본 그대로 반환 (에러는 DB 접속 시점에 자연스럽게 발생)
"""
from __future__ import annotations
import logging
from typing import Optional

from app.core.crypto import decrypt as _dec, is_encrypted as _is_enc
from app.engine.security import MASK_TOKEN

logger = logging.getLogger("databridge.password_resolver")


def resolve_password(
    password: str,
    *,
    profile_id: Optional[str] = None,
    job_id: Optional[str] = None,
    side: str = "source",
    host: Optional[str] = None,
    username: Optional[str] = None,
    database: Optional[str] = None,
) -> str:
    """
    프론트가 보낸 password 필드를 실제 사용 가능한 평문으로 변환.

    Args:
        password:   프론트가 보낸 원본 값 (평문/마스크/암호문)
        profile_id: 프로파일 ID (있으면 가장 확실한 해결 경로)
        job_id:     v90.55 신규 — Job ID. 활성 Job 의 src/tgt password 사용.
                    검증 화면(Validate.vue) 에서 이관 진행 중 Job 의 연결 재사용 용도.
        side:       "source" | "target" (profile_id / job_id 사용 시 필요)
        host, username, database:
                    profile_id 가 없을 때 프로파일 fallback 검색용

    Returns:
        평문 비밀번호. 해결 불가 시 빈 문자열.
    """
    # 1. 평문 (가장 일반적) — 그대로 반환
    if not password:
        # v90.55: password 가 비어있어도 job_id 가 있으면 그쪽에서 복원 가능
        if job_id:
            try:
                plain = _load_from_job_by_id(job_id, side)
                if plain:
                    logger.debug("password 해결: job_id=%s side=%s → 성공 (빈 입력)",
                                 job_id, side)
                    return plain
            except Exception as e:
                logger.warning("job_id 기반 해결 실패 (%s): %s", job_id, e)
        return ""
    if password != MASK_TOKEN and not _is_enc(password):
        return password

    # 2. 암호문이면 바로 복호화
    if _is_enc(password):
        try:
            plain = _dec(password)
            if plain:
                return plain
        except Exception as e:
            logger.warning("암호문 복호화 실패: %s", e)

    # 3. 마스크 토큰이면 프로파일/Job 에서 복원
    # 3-0. v90.55 신규 — job_id 로 직접 조회 (가장 우선)
    #     검증 화면이 활성 Job 연결정보를 자동 적용한 경우 이쪽 경로 사용.
    if job_id:
        try:
            plain = _load_from_job_by_id(job_id, side)
            if plain:
                logger.debug("password 해결: job_id=%s side=%s → 성공",
                             job_id, side)
                return plain
        except Exception as e:
            logger.warning("job_id 기반 해결 실패 (%s): %s", job_id, e)

    # 3-1. profile_id 로 직접 조회
    if profile_id:
        try:
            plain = _load_from_profile_by_id(profile_id, side)
            if plain:
                logger.debug("password 해결: profile_id=%s side=%s → 성공",
                             profile_id, side)
                return plain
        except Exception as e:
            logger.warning("profile_id 기반 해결 실패 (%s): %s", profile_id, e)

    # 3-2. host+username+database 조합으로 fallback 검색
    if host and username:
        try:
            plain = _load_from_profile_by_conn(host, username, database, side)
            if plain:
                logger.debug("password 해결: host=%s user=%s db=%s → 성공",
                             host, username, database)
                return plain
        except Exception as e:
            logger.warning("host/user 기반 해결 실패: %s", e)

    # 4. 해결 불가 — 마스크 토큰이면 빈 문자열 반환 (원본 반환 시 드라이버가
    #    latin-1 인코딩 오류로 터짐. 빈 문자열이면 정상적인 "로그인 실패" 에러.)
    logger.warning(
        "password 해결 불가 — 빈 문자열로 대체 "
        "(profile_id=%s, host=%s, user=%s, side=%s)",
        profile_id, host, username, side
    )
    if password == MASK_TOKEN:
        return ""
    return password


def _load_from_profile_by_id(profile_id: str, side: str) -> str:
    """프로파일 ID로 저장된 암호문을 복호화해서 반환 — 다양한 저장 구조 대응"""
    from app.core.store import Store
    profiles = Store("profiles")
    p = profiles.get(profile_id)
    if not p:
        return ""
    return _extract_password_from_profile(p, side)


def _load_from_job_by_id(job_id: str, side: str) -> str:
    """
    v90.55 신규: Job ID로 저장된 src/tgt password 를 복호화해서 반환.
    
    검증 화면(Validate.vue) 에서 활성 Job 의 연결정보를 자동 적용한 경우,
    각 API 호출 시 job_id 만 전달하면 backend 가 password 자동 복원.
    
    Args:
        job_id: jobs Store 의 Job ID
        side:   "source" | "target"
    
    Returns:
        평문 비밀번호. Job 없거나 password 없으면 빈 문자열.
    """
    from app.core.store import Store
    jobs = Store("jobs")
    job = jobs.get(job_id)
    if not job:
        logger.debug("job_id=%s 미존재", job_id)
        return ""
    
    # Job dict 의 src_password / tgt_password 키 사용 (security.py 와 동일 규약)
    key = "src_password" if side == "source" else "tgt_password"
    enc_or_plain = job.get(key, "")
    if not enc_or_plain:
        return ""
    
    # 암호화되어 있으면 복호화, 평문이면 그대로
    if _is_enc(enc_or_plain):
        try:
            return _dec(enc_or_plain)
        except Exception as e:
            logger.warning("Job password 복호화 실패 (job_id=%s side=%s): %s",
                           job_id, side, e)
            return ""
    return enc_or_plain


def _load_from_profile_by_conn(host: str, username: str,
                                database: Optional[str], side: str) -> str:
    """host+username(+database) 매칭으로 프로파일 검색 후 복호화

    다양한 저장 구조 자동 대응:
      1. p["source"]["host"], p["source"]["password"] 형태
      2. p["target"]["host"], p["target"]["password"] 형태
      3. p["host"], p["password"] 같은 평탄한 구조

    side 힌트가 있으면 우선 매칭하되, 못 찾으면 다른 side 도 시도.
    """
    from app.core.store import Store
    profiles = Store("profiles")

    # 여러 매칭 후보 중 "가장 적합한 것" 선택 위해 점수 매김
    best_score = -1
    best_pw = ""

    for p in profiles.values():
        # 1. source/target 분리 구조 탐색
        for candidate_side in (side, "source", "target"):
            side_data = p.get(candidate_side) if isinstance(p.get(candidate_side), dict) else None
            if not side_data:
                continue
            score = _match_score(side_data, host, username, database, candidate_side == side)
            if score > best_score:
                pw = _decrypt_if_needed(side_data.get("password", ""))
                if pw:
                    best_score = score
                    best_pw = pw

        # 2. 평탄한 구조 (p 자체가 연결 정보)
        score = _match_score(p, host, username, database, True)
        if score > best_score:
            pw = _decrypt_if_needed(p.get("password", ""))
            if pw:
                best_score = score
                best_pw = pw

    return best_pw


def _extract_password_from_profile(p: dict, side: str) -> str:
    """프로파일 내부에서 side 에 해당하는 password 추출 (구조 자동 탐지)"""
    # 우선순위:
    #   1. p[side].password (명시된 side 우선)
    #   2. p[다른_side].password
    #   3. p.password (평탄한 구조)
    for candidate_side in (side, "source", "target"):
        sd = p.get(candidate_side)
        if isinstance(sd, dict):
            pw = _decrypt_if_needed(sd.get("password", ""))
            if pw:
                return pw
    pw = _decrypt_if_needed(p.get("password", ""))
    return pw


def _match_score(data: dict, host: str, username: str,
                 database: Optional[str], side_match: bool) -> int:
    """connection 정보 매칭 점수 — 높을수록 좋은 매칭"""
    if not isinstance(data, dict):
        return -1
    score = 0
    d_host = _normalize_host(data.get("host", ""))
    n_host = _normalize_host(host or "")
    if d_host and d_host == n_host:
        score += 10
    elif not n_host:
        pass
    else:
        return -1  # 호스트 불일치면 탈락

    if username:
        if data.get("username") == username:
            score += 5
        else:
            return -1  # 사용자 불일치면 탈락

    if database and data.get("database") == database:
        score += 3

    if side_match:
        score += 1

    return score


def _normalize_host(h: str) -> str:
    """host 표기 정규화 - localhost ↔ 127.0.0.1 동일시"""
    h = (h or "").strip().lower()
    if h in ("localhost", "127.0.0.1", "::1", ""):
        return "127.0.0.1" if h else ""
    return h


def _decrypt_if_needed(pw: str) -> str:
    """암호문이면 복호화, 평문이면 그대로. 마스크/빈값은 '' 반환"""
    if not pw:
        return ""
    if pw == MASK_TOKEN:
        return ""
    if _is_enc(pw):
        try:
            return _dec(pw)
        except Exception:
            return ""
    return pw


# ── 편의 함수: Job 생성 body 전체에 대해 일괄 해결 ──────────
def resolve_job_passwords(body: dict) -> dict:
    """
    Job 생성 요청 body의 src_password/tgt_password 를 일괄 해결.
    body를 직접 수정하지 않고 사본 반환.
    """
    resolved = dict(body)
    resolved["src_password"] = resolve_password(
        body.get("src_password", ""),
        profile_id=body.get("src_profile_id") or body.get("src_profile"),
        side="source",
        host=body.get("src_host"),
        username=body.get("src_username"),
        database=body.get("src_database"),
    )
    resolved["tgt_password"] = resolve_password(
        body.get("tgt_password", ""),
        profile_id=body.get("tgt_profile_id") or body.get("tgt_profile"),
        side="target",
        host=body.get("tgt_host"),
        username=body.get("tgt_username"),
        database=body.get("tgt_database"),
    )
    return resolved


def resolve_single_password(body: dict) -> dict:
    """
    /connectors/test 나 /schema/... 같은 단일 password body 해결.
    body의 password 필드를 실제 평문으로 치환한 사본 반환.
    
    v90.55: body 에 'job_id' 가 있으면 활성 Job 에서 password 복원.
    """
    resolved = dict(body)
    resolved["password"] = resolve_password(
        body.get("password", ""),
        profile_id=body.get("profile_id") or body.get("profile"),
        job_id=body.get("job_id"),  # v90.55
        side=body.get("side", "source"),  # 프론트가 전달하면 사용
        host=body.get("host"),
        username=body.get("username"),
        database=body.get("database"),
    )
    return resolved
