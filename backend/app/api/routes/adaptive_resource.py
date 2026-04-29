"""
adaptive_resource.py — Phase I-6 (2026-04-25)

Adaptive Resource Controller 의 REST + WebSocket API.

엔드포인트:
  GET  /api/v1/jobs/{job_id}/resource/status     — 현재 상태
  POST /api/v1/jobs/{job_id}/resource/throttle    — 수동 throttle 변경
  POST /api/v1/jobs/{job_id}/resource/mode        — 모드 변경 (AUTO/MANUAL/HYBRID)
  POST /api/v1/jobs/{job_id}/resource/pause       — 테이블 일시정지
  POST /api/v1/jobs/{job_id}/resource/resume      — 테이블 재개
  GET  /api/v1/jobs/{job_id}/resource/decisions   — 의사결정 로그 (audit)
  WS   /api/v1/jobs/{job_id}/resource/stream      — 실시간 메트릭 + 결정 스트림

작동 방식:
  - 이관 엔진이 job 별로 AdaptiveResourceController 인스턴스 보유
  - 이 모듈은 그 인스턴스에 접근하는 API 만 제공
  - WebSocket 은 각 tick 마다 메트릭 + 결정 push
"""

from __future__ import annotations
import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Body
from pydantic import BaseModel, Field

_log = logging.getLogger("databridge.api.adaptive_resource")

router = APIRouter(prefix="/jobs/{job_id}/resource", tags=["Adaptive Resource Control"])


# ════════════════════════════════════════════════════════════════════════════
# 요청 모델
# ════════════════════════════════════════════════════════════════════════════

class ThrottleRequest(BaseModel):
    """수동 throttle 변경"""
    throttle_pct: int = Field(..., ge=10, le=100, description="10~100%")
    user: Optional[str] = Field("anonymous")


class ModeRequest(BaseModel):
    """제어 모드 변경"""
    mode: str = Field(..., pattern="^(auto|manual|hybrid)$")
    user: Optional[str] = Field("anonymous")


class PauseRequest(BaseModel):
    """테이블 일시정지/재개"""
    table_name: str
    user: Optional[str] = Field("anonymous")


# ════════════════════════════════════════════════════════════════════════════
# 컨트롤러 접근 헬퍼
# ════════════════════════════════════════════════════════════════════════════

def _get_controller(job_id: str):
    """
    Job 의 AdaptiveResourceController 인스턴스 반환.
    
    실제 구현: migration_engine 인스턴스 레지스트리에서 조회.
    
    v90.21: 미연결 상태 fallback - 메모리 저장소로 자동 생성
    → migration_engine 통합 (Phase I-1) 전에도 UI 가 작동하도록
    """
    # 1차: migration_engine 의 정식 레지스트리 조회
    try:
        from app.engine import migration_engine as me
        registry = getattr(me, '_ENGINE_REGISTRY', {})
        engine = registry.get(job_id)
        if engine and hasattr(engine, 'adaptive_controller'):
            return engine.adaptive_controller
    except Exception:
        pass
    
    # 2차 (v90.21): 메모리 저장소 fallback
    #   migration_engine 통합 미완성 시 stub controller 자동 생성
    #   → UI 클릭이 즉시 반응하도록
    if not hasattr(_get_controller, '_fallback_registry'):
        _get_controller._fallback_registry = {}
    
    if job_id in _get_controller._fallback_registry:
        return _get_controller._fallback_registry[job_id]
    
    # 자동 생성 (stub)
    try:
        from app.core.adaptive_resource_controller import (
            AdaptiveResourceController, ControlPolicy, ControlMode
        )
        # 시그니처: __init__(src_conn, tgt_conn, initial_policy, on_decision)
        ctrl = AdaptiveResourceController(
            src_conn=None,
            tgt_conn=None,
            initial_policy=ControlPolicy(mode=ControlMode.HYBRID),
        )
        # job_id 보관 (디버깅용)
        ctrl._fallback_job_id = job_id
        _get_controller._fallback_registry[job_id] = ctrl
        _log.info(f"[adaptive] Job '{job_id}' fallback controller 자동 생성 (메모리 저장소)")
        return ctrl
    except Exception as e:
        _log.warning(f"[adaptive] fallback controller 생성 실패: {e}")
        import traceback
        _log.warning(traceback.format_exc())
        return None


def _ensure_controller(job_id: str):
    """컨트롤러 없으면 404"""
    ctrl = _get_controller(job_id)
    if not ctrl:
        raise HTTPException(
            404, 
            f"Job '{job_id}' 의 Adaptive Resource Controller 가 활성화되지 않았습니다. "
            "백엔드 재시작 후 다시 시도해주세요."
        )
    return ctrl


# ════════════════════════════════════════════════════════════════════════════
# REST 엔드포인트
# ════════════════════════════════════════════════════════════════════════════

@router.get("/status")
async def get_status(job_id: str):
    """현재 상태 조회 (UI 폴링용 또는 초기 로드)"""
    ctrl = _ensure_controller(job_id)
    return ctrl.get_status()


@router.post("/throttle")
async def set_throttle(job_id: str, req: ThrottleRequest):
    """수동 throttle 변경"""
    ctrl = _ensure_controller(job_id)
    decision = ctrl.manual_set_throttle(req.throttle_pct, user=req.user or "anonymous")
    return {
        "success": True,
        "decision_id": decision.decision_id,
        "from": decision.from_value,
        "to": decision.to_value,
        "policy": ctrl.get_status()["policy"],
    }


