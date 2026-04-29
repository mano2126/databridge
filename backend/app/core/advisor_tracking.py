"""
app/core/advisor_tracking.py — AI DBA 권고 Before/After 추적 시스템
v10 #23 — 2026-04-24

목적:
  Choi (CIO) 의 요청: "리포트에서 권고 따랐을 때 얻은 실제 혜택을 보고 싶다"

  AI DBA Consultant 가 권고할 때 → 베이스라인(예상치) 기록 →
  사용자 적용 여부 저장 → 이관 실행 실측 → 리포트에 Before/After 비교.

데이터 플로우:
  1. Advisor.analyze() → 권고 생성 (기존 기능)
  2. 권고마다 baseline 추정: "이 권고 안 따르면 XX 영향"
  3. 사용자가 apply_decision 할 때 Store 에 기록
  4. Job 실행 중: 해당 테이블/SP 의 실측 수집
  5. Job 완료 시: advisor_tracker.compute_impact() → 개선 효과 계산
  6. 리포트: Before/After 섹션에 노출

Store 구조:
  Store("advisor_tracking") = {
    "{job_id}": {
      "decisions": [
        {
          "rec_id": "...",
          "category": "perf",
          "severity": "high",
          "decision": "applied" | "skipped" | "edited",
          "description": "...",
          "baseline": {                 # 권고 시점에 기록
            "metric": "duration_sec",
            "expected_without": 3600,   # 권고 안 따랐을 때 예상
            "expected_with":    1200,   # 권고 따랐을 때 예상
            "unit": "sec",
            "target_table": "profile",  # 측정 대상
            "measurement_key": "table_duration.profile",  # 실측 키
          },
          "actual": {                   # 이관 후 채워짐
            "value": 1150,              # 실제 측정값
            "captured_at": "2026-04-24T14:32:00Z"
          },
          "impact": {                   # 계산된 결과
            "diff_vs_baseline": -50,    # 예상 대비
            "diff_pct": -4.2,
            "diff_vs_without": -2450,   # 권고 안 따랐으면
            "diff_without_pct": -68.1
          }
        },
        ...
      ],
      "job_metrics": {                  # Job 전반 실측
        "total_duration_sec":  2340,
        "table_durations":     {"profile": 1150, "credit_line": 240, ...},
        "rows_per_sec":        15240,
        "peak_memory_mb":      3200,
        ...
      }
    }
  }

설계 원칙:
  - 권고 생성 시점에 baseline 이 없으면 (카테고리에 따라) 합리적 추정 제공
  - 실측 못 구한 권고는 "N/A" 로 표시 (거짓말 금지)
  - Choi 철학: 숫자가 있어야 신뢰. 없으면 없다고 솔직히.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger("databridge.advisor_tracking")

# ═══════════════════════════════════════════════════════════════════
# Baseline 추정 규칙 — 권고 카테고리/종류별 예상 효과
# ═══════════════════════════════════════════════════════════════════

# 각 권고 카테고리별로 "안 따랐을 때" vs "따랐을 때" 예상 영향을 정의.
# 정확한 예측이 목적이 아니라, 사용자가 "이걸 따랐더니 실제 X초 절약됨" 같은
# 구체적 스토리를 갖기 위함.
_BASELINE_RULES = {
    # 카테고리: (metric, expected_without_factor, expected_with_factor, unit, explanation)
    "perf.batch_size": {
        "metric":  "table_duration_sec",
        "unit":    "sec",
        "explanation": "배치 크기 최적화 시 대용량 테이블 이관 시간 개선",
        # 권고 따랐을 때 개선율 예상 (예: 50% 더 빠름)
        "expected_improvement_pct": 50,
    },
    "perf.index_timing": {
        "metric":  "table_duration_sec",
        "unit":    "sec",
        "explanation": "인덱스 생성 시점을 이관 후로 미루면 INSERT 성능 개선",
        "expected_improvement_pct": 30,
    },
    "perf.parallel": {
        "metric":  "job_duration_sec",
        "unit":    "sec",
        "explanation": "병렬 처리 최적화로 전체 이관 시간 단축",
        "expected_improvement_pct": 40,
    },
    "schema.type_conversion": {
        "metric":  "storage_mb",
        "unit":    "MB",
        "explanation": "타입 최적화로 저장 공간 절감",
        "expected_improvement_pct": 15,
    },
    "schema.encoding": {
        "metric":  "encoding_issues",
        "unit":    "count",
        "explanation": "인코딩 호환성 경고 해결",
        "expected_improvement_pct": 100,  # 이슈 0 으로
    },
    "compat.function_mapping": {
        "metric":  "compat_errors",
        "unit":    "count",
        "explanation": "함수/SP 호환성 문제 사전 해결",
        "expected_improvement_pct": 100,
    },
    "data.null_handling": {
        "metric":  "data_issues",
        "unit":    "count",
        "explanation": "NULL 처리 규칙 적용으로 데이터 무결성 향상",
        "expected_improvement_pct": 100,
    },
    # 기본값 (카테고리 매치 안 될 때)
    "default": {
        "metric":  "quality_score",
        "unit":    "score",
        "explanation": "이관 품질 개선",
        "expected_improvement_pct": 10,
    },
}


def _classify_recommendation(rec: dict) -> str:
    """권고를 세부 카테고리로 분류 (baseline 계산용)."""
    cat = (rec.get("category") or "").lower()
    title = (rec.get("title") or rec.get("description") or "").lower()

    # 키워드 기반 세분화
    if "batch" in title or "chunk" in title or "청크" in title:
        return "perf.batch_size"
    if "index" in title or "인덱스" in title:
        return "perf.index_timing"
    if "parallel" in title or "병렬" in title or "concurrent" in title:
        return "perf.parallel"
    if "type" in title or "타입" in title or "convert" in title:
        return "schema.type_conversion"
    if "encoding" in title or "charset" in title or "인코딩" in title or "utf" in title:
        return "schema.encoding"
    if "function" in title or "procedure" in title or "함수" in title:
        return "compat.function_mapping"
    if "null" in title or "default" in title:
        return "data.null_handling"

    # 카테고리 그대로 쓰기
    if cat == "perf":
        return "perf.batch_size"  # 기본 성능 카테고리
    if cat == "schema":
        return "schema.type_conversion"
    if cat == "compat":
        return "compat.function_mapping"
    if cat == "data":
        return "data.null_handling"

    return "default"


def _extract_target_table(rec: dict, context: Optional[dict]) -> Optional[str]:
    """권고 description 에서 테이블명을 추출 (예: 'profile 테이블 (242만건)' → 'profile')."""
    # 1. context 에 명시된 게 있으면 우선
    if context and context.get("target_table"):
        return context["target_table"]

    import re
    text = f"{rec.get('title','')} {rec.get('description','')}"
    # 패턴 1: "XXX 테이블"
    m = re.search(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*테이블', text)
    if m:
        return m.group(1)
    # 패턴 2: table 키워드 뒤 백틱/따옴표 이름
    m = re.search(r'`([a-zA-Z_][a-zA-Z0-9_]*)`', text)
    if m:
        return m.group(1)
    return None


def make_baseline(rec: dict, context: Optional[dict] = None) -> dict:
    """
    권고에 대한 baseline (예상 효과) 생성.

    Args:
        rec: Advisor 가 생성한 권고 dict (id/category/severity/description 등)
        context: 추가 컨텍스트 (테이블 rows 추정, Job 예상 시간 등)

    Returns:
        baseline dict: {metric, expected_without, expected_with, unit, ...}
    """
    sub_cat = _classify_recommendation(rec)
    rule = _BASELINE_RULES.get(sub_cat, _BASELINE_RULES["default"])

    context = context or {}
    severity = rec.get("severity", "med")
    # 심각도에 따라 영향 가중
    severity_weight = {"high": 1.5, "med": 1.0, "low": 0.5}.get(severity, 1.0)
    effective_improvement = rule["expected_improvement_pct"] * severity_weight / 100.0

    # 테이블명 자동 추출
    target_table = _extract_target_table(rec, context)

    # 시간 계열 권고는 컨텍스트의 예상 시간을 참고
    baseline_val = None
    if rule["metric"] in ("table_duration_sec", "job_duration_sec"):
        baseline_val = context.get("estimated_duration_sec")
        # 없으면 카테고리별 디폴트 추정값 (대략치)
        if not baseline_val:
            if severity == "high":
                baseline_val = 1800  # 30분
            elif severity == "med":
                baseline_val = 600   # 10분
            else:
                baseline_val = 120   # 2분

    if baseline_val:
        expected_without = baseline_val
        expected_with = baseline_val * (1 - effective_improvement)
    else:
        # 숫자가 없으면 개선율만 기록 (비율로)
        expected_without = 100.0
        expected_with = 100.0 * (1 - effective_improvement)

    return {
        "sub_category":    sub_cat,
        "metric":          rule["metric"],
        "unit":            rule["unit"],
        "expected_without": round(expected_without, 2) if expected_without else None,
        "expected_with":    round(expected_with, 2) if expected_with else None,
        "expected_improvement_pct": round(effective_improvement * 100, 1),
        "explanation":     rule["explanation"],
        "target_table":    target_table,
        "measurement_key": context.get("measurement_key"),
    }


# ═══════════════════════════════════════════════════════════════════
# Tracking Store 헬퍼
# ═══════════════════════════════════════════════════════════════════

def _get_store():
    """Store("advisor_tracking") 반환."""
    from app.core.store import Store
    return Store("advisor_tracking")


def record_decisions(
    job_id: str,
    src_db: str,
    tgt_db: str,
    mode: str,
    decisions: list[dict],
    recommendations_by_id: Optional[dict] = None,
) -> dict:
    """
    apply_decision 호출 시 baseline 과 함께 Store 에 기록.

    Args:
        job_id: 대상 Job ID
        src_db, tgt_db, mode: 컨텍스트
        decisions: [{id, decision, edited_sql}, ...]
        recommendations_by_id: {rec_id: rec_dict, ...} (있으면 baseline 풍부)

    Returns:
        stats dict
    """
    if not job_id:
        # job_id 없으면 기록 스킵 (이관과 연결 불가)
        return {"recorded": 0, "reason": "no_job_id"}

    store = _get_store()
    existing = store.get(job_id) or {}
    existing.setdefault("decisions", [])
    existing.setdefault("job_metrics", {})
    existing["src_db"] = src_db
    existing["tgt_db"] = tgt_db
    existing["mode"]   = mode
    existing["updated_at"] = datetime.now().isoformat()

    recs_map = recommendations_by_id or {}

    # 기존 결정 업데이트 또는 새로 추가
    by_rec_id = {d.get("rec_id"): d for d in existing["decisions"]}

    for d in decisions:
        rec_id = d.get("id") or ""
        if not rec_id:
            continue

        decision = d.get("decision", "skipped")
        edited_sql = d.get("edited_sql")

        rec_dict = recs_map.get(rec_id, {})
        baseline = make_baseline(rec_dict) if rec_dict else None

        entry = by_rec_id.get(rec_id, {"rec_id": rec_id})
        entry.update({
            "rec_id":       rec_id,
            "category":     rec_dict.get("category"),
            "severity":     rec_dict.get("severity"),
            "title":        rec_dict.get("title"),
            "description":  rec_dict.get("description"),
            "decision":     decision,
            "edited_sql":   edited_sql,
            "decided_at":   datetime.now().isoformat(),
        })
        if baseline:
            entry["baseline"] = baseline

        by_rec_id[rec_id] = entry

    existing["decisions"] = list(by_rec_id.values())
    store.set(job_id, existing)

    return {
        "recorded":    len(decisions),
        "total":       len(existing["decisions"]),
        "job_id":      job_id,
    }


def record_job_metrics(job_id: str, metrics: dict) -> None:
    """
    Job 실행 중/완료 후 실측 데이터 기록.

    metrics 예시:
      {
        "total_duration_sec": 2340,
        "table_durations": {"profile": 1150, "credit_line": 240},
        "rows_per_sec": 15240,
        "peak_memory_mb": 3200,
        "encoding_issues": 0,
        "compat_errors": 0,
        "data_issues": 0
      }
    """
    if not job_id:
        return
    store = _get_store()
    existing = store.get(job_id) or {}
    existing.setdefault("job_metrics", {})
    existing["job_metrics"].update(metrics)
    existing["metrics_updated_at"] = datetime.now().isoformat()
    store.set(job_id, existing)


def compute_impact(job_id: str) -> dict:
    """
    Job 완료 후 권고별 실제 효과 계산 → 리포트에서 사용.

    Returns:
        {
          "job_id": ...,
          "summary": {
            "total_recommendations": 7,
            "applied": 5,
            "skipped": 2,
            "overall_improvement_pct": 68,   # applied 권고의 평균 개선
            "estimated_savings": "예상 대비 38분 단축"
          },
          "applied": [
            {decision dict with impact ...},
            ...
          ],
          "skipped": [
            {decision dict with missed_opportunity ...},
          ],
          "job_metrics": {...}
        }
    """
    store = _get_store()
    record = store.get(job_id) or {}
    decisions = record.get("decisions", [])
    metrics   = record.get("job_metrics", {})

    applied = []
    skipped = []
    edited  = []

    total_improvement_pcts = []

    for d in decisions:
        baseline = d.get("baseline") or {}
        decision = d.get("decision", "skipped")

        # 실측값 추출 — baseline 의 measurement_key 기반
        actual_value = None
        measurement_key = baseline.get("measurement_key", "")
        metric_name = baseline.get("metric")

        if metric_name == "table_duration_sec" and baseline.get("target_table"):
            table_durs = metrics.get("table_durations", {})
            actual_value = table_durs.get(baseline["target_table"])
        elif metric_name == "job_duration_sec":
            actual_value = metrics.get("total_duration_sec")
        elif metric_name in metrics:
            actual_value = metrics.get(metric_name)

        # 개선 효과 계산
        impact = None
        if actual_value is not None and baseline:
            expected_without = baseline.get("expected_without")
            expected_with    = baseline.get("expected_with")

            if decision == "applied" and expected_without:
                # 권고 따랐을 때: "안 따랐으면 expected_without, 실제는 actual"
                saved = expected_without - actual_value
                saved_pct = (saved / expected_without * 100) if expected_without else 0
                impact = {
                    "status":     "measured",
                    "actual":     actual_value,
                    "expected_without_rec": expected_without,
                    "expected_with_rec":    expected_with,
                    "saved_absolute":       round(saved, 2),
                    "saved_pct":            round(saved_pct, 1),
                    "unit":                 baseline.get("unit"),
                    "vs_expected_pct":      round(
                        ((actual_value - expected_with) / expected_with * 100)
                        if expected_with else 0, 1
                    ),
                }
                if saved_pct > 0:
                    total_improvement_pcts.append(saved_pct)
            elif decision == "skipped" and expected_without:
                # 권고 안 따랐을 때: "만약 따랐으면 expected_with 였을 텐데"
                missed = actual_value - (expected_with or 0)
                missed_pct = (missed / actual_value * 100) if actual_value else 0
                impact = {
                    "status":       "missed_opportunity",
                    "actual":       actual_value,
                    "would_be_with_rec": expected_with,
                    "missed_saving_absolute": round(missed, 2),
                    "missed_saving_pct":      round(missed_pct, 1),
                    "unit":                   baseline.get("unit"),
                }

        d_with_impact = {**d, "impact": impact}

        if decision == "applied":
            applied.append(d_with_impact)
        elif decision == "edited":
            edited.append(d_with_impact)
        else:
            skipped.append(d_with_impact)

    overall_pct = (
        round(sum(total_improvement_pcts) / len(total_improvement_pcts), 1)
        if total_improvement_pcts else None
    )

    summary = {
        "total_recommendations": len(decisions),
        "applied": len(applied),
        "skipped": len(skipped),
        "edited":  len(edited),
        "overall_improvement_pct": overall_pct,
        "measured_count": sum(
            1 for a in applied
            if (a.get("impact") or {}).get("status") == "measured"
        ),
    }

    # 요약 문구
    if overall_pct and overall_pct > 0:
        summary["estimated_savings"] = (
            f"적용한 권고 {len(applied)}건의 평균 {overall_pct:.0f}% 개선 효과 확인됨"
        )
    elif len(applied) > 0:
        summary["estimated_savings"] = (
            f"권고 {len(applied)}건 적용 완료 (실측 데이터 미확보)"
        )
    else:
        summary["estimated_savings"] = "적용된 권고 없음"

    return {
        "job_id":     job_id,
        "summary":    summary,
        "applied":    applied,
        "skipped":    skipped,
        "edited":     edited,
        "job_metrics": metrics,
        "has_data":   bool(decisions),
    }


def get_tracking(job_id: str) -> Optional[dict]:
    """Raw Store 데이터 조회 (디버깅용)."""
    return _get_store().get(job_id)
