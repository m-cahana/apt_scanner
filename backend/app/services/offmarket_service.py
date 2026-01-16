"""
Off-market detection service.
Compares current scrape results against existing active listings.
"""
from datetime import datetime, timedelta
from typing import Set, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..models import Listing


def mark_offmarket_listings(
    db: Session,
    source: str,
    active_before: Set[str],
    scraped_ids: Set[str],
    scrape_run_id: Optional[int] = None
) -> int:
    """
    Mark listings as off-market if they were active but not found in current scrape.

    Args:
        db: Database session
        source: Source being scraped (e.g., "craigslist")
        active_before: Set of external_ids that were active before scrape
        scraped_ids: Set of external_ids found in current scrape
        scrape_run_id: ID of the current scrape run for tracking

    Returns:
        Number of listings marked as off-market
    """
    # Listings that disappeared: were active but not in current scrape
    disappeared = active_before - scraped_ids

    if not disappeared:
        return 0

    # Mark as inactive
    now = datetime.utcnow()

    count = db.query(Listing).filter(
        and_(
            Listing.source == source,
            Listing.external_id.in_(disappeared),
            Listing.is_active == True
        )
    ).update(
        {
            "is_active": False,
            "deactivated_at": now,
            "last_scrape_run_id": scrape_run_id
        },
        synchronize_session=False
    )

    db.commit()

    return count


def reactivate_listing(
    db: Session,
    source: str,
    external_id: str,
    scrape_run_id: Optional[int] = None
) -> bool:
    """
    Reactivate a listing that was previously marked off-market.
    Called when a listing reappears in a scrape.

    Returns:
        True if listing was reactivated, False if already active or not found
    """
    listing = db.query(Listing).filter(
        Listing.source == source,
        Listing.external_id == external_id
    ).first()

    if not listing or listing.is_active:
        return False

    listing.is_active = True
    listing.deactivated_at = None
    listing.last_seen = datetime.utcnow()
    listing.last_scrape_run_id = scrape_run_id

    db.commit()
    return True


def get_active_external_ids(db: Session, source: str) -> Set[str]:
    """Get set of external_ids for active listings from a source."""
    results = db.query(Listing.external_id).filter(
        Listing.source == source,
        Listing.is_active == True
    ).all()
    return {row[0] for row in results}


def get_offmarket_stats(db: Session, source: Optional[str] = None) -> dict:
    """Get statistics about off-market listings."""
    query = db.query(Listing).filter(Listing.is_active == False)

    if source:
        query = query.filter(Listing.source == source)

    total_offmarket = query.count()

    # Recent off-market (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_offmarket = query.filter(Listing.deactivated_at >= week_ago).count()

    return {
        "total_offmarket": total_offmarket,
        "recent_offmarket_7d": recent_offmarket
    }
