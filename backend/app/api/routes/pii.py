"""
app/api/routes/pii.py — PII Privacy Scanner REST API
Phase F-1c (2026-04-25)

Endpoints:
  POST  /pii/scan                 — 테이블 PII 자동 스캔 (탐지)
  POST  /pii/preview              — 마스킹 미리보기 (Before/After)
  POST  /pii/generate-sql         — 마스킹 SQL 자동 생성
  GET   /pii/presets              — 사용 가능한 Preset 정책 목록
  POST  /pii/apply-policies       — Job 에 마스킹 정책 적용 (Wizard 연동용)
  GET   /pii/health               — 라우터 헬스체크

설계 원칙:
  - advisor.py 패턴 따름 (FastAPI + Pydantic)
  - 모든 요청에 Job context 가능 (job_id 또는 직접 selection)
  - 응답은 위저드에서 그대로 표시 가능한 형태
  - 에러는 명확하게 HTTP 4xx/5xx + detail
"""

from __future__ import annotations

import logging
from typing import Any, Optional, List, Dict

from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel, Field

from app.core.pii_detector import (
    scan_table_schema,
    summarize_detections,
    PIIDetection,
    PIICategory,
    PIISensitivity,
)
from app.core.pii_masker import (
    PIIMasker,
    MaskingStrategy,
    MaskingPreset,
    MaskingPolicy,
    build_policies_from_preset,
    generate_preview,
    generate_masking_sql,
)

logger = logging.getLogger("databridge.pii")
router = APIRouter()


# ════════════════════════════════════════════════════════════════════════════
# 요청 스키마
# ════════════════════════════════════════════════════════════════════════════

class ColumnInfo(BaseModel):
    """컬럼 정보"""
    name: str = Field(..., description="컬럼명")
    type: Optional[str] = Field(None, description="컬럼 타입 (참고용)")
    nullable: Optional[bool] = Field(None)


class TableSchema(BaseModel):
    """단일 테이블 스키마 + 샘플 데이터"""
    table_name: str = Field(..., description="테이블명 (스키마 포함 가능)")
    columns: List[ColumnInfo] = Field(default_factory=list)
    sample_data: Optional[Dict[str, List[Any]]] = Field(
        None,
        description="컬럼별 샘플 데이터 (보통 100건). None 이면 컬럼명만으로 추정"
    )


class ScanRequest(BaseModel):
    """PII 스캔 요청"""
    tables: List[TableSchema] = Field(..., description="스캔 대상 테이블 목록")
    job_id: Optional[str] = Field(None, description="Job ID (선택)")
    source_profile_id: Optional[str] = Field(
        None,
        description=(
            "소스 DB 프로파일 ID. 제공 시 백엔드가 자동으로 샘플 데이터 fetch. "
            "(sample_data 직접 제공 안 하는 경우 — 정확도 향상)"
        ),
    )
    sample_count: int = Field(
        100,
        description="자동 샘플링 시 컬럼당 row 수 (기본 100)",
        ge=10, le=1000,
    )


class PreviewRequest(BaseModel):
    """마스킹 미리보기 요청"""
    tables: List[TableSchema] = Field(..., description="대상 테이블")
    preset: str = Field("dev_environment", description="Preset 이름")
    custom_policies: Optional[List[Dict[str, str]]] = Field(
        None,
        description="사용자 정의 정책 (preset='custom' 일 때). [{column, strategy}]"
    )
    sample_count: int = Field(5, description="컬럼당 미리보기 샘플 수")


class GenerateSQLRequest(BaseModel):
    """마스킹 SQL 생성 요청"""
    tables: List[TableSchema] = Field(...)
    preset: str = Field("dev_environment")
    custom_policies: Optional[List[Dict[str, str]]] = Field(None)
    target_db: str = Field("mysql", description="MySQL/MSSQL/PostgreSQL")


class ApplyPoliciesRequest(BaseModel):
    """Job 에 마스킹 정책 적용"""
    job_id: str = Field(..., description="DataBridge Job ID")
    tables: List[TableSchema] = Field(...)
    preset: str = Field(...)
    custom_policies: Optional[List[Dict[str, str]]] = Field(None)


