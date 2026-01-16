"""
Migration script: SQLite to Supabase PostgreSQL

Usage:
  python -m app.scripts.migrate_to_supabase --source sqlite:///./apt_scanner.db --target postgresql://...

This script:
1. Creates all tables in the target database
2. Migrates all data from source to target
3. Preserves relationships between tables
"""
import argparse
import sys
from pathlib import Path
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models import Base, Listing, Favorite, Alert, ScrapeRun


def migrate_data(source_url: str, target_url: str, batch_size: int = 100):
    """Migrate all data from source to target database."""

    print(f"Source: {source_url[:50]}...")
    print(f"Target: {target_url[:50]}...")

    # Create engines
    if source_url.startswith("sqlite"):
        source_engine = create_engine(source_url, connect_args={"check_same_thread": False})
    else:
        source_engine = create_engine(source_url)

    target_engine = create_engine(target_url)

    SourceSession = sessionmaker(bind=source_engine)
    TargetSession = sessionmaker(bind=target_engine)

    # Create tables in target (this is idempotent)
    print("\nCreating tables in target database...")
    Base.metadata.create_all(bind=target_engine)

    source_db = SourceSession()
    target_db = TargetSession()

    try:
        # Migrate Listings
        print("\nMigrating listings...")
        listing_count = source_db.query(Listing).count()
        print(f"  Found {listing_count} listings to migrate")

        offset = 0
        while True:
            listings = source_db.query(Listing).offset(offset).limit(batch_size).all()
            if not listings:
                break

            for listing in listings:
                # Check if already exists in target
                existing = target_db.query(Listing).filter(
                    Listing.source == listing.source,
                    Listing.external_id == listing.external_id
                ).first()

                if existing:
                    # Update existing
                    existing.url = listing.url
                    existing.title = listing.title
                    existing.price = listing.price
                    existing.bedrooms = listing.bedrooms
                    existing.bathrooms = listing.bathrooms
                    existing.neighborhood = listing.neighborhood
                    existing.neighborhood_nta = listing.neighborhood_nta
                    existing.latitude = listing.latitude
                    existing.longitude = listing.longitude
                    existing.address = listing.address
                    existing.sqft = listing.sqft
                    existing.amenities = listing.amenities
                    existing.images = listing.images
                    existing.description = listing.description
                    existing.first_seen = listing.first_seen
                    existing.last_seen = listing.last_seen
                    existing.is_active = listing.is_active
                    existing.created_at = listing.created_at
                else:
                    # Create new
                    new_listing = Listing(
                        external_id=listing.external_id,
                        source=listing.source,
                        url=listing.url,
                        title=listing.title,
                        price=listing.price,
                        bedrooms=listing.bedrooms,
                        bathrooms=listing.bathrooms,
                        neighborhood=listing.neighborhood,
                        neighborhood_nta=listing.neighborhood_nta,
                        latitude=listing.latitude,
                        longitude=listing.longitude,
                        address=listing.address,
                        sqft=listing.sqft,
                        amenities=listing.amenities,
                        images=listing.images,
                        description=listing.description,
                        first_seen=listing.first_seen,
                        last_seen=listing.last_seen,
                        is_active=listing.is_active,
                        created_at=listing.created_at
                    )
                    target_db.add(new_listing)

            target_db.commit()
            offset += batch_size
            print(f"  Migrated {min(offset, listing_count)}/{listing_count} listings...")

        # Migrate Favorites
        print("\nMigrating favorites...")
        favorites = source_db.query(Favorite).all()
        print(f"  Found {len(favorites)} favorites to migrate")

        for fav in favorites:
            # Find the corresponding listing in target by external_id
            source_listing = source_db.query(Listing).filter(Listing.id == fav.listing_id).first()
            if source_listing:
                target_listing = target_db.query(Listing).filter(
                    Listing.source == source_listing.source,
                    Listing.external_id == source_listing.external_id
                ).first()

                if target_listing:
                    # Check if favorite already exists
                    existing_fav = target_db.query(Favorite).filter(
                        Favorite.listing_id == target_listing.id
                    ).first()

                    if not existing_fav:
                        new_fav = Favorite(
                            listing_id=target_listing.id,
                            notes=fav.notes,
                            created_at=fav.created_at
                        )
                        target_db.add(new_fav)

        target_db.commit()

        # Migrate Alerts
        print("\nMigrating alerts...")
        alerts = source_db.query(Alert).all()
        print(f"  Found {len(alerts)} alerts to migrate")

        for alert in alerts:
            # Check if alert already exists (by email)
            existing_alert = target_db.query(Alert).filter(
                Alert.email == alert.email
            ).first()

            if not existing_alert:
                new_alert = Alert(
                    email=alert.email,
                    filters=alert.filters,
                    is_active=alert.is_active,
                    created_at=alert.created_at
                )
                target_db.add(new_alert)

        target_db.commit()

        # Summary
        print("\n" + "="*50)
        print("Migration completed successfully!")
        print("="*50)

        target_listings = target_db.query(Listing).count()
        target_favorites = target_db.query(Favorite).count()
        target_alerts = target_db.query(Alert).count()

        print(f"\nTarget database now contains:")
        print(f"  - {target_listings} listings")
        print(f"  - {target_favorites} favorites")
        print(f"  - {target_alerts} alerts")

    except Exception as e:
        print(f"\nError during migration: {e}")
        target_db.rollback()
        raise
    finally:
        source_db.close()
        target_db.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate data from SQLite to Supabase")
    parser.add_argument("--source", required=True, help="Source database URL (e.g., sqlite:///./apt_scanner.db)")
    parser.add_argument("--target", required=True, help="Target database URL (e.g., postgresql://...)")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for migration")
    args = parser.parse_args()

    migrate_data(args.source, args.target, args.batch_size)


if __name__ == "__main__":
    main()
