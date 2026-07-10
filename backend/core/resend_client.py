"""
core/resend_client.py — Shared Resend email client.

Used by both:
  - auth/email.py        (OTP verification emails)
  - alerts/notifier.py   (price drop alert emails)

Setup (one-time):
  1. Sign up at https://resend.com
  2. Verify a sending domain (Domains → Add Domain → follow DNS instructions)
     OR use Resend's shared test domain for development: onboarding@resend.dev
     (test domain only delivers to the email you signed up with)
  3. API Keys → Create API Key → copy it
  4. Set env vars:
       RESEND_API_KEY=re_xxxxxxxxxxxx
       RESEND_FROM_EMAIL=alerts@yourdomain.com   (must be on a verified domain)
       RESEND_FROM_NAME=MarketLens

Why Resend instead of Gmail SMTP:
  - No App Password fragility, no 2FA dance, no "less secure app" blocks
  - Proper SPF/DKIM under your own domain → lands in inbox, not spam
  - HTTPS API call instead of a raw SMTP socket — faster, no blocking handshake
  - Delivery status visible in the Resend dashboard
"""

from __future__ import annotations

import os
import logging
import httpx

log = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


def _config() -> dict:
    return {
        "api_key":    os.getenv("RESEND_API_KEY", ""),
        "from_email": os.getenv("RESEND_FROM_EMAIL", ""),
        "from_name":  os.getenv("RESEND_FROM_NAME", "MarketLens"),
    }


def is_configured() -> bool:
    cfg = _config()
    return bool(cfg["api_key"] and cfg["from_email"])


def send_email(
    to_email: str,
    subject: str,
    html: str,
    text: str | None = None,
) -> bool:
    """
    Send an email via the Resend API.
    Returns True on success, False on failure. Never raises — callers should
    check the return value rather than relying on try/except.
    """
    cfg = _config()

    if not cfg["api_key"] or not cfg["from_email"]:
        log.warning(
            "[resend] Not configured — set RESEND_API_KEY and RESEND_FROM_EMAIL. "
            "No email was sent."
        )
        return False

    payload = {
        "from": f"{cfg['from_name']} <{cfg['from_email']}>",
        "to": [to_email],
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text

    try:
        response = httpx.post(
            RESEND_API_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {cfg['api_key']}",
                "Content-Type": "application/json",
            },
            timeout=10.0,
        )
        if response.status_code in (200, 201):
            log.info(f"[resend] ✉ Sent → {to_email} | {subject}")
            return True

        log.error(
            f"[resend] Failed → {to_email} | "
            f"status={response.status_code} body={response.text[:300]}"
        )
        return False

    except httpx.HTTPError as e:
        log.error(f"[resend] Request error → {to_email}: {e}")
        return False