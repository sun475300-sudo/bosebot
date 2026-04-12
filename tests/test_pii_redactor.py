import pytest
from src.pii_redactor import PIIRedactor


class TestPIIRedactor:
    @pytest.fixture
    def redactor(self):
        return PIIRedactor(enabled=True)

    def test_email_redaction(self, redactor):
        text = "연락처는 admin@example.com 혹은 hr@my-company.co.kr 입니다."
        expected = "연락처는 [REDACTED_EMAIL] 혹은 [REDACTED_EMAIL] 입니다."
        assert redactor.redact(text) == expected

    def test_phone_redaction(self, redactor):
        text = "제 번호는 010-1234-5678 이고 사무실은 02-987-6543 입니다. 01012345678도 됨."
        expected = "제 번호는 [REDACTED_PHONE] 이고 사무실은 [REDACTED_PHONE] 입니다. [REDACTED_PHONE]도 됨."
        assert redactor.redact(text) == expected

    def test_jumin_redaction(self, redactor):
        text = "초본 주민번호: 990101-1234567 확인 부탁드립니다."
        expected = "초본 주민번호: [REDACTED_JUMIN] 확인 부탁드립니다."
        assert redactor.redact(text) == expected

    def test_credit_card_redaction(self, redactor):
        text = "결제 카드 1234-5678-9012-3456 로 진행해주세요."
        expected = "결제 카드 [REDACTED_CREDIT_CARD] 로 진행해주세요."
        assert redactor.redact(text) == expected

    def test_mixed_pii(self, redactor):
        text = "이름: 김보안, 이메일: secure_99@test.com, 연락처 010-9999-8888"
        expected = "이름: 김보안, 이메일: [REDACTED_EMAIL], 연락처 [REDACTED_PHONE]"
        assert redactor.redact(text) == expected

    def test_disabled_redactor(self):
        redactor = PIIRedactor(enabled=False)
        text = "내 번호 010-1234-5678"
        assert redactor.redact(text) == text

    def test_no_pii(self, redactor):
        text = "보세전시장의 반출 규정에 대해 알려주세요."
        assert redactor.redact(text) == text
