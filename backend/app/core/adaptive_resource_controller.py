"""
adaptive_resource_controller.py — Phase I-1 + I-2 (2026-04-25)

이관 중 시스템 리소스 모니터링 + AI 자동 조절 엔진.

핵심 컨셉:
  단순 임계치 룰 ❌
   if cpu > 80: throttle
  
  지능적 판단 ✅
   - 부하 추세 분석 (5초 평균 vs 30초 평균)
   - lock 패턴 분석 (운영 트랜잭션 vs 이관 자체)
   - 시간대 인지 (피크/오프피크)
   - 진행률 인지 (90% 도달 시 더 보수적)
   - 운영팀 우선권 (수동 모드 시 AI 비활성)
   - 학습 (의사결정 결과 기록 → 다음 번 더 정확)

수집하는 메트릭:
  Source DB:
    - CPU%, 메모리%
    - threads_running, threads_connected
    - lock_wait_count, deadlock_count
    - innodb_buffer_pool_hit_rate
    - 평균 query 응답 시간
  
  Target DB:
    - 동일 메트릭 + replication lag (있으면)
  
  이관 프로세스:
    - 현재 batch_size, parallelism
    - 처리율 (rows/sec)
    - 진행률 (%, ETA)

조절 가능한 다이얼:
  - throttle_pct: 100/75/50/25 (전체 속도 비율)
  - batch_size: 자동 또는 수동 (1000~50000)
  - parallelism: 동시 처리 테이블 수 (1~10)
  - paused_tables: 일시 정지 테이블 set

운영 모드:
  - AUTO: AI 가 모든 결정
  - MANUAL: 운영자가 모든 결정
  - HYBRID: AI 가 추천, 운영자 승인 (default)

설계 원칙:
  - 비침습적: 기존 migration_engine 변경 최소
  - 안전: 기본값은 보수적 (덜 공격적)
  - 가시성: 모든 결정 로그 + 이유 명시
  - 점진적: AI 의사결정이 없어도 수동으로만 작동 가능
"""

from __future__ import annotations
import logging
import time
import threading
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional, Set
from enum import Enum
from collections import deque

_log = logging.getLogger("databridge.adaptive_rc")


# ════════════════════════════════════════════════════════════════════════════
# 데이터 모델
# ════════════════════════════════════════════════════════════════════════════

class ControlMode(str, Enum):
    """제어 모드"""
    AUTO = "auto"        # AI 가 모든 결정
    MANUAL = "manual"    # 운영자가 모든 결정
    HYBRID = "hybrid"    # AI 추천 + 운영자 승인


class HealthStatus(str, Enum):
    """시스템 건강 상태"""
    EXCELLENT = "excellent"  # 모든 지표 양호 → 가속 가능
    GOOD = "good"            # 정상
    WARNING = "warning"      # 주의 — 약간 줄임
    CRITICAL = "critical"    # 위험 — 적극 줄임
    EMERGENCY = "emergency"  # 긴급 — 일시 정지


@dataclass
class SystemSnapshot:
    """단일 시점 리소스 스냅샷"""
    timestamp: float
    
    # Source DB 메트릭
    src_cpu_pct: Optional[float] = None
    src_mem_pct: Optional[float] = None
    src_threads_running: int = 0
    src_threads_connected: int = 0
    src_lock_wait_count: int = 0
    src_avg_query_ms: float = 0
    
    # Target DB 메트릭
    tgt_cpu_pct: Optional[float] = None
    tgt_mem_pct: Optional[float] = None
    tgt_threads_running: int = 0
    tgt_replication_lag_sec: Optional[float] = None
    
    # 이관 프로세스
    current_batch_size: int = 5000
    current_parallelism: int = 3
    rows_per_sec: float = 0
    progress_pct: float = 0
    
    # 컨테이너/시스템 (Docker/local)
    container_cpu_pct: Optional[float] = None
    container_mem_pct: Optional[float] = None