# ════════════════════════════════════════════════════════════════════════════
# 응답 스키마
# ════════════════════════════════════════════════════════════════════════════

class DetectionEvidence(BaseModel):
    """탐지 근거 상세 (시각화용)"""
    column_name_signal: bool = Field(False, description="컬럼명 매칭 여부")
    column_name_pattern: Optional[str] = Field(None, description="매칭된 컬럼명 패턴")
    data_signal: bool = Field(False, description="데이터 패턴 매칭 여부")
    data_match_count: int = Field(0, description="데이터 매칭 row 수")
    data_total_count: int = Field(0, description="검사한 row 수")
    checksum_valid_count: int = Field(0, description="체크섬 통과 수 (RRN/사업자번호 등)")
    checksum_total_count: int = Field(0, description="체크섬 검사 대상 수")
    sample_examples_masked: List[str] = Field(
        default_factory=list,
        description="샘플 예시 (마스킹 처리된 형태로만 노출)",
    )


class DetectionResponse(BaseModel):
    """단일 탐지 결과"""
    column_name: str
    table_name: str
    category: str
    sensitivity: str
    confidence: float
    column_match: bool
    pattern_match_rate: float
    sample_count: int
    matched_count: int
    recommended_masking: str
    legal_reference: str
    
    # F-1f-2: 시각화 강화
    evidence: Optional[DetectionEvidence] = Field(
        None,
        description="탐지 근거 상세 (UI 시각화용)",
    )
    risk_label: str = Field("", description="위험도 라벨 (한글)")
    confidence_label: str = Field("", description="신뢰도 라벨 (LOW/MEDIUM/HIGH)")
    
    # v90.6: 컬럼 타입 정보 (UI 표시용)
    column_type: Optional[str] = Field(None, description="컬럼 데이터 타입 (예: VARCHAR(13))")


class ScanResponse(BaseModel):
    """스캔 응답"""
    success: bool = True
    job_id: Optional[str] = None
    detections: List[DetectionResponse]
    summary: Dict[str, Any]
    scan_metadata: Dict[str, Any]


class PreviewSample(BaseModel):
    """미리보기 단일 샘플"""
    before: str
    after: str


class PreviewItem(BaseModel):
    """컬럼별 미리보기"""
    table_name: str
    column_name: str
    category: str
    strategy: str
    samples: List[PreviewSample]


class PreviewResponse(BaseModel):
    """미리보기 응답"""
    success: bool = True
    preset: str
    items: List[PreviewItem]
    total_columns_masked: int


class GenerateSQLResponse(BaseModel):
    """SQL 생성 응답"""
    success: bool = True
    target_db: str
    sql_by_table: Dict[str, List[str]]
    total_columns: int


class PresetInfo(BaseModel):
    """Preset 정보"""
    id: str
    name: str
    description: str
    use_case: str
    legal_basis: List[str]


class PresetsResponse(BaseModel):
    """Preset 목록 응답"""
    presets: List[PresetInfo]


class ApplyPoliciesResponse(BaseModel):
    """정책 적용 응답"""
    success: bool = True
    job_id: str
    policies_applied: int
    sql_fragments_generated: int
    message: str


# ════════════════════════════════════════════════════════════════════════════
# 유틸리티
# ════════════════════════════════════════════════════════════════════════════

