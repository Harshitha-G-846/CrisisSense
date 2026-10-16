"""
email_service.py - Incident Submission Confirmation Email Service
Handles generating and dispatching confirmation emails to registered citizens
following successful incident persistence.

Supports real SMTP (e.g., Gmail with App Password) as well as an in-memory
mock delivery mode for automated testing and local development.
"""

from __future__ import annotations

import logging
import os
import smtplib
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

logger = logging.getLogger("resqsense.email")

# In-memory outbox for testing, inspection, and offline verification
_MOCK_OUTBOX: List[Dict[str, Any]] = []


@dataclass
class EmailDeliveryResult:
    status: str  # "SENT", "MOCKED", "FAILED", "SKIPPED"
    recipient: str
    subject: str
    message: str
    tracking_url: str
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.status in ("SENT", "MOCKED")

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "status": self.status,
            "recipient": self.recipient,
            "subject": self.subject,
            "message": self.message,
            "tracking_url": self.tracking_url,
        }
        if self.error:
            result["error"] = self.error
        return result


def get_mock_outbox() -> List[Dict[str, Any]]:
    """Return all emails captured in the mock outbox."""
    return list(_MOCK_OUTBOX)


def clear_mock_outbox() -> None:
    """Clear all emails from the mock outbox (useful between tests)."""
    _MOCK_OUTBOX.clear()


def is_placeholder_credential(val: str) -> bool:
    """Check if a string is a placeholder rather than real credentials."""
    if not val:
        return True
    lower = val.lower()
    return any(p in lower for p in ["your-organization", "placeholder", "your-", "example.com", "change-me"])


def send_incident_confirmation_email(
    recipient_email: str,
    citizen_name: str,
    incident_id: str,
    incident_type: str = "Crisis Incident",
    location_name: Optional[str] = None,
    submission_timestamp: Optional[str] = None,
    mock_mode_override: Optional[bool] = None,
) -> EmailDeliveryResult:
    """Send an incident submission confirmation email to the citizen.

    Subject: 'ResQ-Sense: Incident submitted successfully'
    Includes incident reference ID, timestamp, and tracking link.
    """
    if not recipient_email:
        return EmailDeliveryResult(
            status="SKIPPED",
            recipient="",
            subject="ResQ-Sense: Incident submitted successfully",
            message="No recipient email address specified.",
            tracking_url="",
        )

    subject = "ResQ-Sense: Incident submitted successfully"

    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    smtp_from_email = os.environ.get("SMTP_FROM_EMAIL", smtp_user or "notifications@resqsense.org")
    smtp_from_name = os.environ.get("SMTP_FROM_NAME", "ResQ-Sense Emergency Intelligence")
    smtp_tls = os.environ.get("SMTP_TLS", "true").lower() in ("true", "1", "yes")

    # Determine whether mock mode is active
    env_mock_mode = os.environ.get("EMAIL_MOCK_MODE", "true").lower() in ("true", "1", "yes")
    is_mock = mock_mode_override if mock_mode_override is not None else (
        env_mock_mode or not smtp_user or is_placeholder_credential(smtp_user) or is_placeholder_credential(smtp_password)
    )

    # Compose plain-text body
    loc_display = location_name if location_name else "Location submitted with report"
    time_display = submission_timestamp if submission_timestamp else "Just now"

    text_body = f"""Hello {citizen_name},

Thank you for reporting an emergency to the ResQ-Sense Emergency Response Network.
Your report has been successfully registered and queued for response verification.

INCIDENT DETAILS:
--------------------------------------------------
Tracking Reference ID : {incident_id}
Incident Type         : {incident_type}
Location              : {loc_display}
Submitted At          : {time_display}

TRACKING YOUR INCIDENT:
You can track real-time authority verification, status updates, and emergency response planning inside the ResQ-Sense Citizen Portal using your Tracking Reference ID ({incident_id}).

Please note: You must be logged into your registered citizen account ({recipient_email}) to view private incident details.

Stay safe,
The ResQ-Sense Operations Team
"""

    # Compose HTML body
    html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