@router.post("/mode")
async def set_mode(job_id: str, req: ModeRequest):
    """제어 모드 변경"""
    from app.core.adaptive_resource_controller import ControlMode
    ctrl = _ensure_controller(job_id)
    
    try:
        mode = ControlMode(req.mode)
    except ValueError:
        raise HTTPException(400, f"잘못된 모드: {req.mode}")
    
    decision = ctrl.set_mode(mode, user=req.user or "anonymous")
    return {
        "success": True,
        "mode": mode.value,
        "policy": ctrl.get_status()["policy"],
    }


@router.post("/pause")
async def pause_table(job_id: str, req: PauseRequest):
    """특정 테이블 일시정지"""
    ctrl = _ensure_controller(job_id)
    decision = ctrl.manual_pause_table(req.table_name, user=req.user or "anonymous")
    return {
        "success": True,
        "table_name": req.table_name,
        "paused_tables": list(ctrl.policy.paused_tables),
    }


@router.post("/resume")
async def resume_table(job_id: str, req: PauseRequest):
    """테이블 재개"""
    ctrl = _ensure_controller(job_id)
    decision = ctrl.manual_resume_table(req.table_name, user=req.user or "anonymous")
    return {
        "success": True,
        "table_name": req.table_name,
        "paused_tables": list(ctrl.policy.paused_tables),
    }


@router.get("/decisions")
async def get_decisions(job_id: str, limit: int = 100):
    """의사결정 로그 (audit)"""
    ctrl = _ensure_controller(job_id)
    return {
        "decisions": ctrl.get_decisions_log(limit=limit),
        "total": len(ctrl.decisions_log),
    }


# ════════════════════════════════════════════════════════════════════════════
# WebSocket 스트림
# ════════════════════════════════════════════════════════════════════════════

@router.websocket("/stream")
async def stream_metrics(websocket: WebSocket, job_id: str):
    """
    실시간 메트릭 + 결정 스트림.
    
    1초마다 push:
      {
        "type": "snapshot",
        "data": {
          "timestamp": 1714000000.0,
          "src_cpu_pct": 65.5,
          "container_cpu_pct": 70.0,
          "src_lock_wait_count": 12,
          "current_batch_size": 5000,
          ...
        }
      }
    
    AI 결정 발생 시 push:
      {
        "type": "decision",
        "data": {
          "action": "set_throttle",
          "from": 100,
          "to": 50,
          "reason": "CRITICAL — CPU 92%",
          "triggered_by": "ai",
          "confidence": 0.9
        }
      }
    """
    await websocket.accept()
    
    ctrl = _get_controller(job_id)
    if not ctrl:
        await websocket.send_json({
            "type": "error",
            "message": f"Job '{job_id}' 의 ARC 가 활성화 안 됨"
        })
        await websocket.close()
        return
    
    last_decision_count = len(ctrl.decisions_log)
    
    try:
        while True:
            # 최신 스냅샷 push
            history = list(ctrl.collector._history)
            if history:
                latest = history[-1]
                await websocket.send_json({
                    "type": "snapshot",
                    "data": {
                        "timestamp": latest.timestamp,
                        "src_cpu_pct": latest.src_cpu_pct,
                        "src_mem_pct": latest.src_mem_pct,
                        "src_threads_running": latest.src_threads_running,
                        "src_threads_connected": latest.src_threads_connected,
                        "src_lock_wait_count": latest.src_lock_wait_count,
                        "tgt_cpu_pct": latest.tgt_cpu_pct,
                        "tgt_threads_running": latest.tgt_threads_running,
                        "tgt_replication_lag_sec": latest.tgt_replication_lag_sec,
                        "container_cpu_pct": latest.container_cpu_pct,
                        "container_mem_pct": latest.container_mem_pct,
                        "current_batch_size": latest.current_batch_size,
                        "current_parallelism": latest.current_parallelism,
                        "rows_per_sec": latest.rows_per_sec,
                        "progress_pct": latest.progress_pct,
                    }
                })
            
            # 정책 push
            await websocket.send_json({
                "type": "policy",
                "data": ctrl.get_status()["policy"],
            })
            
            # 새 결정 push (지난 push 이후 추가된 것만)
            current_count = len(ctrl.decisions_log)
            if current_count > last_decision_count:
                new_decisions = ctrl.decisions_log[last_decision_count:current_count]
                for d in new_decisions:
                    await websocket.send_json({
                        "type": "decision",
                        "data": {
                            "decision_id": d.decision_id,
                            "timestamp": d.timestamp,
                            "action": d.action,
                            "target": d.target,
                            "from": d.from_value,
                            "to": d.to_value,
                            "reason": d.reason,
                            "triggered_by": d.triggered_by,
                            "confidence": d.confidence,
                            "health_status": d.health_status.value if d.health_status else None,
                        }
                    })
                last_decision_count = current_count
            
            await asyncio.sleep(1)  # 1초 간격
    
    except WebSocketDisconnect:
        _log.info(f"[ARC WebSocket] Job {job_id} 클라이언트 연결 종료")
    except Exception as e:
        _log.warning(f"[ARC WebSocket] Job {job_id} 에러: {e}")
        try:
            await websocket.close()
        except Exception:
            pass
