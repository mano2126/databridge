"""
smart_retry_engine.py — Phase H-3 (2026-04-25)

스마트 재시도 + 실패 격리 엔진.

설계 철학 (본부장님이 발견한 미스터리에서 출발):
  "재이관하면 성공하는 이유" = 다음 두 가지 중 하나:
    1. 첫 번째 시도 후 다른 오브젝트가 생성되어 의존성 충족
    2. AI 가 같은 입력에 다른 출력을 내서 우연히 syntax 통과

  이걸 결정론적으로 만들면 → 첫 이관 성공률 95%+

작동 원리 (3단계 재시도):
  1차 시도 (Topological Sort 순서):
     - H-1 으로 의존성 정렬
     - H-2 로 사전 검증 + auto-fix
     - 실패 시 → 에러 분석

  2차 시도 (스마트 재정렬 + AI 재변환):
     - 실패 원인 분류:
        a) 의존성 누락 (1146) → 후순위 이동, 일단 skip
        b) AI 변환 결함 (1064) → AI 재호출 (error_cases 학습 주입)
        c) 권한 문제 (1419) → 권한 가이드 후 skip
     - 모든 가능한 오브젝트 처리 후 실패한 것만 재시도
     - 이때 이미 생성된 오브젝트가 의존성 충족시켜 줄 수 있음

  3차 시도 (에러 패턴 학습):
     - 1~2차 모두 실패 → error_cases.txt 에 자동 기록
     - 수동 검토 큐로 이동
     - 다음 번에는 이 패턴이 H-2 룰에 추가됨

핵심 컴포넌트:
  - ErrorClassifier: 에러 메시지 분류
  - RetryStrategy: 재시도 전략 결정
  - DeferredQueue: 후순위 이동 관리
  - RetryReport: 재시도 결과 리포트
"""

from __future__ import annotations
import logging
import re
import time
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Callable, Any, Tuple
from enum import Enum

_log = logging.getLogger("databridge.retry")


# ════════════════════════════════════════════════════════════════════════════
# 에러 분류
# ════════════════════════════════════════════════════════════════════════════

class ErrorCategory(str, Enum):
    """에러 카테고리 — 재시도 전략 결정"""
    DEPENDENCY = "dependency"        # 1146 Table doesn't exist 등
    SYNTAX = "syntax"                 # 1064 SQL syntax
    PERMISSION = "permission"         # 1419 SUPER privilege, 1142 권한
    TIMEOUT = "timeout"               # 타임아웃
    NETWORK = "network"               # 네트워크 일시 끊김
    DATA_TYPE = "data_type"           # 1406 Data too long, 1292 Incorrect datetime
    COLLATION = "collation"           # 1270 Illegal mix of collations
    DUPLICATE = "duplicate"           # 이미 존재 (skip 가능)
    UNKNOWN = "unknown"               # 알려지지 않은 패턴


class RetryAction(str, Enum):
    """재시도 액션"""
    DEFER = "defer"                  # 후순위 이동 (의존성 충족 대기)
    REGENERATE = "regenerate"        # AI 재변환 (학습 주입)
    SKIP = "skip"                    # 스킵 (이미 존재 등)
    GIVE_UP = "give_up"              # 포기 (수동 검토)
    RETRY_AS_IS = "retry_as_is"     # 그대로 재시도 (네트워크/타임아웃)