</head>
<body style="font-family: 'Segoe UI', Helvetica, Arial, sans-serif; background-color: #0a0c10; color: #f8fafc; margin: 0; padding: 24px;">
  <div style="max-width: 580px; margin: 0 auto; background-color: #12161f; border: 1px solid rgba(255,255,255,0.12); border-radius: 12px; padding: 32px; box-shadow: 0 8px 30px rgba(0,0,0,0.5);">
    <div style="border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 18px; margin-bottom: 24px;">
      <h1 style="color: #6366f1; margin: 0; font-size: 22px; font-weight: 700;">ResQ-Sense</h1>
      <p style="color: #94a3b8; margin: 4px 0 0 0; font-size: 13px;">Crisis Intelligence &amp; Response Orchestration</p>
    </div>

    <h2 style="color: #ffffff; font-size: 18px; margin-top: 0;">Incident Submitted Successfully</h2>
    <p style="color: #cbd5e1; font-size: 14px; line-height: 1.6;">
      Dear <strong>{citizen_name}</strong>,<br>
      Your emergency report has been received and persisted in the ResQ-Sense system. Response authorities have been alerted.
    </p>

    <div style="background: rgba(99, 102, 241, 0.08); border: 1px solid rgba(99, 102, 241, 0.25); border-radius: 8px; padding: 18px; margin: 20px 0;">
      <div style="font-size: 12px; color: #94a3b8; text-transform: uppercase; font-weight: 700; margin-bottom: 6px;">Tracking Reference ID</div>
      <div style="font-family: monospace; font-size: 16px; color: #60a5fa; font-weight: bold; margin-bottom: 12px;">{incident_id}</div>
      <table style="width: 100%; font-size: 13px; color: #e2e8f0; border-collapse: collapse;">
        <tr><td style="padding: 4px 0; color: #94a3b8; width: 110px;">Incident Type:</td><td style="padding: 4px 0; font-weight: 600;">{incident_type}</td></tr>
        <tr><td style="padding: 4px 0; color: #94a3b8;">Location:</td><td style="padding: 4px 0;">{loc_display}</td></tr>
        <tr><td style="padding: 4px 0; color: #94a3b8;">Registered At:</td><td style="padding: 4px 0;">{time_display}</td></tr>
      </table>
    </div>

    <div style="background: rgba(255, 255, 255, 0.04); border-left: 3px solid #6366f1; border-radius: 4px; padding: 14px 18px; margin: 22px 0;">
      <p style="color: #cbd5e1; font-size: 13px; margin: 0; line-height: 1.5;">
        <strong>Track Incident Status:</strong> You can track real-time verification and response planning anytime directly in the ResQ-Sense Citizen Portal using your reference ID <span style="font-family: monospace; color: #60a5fa; font-weight: bold;">{incident_id}</span>.
      </p>
    </div>

    <p style="color: #64748b; font-size: 12px; text-align: center; margin-top: 24px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 16px;">
      This email was sent to {recipient_email}. You must be logged into your registered citizen account to inspect verification and resource planning details.
    </p>
  </div>
</body>
</html>"""

    email_record = {
        "recipient": recipient_email,
        "citizen_name": citizen_name,
        "incident_id": incident_id,
        "subject": subject,
        "text_body": text_body,
        "text_content": text_body,
        "html_body": html_body,
        "tracking_url": "",
        "mock": is_mock,
    }

    if is_mock:
        _MOCK_OUTBOX.append(email_record)
        logger.info(
            "Email notification [MOCKED] to %s for incident %s",
            recipient_email,
            incident_id,
        )
        return EmailDeliveryResult(
            status="MOCKED",
            recipient=recipient_email,
            subject=subject,
            message="Confirmation email recorded in mock outbox.",
            tracking_url="",
        )

    # Real SMTP delivery via configured credentials
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{smtp_from_name} <{smtp_from_email}>"
        msg["To"] = recipient_email

        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=10.0) as server:
            if smtp_tls:
                server.starttls()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)

        logger.info(
            "Email notification [SENT] to %s for incident %s",
            recipient_email,
            incident_id,
        )
        return EmailDeliveryResult(
            status="SENT",
            recipient=recipient_email,
            subject=subject,
            message="Confirmation email dispatched successfully via SMTP.",
            tracking_url="",
        )
    except Exception as err:
        err_msg = f"{type(err).__name__}: {str(err)}"
        # Sanitize error message to prevent logging credentials
        if smtp_password and smtp_password in err_msg:
            err_msg = err_msg.replace(smtp_password, "[REDACTED]")
        logger.warning(
            "Email notification [FAILED] to %s for incident %s: %s",
            recipient_email,
            incident_id,
            err_msg,
        )
        return EmailDeliveryResult(
            status="FAILED",
            recipient=recipient_email,
            subject=subject,
            message="Confirmation email delivery failed.",
            tracking_url="",
            error=err_msg,
        )


def send_verification_code_email(
    recipient_email: str,
    citizen_name: str,
    code: str,
    expires_minutes: int = 15,
    mock_mode_override: Optional[bool] = None,
) -> EmailDeliveryResult:
    """Send an account email verification code to the citizen."""
    if not recipient_email:
        return EmailDeliveryResult(
            status="SKIPPED",
            recipient="",
            subject="ResQ-Sense: Verify your email address",
            message="No recipient email address specified.",
            tracking_url="",
        )

    subject = "ResQ-Sense: Verify your email address"

    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    smtp_from_email = os.environ.get("SMTP_FROM_EMAIL", smtp_user or "notifications@resqsense.org")
    smtp_from_name = os.environ.get("SMTP_FROM_NAME", "ResQ-Sense Emergency Intelligence")
    smtp_tls = os.environ.get("SMTP_TLS", "true").lower() in ("true", "1", "yes")

    env_mock_mode = os.environ.get("EMAIL_MOCK_MODE", "true").lower() in ("true", "1", "yes")
    is_mock = mock_mode_override if mock_mode_override is not None else (
        env_mock_mode or not smtp_user or is_placeholder_credential(smtp_user) or is_placeholder_credential(smtp_password)
    )

    text_body = f"""Hello {citizen_name},

