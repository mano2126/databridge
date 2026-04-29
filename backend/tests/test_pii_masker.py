"""
tests/test_pii_masker.py — PII 탐지·마스킹 테스트
v10 #21
"""
import logging
import pytest


@pytest.fixture(scope="module")
def pm():
    from app.core import pii_masker
    return pii_masker


class TestRRNMasking:
    def test_rrn_with_hyphen(self, pm):
        assert "901231" in pm.mask_pii("주민번호 901231-1234567 입니다")
        assert "1234567" not in pm.mask_pii("주민번호 901231-1234567 입니다")

    def test_rrn_no_hyphen(self, pm):
        # 13자리 연속 숫자도 잡힘
        s = pm.mask_pii("RRN 9012311234567 입니다")
        assert "1234567" not in s

    def test_rrn_detected(self, pm):
        assert "RRN" in pm.detect_pii_types("901231-1234567")


class TestCardMasking:
    def test_16_digit_card(self, pm):
        s = pm.mask_pii("카드번호 4111-1111-1111-1111")
        assert "4111-1111-1111-1111" not in s
        assert "4111" in s   # 앞 4자리 유지
        assert "1111" in s   # 뒷 4자리 유지

    def test_card_no_separator(self, pm):
        s = pm.mask_pii("4111 1111 1111 1111")
        assert "4111 1111 1111 1111" not in s


class TestAccountMasking:
    def test_account_format(self, pm):
        # 농협 형태
        s = pm.mask_pii("계좌: 302-1234-5678-91 김철수")
        assert "302-1234-5678-91" not in s

    def test_short_account_not_overly_masked(self, pm):
        # 너무 짧으면 오탐 가능 — 최소 길이 보장
        s = pm.mask_pii("12-34")  # 5글자 — 매칭 안 됨 (최소 2-2-2 = 6자리)
        # 단정 없음, false positive 만 확인
        assert s == "12-34"


class TestPhoneMasking:
    def test_mobile_phone(self, pm):
        s = pm.mask_pii("연락처 010-1234-5678")
        assert "1234" not in s
        assert "5678" in s   # 뒷자리만 유지

    def test_phone_no_hyphen(self, pm):
        s = pm.mask_pii("01012345678 입니다")
        assert "12345" not in s


class TestEmailMasking:
    def test_email_basic(self, pm):
        s = pm.mask_pii("내 이메일은 choi@example.com 이야")
        assert "choi@" not in s
        assert "@example.com" in s  # 도메인은 유지

    def test_short_local_part(self, pm):
        s = pm.mask_pii("ab@x.com")
        assert "ab" not in s
        assert "@x.com" in s


class TestIPMasking:
    def test_private_ip_not_masked(self, pm):
        # 로컬/사설 IP 는 디버그에 필요하므로 유지
        assert "127.0.0.1" in pm.mask_pii("host 127.0.0.1")
        assert "192.168.1.100" in pm.mask_pii("host 192.168.1.100")
        assert "10.0.0.5" in pm.mask_pii("host 10.0.0.5")

    def test_public_ip_partial_mask(self, pm):
        s = pm.mask_pii("connect to 8.8.8.8 failed")
        assert "8.8.8.8" not in s
        assert "8.8" in s   # 앞 두 옥텟 유지


class TestAPIKeyMasking:
    def test_anthropic_key_pattern(self, pm):
        s = pm.mask_pii("API key is sk-ant-api03-abcdefghijklmnop12345")
        assert "abcdefghijklmnop" not in s

    def test_aws_access_key(self, pm):
        s = pm.mask_pii("AKIAIOSFODNN7EXAMPLE in config")
        assert "AKIAIOSFODNN7EXAMPLE" not in s


class TestPasswordKVMasking:
    def test_password_kv(self, pm):
        s = pm.mask_pii('config: password="secret123"')
        assert "secret123" not in s
        assert "***" in s

    def test_pwd_variant(self, pm):
        s = pm.mask_pii("pwd: mySecret")
        assert "mySecret" not in s


class TestContainsAndDetect:
    def test_contains_pii_positive(self, pm):
        assert pm.contains_pii("901231-1234567") is True
        assert pm.contains_pii("010-1234-5678") is True

    def test_contains_pii_negative(self, pm):
        assert pm.contains_pii("hello world") is False
        assert pm.contains_pii("SELECT * FROM users") is False

    def test_contains_non_string_safe(self, pm):
        assert pm.contains_pii(None) is False
        assert pm.contains_pii(123) is False

    def test_detect_multiple(self, pm):
        types = pm.detect_pii_types("RRN 901231-1234567, 연락처 010-1234-5678")
        assert "RRN" in types
        assert "PHONE" in types


class TestEdgeCases:
    def test_none_input(self, pm):
        assert pm.mask_pii(None) == ""

    def test_non_string_input(self, pm):
        # 숫자/불리언도 안전하게 str 변환
        result = pm.mask_pii(12345)
        assert isinstance(result, str)

    def test_empty_string(self, pm):
        assert pm.mask_pii("") == ""

    def test_clean_sql_passes_through(self, pm):
        sql = "SELECT col1, col2 FROM my_table WHERE id = 100"
        assert pm.mask_pii(sql) == sql


class TestLoggingFilter:
    def test_filter_masks_msg(self, pm):
        flt = pm.PIILogFilter()
        record = logging.LogRecord(
            name="t", level=logging.INFO, pathname="", lineno=0,
            msg="사용자 주민번호 901231-1234567 가입", args=(),
            exc_info=None,
        )
        flt.filter(record)
        assert "1234567" not in record.msg

    def test_filter_masks_args_tuple(self, pm):
        flt = pm.PIILogFilter()
        record = logging.LogRecord(
            name="t", level=logging.INFO, pathname="", lineno=0,
            msg="user %s logged in", args=("901231-1234567",),
            exc_info=None,
        )
        flt.filter(record)
        formatted = record.getMessage()
        assert "1234567" not in formatted

    def test_filter_never_raises(self, pm):
        flt = pm.PIILogFilter()
        # 이상한 args 타입
        class Weird:
            def __str__(self): raise RuntimeError("boom")
        record = logging.LogRecord(
            name="t", level=logging.INFO, pathname="", lineno=0,
            msg="msg", args=(Weird(),), exc_info=None,
        )
        # 예외 던지면 안 됨
        assert flt.filter(record) is True
