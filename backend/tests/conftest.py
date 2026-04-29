"""
backend/tests/conftest.py — 공통 pytest fixture
v10 #21

핵심 fixture:
  - isolated_store: 각 테스트마다 임시 SQLite 로 격리 (실제 DB 안 건드림)
  - app_client:     FastAPI TestClient (통합 테스트용)
"""
import os
import sys
import tempfile
import pytest
from pathlib import Path

# backend/ 를 import 경로에 추가
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture
def tmp_data_dir(monkeypatch, tmp_path):
    """
    app.core.store 의 데이터 디렉토리를 임시 폴더로 리다이렉트.
    각 테스트가 독립된 SQLite 를 쓰도록 보장.
    """
    # 모든 관련 모듈을 sys.modules 에서 제거
    to_remove = [m for m in sys.modules.keys()
                 if m == "app.core.store"
                 or m.startswith("app.engine.conversion_learner")
                 or m.startswith("app.core.audit")
                 or m.startswith("app.api.routes.mapping")
                 or m.startswith("app.api.routes.obj_mapping")]
    for m in to_remove:
        del sys.modules[m]

    # 부모 패키지의 attribute 도 제거 — `from app.engine import conversion_learner` 가
    # sys.modules 에 없어도 패키지 attr 에서 찾아 같은 인스턴스를 반환하는 문제 방지.
    _clear_package_attr("app.engine", "conversion_learner")
    _clear_package_attr("app.core", "audit")
    _clear_package_attr("app.core", "store")
    _clear_package_attr("app.api.routes", "mapping")
    _clear_package_attr("app.api.routes", "obj_mapping")

    # store 를 fresh import 하면서 _DATA_DIR 교체
    import app.core.store as store_mod
    store_mod._DATA_DIR = tmp_path
    store_mod._DB_PATH = tmp_path / "databridge.db"
    store_mod._MIGRATED_DIR = tmp_path / "_migrated"
    store_mod._registry.clear()
    store_mod._migrated_names.clear()
    if hasattr(store_mod._tls, "conn") and store_mod._tls.conn is not None:
        try:
            store_mod._tls.conn.close()
        except Exception:
            pass
        store_mod._tls.conn = None

    yield tmp_path

    # teardown
    if hasattr(store_mod._tls, "conn") and store_mod._tls.conn is not None:
        try:
            store_mod._tls.conn.close()
        except Exception:
            pass
        store_mod._tls.conn = None
    store_mod._registry.clear()
    store_mod._migrated_names.clear()
    for m in list(sys.modules.keys()):
        if (m.startswith("app.engine.conversion_learner")
            or m.startswith("app.core.audit")
            or m.startswith("app.api.routes.mapping")
            or m.startswith("app.api.routes.obj_mapping")):
            del sys.modules[m]
    _clear_package_attr("app.engine", "conversion_learner")
    _clear_package_attr("app.core", "audit")
    _clear_package_attr("app.api.routes", "mapping")
    _clear_package_attr("app.api.routes", "obj_mapping")


def _clear_package_attr(pkg_name: str, attr: str):
    """부모 패키지에 남아있는 모듈 attribute 제거."""
    pkg = sys.modules.get(pkg_name)
    if pkg is not None and hasattr(pkg, attr):
        try:
            delattr(pkg, attr)
        except Exception:
            pass


@pytest.fixture
def learner_clean(tmp_data_dir):
    """
    conversion_learner 가 새 DATA_DIR 기준으로 Store 재초기화.
    Store 싱글턴 레지스트리도 완전 초기화해야 이전 테스트의 _type_rules 가 남지 않음.
    """
    import app.core.store as store_mod
    # Store 싱글턴 레지스트리 완전 비우기 (tmp_data_dir 가 이미 clear 했지만 안전하게)
    store_mod._registry.clear()
    store_mod._migrated_names.clear()

    # conversion_learner 관련 모듈 전부 제거 (재import 강제)
    for mod in list(sys.modules.keys()):
        if mod.startswith("app.engine.conversion_learner"):
            del sys.modules[mod]
    from app.engine import conversion_learner
    yield conversion_learner


@pytest.fixture
def audit_clean(tmp_data_dir):
    """audit 모듈 재초기화 — Store 싱글턴 + 해시 체인 캐시 전부 리셋."""
    import app.core.store as store_mod
    store_mod._registry.clear()
    store_mod._migrated_names.clear()

    for mod in list(sys.modules.keys()):
        if mod.startswith("app.core.audit"):
            del sys.modules[mod]
    from app.core import audit
    audit._last_hash = None
    yield audit
