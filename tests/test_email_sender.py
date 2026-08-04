"""
Unit tests for src/email_sender.py
"""

from src.email_sender import EmailSender
from src.config import load_config


def test_email_sender_dryrun(tmp_path):
    config = load_config()
    sender = EmailSender(config)
    pdf_path = tmp_path / "dummy.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy content")

    # When SMTP is not configured, should log warning and return True safely
    result = sender.send_report_email(pdf_path, product_count=3)
    assert result is True