# 에러 코드 → 카테고리 매핑 (실측 기반)
_MYSQL_ERROR_PATTERNS = [
    # 의존성 (재시도 시 해결될 가능성 큼)
    (r'1146', ErrorCategory.DEPENDENCY),       # Table doesn't exist
    (r"doesn't exist", ErrorCategory.DEPENDENCY),
    (r'Unknown table', ErrorCategory.DEPENDENCY),
    (r'1049', ErrorCategory.DEPENDENCY),       # Unknown database
    
    # Syntax — AI 재변환 후보
    (r'1064', ErrorCategory.SYNTAX),
    (r'syntax error', ErrorCategory.SYNTAX),
    (r'1308', ErrorCategory.SYNTAX),           # LEAVE no matching label
    
    # 권한
    (r'1419', ErrorCategory.PERMISSION),       # SUPER privilege required
    (r'1142', ErrorCategory.PERMISSION),       # access denied
    (r'access denied', ErrorCategory.PERMISSION),
    
    # 데이터 타입
    (r'1406', ErrorCategory.DATA_TYPE),        # Data too long
    (r'1292', ErrorCategory.DATA_TYPE),        # Incorrect datetime
    (r'1366', ErrorCategory.DATA_TYPE),        # Incorrect integer value
    
    # Collation
    (r'1270', ErrorCategory.COLLATION),        # Illegal mix of collations
    (r'Illegal mix', ErrorCategory.COLLATION),
    
    # 중복
    (r'1050', ErrorCategory.DUPLICATE),        # Table already exists
    (r'1304', ErrorCategory.DUPLICATE),        # PROCEDURE already exists
    (r'1359', ErrorCategory.DUPLICATE),        # TRIGGER already exists
    (r'already exists', ErrorCategory.DUPLICATE),
    
    # 타임아웃
    (r'timeout', ErrorCategory.TIMEOUT),
    (r'lock wait', ErrorCategory.TIMEOUT),
    (r'2006', ErrorCategory.NETWORK),          # MySQL server has gone away
    (r'2013', ErrorCategory.NETWORK),          # Lost connection
]


def classify_error(error_msg: str) -> ErrorCategory:
    """에러 메시지 → 카테고리 분류"""
    if not error_msg:
        return ErrorCategory.UNKNOWN
    
    msg_lower = error_msg.lower()
    for pattern, category in _MYSQL_ERROR_PATTERNS:
        if re.search(pattern, error_msg, re.IGNORECASE):
            return category
    
    return ErrorCategory.UNKNOWN


def decide_retry_action(
    category: ErrorCategory,
    attempt: int,
    max_attempts: int = 3,
) -> RetryAction:
    """
    카테고리 + 시도 횟수 → 재시도 액션 결정.
    
    Args:
        category: 에러 카테고리
        attempt: 현재 시도 회수 (1, 2, 3, ...)
        max_attempts: 최대 시도 회수
    """
    # 마지막 시도 → 포기
    if attempt >= max_attempts:
        if category == ErrorCategory.DUPLICATE:
            return RetryAction.SKIP
        return RetryAction.GIVE_UP
    
    # 카테고리별 전략
    if category == ErrorCategory.DUPLICATE:
        return RetryAction.SKIP  # 즉시 skip
    
    if category == ErrorCategory.DEPENDENCY:
        # 1차: defer (다른 거 먼저 처리)
        # 2차: defer 한번 더 (다단 의존성)
        # 3차: 포기
        return RetryAction.DEFER if attempt < max_attempts else RetryAction.GIVE_UP
    
    if category == ErrorCategory.SYNTAX:
        # 1차: AI 재변환 (error_cases 학습 주입)
        # 2차: 한번 더 재변환
        # 3차: 포기 → 수동 검토
        return RetryAction.REGENERATE
    
    if category in (ErrorCategory.NETWORK, ErrorCategory.TIMEOUT):
        # 일시적 — 그대로 재시도
        return RetryAction.RETRY_AS_IS
    
    if category == ErrorCategory.PERMISSION:
        # 권한 문제는 재시도해도 안 됨 — 즉시 포기
        return RetryAction.GIVE_UP
    
    if category in (ErrorCategory.DATA_TYPE, ErrorCategory.COLLATION):
        # 변환 결함 — AI 재변환
        return RetryAction.REGENERATE
    
    # UNKNOWN — 일단 한번 재시도, 안 되면 포기
    return RetryAction.RETRY_AS_IS if attempt == 1 else RetryAction.GIVE_UP


# ════════════════════════════════════════════════════════════════════════════
# 재시도 결과 모델
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class AttemptRecord:
    """단일 시도 기록"""
    attempt_num: int
    timestamp: float
    success: bool
    error_message: Optional[str] = None
    error_category: Optional[ErrorCategory] = None
    action_taken: Optional[RetryAction] = None
    duration_ms: float = 0