Welcome to ResQ-Sense. Please use the verification code below to verify your citizen account:

VERIFICATION CODE: {code}

This code will expire in {expires_minutes} minutes.
If you did not create a ResQ-Sense account, please disregard this email.

Stay safe,
The ResQ-Sense Team
"""

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{subject}</title></head>
<body style="font-family: 'Segoe UI', Helvetica, Arial, sans-serif; background-color: #0a0c10; color: #f8fafc; margin: 0; padding: 24px;">
  <div style="max-width: 540px; margin: 0 auto; background-color: #12161f; border: 1px solid rgba(255,255,255,0.12); border-radius: 12px; padding: 32px; box-shadow: 0 8px 30px rgba(0,0,0,0.5);">
    <div style="border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 18px; margin-bottom: 24px;">
      <h1 style="color: #85543A; margin: 0; font-size: 22px; font-weight: 700;">ResQ-Sense</h1>
      <p style="color: #A77E5C; margin: 4px 0 0 0; font-size: 13px;">Crisis Intelligence &amp; Emergency Reporting</p>
    </div>
    <h2 style="color: #ffffff; font-size: 18px; margin-top: 0;">Verify Your Email Address</h2>
    <p style="color: #cbd5e1; font-size: 14px; line-height: 1.6;">
      Dear <strong>{citizen_name}</strong>,<br>
      Thank you for registering on ResQ-Sense. Enter the single-use verification code below to activate your account:
    </p>
    <div style="text-align: center; margin: 28px 0; background: rgba(191, 141, 98, 0.12); border: 1px solid rgba(191, 141, 98, 0.35); border-radius: 8px; padding: 20px;">
      <span style="font-family: monospace; font-size: 32px; letter-spacing: 8px; font-weight: 800; color: #EAB883;">{code}</span>
      <p style="color: #A77E5C; font-size: 12px; margin: 10px 0 0 0;">Valid for {expires_minutes} minutes • Single-use only</p>
    </div>
    <p style="color: #64748b; font-size: 12px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 16px; margin-top: 24px; text-align: center;">
      This email was sent to {recipient_email}. If you did not request this code, no action is needed.
    </p>
  </div>
</body>
</html>"""

    email_record = {
        "recipient": recipient_email,
        "recipient_email": recipient_email,
        "citizen_name": citizen_name,
        "code": code,
        "subject": subject,
        "text_body": text_body,
        "text_content": text_body,
        "html_body": html_body,
        "tracking_url": "",
        "mock": is_mock,
        "metadata": {"code": code},
    }

    if is_mock:
        _MOCK_OUTBOX.append(email_record)
        return EmailDeliveryResult(
            status="MOCKED",
            recipient=recipient_email,
            subject=subject,
            message="Verification code email recorded in mock outbox.",
            tracking_url="",
        )

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{smtp_from_name} <{smtp_from_email}>"
        msg["To"] = recipient_email
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=10.0) as server:
            if smtp_tls:
                server.starttls()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)

        return EmailDeliveryResult(
            status="SENT",
            recipient=recipient_email,
            subject=subject,
            message="Verification code dispatched successfully via SMTP.",
            tracking_url="",
        )
    except Exception as err:
        err_msg = f"{type(err).__name__}: {str(err)}"
        if smtp_password and smtp_password in err_msg:
            err_msg = err_msg.replace(smtp_password, "[REDACTED]")
        return EmailDeliveryResult(
            status="FAILED",
            recipient=recipient_email,
            subject=subject,
            message="Verification code email delivery failed.",
            tracking_url="",
            error=err_msg,
        )


