"""
app/api/routes/connector.py
커넥터 관리 REST API — JSON 파일 영속성 적용
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from app.core.auth_deps import require_viewer, require_operator
from app.core import audit as _audit
from app.core.audit import Actions as _AuditActions
import uuid, time
from datetime import datetime
from app.core.store import Store

router = APIRouter()

# ── JSON 파일 영속 스토어 ─────────────────────────────────
_profiles = Store("profiles")

# 초기 샘플 프로파일 (profiles.json이 없을 때만 생성)
if len(_profiles) == 0:
    _default = {
        "id": "p1",
        "name": "MySQL Local → MSSQL Local",
        "source": {
            "db_type": "mysql", "host": "localhost", "port": 3306,
            "username": "root", "password": "", "database": "sakila",
            "version": "MySQL 8.0",
        },
        "target": {
            "db_type": "mssql", "host": "localhost", "port": 1433,
            "username": "sa", "password": "", "database": "target_db",
            "version": "SQL Server 2019",
        },
        "created_at": datetime.now().isoformat(),
        "status": "ok",
    }
    _profiles.set("p1", _default)

# ── DB 버전 Mock 매핑 ─────────────────────────────────────
# ── Note: 이전 버전에 있던 Mock 버전 사전(_DB_VER)은 제거됨.
# 지원 DB 메타데이터는 app/core/supported_dbs.py 에서 단일 관리.


# ── 연결 테스트 ───────────────────────────────────────────

@router.post("/test")
def test_connection(body: dict):
    """
    DB 연결 테스트 — 실제 드라이버로만 테스트. Mock 없음.

    body: { db_type, host, port, username, password, database }
    """
    from app.core.supported_dbs import get_info, SupportTier

    db_type  = (body.get("db_type", "") or "").lower()
    host     = body.get("host", "").strip()
    port     = body.get("port", 3306)
    username = body.get("username", "").strip()
    password = body.get("password", "")
    database = body.get("database", "").strip()

    # v9 패치 #4: 마스크(●●●●●●●●) 또는 암호문(enc::) 을 받은 경우 해결
    # 프론트가 "저장된 프로파일 선택 → 연결 테스트" 흐름으로 사용 시
    # password 필드가 마스크 그대로 넘어오기 때문
    # v90.55: job_id 지원 추가 (활성 Job 연결 자동 적용 시나리오)
    from app.core.password_resolver import resolve_password as _resolve
    password = _resolve(
        password,
        profile_id=body.get("profile_id") or body.get("profile"),
        job_id=body.get("job_id"),  # v90.55
        side=body.get("side", "source"),
        host=host, username=username, database=database,
    )

    # 지원 범위 우선 체크 (고객에게 정직하게 알림)
    info = get_info(db_type)
    if info is None:
        return {
            "success": False, "latency": None, "version": None,
            "message": f"알 수 없는 DB 유형: {db_type}",
        }
    if info["tier"] == SupportTier.PLANNED:
        return {
            "success": False, "latency": None, "version": None,
            "message": f"{info['label']}은(는) 아직 지원되지 않습니다 (로드맵 예정)",
        }

    # 기본 유효성 검사
    if not host:
        return {"success": False, "latency": None, "version": None, "message": "호스트를 입력하세요"}
    if not username and db_type != "sqlite":
        return {"success": False, "latency": None, "version": None, "message": "사용자명을 입력하세요"}
    if not database:
        return {"success": False, "latency": None, "version": None, "message": "데이터베이스명을 입력하세요"}

    # 실제 드라이버 연결 시도
    try:
        return _real_connect(db_type, host, int(port), username, password, database)
    except ImportError as e:
        # 드라이버 미설치 — 재현 가능한 에러 반환 (Mock 아님)
        return {
            "success": False, "latency": None, "version": None,
            "message": f"드라이버 미설치: {info.get('driver_module','?')} — pip install 필요 ({e})",
        }
    except NotImplementedError:
        return {
            "success": False, "latency": None, "version": None,
            "message": f"{info['label']}은(는) 현재 연결만 지원되거나 미구현 상태입니다",
        }
    except Exception as e:
        # 드라이버는 있는데 연결 실패 — 실제 에러 반환
        return {
            "success": False, "latency": None, "version": None,
            "message": f"연결 실패: {str(e)[:200]}",
        }


def _real_connect(db_type: str, host: str, port: int,
                  username: str, password: str, database: str) -> dict:
    """실제 드라이버로 연결 시도"""
    start = time.monotonic()

    if db_type in ("mysql", "aurora", "cloudsql", "tidb", "mariadb"):
        import pymysql
        conn = pymysql.connect(
            host=host, port=port, user=username, password=password,
            database=database, charset="utf8mb4", connect_timeout=8
        )
        cur = conn.cursor()
        cur.execute("SELECT VERSION()")
        ver = cur.fetchone()[0]
        conn.close()
        lat = round((time.monotonic() - start) * 1000, 1)
        return {"success": True, "latency": lat, "version": ver,
                "message": f"연결 성공 — MySQL {ver}"}

    elif db_type in ("mssql", "azure"):
        # make_mssql_conn: 드라이버 18→17→SQL Server 자동선택, Encrypt=no, 재시도 포함
        from app.core.db_conn import make_mssql_conn
        conn = make_mssql_conn(host, port, username, password, database, timeout=8)
        cur = conn.cursor()
        cur.execute("SELECT @@VERSION")
        ver = str(cur.fetchone()[0])[:80]
        conn.close()
        lat = round((time.monotonic() - start) * 1000, 1)
        return {"success": True, "latency": lat, "version": ver,
                "message": f"연결 성공 — SQL Server"}

    elif db_type == "postgresql":
        import psycopg2
        conn = psycopg2.connect(
            host=host, port=port, user=username, password=password,
            dbname=database, connect_timeout=8
        )
        cur = conn.cursor()
        cur.execute("SELECT version()")
        ver = cur.fetchone()[0][:80]
        conn.close()
        lat = round((time.monotonic() - start) * 1000, 1)
        return {"success": True, "latency": lat, "version": ver, "message": "연결 성공"}

    elif db_type == "sqlite":
        import sqlite3
        conn = sqlite3.connect(database)
        ver = f"SQLite {sqlite3.sqlite_version}"
        conn.close()
        lat = round((time.monotonic() - start) * 1000, 1)
        return {"success": True, "latency": lat, "version": ver, "message": "연결 성공"}

    else:
        raise NotImplementedError(f"드라이버 미구현: {db_type}")


# ── 프로파일 CRUD ─────────────────────────────────────────
#
# 보안 정책:
#  - 저장 시: password 필드를 Fernet으로 암호화 (app.core.crypto.encrypt).
#    클라이언트가 평문으로 POST/PUT 하더라도 디스크에는 암호문만 기록.
#  - 응답 시: password 필드를 마스킹(●●●●●●●●)하여 반환.
#    평문 비밀번호가 네트워크로 재전송되는 경로 자체를 제거.
#  - PUT에서 password가 마스크 문자열이면 "변경 없음"으로 해석 (기존 값 유지).
#    → 프론트에서 기존 프로파일 편집 시 password 필드를 비워도 기존 암호가 유지됨.
#  - 실제 DB 연결 코드(jobs.py, schema.py 등)는 _profiles.get()에서 꺼낸 뒤
#    decrypt()로 복호화하여 사용 — 저장/응답과 사용 경로가 분리됨.

from app.core.crypto import encrypt as _enc, decrypt as _dec, mask as _mask, is_encrypted as _is_enc

_MASK_TOKEN = "●●●●●●●●"  # 마스킹된 값을 프론트가 보낼 때 식별하는 토큰


def _encrypt_profile(p: dict) -> dict:
    """프로파일을 디스크 저장용으로 변환 — password 필드 암호화"""
    for side in ("source", "target"):
        if side in p and isinstance(p[side], dict):
            pw = p[side].get("password", "")
            if pw and not _is_enc(pw):
                p[side]["password"] = _enc(pw)
    return p


def _mask_profile_response(p: dict) -> dict:
    """API 응답용 — password를 마스킹 처리"""
    import copy
    out = copy.deepcopy(p)
    for side in ("source", "target"):
        if side in out and isinstance(out[side], dict):
            if out[side].get("password"):
                out[side]["password"] = _MASK_TOKEN
    return out


def _preserve_masked_passwords(new_body: dict, existing: dict) -> dict:
    """
    PUT 요청에서 password가 마스크 문자열이면 기존 암호문으로 복원.
    (사용자가 비밀번호를 바꾸지 않은 편집을 처리)
    """
    for side in ("source", "target"):
        if side in new_body and isinstance(new_body[side], dict):
            incoming_pw = new_body[side].get("password", "")
            if incoming_pw == _MASK_TOKEN or incoming_pw == "":
                # 기존 값 유지
                existing_pw = (existing.get(side) or {}).get("password", "")
                new_body[side]["password"] = existing_pw
    return new_body


@router.get("/profiles")
def list_profiles(_=Depends(require_viewer)):
    return [_mask_profile_response(p) for p in _profiles.values()]


@router.post("/profiles", status_code=201)
def create_profile(body: dict, request: Request, user=Depends(require_operator)):
    pid = str(uuid.uuid4())[:8]
    profile = {
        "id":         pid,
        "name":       body.get("name", "새 프로파일"),
        "source":     body.get("source", {}),
        "target":     body.get("target", {}),
        "created_at": datetime.now().isoformat(),
        "status":     "ok",
    }
    profile = _encrypt_profile(profile)
    _profiles.set(pid, profile)
    _audit.record(
        action=_AuditActions.PROFILE_CREATE, status="ok",
        user=user, resource="profile", resource_id=pid,
        ip=(request.client.host if request.client else None),
        details={"name": profile.get("name")},
    )
    return _mask_profile_response(profile)


@router.get("/profiles/{pid}")
def get_profile(pid: str, _=Depends(require_viewer)):
    p = _profiles.get(pid)
    if p is None:
        raise HTTPException(404, "프로파일을 찾을 수 없습니다")
    return _mask_profile_response(p)


@router.put("/profiles/{pid}")
def update_profile(pid: str, body: dict, request: Request, user=Depends(require_operator)):
    """프로파일 수정"""
    p = _profiles.get(pid)
    if p is None:
        raise HTTPException(404, "프로파일을 찾을 수 없습니다")
    if "name" in body: p["name"] = body["name"]
    # source/target은 마스크 처리된 password를 기존 값으로 복원한 뒤 병합
    body = _preserve_masked_passwords(body, p)
    if "source" in body: p["source"] = body["source"]
    if "target" in body: p["target"] = body["target"]
    p["updated_at"] = datetime.now().isoformat()
    p = _encrypt_profile(p)
    _profiles.set(pid, p)
    _audit.record(
        action=_AuditActions.PROFILE_UPDATE, status="ok",
        user=user, resource="profile", resource_id=pid,
        ip=(request.client.host if request.client else None),
        details={"changed_fields": [k for k in body.keys() if k in ("name","source","target")]},
    )
    return _mask_profile_response(p)


@router.delete("/profiles/{pid}", status_code=204)
def delete_profile(pid: str, request: Request, user=Depends(require_operator)):
    if pid not in _profiles:
        raise HTTPException(404, "프로파일을 찾을 수 없습니다")
    _profiles.delete(pid)
    _audit.record(
        action=_AuditActions.PROFILE_DELETE, status="ok",
        user=user, resource="profile", resource_id=pid,
        ip=(request.client.host if request.client else None),
    )


# ── 내부 사용: 복호화된 프로파일 반환 (DB 연결용) ─────────
def get_profile_decrypted(pid: str) -> dict | None:
    """
    다른 라우터/엔진이 실제 DB 연결에 사용할 때 호출.
    API 응답 경로에는 절대 노출되지 않음.
    """
    p = _profiles.get(pid)
    if p is None:
        return None
    import copy
    out = copy.deepcopy(p)
    for side in ("source", "target"):
        if side in out and isinstance(out[side], dict):
            pw = out[side].get("password", "")
            if _is_enc(pw):
                out[side]["password"] = _dec(pw)
    return out


# ── 지원 DB 정보 엔드포인트 (SSOT 노출) ───────────────────
@router.get("/supported-dbs")
def get_supported_dbs(_=Depends(require_viewer)):
    """
    프론트엔드가 DB 선택 UI를 렌더링할 때 호출하는 단일 진실 원천.
    각 항목에 tier 정보가 포함되어 UI가 아래와 같이 제어한다:
      - full    : 정상 선택 가능 (녹색 배지, 이관 시나리오에 포함)
      - connect : 선택 가능하되 이관은 불가 (노란 배지, "연결·조회만" 표시)
      - planned : 회색 처리·disabled (로드맵 배지)

    라이선스 정보도 함께 반환 — 클라이언트가 edition별 UI 차별화 가능.
    """
    from app.core.supported_dbs import all_dbs
    from app.core.license import get_license
    lic = get_license()
    return {
        "dbs": all_dbs(),
        "license": {
            "edition": lic.edition,
            "tier2_tier3_allowed": lic.feature("tier2_tier3_dbs", False),
        },
    }


@router.post("/migration-compatible")
def check_migration_compatible(body: dict):
    """
    src/tgt DB 조합이 이관 가능한지 판정.
    프론트에서 Job Wizard 등에서 호출하여 경로 조합 검증.
    body: { src_db, tgt_db }
    """
    from app.core.supported_dbs import is_migration_supported, get_info
    src = (body.get("src_db") or "").lower()
    tgt = (body.get("tgt_db") or "").lower()
    ok  = is_migration_supported(src, tgt)
    reason = None
    if not ok:
        s = get_info(src); t = get_info(tgt)
        if not s or not t:
            reason = "알 수 없는 DB 유형"
        elif s["tier"] != "full" and not hasattr(s["tier"], "value"):
            reason = f"{s['label']}은(는) 이관 소스로 지원되지 않습니다"
        else:
            # tier enum인 경우 문자열 비교
            s_tier = s["tier"].value if hasattr(s["tier"], "value") else s["tier"]
            t_tier = t["tier"].value if hasattr(t["tier"], "value") else t["tier"]
            if s_tier != "full":
                reason = f"{s['label']}은(는) 이관 소스로 지원되지 않습니다 (현재 tier={s_tier})"
            elif t_tier != "full":
                reason = f"{t['label']}은(는) 이관 타겟으로 지원되지 않습니다 (현재 tier={t_tier})"
    return {"compatible": ok, "reason": reason}


# ════════════════════════════════════════════════════════════════════════════
# v90.55 신규: 활성 Job 의 연결정보를 connector store 로 가져오는 endpoint
# ════════════════════════════════════════════════════════════════════════════
# 본부장님 시나리오: 검증 화면(Validate.vue) 진입 시 이관 진행 중인 Job 이 있으면
# 그 연결정보를 자동으로 connector store 에 채워서 별도 연결 작업 없이 검증 가능.
#
# 보안 원칙 (v9 패치 #5 의 profile 패턴 동일):
#   - 응답에는 password 마스킹 (●●●●●●●●)
#   - 실제 password 는 backend 가 job_id 로 자동 복원 (password_resolver)
#   - frontend 는 connector store 에 src/tgt host/port/db 등 표시용 정보만 보관
@router.get("/from-job/{job_id}")
def get_connection_from_job(job_id: str, _user=Depends(require_viewer)):
    """
    Job ID 로 src/tgt 연결정보 반환 (password 마스킹).
    
    검증 화면 등에서 활성 Job 의 연결정보를 connector store 에 적용할 때 사용.
    실제 검증 API 호출 시는 job_id 만 전달하면 backend 가 password 자동 복원.
    
    Returns:
        { "job_id": "...", "name": "...", "source": {...}, "target": {...} }
        (password 필드는 MASK_TOKEN 으로 표시)
    """
    from app.engine.security import MASK_TOKEN
    
    _jobs_store = Store("jobs")
    job = _jobs_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    
    def _build_side(prefix: str, default_db: str) -> dict:
        """src_xxx 또는 tgt_xxx 키들을 표시용 dict 로 변환."""
        return {
            "db_type":  job.get(f"{prefix}_db", default_db),
            "host":     job.get(f"{prefix}_host", ""),
            "port":     job.get(f"{prefix}_port", 0),
            "username": job.get(f"{prefix}_username", ""),
            "password": MASK_TOKEN if job.get(f"{prefix}_password") else "",
            "database": job.get(f"{prefix}_database", ""),
            "version":  job.get(f"{prefix}_version", ""),
        }
    
    return {
        "job_id":  job_id,
        "name":    job.get("name", ""),
        "status":  job.get("status", ""),
        "source":  _build_side("src", "mysql"),
        "target":  _build_side("tgt", "mssql"),
    }