@dataclass
class ObjectRetryStatus:
    """오브젝트별 재시도 현황"""
    name: str
    object_type: str
    attempts: List[AttemptRecord] = field(default_factory=list)
    final_status: str = "pending"     # pending/success/failed/skipped/deferred
    final_error: Optional[str] = None
    
    @property
    def attempt_count(self) -> int:
        return len(self.attempts)
    
    @property
    def succeeded(self) -> bool:
        return self.final_status == "success"


@dataclass
class RetryReport:
    """전체 재시도 리포트"""
    total_objects: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    deferred_count: int = 0
    
    objects: Dict[str, ObjectRetryStatus] = field(default_factory=dict)
    
    # 통계
    total_attempts: int = 0
    auto_recovered: int = 0      # 1차 실패했지만 재시도로 성공
    
    # 카테고리별 카운트
    error_categories: Dict[str, int] = field(default_factory=dict)
    
    duration_seconds: float = 0
    
    def to_dict(self) -> dict:
        return {
            "total_objects": self.total_objects,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "skipped": self.skipped,
            "deferred_count": self.deferred_count,
            "total_attempts": self.total_attempts,
            "auto_recovered": self.auto_recovered,
            "first_try_success_rate": self.first_try_success_rate,
            "final_success_rate": self.final_success_rate,
            "error_categories": self.error_categories,
            "duration_seconds": self.duration_seconds,
        }
    
    @property
    def first_try_success_rate(self) -> float:
        """첫 시도 성공률"""
        if self.total_objects == 0:
            return 0.0
        first_try_success = sum(
            1 for o in self.objects.values()
            if o.succeeded and o.attempt_count == 1
        )
        return round(first_try_success / self.total_objects * 100, 1)
    
    @property
    def final_success_rate(self) -> float:
        """최종 성공률"""
        if self.total_objects == 0:
            return 0.0
        return round(self.succeeded / self.total_objects * 100, 1)


# ════════════════════════════════════════════════════════════════════════════
# 스마트 재시도 엔진
# ════════════════════════════════════════════════════════════════════════════