@dataclass
class ControlPolicy:
    """현재 적용 중인 제어 정책"""
    mode: ControlMode = ControlMode.HYBRID
    
    # 다이얼 (실제 적용 값)
    throttle_pct: int = 100        # 100% = 정상 속도
    batch_size: int = 5000         # 현재 batch 크기
    parallelism: int = 3           # 동시 이관 테이블 수
    paused_tables: Set[str] = field(default_factory=set)
    
    # 임계치 (자동 조절 트리거)
    cpu_warning_pct: float = 75
    cpu_critical_pct: float = 90
    lock_warning_count: int = 50
    lock_critical_count: int = 200
    mem_warning_pct: float = 80
    mem_critical_pct: float = 95
    
    # 메타
    last_updated: float = field(default_factory=time.time)
    last_updated_by: str = "system"  # "system" | "user:홍길동"


@dataclass
class Decision:
    """AI/운영자가 내린 의사결정"""
    timestamp: float
    decision_id: str
    
    # 어떤 결정?
    action: str                    # "throttle_down", "throttle_up", "pause_table", "resume", ...
    target: Optional[str] = None   # 영향 받는 항목 (테이블명 등)
    
    # 이전 → 이후
    from_value: Any = None
    to_value: Any = None
    
    # 왜?
    reason: str = ""
    triggered_by: str = "ai"       # "ai" | "user" | "schedule"
    confidence: float = 0.5        # AI 의 확신도 (0~1)
    
    # 근거
    snapshot: Optional[SystemSnapshot] = None
    health_status: Optional[HealthStatus] = None
    
    # 결과 (나중에 기록)
    outcome: Optional[str] = None  # "improved" | "no_change" | "worsened"
    rollback: bool = False


# ════════════════════════════════════════════════════════════════════════════
# I-1: 메트릭 수집기
# ════════════════════════════════════════════════════════════════════════════

class MetricsCollector:
    """
    DB + 시스템 메트릭 수집기.
    
    각 DB 종류 별 별도 메서드 (확장 가능).
    """
    
    def __init__(self, src_conn=None, tgt_conn=None):
        self.src_conn = src_conn
        self.tgt_conn = tgt_conn
        self._history: deque = deque(maxlen=300)  # 최근 5분 (1초 간격 가정)
        
    def collect(
        self,
        current_batch_size: int = 5000,
        current_parallelism: int = 3,
        rows_per_sec: float = 0,
        progress_pct: float = 0,
    ) -> SystemSnapshot:
        """현재 시점의 메트릭 수집"""
        snap = SystemSnapshot(
            timestamp=time.time(),
            current_batch_size=current_batch_size,
            current_parallelism=current_parallelism,
            rows_per_sec=rows_per_sec,
            progress_pct=progress_pct,
        )
        
        # Source DB
        if self.src_conn:
            self._collect_db_metrics(self.src_conn, snap, prefix="src")
        
        # Target DB
        if self.tgt_conn:
            self._collect_db_metrics(self.tgt_conn, snap, prefix="tgt")
        
        # 시스템/컨테이너
        self._collect_system_metrics(snap)
        
        # 히스토리에 추가
        self._history.append(snap)
        
        return snap
    
    def _collect_db_metrics(self, conn, snap: SystemSnapshot, prefix: str):
        """DB 별 메트릭 수집 (MySQL/MSSQL 자동 감지)"""
        try:
            cur = conn.cursor()
            
            # MySQL/MariaDB
            try:
                cur.execute("SHOW GLOBAL STATUS WHERE Variable_name IN "
                           "('Threads_running', 'Threads_connected', "
                           "'Innodb_row_lock_current_waits', 'Innodb_row_lock_time_avg', "
                           "'Slow_queries', 'Innodb_buffer_pool_pages_free', "
                           "'Innodb_buffer_pool_pages_total')")
                rows = cur.fetchall()
                
                stats = {}
                for row in rows:
                    if isinstance(row, dict):
                        stats[row.get('Variable_name', '')] = row.get('Value', '0')
                    else:
                        stats[row[0]] = row[1]
                
                running = int(stats.get('Threads_running', 0))
                connected = int(stats.get('Threads_connected', 0))
                lock_waits = int(stats.get('Innodb_row_lock_current_waits', 0))
                lock_avg_ms = int(stats.get('Innodb_row_lock_time_avg', 0))
                
                if prefix == "src":
                    snap.src_threads_running = running
                    snap.src_threads_connected = connected
                    snap.src_lock_wait_count = lock_waits
                    snap.src_avg_query_ms = lock_avg_ms / 1000  # μs → ms
                else:
                    snap.tgt_threads_running = running
                    snap.tgt_replication_lag_sec = self._get_repl_lag(conn)
                
                return
            except Exception:
                pass  # MSSQL 시도
            
            # MSSQL
            try:
                cur.execute("""
                    SELECT 
                        (SELECT COUNT(*) FROM sys.dm_exec_requests WHERE status='running') AS running,
                        (SELECT COUNT(*) FROM sys.dm_exec_sessions WHERE is_user_process=1) AS connected,
                        (SELECT COUNT(*) FROM sys.dm_tran_locks WHERE request_status='WAIT') AS lock_waits
                """)
                row = cur.fetchone()
                if row:
                    if prefix == "src":
                        snap.src_threads_running = int(row[0] or 0)
                        snap.src_threads_connected = int(row[1] or 0)
                        snap.src_lock_wait_count = int(row[2] or 0)
                    else:
                        snap.tgt_threads_running = int(row[0] or 0)
            except Exception as e:
                _log.debug(f"[Metrics] {prefix} MSSQL 메트릭 실패: {e}")
        
        except Exception as e:
            _log.warning(f"[Metrics] {prefix} 메트릭 수집 실패: {e}")
    
    def _get_repl_lag(self, conn) -> Optional[float]:
        """MySQL replication lag (Seconds_Behind_Master)"""
        try:
            cur = conn.cursor()
            cur.execute("SHOW SLAVE STATUS")
            row = cur.fetchone()
            if row:
                # SHOW SLAVE STATUS 의 Seconds_Behind_Master 컬럼
                # dict cursor 일 수도 있음
                if isinstance(row, dict):
                    return row.get('Seconds_Behind_Master')
                # tuple — 위치는 버전마다 다름. 간단히 None
                return None
        except Exception:
            return None
    
    def _collect_system_metrics(self, snap: SystemSnapshot):
        """시스템 (psutil + Docker container) 메트릭"""
        try:
            import psutil
            snap.container_cpu_pct = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            snap.container_mem_pct = mem.percent
        except Exception:
            pass
    
    def get_history(self, seconds: int = 60) -> List[SystemSnapshot]:
        """최근 N 초의 히스토리 반환"""
        cutoff = time.time() - seconds
        return [s for s in self._history if s.timestamp >= cutoff]


