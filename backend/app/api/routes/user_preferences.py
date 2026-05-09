"""
user_preferences.py — 사용자별 환경설정 (v90.1)

저장 항목:
  - scenario_history: 최근 사용한 이관 시나리오 (최대 10개)
  - 향후: 즐겨찾기, UI 설정 등

엔드포인트:
  GET  /api/v1/user/preferences/scenarios     사용자 시나리오 이력 조회
  POST /api/v1/user/preferences/scenarios     시나리오 사용 기록 추가
  DELETE /api/v1/user/preferences/scenarios   이력 전체 삭제 (옵션)
"""
from __future__ import annotations
import logging
import time
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth_deps import current_user
from app.core.store import Store

logger = logging.getLogger("databridge.user_pref")
router = APIRouter()

# ─── Pydantic 모델 ────────────────────────────────────────────
class ScenarioHistoryItem(BaseModel):
    scenario_id: str = Field(..., description="시나리오 ID (예: 'prod_to_dev')")
    used_at: float = Field(..., description="사용 시점 timestamp (epoch sec)")
    use_count: int = Field(default=1, description="누적 사용 횟수")


class ScenarioHistoryResponse(BaseModel):
    items: List[ScenarioHistoryItem]
    recent: List[ScenarioHistoryItem] = Field(
        default=[], description="최근 사용 N개 (자주 사용 우선)"
    )


class RecordScenarioRequest(BaseModel):
    scenario_id: str


# ─── 저장소 키 패턴 ───────────────────────────────────────────
# preferences.json:
#   {
#     "users": {
#       "<username>": {
#         "scenario_history": [
#           {"scenario_id": "prod_to_dev", "used_at": 1729872345.123, "use_count": 5},
#           ...
#         ]
#       }
#     }
#   }

PREFS_STORE = "preferences"
MAX_HISTORY = 10  # 최대 10개 시나리오 기록


def _get_user_history(username: str) -> List[dict]:
    """사용자의 시나리오 이력 가져오기 (없으면 빈 배열)"""
    try:
        store = Store(PREFS_STORE)
        users = store.get("users", {}) or {}
        user_data = users.get(username, {})
        return user_data.get("scenario_history", []) or []
    except Exception as e:
        logger.warning(f"_get_user_history 실패 ({username}): {e}")
        return []


def _save_user_history(username: str, history: List[dict]) -> None:
    """사용자의 시나리오 이력 저장"""
    try:
        store = Store(PREFS_STORE)
        users = store.get("users", {}) or {}
        if username not in users:
            users[username] = {}
        users[username]["scenario_history"] = history
        store.set("users", users)
    except Exception as e:
        logger.error(f"_save_user_history 실패 ({username}): {e}")
        raise


# ─── API 엔드포인트 ───────────────────────────────────────────
@router.get("/scenarios", response_model=ScenarioHistoryResponse)
def get_scenario_history(user=Depends(current_user)):
    """
    현재 사용자의 시나리오 사용 이력 조회.
    
    - items: 모든 이력 (최근 사용 순)
    - recent: 최근 2개 (Step 0 큰 카드용)
    """
    username = user.get("username") or user.get("id") or "anonymous"
    history = _get_user_history(username)
    
    # 최근 사용 순 정렬 (used_at 내림차순)
    sorted_items = sorted(
        history, key=lambda x: x.get("used_at", 0), reverse=True
    )
    
    # 모델로 변환
    items = [ScenarioHistoryItem(**h) for h in sorted_items]
    
    # 최근 2개 (UI 의 큰 카드 영역용)
    recent = items[:2]
    
    return ScenarioHistoryResponse(items=items, recent=recent)


@router.post("/scenarios", response_model=ScenarioHistoryResponse)
def record_scenario_use(
    body: RecordScenarioRequest,
    user=Depends(current_user),
):
    """
    시나리오 사용 기록.
    
    동작:
    - 같은 scenario_id 가 이미 있으면 used_at 갱신 + use_count++
    - 없으면 새 항목 추가
    - 최대 MAX_HISTORY 개까지만 유지 (가장 오래된 것 제거)
    """
    username = user.get("username") or user.get("id") or "anonymous"
    scenario_id = body.scenario_id.strip()
    
    if not scenario_id:
        raise HTTPException(400, "scenario_id 가 비어있음")
    
    history = _get_user_history(username)
    now = time.time()
    
    # 기존 항목 찾기
    existing = next(
        (i for i, h in enumerate(history) if h.get("scenario_id") == scenario_id),
        None
    )
    
    if existing is not None:
        # 갱신
        history[existing]["used_at"] = now
        history[existing]["use_count"] = history[existing].get("use_count", 0) + 1
    else:
        # 신규 추가
        history.append({
            "scenario_id": scenario_id,
            "used_at": now,
            "use_count": 1,
        })
    
    # 최근 사용 순으로 정렬
    history.sort(key=lambda x: x.get("used_at", 0), reverse=True)
    
    # 최대 MAX_HISTORY 개 유지
    if len(history) > MAX_HISTORY:
        history = history[:MAX_HISTORY]
    
    _save_user_history(username, history)
    logger.info(f"[scenario] {username} 사용: {scenario_id} (count={history[0].get('use_count')})")
    
    items = [ScenarioHistoryItem(**h) for h in history]
    return ScenarioHistoryResponse(items=items, recent=items[:2])