class SmartRetryEngine:
    """
    스마트 재시도 엔진.
    
    사용법:
        engine = SmartRetryEngine(
            executor=execute_ddl,        # 실행 함수
            regenerator=ai_regenerate,   # AI 재변환 함수 (선택)
            max_attempts=3,
        )
        
        report = engine.run(ordered_objects)
    """
    
    def __init__(
        self,
        executor: Callable[[str, str, str], Tuple[bool, Optional[str]]],
        regenerator: Optional[Callable[[str, str, str, str], Optional[str]]] = None,
        max_attempts: int = 3,
        retry_delay_sec: float = 0.1,
    ):
        """
        Args:
            executor: (name, object_type, ddl) -> (success, error_msg)
            regenerator: AI 재변환 — (name, type, old_ddl, error) -> new_ddl or None
            max_attempts: 최대 시도 횟수
            retry_delay_sec: 재시도 간 딜레이
        """
        self.executor = executor
        self.regenerator = regenerator
        self.max_attempts = max_attempts
        self.retry_delay = retry_delay_sec
    
    def run(
        self,
        objects: List[Dict[str, Any]],
        on_progress: Optional[Callable[[str, str], None]] = None,
    ) -> RetryReport:
        """
        오브젝트 리스트 실행 + 스마트 재시도.
        
        Args:
            objects: [{"name": "...", "type": "view", "ddl": "..."}]
            on_progress: 진행 상황 콜백 (name, status)
        
        Returns:
            RetryReport
        """
        report = RetryReport(total_objects=len(objects))
        start_time = time.monotonic()
        
        # 인덱스 빌드
        for obj in objects:
            name = obj['name']
            report.objects[name] = ObjectRetryStatus(
                name=name,
                object_type=obj.get('type', 'unknown'),
            )
        
        # ═══ 1차 시도: 순서대로 ═══
        deferred: List[Dict[str, Any]] = []
        
        for obj in objects:
            name = obj['name']
            self._notify(on_progress, name, "trying")
            
            success, error_msg = self._execute_with_record(obj, attempt=1, report=report)
            
            if success:
                report.objects[name].final_status = "success"
                report.succeeded += 1
                self._notify(on_progress, name, "success")
            else:
                category = classify_error(error_msg)
                action = decide_retry_action(category, attempt=1, max_attempts=self.max_attempts)
                
                # 액션 적용
                if action == RetryAction.SKIP:
                    report.objects[name].final_status = "skipped"
                    report.skipped += 1
                    self._notify(on_progress, name, "skipped (already exists)")
                
                elif action == RetryAction.DEFER:
                    deferred.append(obj)
                    report.deferred_count += 1
                    self._notify(on_progress, name, f"deferred ({category.value})")
                
                elif action == RetryAction.GIVE_UP:
                    report.objects[name].final_status = "failed"
                    report.objects[name].final_error = error_msg
                    report.failed += 1
                    self._notify(on_progress, name, f"failed ({category.value})")
                
                else:
                    # REGENERATE / RETRY_AS_IS — 즉시 재시도
                    deferred.append(obj)
        
        # ═══ 2차 시도: deferred 처리 ═══
        if deferred:
            _log.info(f"[Retry] 1차 후 deferred: {len(deferred)}개 — 2차 시도 시작")
            
            # deferred 다시 순회 (이미 다른 거 생성됨 → 의존성 충족 가능성)
            still_deferred: List[Dict[str, Any]] = []
            
            for obj in deferred:
                name = obj['name']
                if report.objects[name].final_status != "pending":
                    continue
                
                # AI 재변환 필요한지 결정
                last_attempt = report.objects[name].attempts[-1] if report.objects[name].attempts else None
                if (last_attempt and 
                    last_attempt.error_category == ErrorCategory.SYNTAX and
                    self.regenerator):
                    # AI 재변환 시도
                    new_ddl = self._try_regenerate(obj, last_attempt.error_message)
                    if new_ddl:
                        obj = {**obj, "ddl": new_ddl}
                
                # 재시도
                success, error_msg = self._execute_with_record(obj, attempt=2, report=report)
                
                if success:
                    report.objects[name].final_status = "success"
                    report.succeeded += 1
                    report.auto_recovered += 1
                    self._notify(on_progress, name, "success (after retry)")
                else:
                    category = classify_error(error_msg)
                    action = decide_retry_action(category, attempt=2, max_attempts=self.max_attempts)
                    
                    if action == RetryAction.SKIP:
                        report.objects[name].final_status = "skipped"
                        report.skipped += 1
                    elif action == RetryAction.DEFER:
                        still_deferred.append(obj)
                    else:
                        report.objects[name].final_status = "failed"
                        report.objects[name].final_error = error_msg
                        report.failed += 1
            
            # ═══ 3차 시도: 마지막 ═══
            if still_deferred:
                _log.info(f"[Retry] 2차 후 still deferred: {len(still_deferred)}개 — 최종 시도")
                
                for obj in still_deferred:
                    name = obj['name']
                    if report.objects[name].final_status != "pending":
                        continue
                    
                    # AI 재변환 시도 (마지막 기회)
                    if self.regenerator:
                        last_attempt = report.objects[name].attempts[-1]
                        new_ddl = self._try_regenerate(obj, last_attempt.error_message)
                        if new_ddl:
                            obj = {**obj, "ddl": new_ddl}
                    
                    success, error_msg = self._execute_with_record(obj, attempt=3, report=report)
                    
                    if success:
                        report.objects[name].final_status = "success"
                        report.succeeded += 1
                        report.auto_recovered += 1
                    else:
                        report.objects[name].final_status = "failed"
                        report.objects[name].final_error = error_msg
                        report.failed += 1
        
        # 완료 — 통계 계산
        report.duration_seconds = round(time.monotonic() - start_time, 2)
        
        return report
    
    def _execute_with_record(
        self,
        obj: Dict[str, Any],
        attempt: int,
        report: RetryReport,
    ) -> Tuple[bool, Optional[str]]:
        """실행 + 시도 기록"""
        name = obj['name']
        obj_type = obj.get('type', 'unknown')
        ddl = obj.get('ddl', '')
        
        if attempt > 1 and self.retry_delay > 0:
            time.sleep(self.retry_delay)
        
        start = time.monotonic()
        try:
            success, error_msg = self.executor(name, obj_type, ddl)
        except Exception as e:
            success, error_msg = False, str(e)
        duration_ms = (time.monotonic() - start) * 1000
        
        category = classify_error(error_msg) if not success else None
        action = decide_retry_action(category, attempt, self.max_attempts) if category else None
        
        record = AttemptRecord(
            attempt_num=attempt,
            timestamp=time.time(),
            success=success,
            error_message=error_msg,
            error_category=category,
            action_taken=action,
            duration_ms=duration_ms,
        )
        report.objects[name].attempts.append(record)
        report.total_attempts += 1
        
        # 카테고리 카운트
        if category:
            cat_str = category.value
            report.error_categories[cat_str] = report.error_categories.get(cat_str, 0) + 1
        
        return success, error_msg
    
    def _try_regenerate(
        self,
        obj: Dict[str, Any],
        error_msg: str,
    ) -> Optional[str]:
        """AI 재변환 시도 (regenerator 가 있을 때만)"""
        if not self.regenerator:
            return None
        try:
            return self.regenerator(
                obj['name'],
                obj.get('type', 'unknown'),
                obj.get('ddl', ''),
                error_msg or '',
            )
        except Exception as e:
            _log.warning(f"[Retry] AI 재변환 실패: {e}")
            return None
    
    def _notify(self, callback, name: str, status: str):
        if callback:
            try:
                callback(name, status)
            except Exception:
                pass


