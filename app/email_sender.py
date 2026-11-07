"""
Email Sender — Password Reset Delivery via SMTP
================================================
Sends password reset links via Gmail SMTP.
Features:
- Full HTML escaping of any user-controlled values (username)
- Plain text fallback
- Masked logging of email addresses (never logs full emails or reset tokens)
- Reuses existing SMTP configuration
"""

import html
import logging
import smtplib
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import current_app

logger = logging.getLogger(__name__)

DEFAULT_SMTP_TIMEOUT = 10.0


class EmailDeliveryError(Exception):
    """Raised when password reset email delivery fails."""
    pass


def mask_email(email: str) -> str:
    """Mask email for safe logging (e.g. s***@gmail.com)."""
    if not email or '@' not in email:
        return '***'
    user_part, domain_part = email.split('@', 1)
    if len(user_part) <= 1:
        masked_user = user_part + '***'
    else:
        masked_user = user_part[0] + '***'
    return f"{masked_user}@{domain_part}"


def send_password_reset_email(to_email: str, reset_url: str, username: str) -> None:
    """
    Send a password reset email containing the secure link to the user.
    Escapes all user-provided variables.
    """
    mail_server = current_app.config.get('MAIL_SERVER', 'smtp.gmail.com')
    mail_port = current_app.config.get('MAIL_PORT', 587)
    mail_use_tls = current_app.config.get('MAIL_USE_TLS', True)
    mail_username = current_app.config.get('MAIL_USERNAME', '').strip()
    mail_password = current_app.config.get('MAIL_PASSWORD', '').replace(' ', '').strip()
    mail_timeout = float(current_app.config.get('MAIL_TIMEOUT_SECONDS', DEFAULT_SMTP_TIMEOUT))

    if not mail_username or not mail_password:
        raise ValueError("SMTP credentials not configured. Set MAIL_USERNAME and MAIL_PASSWORD.")

    app_name = current_app.config.get('APP_NAME', 'KickoffXI')
    safe_username = html.escape(username or 'User')
    safe_reset_url = html.escape(reset_url)

    subject = f"{app_name} — Password Reset Request"

    html_body = f"""
    <div style="font-family: 'Inter', -apple-system, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px 24px;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h1 style="color: #141e33; font-size: 20px; font-weight: 800; letter-spacing: 0.05em; text-transform: uppercase; margin: 0;">
                {app_name}
            </h1>
        </div>

        <div style="background: #f8f9fa; border-radius: 16px; padding: 32px 24px; text-align: center;">
            <h2 style="color: #141e33; font-size: 18px; font-weight: 700; margin: 0 0 8px 0;">
                Password Reset
            </h2>
            <p style="color: #667; font-size: 14px; margin: 0 0 24px 0; line-height: 1.5;">
                Hi <strong>{safe_username}</strong>, click the button below to choose a new password for your account.
            </p>

            <div style="margin: 0 0 24px 0;">
                <a href="{safe_reset_url}"
                   style="display: inline-block; background: #d4a017; color: #141e33; font-size: 15px; font-weight: 700; text-decoration: none; padding: 12px 28px; border-radius: 10px;">
                    Reset Password
                </a>
            </div>

            <p style="color: #999; font-size: 12px; margin: 0; line-height: 1.5;">
                This password reset link is valid for a limited time and can only be used once.<br>
                If you didn't request a password reset, you can safely ignore this email.
            </p>
        </div>

        <p style="color: #ccc; font-size: 11px; text-align: center; margin-top: 24px;">
            &copy; 2026 {app_name}
        </p>
    </div>
    """

    text_body = (
        f"{app_name} — Password Reset\n\n"
        f"Hi {username},\n\n"
        f"Click the link below to choose a new password:\n"
        f"{reset_url}\n\n"
        f"This link is valid for a limited time and can only be used once.\n"
        f"If you didn't request a password reset, you can safely ignore this email.\n"
    )

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{app_name} <{mail_username}>"
    msg['To'] = to_email

    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    try:
        with smtplib.SMTP(mail_server, mail_port, timeout=mail_timeout) as server:
            if mail_use_tls:
                server.starttls()
                if getattr(server, 'sock', None):
                    server.sock.settimeout(mail_timeout)
            server.login(mail_username, mail_password)
            server.sendmail(mail_username, to_email, msg.as_string())

        logger.info(f"[OK] Password reset email sent to {mask_email(to_email)}")

    except (TimeoutError, socket.timeout) as e:
        logger.error(f"[ERROR] SMTP connection timed out while sending reset email to {mask_email(to_email)}")
        raise EmailDeliveryError("Email delivery timed out. Please try again.") from e
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"[ERROR] SMTP authentication failed for configured mail account")
        raise EmailDeliveryError("Email service authentication failure.") from e
    except (smtplib.SMTPException, OSError) as e:
        logger.error(f"[ERROR] SMTP delivery failed for {mask_email(to_email)}: {e.__class__.__name__}")
        raise EmailDeliveryError("Failed to deliver password reset email.") from e