@router.delete("/scenarios")
def clear_scenario_history(user=Depends(current_user)):
    """사용자의 시나리오 이력 전체 삭제"""
    username = user.get("username") or user.get("id") or "anonymous"
    _save_user_history(username, [])
    logger.info(f"[scenario] {username} 이력 삭제")
    return {"ok": True, "message": "이력 삭제 완료"}


# ════════════════════════════════════════════════════════════════
# v95_p89_ux (2026-05-07 본부장님 본질 처방): 개별 시나리오 이력 삭제
# ════════════════════════════════════════════════════════════════
# 본부장님 비전: 카드 우하단 ✕ 버튼 → 안 쓰는 시나리오 제거
# ════════════════════════════════════════════════════════════════
@router.delete("/scenarios/{scenario_id}", response_model=ScenarioHistoryResponse)
def delete_scenario_history_item(scenario_id: str, user=Depends(current_user)):
    """특정 시나리오 1건만 이력에서 제거"""
    username = user.get("username") or user.get("id") or "anonymous"
    history = _get_user_history(username)
    before_n = len(history)
    history = [h for h in history if h.get("scenario_id") != scenario_id]
    after_n = len(history)
    if before_n != after_n:
        _save_user_history(username, history)
        logger.info(f"[scenario] {username} 이력에서 '{scenario_id}' 제거 ({before_n} → {after_n})")
    return ScenarioHistoryResponse(
        items=[ScenarioHistoryItem(**h) for h in history]
    )


# ════════════════════════════════════════════════════════════════
# v90.2: DB 사용 이력 (소스/타겟 각각)
# ════════════════════════════════════════════════════════════════
class DbHistoryItem(BaseModel):
    db_type: str = Field(..., description="DB 타입 (예: 'mysql', 'mssql')")
    side: str = Field(..., description="'source' or 'target'")
    used_at: float
    use_count: int = Field(default=1)


class DbHistoryResponse(BaseModel):
    source_history: List[DbHistoryItem] = Field(default=[])
    target_history: List[DbHistoryItem] = Field(default=[])


class RecordDbRequest(BaseModel):
    db_type: str
    side: str  # 'source' or 'target'


def _get_user_db_history(username: str, side: str) -> List[dict]:
    """사용자의 DB 사용 이력 (side: source/target)"""
    try:
        store = Store(PREFS_STORE)
        users = store.get("users", {}) or {}
        user_data = users.get(username, {})
        key = f"db_history_{side}"
        return user_data.get(key, []) or []
    except Exception as e:
        logger.warning(f"_get_user_db_history 실패 ({username}/{side}): {e}")
        return []


def _save_user_db_history(username: str, side: str, history: List[dict]) -> None:
    try:
        store = Store(PREFS_STORE)
        users = store.get("users", {}) or {}
        if username not in users:
            users[username] = {}
        users[username][f"db_history_{side}"] = history
        store.set("users", users)
    except Exception as e:
        logger.error(f"_save_user_db_history 실패 ({username}/{side}): {e}")
        raise


@router.get("/dbs", response_model=DbHistoryResponse)
def get_db_history(user=Depends(current_user)):
    """소스/타겟 DB 사용 이력 조회 (자주 사용 우선)"""
    username = user.get("username") or user.get("id") or "anonymous"
    src = _get_user_db_history(username, "source")
    tgt = _get_user_db_history(username, "target")
    
    # 사용 횟수(많은 것 우선) + 최근 사용(최신 우선) 조합 정렬
    def _sort(items):
        return sorted(
            items,
            key=lambda x: (x.get("use_count", 0), x.get("used_at", 0)),
            reverse=True,
        )
    
    return DbHistoryResponse(
        source_history=[DbHistoryItem(**h) for h in _sort(src)],
        target_history=[DbHistoryItem(**h) for h in _sort(tgt)],
    )


@router.post("/dbs", response_model=DbHistoryResponse)
def record_db_use(body: RecordDbRequest, user=Depends(current_user)):
    """DB 사용 기록 (위저드에서 connection 성공 시 호출)"""
    username = user.get("username") or user.get("id") or "anonymous"
    db_type = body.db_type.strip().lower()
    side = body.side.strip().lower()
    
    if not db_type or side not in ("source", "target"):
        raise HTTPException(400, "db_type 또는 side 가 잘못됨")
    
    history = _get_user_db_history(username, side)
    now = time.time()
    
    existing = next(
        (i for i, h in enumerate(history) if h.get("db_type") == db_type),
        None
    )
    if existing is not None:
        history[existing]["used_at"] = now
        history[existing]["use_count"] = history[existing].get("use_count", 0) + 1
    else:
        history.append({
            "db_type": db_type,
            "side": side,
            "used_at": now,
            "use_count": 1,
        })
    
    history.sort(key=lambda x: (x.get("use_count", 0), x.get("used_at", 0)), reverse=True)
    if len(history) > 20:
        history = history[:20]
    
    _save_user_db_history(username, side, history)
    logger.info(f"[db] {username} 사용: {db_type} ({side}) count={history[0].get('use_count')}")
    
    return get_db_history(user=user)