def send_admin_information_request_email(
    recipient_email: str,
    citizen_name: str,
    incident_id: str,
    request_message: str,
    admin_name: str = "Emergency Response Authority",
    mock_mode_override: Optional[bool] = None,
) -> EmailDeliveryResult:
    """Send an official information request email from response authorities to a citizen."""
    if not recipient_email:
        return EmailDeliveryResult(
            status="SKIPPED",
            recipient="",
            subject=f"ResQ-Sense: Information Request regarding incident {incident_id}",
            message="No recipient email address specified.",
            tracking_url="",
        )

    subject = f"ResQ-Sense: Response Authority Information Request [{incident_id}]"

    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    smtp_from_email = os.environ.get("SMTP_FROM_EMAIL", smtp_user or "authorities@resqsense.org")
    smtp_from_name = os.environ.get("SMTP_FROM_NAME", "ResQ-Sense Response Operations")
    smtp_tls = os.environ.get("SMTP_TLS", "true").lower() in ("true", "1", "yes")

    env_mock_mode = os.environ.get("EMAIL_MOCK_MODE", "true").lower() in ("true", "1", "yes")
    is_mock = mock_mode_override if mock_mode_override is not None else (
        env_mock_mode or not smtp_user or is_placeholder_credential(smtp_user) or is_placeholder_credential(smtp_password)
    )

    text_body = f"""Hello {citizen_name},

An emergency response administrator ({admin_name}) has requested additional information regarding your reported incident {incident_id}:

OFFICIAL INQUIRY:
--------------------------------------------------
{request_message}
--------------------------------------------------

You can update or submit feedback on your incident anytime directly in the ResQ-Sense Citizen Portal using Reference ID {incident_id}.

Respectfully,
{admin_name}
ResQ-Sense Crisis Response Network
"""

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{subject}</title></head>
<body style="font-family: 'Segoe UI', Helvetica, Arial, sans-serif; background-color: #0a0c10; color: #f8fafc; margin: 0; padding: 24px;">
  <div style="max-width: 580px; margin: 0 auto; background-color: #12161f; border: 1px solid rgba(255,255,255,0.12); border-radius: 12px; padding: 32px; box-shadow: 0 8px 30px rgba(0,0,0,0.5);">
    <div style="border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 18px; margin-bottom: 24px;">
      <h1 style="color: #85543A; margin: 0; font-size: 22px; font-weight: 700;">ResQ-Sense</h1>
      <p style="color: #A77E5C; margin: 4px 0 0 0; font-size: 13px;">Official Response Command Inquiries</p>
    </div>
    <h2 style="color: #ffffff; font-size: 18px; margin-top: 0;">Information Request for Incident {incident_id}</h2>
    <p style="color: #cbd5e1; font-size: 14px; line-height: 1.6;">
      Dear <strong>{citizen_name}</strong>,<br>
      Response authorities are reviewing your emergency report and require the following information to assist dispatch and response planning:
    </p>
    <div style="background: rgba(234, 184, 131, 0.1); border-left: 4px solid #EAB883; border-radius: 6px; padding: 18px; margin: 20px 0;">
      <div style="font-size: 11px; text-transform: uppercase; color: #BF8D62; font-weight: 700; margin-bottom: 6px;">Message from {admin_name}</div>
      <p style="color: #f8fafc; font-size: 14px; margin: 0; line-height: 1.6; white-space: pre-wrap;">{request_message}</p>
    </div>
    <p style="color: #A77E5C; font-size: 13px; line-height: 1.5;">
      You can provide details or feedback directly by searching your Incident Reference ID <strong>{incident_id}</strong> in the Citizen Portal.
    </p>
    <p style="color: #64748b; font-size: 12px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 16px; margin-top: 24px; text-align: center;">
      This email was dispatched to {recipient_email} by authorized response personnel.
    </p>
  </div>
