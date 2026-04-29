"""
scheduler/engine.py
DataBridge Studio — APScheduler 기반 스케줄 실행 엔진

지원 스케줄 타입:
  once     : 특정 일시 1회 실행
  interval : n분 간격 반복 실행
  cron     : cron 표현식 반복 실행 (예: "0 2 * * *" → 매일 새벽 2시)
"""
import logging
import threading
from datetime import datetime, timezone

logger = logging.getLogger("databridge.scheduler")

# APScheduler 임포트 (없으면 폴백)
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron    import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.date    import DateTrigger
    HAS_APS = True
except ImportError:
    HAS_APS = False
    logger.warning("APScheduler 미설치 — 스케줄 반복 실행 불가 (once 타입만 지원)")


class SchedulerEngine:
    """
    DataBridge 스케줄 엔진
    - APScheduler BackgroundScheduler 래퍼
    - once/interval/cron 타입 지원
    - pause/resume/delete 지원
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._scheduler = None
        self._run_fn = None   # jobs.py의 _run_scheduled 주입

        if HAS_APS:
            self._scheduler = BackgroundScheduler(timezone="Asia/Seoul")
            self._scheduler.start()
            logger.info("APScheduler 시작됨 (Asia/Seoul)")

    def set_run_fn(self, fn):
        """jobs.py의 _run_scheduled 함수를 주입"""
        self._run_fn = fn

    # ── 스케줄 등록 ──────────────────────────────────────────────
    def add(self, sid: str, sch: dict):
        """스케줄 등록. APScheduler 없으면 once 타입만 threading으로 처리."""
        if sch.get("status") == "paused":
            return

        stype = sch.get("type", "once")

        if not HAS_APS:
            # APScheduler 없으면 once만 지원
            if stype == "once":
                self._add_once_fallback(sid, sch)
            else:
                logger.warning("[%s] APScheduler 미설치로 %s 스케줄 등록 불가", sid, stype)
            return

        try:
            if stype == "once":
                run_at = sch.get("run_at", "")
                if not run_at:
                    return
                dt = datetime.fromisoformat(run_at.replace("Z", "+00:00"))
                trigger = DateTrigger(run_date=dt)

            elif stype == "interval":
                minutes = int(sch.get("interval_min", 60))
                trigger = IntervalTrigger(minutes=minutes)

            elif stype == "cron":
                expr = sch.get("cron_expr", "").strip()
                if not expr:
                    return
                parts = expr.split()
                if len(parts) == 5:
                    minute, hour, day, month, day_of_week = parts
                    trigger = CronTrigger(
                        minute=minute, hour=hour, day=day,
                        month=month, day_of_week=day_of_week,
                        timezone="Asia/Seoul"
                    )
                else:
                    logger.error("[%s] cron 표현식 오류: %s", sid, expr)
                    return
            else:
                logger.warning("[%s] 알 수 없는 스케줄 타입: %s", sid, stype)
                return

            job_id = f"sch_{sid}"
            # 기존 job 있으면 제거
            if self._scheduler.get_job(job_id):
                self._scheduler.remove_job(job_id)

            self._scheduler.add_job(
                func=self._execute,
                trigger=trigger,
                id=job_id,
                args=[sid],
                name=sch.get("name", sid),
                misfire_grace_time=300,  # 5분 이내 지연 허용
                replace_existing=True,
            )
            logger.info("[%s] 스케줄 등록: type=%s", sid, stype)

        except Exception as e:
            logger.error("[%s] 스케줄 등록 실패: %s", sid, e)

    def _add_once_fallback(self, sid: str, sch: dict):
        """APScheduler 없을 때 threading으로 once 처리"""
        import time
        run_at = sch.get("run_at", "")
        if not run_at:
            return
        try:
            target = datetime.fromisoformat(run_at.replace("Z", ""))
            diff = (target - datetime.utcnow()).total_seconds()
            if diff <= 0:
                self._execute(sid)
            else:
                def delayed():
                    time.sleep(max(0, diff))
                    self._execute(sid)
                threading.Thread(target=delayed, daemon=True).start()
        except Exception as e:
            logger.error("[%s] once 폴백 실패: %s", sid, e)

    # ── 실행 ─────────────────────────────────────────────────────
    def _execute(self, sid: str):
        """스케줄 실행 — jobs.py의 _run_scheduled 호출"""
        logger.info("[%s] 스케줄 실행 시작", sid)
        if self._run_fn:
            try:
                self._run_fn(sid, None)
            except Exception as e:
                logger.error("[%s] 스케줄 실행 오류: %s", sid, e)
        else:
            logger.error("[%s] run_fn 미등록 — 실행 불가", sid)

    # ── 제어 ─────────────────────────────────────────────────────
    def pause(self, sid: str):
        if not HAS_APS or not self._scheduler:
            return
        job = self._scheduler.get_job(f"sch_{sid}")
        if job:
            job.pause()
            logger.info("[%s] 스케줄 일시정지", sid)

    def resume(self, sid: str):
        if not HAS_APS or not self._scheduler:
            return
        job = self._scheduler.get_job(f"sch_{sid}")
        if job:
            job.resume()
            logger.info("[%s] 스케줄 재개", sid)

    def remove(self, sid: str):
        if not HAS_APS or not self._scheduler:
            return
        job_id = f"sch_{sid}"
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)
            logger.info("[%s] 스케줄 제거", sid)

    def next_run(self, sid: str) -> str:
        """다음 실행 예정 시각 반환 — KST 문자열 (Z 없음, 이미 KST)"""
        if not HAS_APS or not self._scheduler:
            return ""
        job = self._scheduler.get_job(f"sch_{sid}")
        if job and job.next_run_time:
            from datetime import timezone, timedelta
            kst = job.next_run_time.astimezone(timezone(timedelta(hours=9)))
            # Z 없이 반환 → dateUtils에서 KST 그대로 표시
            return kst.strftime("%Y-%m-%dT%H:%M:%S")
        return ""

    def get_status(self, sid: str) -> str:
        """APScheduler job 상태 반환"""
        if not HAS_APS or not self._scheduler:
            return "unknown"
        job = self._scheduler.get_job(f"sch_{sid}")
        if not job:
            return "removed"
        return "paused" if job.next_run_time is None else "active"

    def shutdown(self):
        if HAS_APS and self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("APScheduler 종료됨")

    def load_existing(self, schedules: list):
        """앱 재시작 시 기존 활성 스케줄 복원"""
        for sch in schedules:
            if sch.get("status") not in ("done", "error", "paused", "deleted"):
                self.add(sch["id"], sch)
        logger.info("기존 스케줄 %d개 복원", len(schedules))


# ── 싱글톤 ───────────────────────────────────────────────────────
_engine = SchedulerEngine()


def get_engine() -> SchedulerEngine:
    return _engine
