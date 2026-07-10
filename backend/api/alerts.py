"""
api/alerts.py — Price alert API endpoints.

Endpoints:
  POST   /alerts                      Create a new alert
  GET    /alerts/{email}              List all alerts for an email
  DELETE /alerts/{alert_id}          Deactivate alert by ID
  GET    /alerts/unsubscribe          Deactivate via token (email link)
  GET    /alerts/stats                Admin stats

No auth required — alerts are self-managed via token links in notification emails.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.database import Database

from api.dependencies import get_db
from alerts.models import AlertCreate, AlertResponse, AlertRepository

router = APIRouter(prefix="/alerts", tags=["Alerts"])


# ── POST /alerts ──────────────────────────────────────────────────────────────

@router.post("", response_model=AlertResponse, status_code=201)
def create_alert(body: AlertCreate, db: Database = Depends(get_db)):
    """
    Subscribe to a price alert for a product.

    Trigger types:
      - "any_drop":    notify whenever the price drops at all
      - "below_price": notify when price falls below target_price

    Examples:
      {"email": "you@example.com", "slug": "nike-dunk-low-panda", "trigger": "any_drop"}
      {"email": "you@example.com", "slug": "air-jordan-1-bred", "trigger": "below_price", "target_price": 9000}
      {"email": "you@example.com", "phone": "+919876543210", "slug": "yeezy-350-zebra", "trigger": "any_drop", "source_store": "hypefly"}
    """
    # Prevent duplicate active alerts for same (email, slug, store, trigger, target)
    repo = AlertRepository(db)
    existing = repo.get_by_email(body.email, active_only=True)
    for a in existing:
        if (
            a["slug"] == body.slug
            and a.get("source_store") == body.source_store
            and a["trigger"] == body.trigger
            and a.get("target_price") == body.target_price
        ):
            raise HTTPException(
                status_code=409,
                detail="An identical active alert already exists for this product and email.",
            )

    repo.setup_indexes()
    doc = repo.create(body)
    return repo.to_response(doc)


# ── GET /alerts/unsubscribe ───────────────────────────────────────────────────
# Must be defined before /alerts/{email} to avoid route conflict

@router.get("/unsubscribe")
def unsubscribe(
    token: str = Query(..., description="Alert token from notification email"),
    db: Database = Depends(get_db),
):
    """
    Deactivate an alert via the unsubscribe link in a notification email.
    The token is unique per alert and included in every notification.

    Returns a plain confirmation — safe to open in a browser.
    """
    repo = AlertRepository(db)
    ok = repo.deactivate_by_token(token)
    if not ok:
        raise HTTPException(status_code=404, detail="Alert not found or already inactive.")
    return {"status": "unsubscribed", "message": "Your price alert has been deactivated."}


# ── GET /alerts/stats ─────────────────────────────────────────────────────────

@router.get("/stats")
def alert_stats(db: Database = Depends(get_db)):
    """Admin overview of alert counts."""
    repo = AlertRepository(db)
    return repo.stats()


# ── GET /alerts/{email} ───────────────────────────────────────────────────────

@router.get("/{email}", response_model=list[AlertResponse])
def list_alerts(
    email: str,
    active_only: bool = Query(True, description="Return only active alerts"),
    db: Database = Depends(get_db),
):
    """
    List all price alerts for an email address.
    No auth token required — email address acts as the lookup key.
    """
    repo = AlertRepository(db)
    docs = repo.get_by_email(email, active_only=active_only)
    return [repo.to_response(d) for d in docs]


# ── DELETE /alerts/{alert_id} ────────────────────────────────────────────────

@router.delete("/{alert_id}")
def delete_alert(alert_id: str, db: Database = Depends(get_db)):
    """Deactivate a specific alert by its ID."""
    repo = AlertRepository(db)
    try:
        ok = repo.deactivate_by_id(alert_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid alert ID format.")
    if not ok:
        raise HTTPException(status_code=404, detail="Alert not found.")
    return {"status": "deactivated", "id": alert_id}