def _detection_to_response(d: PIIDetection, column_type: Optional[str] = None) -> DetectionResponse:
    """내부 모델 → 응답 모델 (F-1f-2: evidence + 라벨 추가)"""
    
    # 신뢰도 라벨
    if d.confidence >= 0.9:
        conf_label = "매우 높음"
    elif d.confidence >= 0.75:
        conf_label = "높음"
    elif d.confidence >= 0.5:
        conf_label = "보통"
    else:
        conf_label = "낮음"
    
    # 위험도 라벨 (한글)
    risk_labels = {
        "critical": "🔴 매우 위험",
        "high": "🟠 높음",
        "medium": "🟡 보통",
        "low": "🟢 낮음",
    }
    risk_label = risk_labels.get(d.sensitivity.value, d.sensitivity.value)
    
    # Evidence 빌드
    evidence = DetectionEvidence(
        column_name_signal=d.column_match,
        column_name_pattern=_describe_column_match(d.column_name, d.category) if d.column_match else None,
        data_signal=d.pattern_match_rate > 0,
        data_match_count=d.matched_count,
        data_total_count=d.sample_count,
        # 체크섬 검증 카테고리 (RRN/사업자번호/카드)
        checksum_valid_count=d.matched_count if d.category.value in ('rrn', 'frn', 'biz_number', 'card_number') else 0,
        checksum_total_count=d.sample_count if d.category.value in ('rrn', 'frn', 'biz_number', 'card_number') else 0,
        sample_examples_masked=[],  # 보안: 비워둠 (필요 시 별도 미리보기 API 사용)
    )
    
    return DetectionResponse(
        column_name=d.column_name,
        table_name=d.table_name,
        category=d.category.value,
        sensitivity=d.sensitivity.value,
        confidence=d.confidence,
        column_match=d.column_match,
        pattern_match_rate=d.pattern_match_rate,
        sample_count=d.sample_count,
        matched_count=d.matched_count,
        recommended_masking=d.recommended_masking,
        legal_reference=d.legal_reference,
        evidence=evidence,
        risk_label=risk_label,
        confidence_label=conf_label,
        column_type=column_type,  # v90.6
    )


def _describe_column_match(column_name: str, category) -> str:
    """컬럼명 매칭 설명 (사용자에게 왜 PII 인지 보여주기 위한)"""
    cat_descriptions = {
        "rrn": "주민번호 패턴 (rrn/jumin/주민)",
        "frn": "외국인등록번호 패턴",
        "phone": "휴대폰 패턴 (phone/mobile/휴대)",
        "phone_land": "일반전화 패턴",
        "email": "이메일 패턴 (email/mail)",
        "name_kor": "이름 패턴 (name/성명/이름)",
        "address": "주소 패턴 (addr/주소)",
        "dob": "생년월일 패턴 (birth/dob/생일)",
        "bank_account": "계좌번호 패턴 (account/acct/계좌)",
        "card_number": "카드번호 패턴 (card)",
        "card_cvv": "CVV 패턴",
        "biz_number": "사업자번호 패턴",
        "passport": "여권번호 패턴",
        "driver_license": "운전면허 패턴",
        "ip_address": "IP 주소 패턴",
        "mac_address": "MAC 주소 패턴",
    }
    return cat_descriptions.get(category.value, f"{category.value} 관련 키워드")


def _parse_preset(preset_str: str) -> MaskingPreset:
    """문자열 → Preset enum"""
    try:
        return MaskingPreset(preset_str.lower())
    except ValueError:
        valid = [p.value for p in MaskingPreset]
        raise HTTPException(
            status_code=400,
            detail=f"Unknown preset: {preset_str}. Valid: {valid}",
        )


def _scan_all_tables(
    tables: List[TableSchema],
) -> List[PIIDetection]:
    """모든 테이블 스캔"""
    all_detections = []
    for tbl in tables:
        cols_dict = [{"name": c.name, "type": c.type} for c in tbl.columns]
        detections = scan_table_schema(
            tbl.table_name,
            cols_dict,
            tbl.sample_data,
        )
        all_detections.extend(detections)
    return all_detections


def _build_policies(
    detections: List[PIIDetection],
    preset_str: str,
    custom_policies: Optional[List[Dict[str, str]]] = None,
) -> List[MaskingPolicy]:
    """정책 빌드 (preset 또는 custom)"""
    preset = _parse_preset(preset_str)
    
    if preset == MaskingPreset.CUSTOM and custom_policies:
        # 사용자 정의 정책
        policies = []
        # detection 을 column_name 으로 매핑
        det_map = {d.column_name: d for d in detections}
        
        for cp in custom_policies:
            col = cp.get("column")
            strategy_str = cp.get("strategy", "partial")
            
            try:
                strategy = MaskingStrategy(strategy_str.lower())
            except ValueError:
                logger.warning(f"Invalid strategy '{strategy_str}', using PARTIAL")
                strategy = MaskingStrategy.PARTIAL
            
            d = det_map.get(col)
            if not d:
                continue
            
            policies.append(MaskingPolicy(
                column_name=d.column_name,
                table_name=d.table_name,
                category=d.category,
                strategy=strategy,
            ))
        return policies
    
    return build_policies_from_preset(detections, preset)


