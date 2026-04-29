"""
app/api/routes/ai_assistant.py
Claude API 연동 — AI 보조 기능
  GET  /status        : API 연결 상태 확인 (과금 없음)
  POST /chat          : 자유 대화 (이관 관련 질문)
  POST /convert-ddl   : DDL 변환 보조
  POST /analyze-error : 이관 오류 분석 및 해결 방안
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import os, logging, re

router = APIRouter()
_log = logging.getLogger("databridge.ai")


# ── API 키 조회 (settings 저장값 우선, 환경변수 폴백) ──────────
def _get_api_key() -> str:
    """Settings 페이지에서 저장한 키 → 환경변수 순서로 조회"""
    try:
        from app.api.routes.settings import _cfg
        key = _cfg().get("anthropic_api_key", "").strip()
        if key:
            return key
    except Exception:
        pass
    return os.environ.get("ANTHROPIC_API_KEY", "").strip()


def _get_client():
    key = _get_api_key()
    if not key:
        raise HTTPException(
            400,
            "Anthropic API 키가 설정되지 않았습니다. "
            "시스템 설정 → API 키 에서 입력해 주세요."
        )
    try:
        import anthropic
        return anthropic.Anthropic(api_key=key)
    except ImportError:
        raise HTTPException(500, "anthropic 패키지가 설치되지 않았습니다. pip install anthropic")


# ── 요청 모델 ─────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    history: list = []
    context: Optional[str] = None

class ConvertDDLRequest(BaseModel):
    ddl: str
    obj_type: str
    src_db: str
    tgt_db: str
    error_msg: Optional[str] = None

class AnalyzeErrorRequest(BaseModel):
    error_msg: str
    ddl: Optional[str] = None
    src_db: Optional[str] = None
    tgt_db: Optional[str] = None
    context: Optional[str] = None


# ── 1. 상태 확인 (과금 없음 — 키 형식 검증만) ─────────────────
@router.get("/status")
def check_status():
    """API 키 설정 여부 및 형식 확인 (실제 API 호출 없음)"""
    key = _get_api_key()
    if not key:
        return {"status": "not_configured", "message": "API 키 미설정 — 시스템 설정에서 입력하세요"}
    if not key.startswith("sk-ant-"):
        return {"status": "error", "message": "API 키 형식 오류 (sk-ant-... 형태여야 합니다)"}
    masked = key[:12] + "..." + key[-4:]
    return {"status": "ok", "message": f"API 키 설정됨 ({masked})"}


# ── 2. 자유 대화 ──────────────────────────────────────────────
@router.post("/chat")
def chat(req: ChatRequest):
    """DataBridge 관련 AI 어시스턴트 대화"""
    client = _get_client()

    system_prompt = """당신은 DataBridge Studio의 AI 어시스턴트입니다.
DB 마이그레이션 전문가로서 다음 분야를 도와드립니다:
- MSSQL, MySQL, Oracle, PostgreSQL, DB2, SAP HANA 등 DB 간 데이터 이관
- SQL/DDL 변환 (프로시저, 함수, 트리거, 뷰, 이벤트)
- 이관 오류 분석 및 해결 방안
- 타입 매핑 및 데이터 변환 규칙
- 배치 크기, 병렬 처리, 성능 최적화
답변은 한국어로, 명확하고 실용적으로 해주세요.
코드 예시는 SQL 코드 블록을 사용해 주세요."""

    if req.context:
        system_prompt += f"\n\n현재 컨텍스트:\n{req.context}"

    messages = list(req.history) + [{"role": "user", "content": req.message}]

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2048,
            system=system_prompt,
            messages=messages
        )
        reply = response.content[0].text
        _log.info("AI 대화 완료 — 입력:%d 출력:%d 토큰",
                  response.usage.input_tokens, response.usage.output_tokens)
        return {
            "reply": reply,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
        }
    except Exception as e:
        _log.error("AI 대화 오류: %s", e)
        raise HTTPException(500, f"AI 응답 오류: {e}")


# ── 3. DDL 변환 보조 ──────────────────────────────────────────
@router.post("/convert-ddl")
def convert_ddl(req: ConvertDDLRequest):
    """Claude API로 DDL 변환"""
    client = _get_client()

    error_context = ""
    if req.error_msg:
        error_context = (
            f"\n\n이전 변환 시도에서 발생한 오류:\n{req.error_msg}\n"
            "위 오류를 반드시 해결하여 변환해 주세요."
        )

    tgt_is_mysql = req.tgt_db.lower() in ("mysql", "mariadb", "aurora", "tidb")
    mysql_note = """
