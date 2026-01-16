"""
Monitoring API endpoints for scrape runs and dashboard statistics.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
from typing import Optional

from ..database import get_db
from ..models import Listing, ScrapeRun

router = APIRouter()


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Detailed health check including database connectivity."""
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/scrape-runs")
def get_scrape_runs(
    source: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get recent scrape run history."""
    query = db.query(ScrapeRun)

    if source:
        query = query.filter(ScrapeRun.source == source)

    runs = query.order_by(ScrapeRun.started_at.desc()).limit(limit).all()

    return [{
        "id": run.id,
        "source": run.source,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "status": run.status,
        "listings_found": run.listings_found,
        "listings_new": run.listings_new,
        "listings_updated": run.listings_updated,
        "listings_marked_inactive": run.listings_marked_inactive,
        "triggered_by": run.triggered_by,
        "error_message": run.error_message
    } for run in runs]


@router.get("/scrape-runs/{run_id}")
def get_scrape_run(run_id: int, db: Session = Depends(get_db)):
    """Get details of a specific scrape run."""
    run = db.query(ScrapeRun).filter(ScrapeRun.id == run_id).first()

    if not run:
        return {"error": "Scrape run not found"}

    return {
        "id": run.id,
        "source": run.source,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "status": run.status,
        "listings_found": run.listings_found,
        "listings_new": run.listings_new,
        "listings_updated": run.listings_updated,
        "listings_marked_inactive": run.listings_marked_inactive,
        "triggered_by": run.triggered_by,
        "error_message": run.error_message
    }


@router.get("/dashboard")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Dashboard statistics for monitoring."""
    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)

    total_listings = db.query(Listing).count()
    active_listings = db.query(Listing).filter(Listing.is_active == True).count()

    new_today = db.query(Listing).filter(Listing.first_seen >= day_ago).count()
    new_this_week = db.query(Listing).filter(Listing.first_seen >= week_ago).count()

    deactivated_today = db.query(Listing).filter(
        Listing.deactivated_at >= day_ago
    ).count()

    deactivated_this_week = db.query(Listing).filter(
        Listing.deactivated_at >= week_ago
    ).count()

    last_scrape = db.query(ScrapeRun).order_by(
        ScrapeRun.started_at.desc()
    ).first()

    # Success rate of last 10 scrapes
    recent_scrapes = db.query(ScrapeRun).order_by(
        ScrapeRun.started_at.desc()
    ).limit(10).all()

    success_count = sum(1 for s in recent_scrapes if s.status == "completed")
    success_rate = (success_count / len(recent_scrapes) * 100) if recent_scrapes else 0

    return {
        "listings": {
            "total": total_listings,
            "active": active_listings,
            "inactive": total_listings - active_listings
        },
        "activity": {
            "new_today": new_today,
            "new_this_week": new_this_week,
            "deactivated_today": deactivated_today,
            "deactivated_this_week": deactivated_this_week
        },
        "scraping": {
            "last_scrape": {
                "id": last_scrape.id if last_scrape else None,
                "source": last_scrape.source if last_scrape else None,
                "status": last_scrape.status if last_scrape else None,
                "completed_at": last_scrape.completed_at.isoformat() if last_scrape and last_scrape.completed_at else None,
                "listings_found": last_scrape.listings_found if last_scrape else None
            } if last_scrape else None,
            "success_rate_last_10": round(success_rate, 1)
        },
        "timestamp": now.isoformat()
    }