</body>
</html>"""

    email_record = {
        "recipient": recipient_email,
        "recipient_email": recipient_email,
        "citizen_name": citizen_name,
        "incident_id": incident_id,
        "admin_name": admin_name,
        "subject": subject,
        "request_message": request_message,
        "text_body": text_body,
        "text_content": text_body,
        "html_body": html_body,
        "mock": is_mock,
        "metadata": {
            "request_message": request_message,
            "admin_name": admin_name,
            "incident_id": incident_id,
        },
    }

    if is_mock:
        _MOCK_OUTBOX.append(email_record)
        return EmailDeliveryResult(
            status="MOCKED",
            recipient=recipient_email,
            subject=subject,
            message="Information request email recorded in mock outbox.",
            tracking_url="",
        )

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{smtp_from_name} <{smtp_from_email}>"
        msg["To"] = recipient_email
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=10.0) as server:
            if smtp_tls:
                server.starttls()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)

        return EmailDeliveryResult(
            status="SENT",
            recipient=recipient_email,
            subject=subject,
            message="Information request email dispatched successfully via SMTP.",
            tracking_url="",
        )
    except Exception as err:
        err_msg = f"{type(err).__name__}: {str(err)}"
        if smtp_password and smtp_password in err_msg:
            err_msg = err_msg.replace(smtp_password, "[REDACTED]")
        return EmailDeliveryResult(
            status="FAILED",
            recipient=recipient_email,
            subject=subject,
            message="Information request email delivery failed.",
            tracking_url="",
            error=err_msg,
        )


def send_needs_more_info_email(
    recipient_email: str,
    citizen_name: str,
    incident_id: str,
    feedback: str,
    incident_type: Optional[str] = None,
    location_name: Optional[str] = None,
    admin_name: str = "Emergency Operations Authority",
    mock_mode_override: Optional[bool] = None,
) -> EmailDeliveryResult:
    """Send an official notification email when an admin requests more information on an incident.

    Subject: 'Additional Information Required — ResQ-Sense Incident'
    Includes incident reference ID, category, reported location, admin feedback, and
    clear instructions for the citizen to sign in and submit updates via the Citizen Portal.
    """
    subject = "Additional Information Required — ResQ-Sense Incident"

    if not recipient_email:
        return EmailDeliveryResult(
            status="SKIPPED",
            recipient="",
            subject=subject,
            message="No recipient email address specified.",
            tracking_url="",
        )

    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    smtp_from_email = os.environ.get("SMTP_FROM_EMAIL", smtp_user or "authorities@resqsense.org")
    smtp_from_name = os.environ.get("SMTP_FROM_NAME", "ResQ-Sense Response Operations")
    smtp_tls = os.environ.get("SMTP_TLS", "true").lower() in ("true", "1", "yes")

    env_mock_mode = os.environ.get("EMAIL_MOCK_MODE", "true").lower() in ("true", "1", "yes")
    is_mock = mock_mode_override if mock_mode_override is not None else (
        env_mock_mode or not smtp_user or is_placeholder_credential(smtp_user) or is_placeholder_credential(smtp_password)
    )

    category_display = incident_type if incident_type else "Crisis Emergency"
    location_display = location_name if location_name else "Location reported with submission"

    text_body = f"""Hello {citizen_name},

An emergency response administrator ({admin_name}) has reviewed your incident report and requested additional information before response actions can proceed.

INCIDENT DETAILS:
--------------------------------------------------
Reference ID      : {incident_id}
Incident Category : {category_display}
Reported Location : {location_display}

ADMINISTRATOR FEEDBACK & REQUESTED INFORMATION:
--------------------------------------------------
{feedback}
--------------------------------------------------

INSTRUCTIONS TO RESPOND:
Please sign in to the ResQ-Sense Citizen Portal to provide the requested details through the supported workflow:
1. Open the ResQ-Sense web application and sign in with your registered account ({recipient_email}).
2. Navigate to the "Track Status" tab in the Citizen Portal.
3. Search for or select your Incident Reference ID: {incident_id}
4. Review the authority inquiry and submit your live updates in the feedback section.

Your updates will immediately assist emergency response teams and coordinators.