# ════════════════════════════════════════════════════════════════════════════
# Endpoints
# ════════════════════════════════════════════════════════════════════════════

@router.get("/health")
async def health_check():
    """라우터 헬스체크"""
    return {
        "status": "ok",
        "module": "pii",
        "phase": "F-1c",
        "version": "1.0",
    }


@router.post("/scan", response_model=ScanResponse)
async def scan_pii(req: ScanRequest = Body(...)):
    """
    테이블에서 PII 자동 탐지.
    
    입력: 테이블 스키마 + (선택) 샘플 데이터 또는 source_profile_id
    출력: 탐지된 PII 컬럼 + 위험도 요약
    
    샘플 데이터 우선순위:
      1. tables[].sample_data (직접 제공)
      2. source_profile_id 가 있으면 백엔드 자동 fetch
      3. 둘 다 없으면 컬럼명만으로 추정 (정확도 ~60%)
    
    예시 호출 (자동 샘플링):
    {
      "tables": [{
        "table_name": "customer.profile",
        "columns": [{"name": "rrn", "type": "VARCHAR(13)"}]
      }],
      "source_profile_id": "abc-123",
      "sample_count": 100
    }
    """
    if not req.tables:
        raise HTTPException(400, "tables 는 비어있을 수 없습니다")
    
    sampling_meta = None
    
    # 자동 샘플링 시도
    if req.source_profile_id:
        sampling_meta = await _auto_sample_tables(
            req.source_profile_id, req.tables, req.sample_count
        )
    
    try:
        detections = _scan_all_tables(req.tables)
        summary = summarize_detections(detections)
        
        # v90.6: column_type 매핑 (tables → {(table, column): type})
        column_type_map = {}
        for t in req.tables:
            for col in t.columns:
                column_type_map[(t.table_name, col.name)] = col.type
        
        # 메타데이터
        total_columns = sum(len(t.columns) for t in req.tables)
        scan_meta = {
            "total_tables": len(req.tables),
            "total_columns": total_columns,
            "pii_columns": len(detections),
            "pii_ratio": round(len(detections) / max(total_columns, 1), 3),
            "with_sample_data": sum(1 for t in req.tables if t.sample_data),
        }
        if sampling_meta:
            scan_meta["auto_sampling"] = sampling_meta
        
        logger.info(
            f"[PII Scan] job={req.job_id}, tables={len(req.tables)}, "
            f"pii={len(detections)}, risk={summary.get('compliance_risk')}"
        )
        
        return ScanResponse(
            success=True,
            job_id=req.job_id,
            detections=[
                _detection_to_response(
                    d,
                    column_type=column_type_map.get((d.table_name, d.column_name)),
                )
                for d in detections
            ],
            summary=summary,
            scan_metadata=scan_meta,
        )
    
    except Exception as e:
        logger.error(f"[PII Scan] 실패: {e}", exc_info=True)
        raise HTTPException(500, f"스캔 실패: {e}")


async def _auto_sample_tables(
    profile_id: str,
    tables: List[TableSchema],
    sample_count: int,
) -> Optional[Dict[str, Any]]:
    """
    소스 프로파일에서 자동으로 샘플 데이터 fetch 후
    각 TableSchema 의 sample_data 를 채워 넣는다.
    
    실패 시 silent (탐지는 컬럼명만으로 진행).
    """
    try:
        from app.api.routes.connector import get_profile_decrypted
        from app.core.pii_sampler import (
            fetch_samples_for_tables, summarize_sampling,
        )
        
        profile = get_profile_decrypted(profile_id)
        if not profile:
            logger.warning(f"[PII Auto-sample] 프로파일 미발견: {profile_id}")
            return {"enabled": True, "success": False, "error": "프로파일 미발견"}
        
        # 샘플 fetch
        tables_arg = [
            {
                "table_name": t.table_name,
                "columns": [{"name": c.name, "type": c.type} for c in t.columns],
            }
            for t in tables
        ]
        
        results = fetch_samples_for_tables(profile, tables_arg, sample_count)
        
        # 각 테이블에 sample_data 주입
        for t in tables:
            r = results.get(t.table_name)
            if r and r.get('success'):
                # 기존 sample_data 가 없을 때만 채움 (사용자 제공 우선)
                if not t.sample_data:
                    t.sample_data = r.get('sample_data', {})
        
        return {
            "enabled": True,
            **summarize_sampling(results),
        }
    
    except Exception as e:
        logger.warning(f"[PII Auto-sample] 실패: {e}", exc_info=True)
        return {
            "enabled": True,
            "success": False,
            "error": str(e)[:200],
        }