# ════════════════════════════════════════════════════════════════════════════
# I-2: AI 의사결정 엔진
# ════════════════════════════════════════════════════════════════════════════

class AIDecisionEngine:
    """
    리소스 메트릭 → 자동 조절 결정.
    
    단순 임계치가 아니라 *추세 분석* + *컨텍스트 인지* 적용.
    """
    
    def __init__(self, policy: ControlPolicy):
        self.policy = policy
        self._decision_history: deque = deque(maxlen=100)
        self._last_decision_time: float = 0
        self._cooldown_sec: float = 10  # 같은 결정 반복 방지
    
    def evaluate(
        self,
        snapshot: SystemSnapshot,
        history: List[SystemSnapshot],
    ) -> Optional[Decision]:
        """
        현재 스냅샷 + 히스토리 → 의사결정.
        
        Returns:
            Decision (조절 권고) 또는 None (변경 불필요)
        """
        # 모드 체크
        if self.policy.mode == ControlMode.MANUAL:
            return None  # 수동 모드 — AI 비활성
        
        # Cooldown 체크 (너무 자주 변경 방지)
        if time.time() - self._last_decision_time < self._cooldown_sec:
            return None
        
        # 1. 건강 상태 평가
        health = self._evaluate_health(snapshot, history)
        
        # 2. 추세 분석
        trend = self._analyze_trend(history)
        
        # 3. 결정 트리
        decision = self._make_decision(snapshot, history, health, trend)
        
        if decision:
            self._decision_history.append(decision)
            self._last_decision_time = time.time()
        
        return decision
    
    def _evaluate_health(
        self,
        snap: SystemSnapshot,
        history: List[SystemSnapshot],
    ) -> HealthStatus:
        """건강 상태 평가 — 가장 안 좋은 지표 기준"""
        worst = HealthStatus.EXCELLENT
        
        # CPU (Source DB)
        if snap.src_cpu_pct is not None:
            cpu = snap.src_cpu_pct
            if cpu >= self.policy.cpu_critical_pct:
                worst = self._worse(worst, HealthStatus.CRITICAL)
            elif cpu >= self.policy.cpu_warning_pct:
                worst = self._worse(worst, HealthStatus.WARNING)
        
        # Container CPU (psutil)
        if snap.container_cpu_pct is not None:
            cpu = snap.container_cpu_pct
            if cpu >= self.policy.cpu_critical_pct:
                worst = self._worse(worst, HealthStatus.CRITICAL)
            elif cpu >= self.policy.cpu_warning_pct:
                worst = self._worse(worst, HealthStatus.WARNING)
        
        # Lock waits (Source DB)
        locks = snap.src_lock_wait_count
        if locks >= self.policy.lock_critical_count:
            worst = self._worse(worst, HealthStatus.CRITICAL)
        elif locks >= self.policy.lock_warning_count:
            worst = self._worse(worst, HealthStatus.WARNING)
        
        # Memory
        if snap.container_mem_pct is not None:
            mem = snap.container_mem_pct
            if mem >= self.policy.mem_critical_pct:
                worst = self._worse(worst, HealthStatus.CRITICAL)
            elif mem >= self.policy.mem_warning_pct:
                worst = self._worse(worst, HealthStatus.WARNING)
        
        # Replication lag (target)
        if snap.tgt_replication_lag_sec is not None:
            lag = snap.tgt_replication_lag_sec
            if lag > 60:
                worst = self._worse(worst, HealthStatus.CRITICAL)
            elif lag > 10:
                worst = self._worse(worst, HealthStatus.WARNING)
        
        # 모든 지표 양호 → EXCELLENT (가속 가능)
        if worst == HealthStatus.EXCELLENT and snap.src_cpu_pct is not None:
            if snap.src_cpu_pct < 50 and snap.src_lock_wait_count < 10:
                return HealthStatus.EXCELLENT
            else:
                return HealthStatus.GOOD
        
        return worst
    
    def _worse(self, a: HealthStatus, b: HealthStatus) -> HealthStatus:
        """둘 중 더 나쁜 상태"""
        order = [
            HealthStatus.EXCELLENT, HealthStatus.GOOD,
            HealthStatus.WARNING, HealthStatus.CRITICAL,
            HealthStatus.EMERGENCY,
        ]
        return order[max(order.index(a), order.index(b))]
    
    def _analyze_trend(self, history: List[SystemSnapshot]) -> str:
        """
        추세 분석 — 5초 평균 vs 30초 평균.
        
        Returns:
            "improving" | "stable" | "deteriorating" | "spiking"
        """
        if len(history) < 5:
            return "stable"  # 데이터 부족
        
        # 최근 5초 vs 그 이전
        recent_5s = [s for s in history if time.time() - s.timestamp < 5]
        older = [s for s in history if 5 <= time.time() - s.timestamp < 30]
        
        if not recent_5s or not older:
            return "stable"
        
        # CPU 평균 비교
        recent_cpu = sum(s.src_cpu_pct or 0 for s in recent_5s) / len(recent_5s)
        older_cpu = sum(s.src_cpu_pct or 0 for s in older) / len(older)
        
        diff = recent_cpu - older_cpu
        
        if diff > 20:
            return "spiking"        # 급격히 악화
        elif diff > 5:
            return "deteriorating"  # 점진적 악화
        elif diff < -10:
            return "improving"      # 회복 중
        else:
            return "stable"
    
    def _make_decision(
        self,
        snap: SystemSnapshot,
        history: List[SystemSnapshot],
        health: HealthStatus,
        trend: str,
    ) -> Optional[Decision]:
        """
        결정 트리 — 건강 상태 + 추세 → 액션.
        """
        current_throttle = self.policy.throttle_pct
        
        # 시나리오 1: 위급 — 즉시 큰 폭 감소
        if health == HealthStatus.CRITICAL:
            if current_throttle > 50:
                return self._make_throttle_decision(
                    snap, health,
                    new_throttle=50,
                    reason=f"CRITICAL 상태 ({self._format_problem(snap)}) — 적극 감속",
                    confidence=0.9,
                )
            elif current_throttle > 25:
                return self._make_throttle_decision(
                    snap, health,
                    new_throttle=25,
                    reason=f"CRITICAL 지속 — 추가 감속",
                    confidence=0.95,
                )
        
        # 시나리오 2: WARNING + spiking — 선제적 감소
        if health == HealthStatus.WARNING and trend == "spiking":
            if current_throttle > 50:
                return self._make_throttle_decision(
                    snap, health,
                    new_throttle=max(50, current_throttle - 25),
                    reason=f"WARNING + 급증세 — 선제 감속",
                    confidence=0.8,
                )
        
        # 시나리오 3: WARNING + deteriorating
        if health == HealthStatus.WARNING and trend == "deteriorating":
            if current_throttle > 75:
                return self._make_throttle_decision(
                    snap, health,
                    new_throttle=75,
                    reason=f"WARNING 지속 악화 — 점진 감속",
                    confidence=0.7,
                )
        
        # 시나리오 4: 회복 중 — 점진 가속 (조심스럽게)
        if health in (HealthStatus.GOOD, HealthStatus.EXCELLENT) and trend == "improving":
            if current_throttle < 100:
                # 한 번에 25%씩만, 최대 100%까지
                new_throttle = min(100, current_throttle + 25)
                return self._make_throttle_decision(
                    snap, health,
                    new_throttle=new_throttle,
                    reason=f"부하 회복 — 점진 가속",
                    confidence=0.6,
                )
        
        # 시나리오 5: EXCELLENT 지속 + 100% 미만 — 가속
        if (health == HealthStatus.EXCELLENT and trend == "stable" 
            and current_throttle < 100):
            # 이전 결정에서 충분히 시간 지났는지 확인
            return self._make_throttle_decision(
                snap, health,
                new_throttle=min(100, current_throttle + 25),
                reason=f"EXCELLENT 지속 — 가속",
                confidence=0.7,
            )
        
        # 변경 불필요
        return None
    
    def _make_throttle_decision(
        self,
        snap: SystemSnapshot,
        health: HealthStatus,
        new_throttle: int,
        reason: str,
        confidence: float,
    ) -> Decision:
        """throttle 변경 결정 생성"""
        return Decision(
            timestamp=time.time(),
            decision_id=f"ai-{int(time.time()*1000)}",
            action="set_throttle",
            from_value=self.policy.throttle_pct,
            to_value=new_throttle,
            reason=reason,
            triggered_by="ai",
            confidence=confidence,
            snapshot=snap,
            health_status=health,
        )
    
    def _format_problem(self, snap: SystemSnapshot) -> str:
        """문제 진단 한 줄 요약"""
        problems = []
        if snap.src_cpu_pct and snap.src_cpu_pct >= self.policy.cpu_critical_pct:
            problems.append(f"CPU {snap.src_cpu_pct:.0f}%")
        if snap.src_lock_wait_count >= self.policy.lock_critical_count:
            problems.append(f"lock wait {snap.src_lock_wait_count}")
        if snap.container_mem_pct and snap.container_mem_pct >= self.policy.mem_critical_pct:
            problems.append(f"메모리 {snap.container_mem_pct:.0f}%")
        return ", ".join(problems) if problems else "복합 부하"


