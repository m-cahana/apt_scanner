from datetime import datetime, timedelta
from typing import Optional, Set, List
from sqlalchemy.orm import Session

from ..models import Listing
from ..scrapers.base import ScrapedListing
from ..scrapers.streeteasy import run_streeteasy_scraper
from ..scrapers.craigslist import CraigslistScraper


def save_listings_to_db(
    db: Session,
    scraped: List[ScrapedListing],
    scrape_run_id: Optional[int] = None
) -> tuple[int, int, Set[str]]:
    """Save a batch of scraped listings to the database.

    Returns (new_count, updated_count, external_ids)
    """
    new_count = 0
    updated_count = 0
    scraped_external_ids: Set[str] = set()

    for item in scraped:
        scraped_external_ids.add(item.external_id)

        # Check if listing already exists
        existing = db.query(Listing).filter(
            Listing.source == item.source,
            Listing.external_id == item.external_id
        ).first()

        if existing:
            # Update last_seen and any changed fields
            existing.last_seen = datetime.utcnow()
            existing.price = item.price
            existing.is_active = True
            existing.deactivated_at = None  # Clear if reactivated
            existing.last_scrape_run_id = scrape_run_id
            if item.images:
                existing.images = item.images
            if item.latitude:
                existing.latitude = item.latitude
            if item.longitude:
                existing.longitude = item.longitude
            if item.neighborhood:
                existing.neighborhood = item.neighborhood
                existing.neighborhood_nta = item.neighborhood  # NTA from geo lookup
            if item.laundry_type:
                existing.laundry_type = item.laundry_type
            updated_count += 1
        else:
            # Create new listing
            new_listing = Listing(
                external_id=item.external_id,
                source=item.source,
                url=item.url,
                title=item.title,
                price=item.price,
                bedrooms=item.bedrooms,
                bathrooms=item.bathrooms,
                neighborhood=item.neighborhood,
                neighborhood_nta=item.neighborhood,  # NTA from geo lookup
                latitude=item.latitude,
                longitude=item.longitude,
                address=item.address,
                sqft=item.sqft,
                laundry_type=item.laundry_type,
                amenities=item.amenities,
                images=item.images,
                description=item.description,
                first_seen=datetime.utcnow(),
                last_seen=datetime.utcnow(),
                is_active=True,
                last_scrape_run_id=scrape_run_id
            )
            db.add(new_listing)
            new_count += 1

    # Commit this batch
    db.commit()

    return new_count, updated_count, scraped_external_ids


async def run_scrape_and_store(
    db: Session,
    source: str = "craigslist",
    max_pages: int = 5,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    bedrooms: Optional[int] = None,
    neighborhood: Optional[str] = None,
    scrape_run_id: Optional[int] = None
) -> dict:
    """Run a scrape and store results in the database.

    Saves after each page to avoid losing progress on long scrapes.
    """

    if source == "streeteasy":
        # StreetEasy still uses old approach (TODO: refactor if needed)
        scraped = await run_streeteasy_scraper(
            max_pages=max_pages,
            min_price=min_price,
            max_price=max_price,
            bedrooms=bedrooms,
            neighborhood=neighborhood
        )
        new_count, updated_count, scraped_external_ids = save_listings_to_db(
            db, scraped, scrape_run_id
        )
        return {
            "source": source,
            "scraped": len(scraped),
            "new": new_count,
            "updated": updated_count,
            "scraped_external_ids": scraped_external_ids
        }

    elif source == "craigslist":
        # Craigslist: process and save page by page
        total_scraped = 0
        total_new = 0
        total_updated = 0
        all_external_ids: Set[str] = set()

        async with CraigslistScraper() as scraper:
            page = await scraper.get_page()

            try:
                for page_num in range(max_pages):
                    page_listings = await scraper.scrape_single_page(
                        page=page,
                        page_num=page_num,
                        min_price=min_price,
                        max_price=max_price,
                        bedrooms=bedrooms,
                        neighborhood=neighborhood
                    )

                    if not page_listings and page_num > 0:
                        print(f"No more listings found, stopping at page {page_num}")
                        break

                    # Save this page's listings immediately
                    if page_listings:
                        new_count, updated_count, external_ids = save_listings_to_db(
                            db, page_listings, scrape_run_id
                        )
                        total_scraped += len(page_listings)
                        total_new += new_count
                        total_updated += updated_count
                        all_external_ids.update(external_ids)

                        print(f"  Saved page {page_num}: {new_count} new, {updated_count} updated (total: {total_scraped})")

            finally:
                await page.close()

        return {
            "source": source,
            "scraped": total_scraped,
            "new": total_new,
            "updated": total_updated,
            "scraped_external_ids": all_external_ids
        }

    else:
        return {"error": f"Unknown source: {source}"}


def mark_stale_listings(db: Session, source: str, hours_threshold: int = 24):
    """Mark listings as inactive if not seen in recent scrapes.

    Note: This is the legacy time-based approach. For more accurate detection,
    use the comparison-based approach in offmarket_service.py
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours_threshold)

    now = datetime.utcnow()
    count = db.query(Listing).filter(
        Listing.source == source,
        Listing.is_active == True,
        Listing.last_seen < cutoff
    ).update(
        {
            "is_active": False,
            "deactivated_at": now
        },
        synchronize_session=False
    )

    db.commit()

    return count