@router.post("/preview", response_model=PreviewResponse)
async def preview_masking(req: PreviewRequest = Body(...)):
    """
    마스킹 적용 결과 미리보기.
    
    Before/After 형태로 사용자에게 보여줌.
    스캔 → 정책 빌드 → 미리보기 한 번에 처리.
    """
    if not req.tables:
        raise HTTPException(400, "tables 는 비어있을 수 없습니다")
    
    try:
        detections = _scan_all_tables(req.tables)
        if not detections:
            return PreviewResponse(
                success=True,
                preset=req.preset,
                items=[],
                total_columns_masked=0,
            )
        
        policies = _build_policies(detections, req.preset, req.custom_policies)
        
        # sample_data 합치기 (모든 테이블)
        all_samples: Dict[str, List[Any]] = {}
        for tbl in req.tables:
            if tbl.sample_data:
                all_samples.update(tbl.sample_data)
        
        previews = generate_preview(policies, all_samples, req.sample_count)
        
        items = []
        for pv in previews:
            # column → table 매핑
            table_name = next(
                (p.table_name for p in policies if p.column_name == pv.column_name),
                "unknown"
            )
            items.append(PreviewItem(
                table_name=table_name,
                column_name=pv.column_name,
                category=pv.category,
                strategy=pv.strategy,
                samples=[PreviewSample(before=s["before"], after=s["after"])
                        for s in pv.samples],
            ))
        
        # KEEP 정책은 미리보기에서 제외해야 (마스킹 안 됨)
        masked_count = sum(1 for p in policies if p.strategy != MaskingStrategy.KEEP)
        
        return PreviewResponse(
            success=True,
            preset=req.preset,
            items=items,
            total_columns_masked=masked_count,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PII Preview] 실패: {e}", exc_info=True)
        raise HTTPException(500, f"미리보기 실패: {e}")


@router.post("/generate-sql", response_model=GenerateSQLResponse)
async def generate_sql(req: GenerateSQLRequest = Body(...)):
    """
    마스킹 SQL 자동 생성.
    
    이관 SQL 의 SELECT 절에 그대로 끼워넣을 수 있는 형태.
    예: SELECT customer_id, [생성된 마스킹 SQL] FROM source_table
    """
    if not req.tables:
        raise HTTPException(400, "tables 는 비어있을 수 없습니다")
    
    target_db = req.target_db.lower()
    if target_db not in ("mysql", "mssql", "azure", "sqlserver", "postgres", "postgresql"):
        raise HTTPException(400, f"지원되지 않는 target_db: {req.target_db}")
    
    try:
        detections = _scan_all_tables(req.tables)
        if not detections:
            return GenerateSQLResponse(
                success=True,
                target_db=target_db,
                sql_by_table={},
                total_columns=0,
            )
        
        policies = _build_policies(detections, req.preset, req.custom_policies)
        sql_by_table = generate_masking_sql(policies, target_db)
        
        total = sum(len(v) for v in sql_by_table.values())
        
        logger.info(
            f"[PII SQL Gen] preset={req.preset}, target={target_db}, "
            f"tables={len(sql_by_table)}, columns={total}"
        )
        
        return GenerateSQLResponse(
            success=True,
            target_db=target_db,
            sql_by_table=sql_by_table,
            total_columns=total,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PII SQL Gen] 실패: {e}", exc_info=True)
        raise HTTPException(500, f"SQL 생성 실패: {e}")


