"""
alerts/notifier.py — Notification delivery.

Supports:
  - Email via Resend (see core/resend_client.py for setup instructions)
  - WhatsApp via Twilio (optional — only active when TWILIO_* env vars are set)

.env variables:
  RESEND_API_KEY        = "re_xxxxxxxxxxxx"
  RESEND_FROM_EMAIL      = "alerts@yourdomain.com"   # must be on a verified Resend domain
  RESEND_FROM_NAME       = "MarketLens"               # optional, defaults to "MarketLens"

  TWILIO_ACCOUNT_SID    = "ACxxxxxxx"   # leave unset to disable WhatsApp
  TWILIO_AUTH_TOKEN     = "xxxxxxx"
  TWILIO_WHATSAPP_FROM  = "whatsapp:+14155238886"  # Twilio sandbox number

Resend setup:
  1. Sign up at resend.com
  2. Verify a sending domain (Domains → Add Domain), or use the shared dev
     domain onboarding@resend.dev for local testing (only delivers to your
     own signup email)
  3. API Keys → Create API Key → set as RESEND_API_KEY

WhatsApp setup (Twilio sandbox, free):
  1. Sign up at twilio.com
  2. Go to Messaging → Try it out → Send a WhatsApp message
  3. Follow the sandbox join instructions (send "join <word>" to the sandbox number)
  4. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM
"""

from __future__ import annotations

import os
import logging

from core.resend_client import send_email as _send_via_resend

log = logging.getLogger(__name__)


# ── Config ────────────────────────────────────────────────────────────────────

def _twilio_cfg():
    return {
        "sid":       os.getenv("TWILIO_ACCOUNT_SID"),
        "token":     os.getenv("TWILIO_AUTH_TOKEN"),
        "from_num":  os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886"),
    }

def _base_url():
    return os.getenv("APP_BASE_URL", "http://localhost:3000")


# ── Payload builder ───────────────────────────────────────────────────────────

def build_alert_payload(alert: dict, product: dict, price_event: dict) -> dict:
    """
    Build a unified alert payload from an alert doc, product doc, and price event.

    price_event: {
        "current_price": float,
        "previous_price": float,
        "drop_pct": float,
        "drop_amount": float,
        "currency": str,
    }
    """
    title = product.get("title", alert["slug"])
    store = alert.get("source_store") or price_event.get("source_store", "")
    currency = price_event.get("currency", "INR")
    current = price_event["current_price"]
    previous = price_event["previous_price"]
    drop_pct = round(price_event.get("drop_pct", 0), 1)
    drop_amt = round(price_event.get("drop_amount", 0), 2)
    product_url = product.get("product_url", f"{_base_url()}/product/{alert['slug']}")
    unsubscribe_url = f"{_base_url()}/alerts/unsubscribe?token={alert['token']}"

    return {
        "title": title,
        "store": store,
        "currency": currency,
        "current_price": current,
        "previous_price": previous,
        "drop_pct": drop_pct,
        "drop_amount": drop_amt,
        "product_url": product_url,
        "unsubscribe_url": unsubscribe_url,
        "trigger": alert.get("trigger", "any_drop"),
        "target_price": alert.get("target_price"),
    }


# ── Email ─────────────────────────────────────────────────────────────────────