# ════════════════════════════════════════════════════════════════════════════
# 리포트 포맷터 (사람이 읽기 쉬운 형식)
# ════════════════════════════════════════════════════════════════════════════

def format_retry_report(report: RetryReport) -> str:
    """이관 종료 후 로그/이메일용 요약"""
    lines = []
    lines.append("=" * 70)
    lines.append("Phase H-3 스마트 재시도 리포트")
    lines.append("=" * 70)
    lines.append(f"")
    lines.append(f"📊 종합:")
    lines.append(f"  - 총 오브젝트:       {report.total_objects}")
    lines.append(f"  - 성공:              {report.succeeded}")
    lines.append(f"  - 실패:              {report.failed}")
    lines.append(f"  - 스킵 (이미 존재):  {report.skipped}")
    lines.append(f"  - 첫 시도 성공률:    {report.first_try_success_rate}%")
    lines.append(f"  - 최종 성공률:       {report.final_success_rate}%")
    lines.append(f"  - 자동 복구:         {report.auto_recovered}건")
    lines.append(f"  - 총 시도 횟수:      {report.total_attempts}")
    lines.append(f"  - 소요 시간:         {report.duration_seconds}초")
    
    if report.error_categories:
        lines.append(f"")
        lines.append(f"🔍 에러 분류:")
        for cat, count in sorted(report.error_categories.items(), key=lambda x: -x[1]):
            lines.append(f"  - {cat}: {count}건")
    
    failed_objs = [o for o in report.objects.values() if not o.succeeded and o.final_status == "failed"]
    if failed_objs:
        lines.append(f"")
        lines.append(f"❌ 최종 실패 ({len(failed_objs)}건) — 수동 검토 필요:")
        for o in failed_objs:
            lines.append(f"  - [{o.object_type}] {o.name}")
            if o.final_error:
                err_preview = o.final_error[:100].replace('\n', ' ')
                lines.append(f"     → {err_preview}")
    
    auto_recovered_objs = [o for o in report.objects.values() 
                          if o.succeeded and o.attempt_count > 1]
    if auto_recovered_objs:
        lines.append(f"")
        lines.append(f"✅ 자동 복구 성공 ({len(auto_recovered_objs)}건):")
        for o in auto_recovered_objs:
            lines.append(f"  - [{o.object_type}] {o.name} ({o.attempt_count}차 시도)")
    
    return "\n".join(lines)
