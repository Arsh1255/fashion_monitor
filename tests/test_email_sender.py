"""
Unit tests for src/email_sender.py
"""

from dataclasses import replace

from src.email_sender import EmailSender
from src.config import load_config


def test_email_sender_dryrun(tmp_path):
    config = replace(
        load_config(), smtp_user="", smtp_password="", notification_email=""
    )
    sender = EmailSender(config)
    pdf_path = tmp_path / "dummy.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy content")

    # When SMTP is not configured, should log warning and return True safely
    result = sender.send_report_email(pdf_path, product_count=3)
    assert result is True


def test_email_sender_uses_report_categories(tmp_path, monkeypatch):
    pdf_path = tmp_path / "men.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy content")
    config = replace(
        load_config(),
        smtp_user="sender@example.net",
        smtp_password="test-password",
        notification_email="reports@example.net",
    )
    sent_messages = []

    class FakeSMTP:
        def __init__(self, server, port):
            self.server = server
            self.port = port

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def starttls(self):
            pass

        def login(self, user, password):
            assert user == "sender@example.net"
            assert password == "test-password"

        def send_message(self, message):
            sent_messages.append(message)

    monkeypatch.setattr("src.email_sender.smtplib.SMTP", FakeSMTP)

    assert EmailSender(config).send_report_email({"Men": pdf_path}, 1) is True
    assert len(sent_messages) == 1
    assert "Men" in sent_messages[0].as_string()
