import os
import logging
from typing import Optional, Tuple
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from python_http_client.exceptions import HTTPError
from app.config import settings

logger = logging.getLogger(__name__)

def send_otp_email(to_email: str, otp_code: str, user_name: Optional[str] = None) -> Tuple[bool, str]:
    """
    Delivers a production-grade 6-digit OTP email using the official SendGrid package.
    Configured via environment variables: SENDGRID_API_KEY, SENDGRID_FROM_EMAIL, SENDGRID_FROM_NAME.
    Never exposes plain text OTP or SendGrid API key in logs or API responses.
    """
    from dotenv import load_dotenv
    from pathlib import Path
    env_file_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_file_path.exists():
        load_dotenv(dotenv_path=env_file_path, override=True)

    api_key = (os.getenv("SENDGRID_API_KEY") or settings.SENDGRID_API_KEY or "").strip()
    from_email = (os.getenv("SENDGRID_FROM_EMAIL") or settings.SENDGRID_FROM_EMAIL or "noreply@paperlens.ai").strip()
    from_name = (os.getenv("SENDGRID_FROM_NAME") or settings.SENDGRID_FROM_NAME or "PaperLens").strip()

    print(f"[CONFIG] SendGrid API key exists: {bool(api_key)}")
    print(f"[CONFIG] Sender email: {from_email}")
    print(f"[OTP] Recipient: {to_email}")
    print(f"[SENDGRID] Sender: {from_email}")
    print(f"[SENDGRID] Sending...")

    # 1. Environment Variable Check
    if not api_key:
        err_msg = "SENDGRID_API_KEY environment variable is not configured in backend/.env."
        print(f"[SENDGRID] SEND FAILED")
        print(f"[SENDGRID] STATUS: CONFIGURATION_ERROR")
        print(f"[SENDGRID] BODY: {err_msg}")
        print(f"[SENDGRID] MESSAGE: Missing SendGrid API Key on server.")
        return False, err_msg

    if not from_email:
        err_msg = "SENDGRID_FROM_EMAIL environment variable is not configured in backend/.env."
        print(f"[SENDGRID] SEND FAILED")
        print(f"[SENDGRID] STATUS: CONFIGURATION_ERROR")
        print(f"[SENDGRID] BODY: {err_msg}")
        print(f"[SENDGRID] MESSAGE: Missing SendGrid Sender Email on server.")
        return False, err_msg

    greeting = f"Hello {user_name}," if user_name else "Hello,"
    subject = "Your PaperLens Verification Code"

    html_content = f"""
      <div style="font-family: Arial, sans-serif; padding: 24px; max-width: 500px; border: 1px solid #e2e8f0; border-radius: 16px; background-color: #ffffff;">
        <h2 style="color: #0f172a; margin-top: 0;">Your verification code</h2>
        <p style="color: #334155; font-size: 14px;">{greeting}</p>
        <p style="color: #475569; font-size: 14px;">Use the following security code to complete your verification for <strong>{from_name}</strong>:</p>
        <div style="background-color: #f1f5f9; border: 2px dashed #cbd5e1; border-radius: 12px; padding: 20px; text-align: center; margin: 20px 0;">
          <h1 style="color: #1e40af; letter-spacing: 8px; font-size: 36px; margin: 0; font-family: monospace;">{otp_code}</h1>
        </div>
        <p style="color: #64748b; font-size: 13px;">This code expires in <strong>5 minutes</strong> and is valid for one use only.</p>
        <p style="color: #94a3b8; font-size: 12px; border-top: 1px solid #f1f5f9; padding-top: 16px; margin-top: 24px;">If you did not request this code, you can safely ignore this email.</p>
      </div>
    """

    text_content = f"Your verification code is {otp_code}. It expires in 5 minutes. If you did not request this code, ignore this email."

    message = Mail(
        from_email=(from_email, from_name),
        to_emails=to_email,
        subject=subject,
        html_content=html_content,
        plain_text_content=text_content
    )

    try:
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)

        if response.status_code in (200, 201, 202):
            print(f"[SENDGRID] EMAIL ACCEPTED")
            print(f"[SENDGRID] STATUS: {response.status_code}")
            logger.info(f"SendGrid email successfully dispatched to {to_email} (Status: {response.status_code})")
            return True, "EMAIL ACCEPTED"
        else:
            print(f"[SENDGRID] SEND FAILED")
            print(f"[SENDGRID] STATUS: {response.status_code}")
            print(f"[SENDGRID] BODY: SendGrid returned status code {response.status_code}")
            print(f"[SENDGRID] MESSAGE: SendGrid dispatch rejected")
            return False, f"SendGrid returned status code {response.status_code}"

    except HTTPError as e:
        status_code = getattr(e, 'status_code', 'HTTP_ERROR')
        body = getattr(e, 'body', str(e))
        msg = getattr(e, 'message', str(e))
        if isinstance(body, bytes):
            body = body.decode('utf-8', errors='ignore')

        print(f"[SENDGRID] SEND FAILED")
        print(f"[SENDGRID] STATUS: {status_code}")
        print(f"[SENDGRID] BODY: {body}")
        print(f"[SENDGRID] MESSAGE: {msg}")
        logger.error(f"SendGrid API HTTPError {status_code}: {msg}. Details: {body}")

        clean_detail = f"SendGrid Error {status_code}: {body}"
        return False, clean_detail

    except Exception as e:
        err_msg = str(e)
        print(f"[SENDGRID] SEND FAILED")
        print(f"[SENDGRID] STATUS: EXCEPTION")
        print(f"[SENDGRID] BODY: {err_msg}")
        print(f"[SENDGRID] MESSAGE: SendGrid dispatch failed with exception.")
        logger.error(f"SendGrid exception: {err_msg}")
        return False, f"SendGrid Exception: {err_msg}"
