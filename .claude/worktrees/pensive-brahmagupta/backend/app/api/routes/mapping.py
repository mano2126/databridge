"""
app/api/routes/mapping.py
타입 매핑 규칙 API — JSON 영속성 적용
"""
from fastapi import APIRouter, HTTPException
import uuid
from app.core.store import Store

router = APIRouter()

_rules = Store("mapping_rules")

# 기본 규칙 (mapping_rules.json 없을 때만)
if len(_rules) == 0:
    _defaults = [
        {"src_db":"mssql","tgt_db":"mysql","src_type":"NVARCHAR","tgt_type":"VARCHAR({n}) CHARACTER SET utf8mb4","note":"Collation 필수","warning":True,"custom":False},
        {"src_db":"mssql","tgt_db":"mysql","src_type":"INT IDENTITY","tgt_type":"INT AUTO_INCREMENT","note":"Seed 값 확인","warning":True,"custom":False},
        {"src_db":"mssql","tgt_db":"mysql","src_type":"DATETIME","tgt_type":"DATETIME(3)","note":"ms 손실 주의","warning":True,"custom":False},
        {"src_db":"mssql","tgt_db":"mysql","src_type":"BIT","tgt_type":"TINYINT(1)","note":None,"warning":False,"custom":False},
        {"src_db":"mssql","tgt_db":"mysql","src_type":"MONEY","tgt_type":"DECIMAL(19,4)","note":None,"warning":False,"custom":False},
        {"src_db":"mssql","tgt_db":"mysql","src_type":"UNIQUEIDENTIFIER","tgt_type":"CHAR(36)","note":"UUID 형식","warning":False,"custom":False},
        {"src_db":"mssql","tgt_db":"mysql","src_type":"VARBINARY(MAX)","tgt_type":"LONGBLOB","note":None,"warning":False,"custom":False},
        {"src_db":"oracle","tgt_db":"postgresql","src_type":"NUMBER","tgt_type":"NUMERIC({p},{s})","note":None,"warning":False,"custom":False},
        {"src_db":"oracle","tgt_db":"postgresql","src_type":"DATE","tgt_type":"TIMESTAMP","note":"시간 포함 여부 확인","warning":True,"custom":False},
        {"src_db":"oracle","tgt_db":"postgresql","src_type":"VARCHAR2","tgt_type":"VARCHAR","note":None,"warning":False,"custom":False},
        {"src_db":"oracle","tgt_db":"postgresql","src_type":"CLOB","tgt_type":"TEXT","note":None,"warning":False,"custom":False},
        {"src_db":"mysql","tgt_db":"mssql","src_type":"TINYINT(1)","tgt_type":"BIT","note":None,"warning":False,"custom":False},
        {"src_db":"mysql","tgt_db":"mssql","src_type":"TEXT","tgt_type":"NVARCHAR(MAX)","note":None,"warning":False,"custom":False},
        {"src_db":"mysql","tgt_db":"mssql","src_type":"DATETIME","tgt_type":"DATETIME2(6)","note":"정밀도 향상","warning":False,"custom":False},
        {"src_db":"mysql","tgt_db":"mssql","src_type":"AUTO_INCREMENT","tgt_type":"IDENTITY(1,1)","note":None,"warning":False,"custom":False},
    ]
    for r in _defaults:
        rid = str(uuid.uuid4())[:8]
        _rules.set(rid, {"id": rid, **r})


@router.get("/rules")
def list_rules(src_db: str = "", tgt_db: str = ""):
    result = _rules.values()
    if src_db: result = [r for r in result if r.get("src_db") == src_db]
    if tgt_db: result = [r for r in result if r.get("tgt_db") == tgt_db]
    return result


@router.post("/rules", status_code=201)
def create_rule(body: dict):
    rid  = str(uuid.uuid4())[:8]
    rule = {"id": rid, "custom": True, **body}
    _rules.set(rid, rule)
    return rule


@router.put("/rules/{rule_id}")
def update_rule(rule_id: str, body: dict):
    existing = _rules.get(rule_id)
    if existing is None:
        raise HTTPException(404, "규칙을 찾을 수 없습니다")
    updated = {**existing, **body, "id": rule_id}
    _rules.set(rule_id, updated)
    return updated


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: str):
    if rule_id not in _rules:
        raise HTTPException(404, "규칙을 찾을 수 없습니다")
    _rules.delete(rule_id)