Stay safe,
{admin_name}
ResQ-Sense Crisis Response Network
"""

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{subject}</title></head>
<body style="font-family: 'Segoe UI', Helvetica, Arial, sans-serif; background-color: #0a0c10; color: #f8fafc; margin: 0; padding: 24px;">
  <div style="max-width: 580px; margin: 0 auto; background-color: #12161f; border: 1px solid rgba(255,255,255,0.12); border-radius: 12px; padding: 32px; box-shadow: 0 8px 30px rgba(0,0,0,0.5);">
    <div style="border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 18px; margin-bottom: 24px;">
      <h1 style="color: #85543A; margin: 0; font-size: 22px; font-weight: 700;">ResQ-Sense</h1>
      <p style="color: #A77E5C; margin: 4px 0 0 0; font-size: 13px;">Crisis Intelligence &amp; Emergency Operations</p>
    </div>

    <h2 style="color: #ffffff; font-size: 18px; margin-top: 0;">Additional Information Required</h2>
    <p style="color: #cbd5e1; font-size: 14px; line-height: 1.6;">
      Dear <strong>{citizen_name}</strong>,<br>
      Emergency response authorities have reviewed your incident report and require additional information to complete verification and dispatch planning.
    </p>

    <div style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 16px; margin: 20px 0;">
      <div style="font-size: 11px; text-transform: uppercase; color: #BF8D62; font-weight: 700; margin-bottom: 8px;">Incident Overview</div>
      <p style="color: #f8fafc; font-size: 13px; margin: 4px 0;"><strong>Incident Reference ID:</strong> <code style="font-family: monospace; color: #EAB883;">{incident_id}</code></p>
      <p style="color: #f8fafc; font-size: 13px; margin: 4px 0;"><strong>Incident Category:</strong> {category_display}</p>
      <p style="color: #f8fafc; font-size: 13px; margin: 4px 0;"><strong>Reported Location:</strong> {location_display}</p>
    </div>

    <div style="background: rgba(234, 184, 131, 0.1); border-left: 4px solid #EAB883; border-radius: 6px; padding: 18px; margin: 20px 0;">
      <div style="font-size: 11px; text-transform: uppercase; color: #BF8D62; font-weight: 700; margin-bottom: 6px;">Administrator Feedback &amp; Request</div>
      <p style="color: #f8fafc; font-size: 14px; margin: 0; line-height: 1.6; white-space: pre-wrap;">{feedback}</p>
    </div>

    <div style="background: rgba(99, 102, 241, 0.1); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 8px; padding: 16px; margin: 20px 0;">
      <div style="font-size: 11px; text-transform: uppercase; color: #a5b4fc; font-weight: 700; margin-bottom: 6px;">How to Provide Additional Information</div>
      <p style="color: #cbd5e1; font-size: 13px; margin: 0; line-height: 1.5;">
        Please sign in to the ResQ-Sense Citizen Portal, navigate to the <strong>Track Status</strong> tab, and search for Reference ID <strong>{incident_id}</strong> to submit your updates directly to response coordinators.
      </p>
    </div>

    <p style="color: #64748b; font-size: 12px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 16px; margin-top: 24px; text-align: center;">
      Dispatched by {admin_name} &bull; ResQ-Sense Emergency Intelligence Network
    </p>
  </div>
</body>
</html>"""

    email_record = {
        "recipient": recipient_email,
        "recipient_email": recipient_email,
        "citizen_name": citizen_name,
        "incident_id": incident_id,
        "admin_name": admin_name,
        "subject": subject,
        "feedback": feedback,
        "request_message": feedback,
        "incident_type": category_display,
        "location_name": location_display,
        "text_body": text_body,
        "text_content": text_body,
        "html_body": html_body,
        "mock": is_mock,
        "metadata": {
            "feedback": feedback,
            "incident_id": incident_id,
            "incident_type": category_display,
            "location_name": location_display,
        },
    }

    if is_mock:
        _MOCK_OUTBOX.append(email_record)
        return EmailDeliveryResult(
            status="MOCKED",
            recipient=recipient_email,
            subject=subject,
            message="Additional information request email recorded in mock outbox.",
            tracking_url="",
        )

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{smtp_from_name} <{smtp_from_email}>"
        msg["To"] = recipient_email
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=10.0) as server:
            if smtp_tls:
                server.starttls()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)

        return EmailDeliveryResult(
            status="SENT",
            recipient=recipient_email,
            subject=subject,
            message="Additional information request email dispatched successfully via SMTP.",
            tracking_url="",
        )
    except Exception as err:
        err_msg = f"{type(err).__name__}: {str(err)}"
        if smtp_password and smtp_password in err_msg:
            err_msg = err_msg.replace(smtp_password, "[REDACTED]")
        return EmailDeliveryResult(
            status="FAILED",
            recipient=recipient_email,
            subject=subject,
            message="Additional information request email delivery failed.",
            tracking_url="",
            error=err_msg,
        )