@router.get("/presets", response_model=PresetsResponse)
async def list_presets():
    """
    사용 가능한 Preset 정책 목록.
    
    위저드 UI 의 정책 선택 드롭다운에 표시.
    """
    presets = [
        PresetInfo(
            id="dev_environment",
            name="개발 환경",
            description="가명화(Pseudonymization) — 같은 원본 → 같은 가짜 값. 조인 보존, 정합성 유지.",
            use_case="운영 → 개발 DB 이관 (조인/조회 테스트 가능)",
            legal_basis=[
                "개인정보보호법 §28 (안전조치)",
                "개인정보보호법 §28의2 (가명정보 처리)",
                "개인정보의 안전성 확보조치 기준",
            ],
        ),
        PresetInfo(
            id="qa_environment",
            name="QA 환경",
            description="Critical 등급 PII (RRN 등) 만 마스킹. 일반 정보는 유지.",
            use_case="QA/테스트 환경",
            legal_basis=[
                "개인정보보호법 §24 (고유식별정보)",
            ],
        ),
        PresetInfo(
            id="analytics",
            name="분석/통계",
            description="해시(Hash) + 일반화. 조인은 가능하나 개인 식별 불가.",
            use_case="BI / 데이터분석 환경",
            legal_basis=[
                "개인정보보호법 §28의2 (가명정보의 처리)",
                "GDPR Art. 4(5) Pseudonymisation",
            ],
        ),
        PresetInfo(
            id="production_clone",
            name="운영 복제",
            description="마스킹 없이 원본 그대로 이관. 운영→운영, DR 사이트.",
            use_case="DR 사이트 동기화 / 운영 백업",
            legal_basis=[
                "전자금융감독규정 §15 (데이터 백업)",
            ],
        ),
        PresetInfo(
            id="gdpr_compliant",
            name="GDPR 준수",
            description="가명화(Pseudonymization) 적용. 매핑테이블 별도 관리.",
            use_case="EU 시민 데이터 처리",
            legal_basis=[
                "GDPR Art. 25 Data Protection by Design",
                "GDPR Art. 32 Security of Processing",
            ],
        ),
        PresetInfo(
            id="pci_dss",
            name="PCI-DSS 준수",
            description="카드번호 PAN 마스킹, CVV 완전 제거.",
            use_case="결제/카드 시스템",
            legal_basis=[
                "PCI-DSS v4.0 Requirement 3 (Stored Card Data)",
                "여신전문금융업법 §54의5",
            ],
        ),
        PresetInfo(
            id="custom",
            name="사용자 정의",
            description="컬럼별로 직접 전략 선택.",
            use_case="복합 시나리오",
            legal_basis=[],
        ),
    ]
    
    return PresetsResponse(presets=presets)


@router.post("/apply-policies", response_model=ApplyPoliciesResponse)
async def apply_policies(req: ApplyPoliciesRequest = Body(...)):
    """
    Job 에 마스킹 정책 적용.
    
    위저드에서 사용자가 "다음" 버튼 누를 때 호출.
    Job context 에 마스킹 SQL 을 저장하여,
    이관 시 자동으로 마스킹된 SELECT 사용하도록 설정.
    
    NOTE: Job 컨텍스트 저장은 Phase F-1d (위저드 통합) 에서 완성.
          여기는 골격만 제공.
    """
    if not req.tables:
        raise HTTPException(400, "tables 는 비어있을 수 없습니다")
    
    try:
        detections = _scan_all_tables(req.tables)
        policies = _build_policies(detections, req.preset, req.custom_policies)
        sql_by_table = generate_masking_sql(policies, target_db="mysql")
        
        # TODO Phase F-1d: Job DB 에 정책 저장
        # from app.core.store import store
        # store.save_pii_policies(req.job_id, policies, sql_by_table)
        
        sql_count = sum(len(v) for v in sql_by_table.values())
        
        logger.info(
            f"[PII Apply] job={req.job_id}, preset={req.preset}, "
            f"policies={len(policies)}, sql={sql_count}"
        )
        
        return ApplyPoliciesResponse(
            success=True,
            job_id=req.job_id,
            policies_applied=len(policies),
            sql_fragments_generated=sql_count,
            message=f"{len(policies)}개 컬럼에 마스킹 정책 적용 완료",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PII Apply] 실패: {e}", exc_info=True)
        raise HTTPException(500, f"정책 적용 실패: {e}")
