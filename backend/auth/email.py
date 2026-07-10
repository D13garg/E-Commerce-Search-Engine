"""
auth/email.py — OTP verification emails.

Sent via Resend (see core/resend_client.py for setup instructions).
Previously used Gmail SMTP — migrated because no sender was ever configured
and failures were silent, so OTP emails were never actually being sent.
"""

from __future__ import annotations

import logging

from core.resend_client import send_email as _send_via_resend

log = logging.getLogger(__name__)


def _build_otp_html(otp_code: str, purpose: str, expires_minutes: int = 3) -> str:
    action = (
        "verify your email and complete registration"
        if purpose == "register"
        else "reset your password"
    )
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: 'DM Mono', monospace, sans-serif; background:#0a0a0a; color:#f0f0f0; margin:0; padding:0;">
  <div style="max-width:480px; margin:40px auto; background:#111; border:1px solid #222; border-radius:8px; overflow:hidden;">
    <div style="background:#000; padding:24px 32px; border-bottom:1px solid #222;">
      <h1 style="margin:0; font-size:20px; letter-spacing:0.08em; color:#fff;">MARKETLENS</h1>
    </div>
    <div style="padding:32px; text-align:center;">
      <p style="font-size:13px; color:#aaa; margin-bottom:24px;">
        Use the code below to {action}
      </p>
      <div style="font-size:36px; font-weight:700; letter-spacing:10px; padding:20px; border:2px solid #ff3d00; border-radius:8px; display:inline-block; color:#ff3d00;">
        {otp_code}
      </div>
      <p style="font-size:12px; color:#666; margin-top:24px;">
        This code expires in {expires_minutes} minutes.<br>
        Never share this code with anyone.
      </p>
    </div>
  </div>
</body>
</html>
"""


def send_otp_email(to_email: str, otp_code: str, purpose: str) -> bool:
    """Send an OTP verification email via Resend. Returns True on success, False on failure."""
    subject = (
        "Verify your email — MarketLens"
        if purpose == "register"
        else "Reset your password — MarketLens"
    )
    plain = f"Your verification code is: {otp_code}\nThis code expires in 3 minutes."
    html = _build_otp_html(otp_code, purpose)

    return _send_via_resend(to_email, subject, html, text=plain)