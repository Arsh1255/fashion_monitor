"""
SMTP email dispatcher module for Fashion Trend Monitor.

Constructs HTML MIME email messages with attached category PDF reports (e.g. Men, Women, Kids)
and dispatches them via SMTP (Gmail, Outlook, custom SMTP server).
"""

import smtplib
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Union, Dict
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from src.config import Config

logger = logging.getLogger(__name__)


class EmailSender:
    """Dispatches MIME emails with attached category PDF reports."""

    def __init__(self, config: Config):
        self.config = config

    def send_report_email(self, pdf_paths: Union[Path, List[Path], Dict[str, Path]], product_count: int) -> bool:
        """
        Send an email containing category PDF reports as attachments.

        Args:
            pdf_paths: Single PDF Path, list of PDF Paths, or dict of category->Path.
            product_count: Total number of new products detected.

        Returns:
            True if email sent successfully (or skipped in dry run), False on error.
        """
        is_placeholder = (
            not self.config.smtp_user or
            not self.config.smtp_password or
            "your_email" in self.config.smtp_user or
            "your_app_password" in self.config.smtp_password or
            not self.config.notification_email or
            "recipient@example.com" in self.config.notification_email
        )
        if is_placeholder:
            logger.warning("SMTP credentials or recipient email not configured (or placeholders). Skipping email dispatch.")
            return True

        if isinstance(pdf_paths, Path):
            path_list = [pdf_paths]
        elif isinstance(pdf_paths, dict):
            path_list = list(pdf_paths.values())
        else:
            path_list = pdf_paths

        valid_paths = [p for p in path_list if p and p.exists()]
        if not valid_paths:
            logger.error("No valid PDF report files exist to attach to email.")
            return False

        today_str = datetime.now().strftime("%B %d, %Y")
        subject = f"[Fashion Monitor] New Arrivals Trend Report ({product_count} New Items) - {today_str}"

        if isinstance(pdf_paths, dict):
            categories_str = ", ".join(str(category) for category in pdf_paths)
        else:
            categories_str = "Fashion categories"

        html_body = f"""
        <html>
          <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
            <h2 style="color: #0f172a;">Fashion Trend Monitoring Update</h2>
            <p>Hello,</p>
            <p>The single-run monitoring cycle has completed for <b>{today_str}</b>.</p>
            <table style="border-collapse: collapse; margin: 15px 0;">
              <tr>
                <td style="padding: 8px 12px; background-color: #f1f5f9; font-weight: bold;">New Items Detected:</td>
                <td style="padding: 8px 12px; background-color: #f1f5f9;">{product_count}</td>
              </tr>
              <tr>
                <td style="padding: 8px 12px; background-color: #ffffff; font-weight: bold;">Categories Monitored:</td>
                <td style="padding: 8px 12px; background-color: #ffffff;">{categories_str}</td>
              </tr>
              <tr>
                <td style="padding: 8px 12px; background-color: #f1f5f9; font-weight: bold;">Attached Reports:</td>
                <td style="padding: 8px 12px; background-color: #f1f5f9;">{len(valid_paths)} Category PDF File(s)</td>
              </tr>
            </table>
            <p>Please find attached the dedicated category PDF report(s) containing product screenshots and NVIDIA NIM visual AI findings (fabric composition, pattern details, and textile weaves).</p>
            <br/>
            <hr style="border: none; border-top: 1px solid #e2e8f0;"/>
            <p style="font-size: 11px; color: #64748b;">This email was sent automatically by Fashion Trend Monitor.</p>
          </body>
        </html>
        """

        try:
            msg = MIMEMultipart()
            msg["From"] = self.config.smtp_user
            msg["To"] = self.config.notification_email
            msg["Subject"] = subject
            msg.attach(MIMEText(html_body, "html"))

            for pdf_path in valid_paths:
                with open(pdf_path, "rb") as f:
                    attach = MIMEApplication(f.read(), _subtype="pdf")
                    attach.add_header("Content-Disposition", "attachment", filename=pdf_path.name)
                    msg.attach(attach)

            logger.info(f"Connecting to SMTP server {self.config.smtp_server}:{self.config.smtp_port}...")
            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                server.starttls()
                server.login(self.config.smtp_user, self.config.smtp_password)
                server.send_message(msg)

            logger.info(f"Successfully sent report email to {self.config.notification_email} with {len(valid_paths)} attachment(s).")
            return True

        except Exception as e:
            logger.error(f"Failed to send SMTP email: {e}")
            return False
