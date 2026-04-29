"""
tests/test_security.py — 비밀번호 암호화/마스킹 테스트
v10 #21
"""
import pytest


@pytest.fixture
def security(tmp_data_dir):
    """crypto 모듈 의존이 있어 별도 초기화."""
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("app.core.crypto") or mod.startswith("app.engine.security"):
            del sys.modules[mod]
    from app.engine import security
    from app.core import crypto
    yield security, crypto


class TestMaskToken:
    def test_mask_token_is_non_empty(self, security):
        sec, _ = security
        assert sec.MASK_TOKEN
        assert len(sec.MASK_TOKEN) > 0


class TestCryptoRoundTrip:
    def test_encrypt_decrypt(self, security):
        _, crypto = security
        if not crypto.is_available():
            pytest.skip("cryptography 패키지 미설치")
        original = "my-secret-password-123"
        enc = crypto.encrypt(original)
        assert enc != original
        assert enc.startswith("enc::")
        dec = crypto.decrypt(enc)
        assert dec == original

    def test_is_encrypted(self, security):
        _, crypto = security
        if not crypto.is_available():
            pytest.skip("cryptography 미설치")
        assert crypto.is_encrypted("enc::somevalue")
        assert not crypto.is_encrypted("plaintext")
        assert not crypto.is_encrypted("")

    def test_empty_string_handling(self, security):
        _, crypto = security
        if not crypto.is_available():
            pytest.skip("cryptography 미설치")
        # 빈 문자열 암호화는 그대로 빈 문자열이 바람직
        assert crypto.encrypt("") == ""
        assert crypto.decrypt("") == ""


class TestPreserveMaskedPasswords:
    """connector.py 의 _preserve_masked_passwords 핵심 로직 검증.
    직접 import 해서 테스트 — HTTP layer 없이 함수 단위."""

    def test_mask_token_replaced_with_original(self):
        from app.api.routes.connector import _preserve_masked_passwords, _MASK_TOKEN
        existing = {"source": {"password": "real_encrypted_val"}}
        incoming = {"source": {"password": _MASK_TOKEN, "host": "new_host"}}
        result = _preserve_masked_passwords(incoming, existing)
        assert result["source"]["password"] == "real_encrypted_val"
        assert result["source"]["host"] == "new_host"

    def test_empty_password_preserved(self):
        from app.api.routes.connector import _preserve_masked_passwords
        existing = {"source": {"password": "real_val"}}
        incoming = {"source": {"password": ""}}
        result = _preserve_masked_passwords(incoming, existing)
        assert result["source"]["password"] == "real_val"

    def test_new_password_passes_through(self):
        from app.api.routes.connector import _preserve_masked_passwords
        existing = {"source": {"password": "old"}}
        incoming = {"source": {"password": "new_password_123"}}
        result = _preserve_masked_passwords(incoming, existing)
        assert result["source"]["password"] == "new_password_123"
