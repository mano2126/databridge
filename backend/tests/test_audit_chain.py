"""
tests/test_audit_chain.py — 감사 로그 해시 체인 무결성 테스트
v10 #21
"""
import pytest


class TestBasicRecording:
    def test_record_creates_entry(self, audit_clean):
        audit_clean.record(action="test.run", status="ok")
        rows = list(audit_clean._store().values())
        assert len(rows) == 1
        e = rows[0]
        assert e["action"] == "test.run"
        assert "this_hash" in e
        assert "prev_hash" in e

    def test_first_record_has_null_prev(self, audit_clean):
        audit_clean.record(action="first")
        rows = list(audit_clean._store().values())
        assert rows[0]["prev_hash"] is None

    def test_second_record_chains_to_first(self, audit_clean):
        audit_clean.record(action="first")
        first = list(audit_clean._store().values())[0]
        audit_clean.record(action="second")
        rows = sorted(audit_clean._store().values(), key=lambda r: r["ts_epoch"])
        assert rows[1]["prev_hash"] == rows[0]["this_hash"]


class TestIntegrityVerification:
    def test_verify_ok_on_clean_chain(self, audit_clean):
        for i in range(5):
            audit_clean.record(action=f"act{i}", resource_id=str(i))
        result = audit_clean.verify_integrity()
        assert result["ok"] is True
        assert result["total"] == 5
        assert result["legacy"] == 0
        assert result["broken_at"] is None

    def test_verify_detects_tampering_in_middle(self, audit_clean):
        # 3개 기록 후 중간 것 변조
        for i in range(3):
            audit_clean.record(action=f"act{i}", resource_id=str(i))
        rows = sorted(audit_clean._store().values(), key=lambda r: r["ts_epoch"])
        middle = rows[1]
        # details 변조
        middle["details"] = {"hacked": "yes"}
        audit_clean._store().set(middle["id"], middle)
        result = audit_clean.verify_integrity()
        assert result["ok"] is False
        assert result["broken_reason"] == "hash_mismatch"

    def test_verify_detects_missing_chain(self, audit_clean):
        for i in range(3):
            audit_clean.record(action=f"act{i}")
        rows = sorted(audit_clean._store().values(), key=lambda r: r["ts_epoch"])
        # 중간 것 prev_hash 조작
        mid = rows[1]
        mid["prev_hash"] = "0" * 64
        audit_clean._store().set(mid["id"], mid)
        result = audit_clean.verify_integrity()
        assert result["ok"] is False
        assert result["broken_reason"] == "prev_mismatch"

    def test_verify_legacy_records_ignored(self, audit_clean):
        """this_hash 없는 예전 레코드는 체인에서 제외."""
        import uuid
        import time
        # 레거시 레코드 (hash 없음) 직접 삽입
        legacy = {
            "id": str(uuid.uuid4()),
            "ts": "2025-01-01T00:00:00",
            "ts_epoch": int(time.time()) - 86400,  # 어제
            "username": "old", "role": "admin",
            "action": "legacy.act", "resource": "",
            "resource_id": None, "status": "ok", "ip": None,
            "details": {},
        }
        audit_clean._store().set(legacy["id"], legacy)

        # 새 기록 추가
        audit_clean.record(action="new.act")
        result = audit_clean.verify_integrity()
        assert result["ok"] is True
        assert result["legacy"] == 1


class TestSensitiveDataRedaction:
    def test_password_field_redacted(self, audit_clean):
        audit_clean.record(
            action="test",
            details={"username": "u", "password": "plaintext-secret"},
        )
        rows = list(audit_clean._store().values())
        assert rows[0]["details"]["password"] == "***REDACTED***"
        assert rows[0]["details"]["username"] == "u"

    def test_token_field_redacted(self, audit_clean):
        audit_clean.record(
            action="test",
            details={"api_token": "bearer abc123"},
        )
        rows = list(audit_clean._store().values())
        assert rows[0]["details"]["api_token"] == "***REDACTED***"


class TestFailSafe:
    def test_record_never_raises(self, audit_clean):
        # 완전히 망가진 입력
        audit_clean.record(action=None, details={"bad": object()})
        # 예외 던지면 pytest 가 fail 잡음 — 여기까지 오면 통과
