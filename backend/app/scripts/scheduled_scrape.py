"""
Scheduled scraping script for GitHub Actions.
Handles scraping, off-market detection, and run logging.

Usage:
    python -m app.scripts.scheduled_scrape --source craigslist --max-pages 10
"""
import asyncio
import argparse
import sys
from pathlib import Path
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.database import SessionLocal, engine, Base
from app.models import Listing, ScrapeRun
from app.services.scraper_service import run_scrape_and_store
from app.services.offmarket_service import mark_offmarket_listings, get_active_external_ids


async def run_scheduled_scrape(
    source: str,
    max_listings: int = 5000,
    triggered_by: str = "scheduled"
) -> dict:
    """Execute a scheduled scrape with full logging and off-market detection."""

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    # Use fresh sessions to avoid connection timeouts during long scrapes
    db = SessionLocal()
    scrape_run_id = None

    try:
        # Create scrape run record
        scrape_run = ScrapeRun(
            source=source,
            started_at=datetime.utcnow(),
            status="running",
            triggered_by=triggered_by
        )
        db.add(scrape_run)
        db.commit()
        db.refresh(scrape_run)
        scrape_run_id = scrape_run.id

        print(f"[{datetime.utcnow()}] Starting scrape run #{scrape_run_id} for {source}")

        # Get current active listing IDs before scrape
        active_before = get_active_external_ids(db, source)
        print(f"[{datetime.utcnow()}] Found {len(active_before)} active listings before scrape")

        # Close session before long scrape operation
        db.close()

        # Run the scrape (passes session factory for fresh connections)
        result = await run_scrape_and_store(
            db_factory=SessionLocal,
            source=source,
            max_listings=max_listings,
            scrape_run_id=scrape_run_id
        )

        # Create fresh session for post-scrape operations
        db = SessionLocal()
        scrape_run = db.query(ScrapeRun).get(scrape_run_id)

        if "error" in result:
            scrape_run.status = "failed"
            scrape_run.error_message = result["error"]
            scrape_run.completed_at = datetime.utcnow()
            db.commit()
            print(f"[{datetime.utcnow()}] Scrape failed: {result['error']}")
            return result

        # Get listing IDs found in this scrape
        scraped_ids = result.get("scraped_external_ids", set())

        # Mark off-market: active before but not in current scrape
        # Only mark off-market if we scraped a significant portion (>50%) of known listings
        # This prevents shallow scrapes from incorrectly marking listings as inactive
        coverage_ratio = len(scraped_ids) / len(active_before) if active_before else 1.0
        if coverage_ratio >= 0.5:
            off_market_count = mark_offmarket_listings(
                db=db,
                source=source,
                active_before=active_before,
                scraped_ids=scraped_ids,
                scrape_run_id=scrape_run_id
            )
        else:
            off_market_count = 0
            print(f"  Skipping off-market detection (coverage {coverage_ratio:.1%} < 50%)")

        # Update scrape run record
        scrape_run.completed_at = datetime.utcnow()
        scrape_run.status = "completed"
        scrape_run.listings_found = result.get("scraped", 0)
        scrape_run.listings_new = result.get("new", 0)
        scrape_run.listings_updated = result.get("updated", 0)
        scrape_run.listings_marked_inactive = off_market_count
        db.commit()

        print(f"[{datetime.utcnow()}] Scrape completed:")
        print(f"  - Found: {scrape_run.listings_found}")
        print(f"  - New: {scrape_run.listings_new}")
        print(f"  - Updated: {scrape_run.listings_updated}")
        print(f"  - Marked off-market: {scrape_run.listings_marked_inactive}")

        return {
            "status": "success",
            "scrape_run_id": scrape_run_id,
            "source": source,
            "scraped": scrape_run.listings_found,
            "new": scrape_run.listings_new,
            "updated": scrape_run.listings_updated,
            "marked_inactive": off_market_count
        }

    except Exception as e:
        print(f"[{datetime.utcnow()}] Scrape failed with exception: {str(e)}")
        if scrape_run_id:
            try:
                db = SessionLocal()
                scrape_run = db.query(ScrapeRun).get(scrape_run_id)
                if scrape_run:
                    scrape_run.status = "failed"
                    scrape_run.error_message = str(e)
                    scrape_run.completed_at = datetime.utcnow()
                    db.commit()
                db.close()
            except Exception:
                pass  # Don't mask original error
        raise
    finally:
        try:
            db.close()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Run scheduled apartment scrape")
    parser.add_argument("--source", default="craigslist", help="Source to scrape")
    parser.add_argument("--max-listings", type=int, default=5000, help="Max listings to scrape")
    parser.add_argument("--triggered-by", default="scheduled", help="Trigger source")
    args = parser.parse_args()

    print(f"Starting scheduled scrape: source={args.source}, max_listings={args.max_listings}")

    result = asyncio.run(run_scheduled_scrape(
        source=args.source,
        max_listings=args.max_listings,
        triggered_by=args.triggered_by
    ))

    if result.get("status") == "failed" or "error" in result:
        print("Scrape failed!")
        sys.exit(1)

    print("Scrape completed successfully!")


if __name__ == "__main__":
    main()