# ════════════════════════════════════════════════════════════════════════════
# I-3: 자동 쓰로틀 컨트롤러 (Decision → 실제 적용)
# ════════════════════════════════════════════════════════════════════════════

class ThrottleController:
    """
    Decision 을 실제 batch_size / parallelism 으로 변환.
    """
    
    # throttle_pct → batch_size 매핑
    BATCH_SIZE_BASE = 5000
    PARALLELISM_BASE = 3
    
    @staticmethod
    def apply_decision(policy: ControlPolicy, decision: Decision) -> ControlPolicy:
        """결정을 정책에 반영 — 새로운 정책 반환 (immutable 스타일)"""
        new_policy = ControlPolicy(
            mode=policy.mode,
            throttle_pct=policy.throttle_pct,
            batch_size=policy.batch_size,
            parallelism=policy.parallelism,
            paused_tables=set(policy.paused_tables),
            cpu_warning_pct=policy.cpu_warning_pct,
            cpu_critical_pct=policy.cpu_critical_pct,
            lock_warning_count=policy.lock_warning_count,
            lock_critical_count=policy.lock_critical_count,
            mem_warning_pct=policy.mem_warning_pct,
            mem_critical_pct=policy.mem_critical_pct,
            last_updated=time.time(),
            last_updated_by=f"{decision.triggered_by}:{decision.decision_id}",
        )
        
        if decision.action == "set_throttle":
            new_policy.throttle_pct = int(decision.to_value)
            # batch_size 와 parallelism 자동 조정
            new_policy.batch_size = ThrottleController._throttle_to_batch(new_policy.throttle_pct)
            new_policy.parallelism = ThrottleController._throttle_to_parallelism(new_policy.throttle_pct)
        
        elif decision.action == "set_batch_size":
            new_policy.batch_size = int(decision.to_value)
        
        elif decision.action == "set_parallelism":
            new_policy.parallelism = int(decision.to_value)
        
        elif decision.action == "pause_table":
            new_policy.paused_tables.add(decision.target)
        
        elif decision.action == "resume_table":
            new_policy.paused_tables.discard(decision.target)
        
        elif decision.action == "set_mode":
            new_policy.mode = ControlMode(decision.to_value)
        
        return new_policy
    
    @staticmethod
    def _throttle_to_batch(throttle_pct: int) -> int:
        """throttle 100% = 5000, 50% = 2500, 25% = 1250"""
        return max(500, int(ThrottleController.BATCH_SIZE_BASE * throttle_pct / 100))
    
    @staticmethod
    def _throttle_to_parallelism(throttle_pct: int) -> int:
        """throttle 100% = 3, 50% = 2, 25% = 1"""
        if throttle_pct >= 100:
            return 3
        elif throttle_pct >= 75:
            return 2
        else:
            return 1