def _build_email_html(payload: dict) -> str:
    title = payload["title"]
    currency = payload["currency"]
    current = payload["current_price"]
    previous = payload["previous_price"]
    drop_pct = payload["drop_pct"]
    drop_amt = payload["drop_amount"]
    product_url = payload["product_url"]
    unsubscribe_url = payload["unsubscribe_url"]
    store = payload["store"].title() if payload["store"] else ""

    trigger_line = (
        f"The price dropped below your target of {currency} {payload['target_price']:,.0f}."
        if payload["trigger"] == "below_price"
        else f"The price just dropped on a product you're tracking."
    )

    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: 'DM Mono', monospace, sans-serif; background: #0a0a0a; color: #f0f0f0; margin: 0; padding: 0; }}
    .container {{ max-width: 560px; margin: 40px auto; background: #111; border: 1px solid #222; border-radius: 8px; overflow: hidden; }}
    .header {{ background: #000; padding: 24px 32px; border-bottom: 1px solid #222; }}
    .header h1 {{ margin: 0; font-size: 22px; letter-spacing: 0.1em; color: #fff; font-family: 'Bebas Neue', sans-serif; }}
    .header p {{ margin: 4px 0 0; font-size: 12px; color: #666; }}
    .body {{ padding: 32px; }}
    .product-title {{ font-size: 18px; font-weight: 600; color: #fff; margin: 0 0 4px; }}
    .store-label {{ font-size: 11px; color: #666; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 24px; }}
    .price-row {{ display: flex; align-items: baseline; gap: 12px; margin: 20px 0; }}
    .price-now {{ font-size: 32px; font-weight: 700; color: #4ade80; }}
    .price-was {{ font-size: 18px; color: #555; text-decoration: line-through; }}
    .badge {{ display: inline-block; background: #4ade8022; color: #4ade80; border: 1px solid #4ade8044; padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: 600; }}
    .trigger-line {{ font-size: 13px; color: #888; margin: 16px 0; }}
    .cta {{ display: block; margin: 28px 0 0; padding: 14px 24px; background: #fff; color: #000; text-decoration: none; font-weight: 700; font-size: 14px; border-radius: 4px; text-align: center; letter-spacing: 0.05em; }}
    .footer {{ padding: 20px 32px; border-top: 1px solid #1a1a1a; font-size: 11px; color: #444; }}
    .footer a {{ color: #555; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Price Alert</h1>
      <p>Sneaker Search Engine</p>
    </div>
    <div class="body">
      <div class="product-title">{title}</div>
      {"<div class='store-label'>" + store + "</div>" if store else ""}
      <div class="trigger-line">{trigger_line}</div>
      <div class="price-row">
        <span class="price-now">{currency} {current:,.0f}</span>
        <span class="price-was">{currency} {previous:,.0f}</span>
        <span class="badge">↓ {drop_pct}% (−{currency} {drop_amt:,.0f})</span>
      </div>
      <a class="cta" href="{product_url}">View Product →</a>
    </div>
    <div class="footer">
      You're receiving this because you set a price alert.<br>
      <a href="{unsubscribe_url}">Unsubscribe</a>
    </div>
  </div>
</body>
</html>
"""


def send_email(to_email: str, payload: dict) -> bool:
    """
    Send a price alert email via Resend.
    Returns True on success, False on failure.
    """
    title = payload["title"]
    currency = payload["currency"]
    current = payload["current_price"]
    drop_pct = payload["drop_pct"]

    subject = f"↓ {drop_pct}% drop — {title} now {currency} {current:,.0f}"

    plain = (
        f"Price Alert: {title}\n\n"
        f"Now: {currency} {current:,.0f}  (was {currency} {payload['previous_price']:,.0f})\n"
        f"Drop: {drop_pct}% (−{currency} {payload['drop_amount']:,.0f})\n\n"
        f"View: {payload['product_url']}\n\n"
        f"Unsubscribe: {payload['unsubscribe_url']}"
    )
    html = _build_email_html(payload)

    return _send_via_resend(to_email, subject, html, text=plain)


# ── WhatsApp (Twilio) ─────────────────────────────────────────────────────────

def _whatsapp_enabled() -> bool:
    cfg = _twilio_cfg()
    return bool(cfg["sid"] and cfg["token"])


def send_whatsapp(to_phone: str, payload: dict) -> bool:
    """
    Send a price alert via WhatsApp using Twilio.
    Returns True on success, False on failure (or if Twilio not configured).

    to_phone must be E.164 format: "+919876543210"
    """
    if not _whatsapp_enabled():
        log.info("[notifier] WhatsApp not configured — set TWILIO_* env vars to enable")
        return False

    try:
        from twilio.rest import Client
    except ImportError:
        log.error("[notifier] twilio package not installed — run: pip install twilio")
        return False

    cfg = _twilio_cfg()
    title = payload["title"]
    currency = payload["currency"]
    current = payload["current_price"]
    previous = payload["previous_price"]
    drop_pct = payload["drop_pct"]
    drop_amt = payload["drop_amount"]

    body = (
        f"🔔 *Price Alert* — {title}\n\n"
        f"*Now:* {currency} {current:,.0f}\n"
        f"*Was:* {currency} {previous:,.0f}\n"
        f"*Drop:* ↓{drop_pct}% (−{currency} {drop_amt:,.0f})\n\n"
        f"👟 {payload['product_url']}\n\n"
        f"_Reply STOP to unsubscribe_"
    )

    try:
        client = Client(cfg["sid"], cfg["token"])
        client.messages.create(
            body=body,
            from_=cfg["from_num"],
            to=f"whatsapp:{to_phone}",
        )
        log.info(f"[notifier] 📱 WhatsApp sent → {to_phone} ({title})")
        return True
    except Exception as e:
        log.error(f"[notifier] WhatsApp failed → {to_phone}: {e}")
        return False


# ── Unified dispatcher ────────────────────────────────────────────────────────

def dispatch(alert: dict, payload: dict) -> dict[str, bool]:
    """
    Send all configured notification channels for an alert.
    Returns a dict of channel → success.
    """
    results: dict[str, bool] = {}

    # Email — always attempt
    if alert.get("email"):
        results["email"] = send_email(alert["email"], payload)

    # WhatsApp — only if phone is set and Twilio is configured
    if alert.get("phone") and _whatsapp_enabled():
        results["whatsapp"] = send_whatsapp(alert["phone"], payload)

    return results