MySQL/MariaDB 변환 시 반드시 지켜야 할 규칙:
- DELIMITER 명령어 절대 포함 금지 (pymysql 미지원)
- CREATE TRIGGER/PROCEDURE/FUNCTION 문 하나만 완전하게 작성
- 본문은 BEGIN ... END; 로 마무리
- INSERT INTO tbl (col) VALUES (...) 형식 준수 (VALUES 절 필수)
""" if tgt_is_mysql else ""

    prompt = (
        f"다음 {req.src_db.upper()} {req.obj_type}을 {req.tgt_db.upper()}용으로 변환해주세요.\n"
        f"{mysql_note}"
        f"\n원본 DDL ({req.src_db.upper()}):\n```sql\n{req.ddl}\n```"
        f"{error_context}\n\n"
        "요구사항:\n"
        f"1. {req.tgt_db.upper()}에서 바로 실행 가능한 완전한 DDL만 반환\n"
        "2. 코드 블록(```) 없이 SQL만 반환\n"
        "3. 설명 없이 SQL 코드만 반환\n"
        "4. 변환 불가능한 구문은 -- 주석으로 처리"
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        converted = response.content[0].text.strip()
        converted = re.sub(r'^```\w*\n?', '', converted)
        converted = re.sub(r'\n?```$', '', converted).strip()

        _log.info("DDL 변환 완료 [%s] %s→%s", req.obj_type, req.src_db, req.tgt_db)
        return {
            "converted_ddl": converted,
            "src_db": req.src_db,
            "tgt_db": req.tgt_db,
            "obj_type": req.obj_type,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
        }
    except Exception as e:
        _log.error("DDL 변환 오류: %s", e)
        raise HTTPException(500, f"AI 변환 오류: {e}")


# ── 4. 오류 분석 ──────────────────────────────────────────────
@router.post("/analyze-error")
def analyze_error(req: AnalyzeErrorRequest):
    """이관 오류 메시지 분석 및 해결 방안 제시"""
    client = _get_client()

    ddl_ctx = f"\n\n관련 DDL:\n```sql\n{req.ddl}\n```" if req.ddl else ""
    db_ctx  = f"\n이관 방향: {req.src_db} → {req.tgt_db}" if req.src_db and req.tgt_db else ""
    extra   = f"\n\n추가 컨텍스트:\n{req.context}" if req.context else ""

    prompt = (
        f"다음 DB 이관 오류를 분석하고 해결 방안을 제시해주세요.\n{db_ctx}\n\n"
        f"오류 메시지:\n{req.error_msg}{ddl_ctx}{extra}\n\n"
        "아래 형식으로 답변해주세요:\n\n"
        "**1. 원인 분석**\n오류 원인을 구체적으로 설명해주세요.\n\n"
        "**2. 해결 방안**\n단계별 해결 방법을 알려주세요.\n\n"
        "**3. 수정된 DDL**\n(DDL이 제공된 경우) 수정된 전체 DDL을 코드 블록으로 제공해주세요."
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )
        _log.info("오류 분석 완료 — 입력:%d 출력:%d 토큰",
                  response.usage.input_tokens, response.usage.output_tokens)
        return {
            "analysis": response.content[0].text,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
        }
    except Exception as e:
        _log.error("오류 분석 실패: %s", e)
        raise HTTPException(500, f"AI 분석 오류: {e}")