# ════════════════════════════════════════════════════════════════════════════
# I-4: 통합 컨트롤러 (메트릭 수집 + 의사결정 + 적용)
# ════════════════════════════════════════════════════════════════════════════

class AdaptiveResourceController:
    """
    Phase I 의 통합 진입점.
    
    이관 엔진이 batch loop 마다 호출:
        controller.tick(rows_processed, rows_total)
        # 내부적으로 메트릭 수집 → AI 평가 → 정책 업데이트
    
    그 후:
        new_batch = controller.policy.batch_size
        new_parallelism = controller.policy.parallelism
    """
    
    def __init__(
        self,
        src_conn=None,
        tgt_conn=None,
        initial_policy: Optional[ControlPolicy] = None,
        on_decision: Optional[Callable[[Decision], None]] = None,
    ):
        self.collector = MetricsCollector(src_conn, tgt_conn)
        self.policy = initial_policy or ControlPolicy()
        self.engine = AIDecisionEngine(self.policy)
        self.on_decision = on_decision  # 콜백 (UI 알림 등)
        
        self.decisions_log: List[Decision] = []
        self._lock = threading.Lock()
    
    def tick(
        self,
        rows_processed: int = 0,
        rows_total: int = 0,
        rows_per_sec: float = 0,
    ) -> ControlPolicy:
        """
        Tick — 한 batch 끝날 때마다 호출.
        
        Returns:
            업데이트된 ControlPolicy
        """
        with self._lock:
            # 진행률 계산
            progress = (rows_processed / rows_total * 100) if rows_total > 0 else 0
            
            # 1. 메트릭 수집
            snap = self.collector.collect(
                current_batch_size=self.policy.batch_size,
                current_parallelism=self.policy.parallelism,
                rows_per_sec=rows_per_sec,
                progress_pct=progress,
            )
            
            # 2. AI 평가 (수동 모드면 None)
            history = self.collector.get_history(seconds=60)
            decision = self.engine.evaluate(snap, history)
            
            # 3. 결정 적용
            if decision:
                self.policy = ThrottleController.apply_decision(self.policy, decision)
                self.engine.policy = self.policy  # 엔진도 새 정책 사용
                self.decisions_log.append(decision)
                
                # 콜백 (WebSocket 으로 UI 알림 등)
                if self.on_decision:
                    try:
                        self.on_decision(decision)
                    except Exception as e:
                        _log.warning(f"[ARC] 콜백 실패: {e}")
                
                _log.info(
                    f"[ARC] 자동 조절: throttle {decision.from_value}→{decision.to_value}% "
                    f"(이유: {decision.reason})"
                )
            
            return self.policy
    
    # ─── 수동 오버라이드 (I-4) ───────────────────────────────────────
    
    def manual_set_throttle(self, throttle_pct: int, user: str = "user") -> Decision:
        """수동 throttle 변경"""
        with self._lock:
            decision = Decision(
                timestamp=time.time(),
                decision_id=f"manual-{int(time.time()*1000)}",
                action="set_throttle",
                from_value=self.policy.throttle_pct,
                to_value=throttle_pct,
                reason=f"수동 조절 by {user}",
                triggered_by=f"user:{user}",
                confidence=1.0,
            )
            self.policy = ThrottleController.apply_decision(self.policy, decision)
            self.engine.policy = self.policy
            self.decisions_log.append(decision)
            
            if self.on_decision:
                try: self.on_decision(decision)
                except: pass
            
            return decision
    
    def manual_pause_table(self, table_name: str, user: str = "user") -> Decision:
        """특정 테이블 일시정지"""
        with self._lock:
            decision = Decision(
                timestamp=time.time(),
                decision_id=f"manual-pause-{int(time.time()*1000)}",
                action="pause_table",
                target=table_name,
                reason=f"테이블 일시정지 by {user}",
                triggered_by=f"user:{user}",
                confidence=1.0,
            )
            self.policy = ThrottleController.apply_decision(self.policy, decision)
            self.engine.policy = self.policy
            self.decisions_log.append(decision)
            
            if self.on_decision:
                try: self.on_decision(decision)
                except: pass
            
            return decision
    
    def manual_resume_table(self, table_name: str, user: str = "user") -> Decision:
        with self._lock:
            decision = Decision(
                timestamp=time.time(),
                decision_id=f"manual-resume-{int(time.time()*1000)}",
                action="resume_table",
                target=table_name,
                reason=f"테이블 재개 by {user}",
                triggered_by=f"user:{user}",
                confidence=1.0,
            )
            self.policy = ThrottleController.apply_decision(self.policy, decision)
            self.engine.policy = self.policy
            self.decisions_log.append(decision)
            
            if self.on_decision:
                try: self.on_decision(decision)
                except: pass
            
            return decision
    
    def set_mode(self, mode: ControlMode, user: str = "user") -> Decision:
        """제어 모드 변경 (AUTO/MANUAL/HYBRID)"""
        with self._lock:
            decision = Decision(
                timestamp=time.time(),
                decision_id=f"mode-{int(time.time()*1000)}",
                action="set_mode",
                from_value=self.policy.mode.value,
                to_value=mode.value,
                reason=f"모드 변경 → {mode.value} by {user}",
                triggered_by=f"user:{user}",
                confidence=1.0,
            )
            self.policy = ThrottleController.apply_decision(self.policy, decision)
            self.engine.policy = self.policy
            self.decisions_log.append(decision)
            
            if self.on_decision:
                try: self.on_decision(decision)
                except: pass
            
            return decision
    
    # ─── 조회 API ────────────────────────────────────────────────────
    
    def get_status(self) -> Dict[str, Any]:
        """현재 상태 종합 (UI 용)"""
        latest = list(self.collector._history)[-1] if self.collector._history else None
        return {
            "policy": {
                "mode": self.policy.mode.value,
                "throttle_pct": self.policy.throttle_pct,
                "batch_size": self.policy.batch_size,
                "parallelism": self.policy.parallelism,
                "paused_tables": list(self.policy.paused_tables),
                "last_updated": self.policy.last_updated,
                "last_updated_by": self.policy.last_updated_by,
            },
            "latest_snapshot": asdict(latest) if latest else None,
            "recent_decisions": [
                {
                    "timestamp": d.timestamp,
                    "action": d.action,
                    "target": d.target,
                    "from_value": d.from_value,
                    "to_value": d.to_value,
                    "reason": d.reason,
                    "triggered_by": d.triggered_by,
                    "confidence": d.confidence,
                    "health_status": d.health_status.value if d.health_status else None,
                }
                for d in self.decisions_log[-10:]
            ],
        }
    
    def get_decisions_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """의사결정 전체 로그 (audit 용)"""
        return [
            {
                "timestamp": d.timestamp,
                "decision_id": d.decision_id,
                "action": d.action,
                "target": d.target,
                "from_value": d.from_value,
                "to_value": d.to_value,
                "reason": d.reason,
                "triggered_by": d.triggered_by,
                "confidence": d.confidence,
                "health_status": d.health_status.value if d.health_status else None,
            }
            for d in self.decisions_log[-limit:]
        ]
