from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import Optional, List

from ..database import get_db
from ..models import Listing, Favorite
from ..schemas import ListingResponse, ListingFilters

router = APIRouter()


@router.get("/", response_model=list[ListingResponse])
def get_listings(
    min_price: Optional[int] = Query(None),
    max_price: Optional[int] = Query(None),
    bedrooms: Optional[str] = Query(None, description="Comma-separated bedroom values, e.g. '0,1,2'"),
    bathrooms: Optional[float] = Query(None),
    neighborhood: Optional[str] = Query(None),
    neighborhood_nta: Optional[str] = Query(None, description="Comma-separated NTA neighborhoods, e.g. 'Williamsburg,Greenpoint'"),
    source: Optional[str] = Query(None),
    is_active: bool = Query(True),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=10000),  # Allow higher limit for map view
    db: Session = Depends(get_db)
):
    query = db.query(Listing)

    # Apply filters
    conditions = []
    if is_active is not None:
        conditions.append(Listing.is_active == is_active)
    if min_price is not None:
        conditions.append(Listing.price >= min_price)
    if max_price is not None:
        conditions.append(Listing.price <= max_price)
    if bedrooms is not None:
        # Support comma-separated values for multi-select
        bedroom_values = [int(b.strip()) for b in bedrooms.split(',') if b.strip().isdigit()]
        if bedroom_values:
            conditions.append(Listing.bedrooms.in_(bedroom_values))
    if bathrooms is not None:
        conditions.append(Listing.bathrooms >= bathrooms)
    if neighborhood is not None:
        conditions.append(Listing.neighborhood.ilike(f"%{neighborhood}%"))
    if neighborhood_nta is not None:
        # Support comma-separated values for multi-select
        nta_values = [n.strip() for n in neighborhood_nta.split(',') if n.strip()]
        if nta_values:
            conditions.append(Listing.neighborhood_nta.in_(nta_values))
    if source is not None:
        conditions.append(Listing.source == source)

    if conditions:
        query = query.filter(and_(*conditions))

    # Get favorite listing IDs for marking
    favorite_ids = {f.listing_id for f in db.query(Favorite.listing_id).all()}

    listings = query.order_by(Listing.first_seen.desc()).offset(skip).limit(limit).all()

    # Add is_favorite flag
    result = []
    for listing in listings:
        listing_dict = {
            "id": listing.id,
            "external_id": listing.external_id,
            "source": listing.source,
            "url": listing.url,
            "title": listing.title,
            "price": listing.price,
            "bedrooms": listing.bedrooms,
            "bathrooms": listing.bathrooms,
            "neighborhood": listing.neighborhood,
            "neighborhood_nta": listing.neighborhood_nta,
            "latitude": listing.latitude,
            "longitude": listing.longitude,
            "address": listing.address,
            "sqft": listing.sqft,
            "laundry_type": listing.laundry_type,
            "amenities": listing.amenities or [],
            "images": listing.images or [],
            "description": listing.description,
            "first_seen": listing.first_seen,
            "last_seen": listing.last_seen,
            "is_active": listing.is_active,
            "is_favorite": listing.id in favorite_ids
        }
        result.append(listing_dict)

    return result


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total = db.query(Listing).count()
    active = db.query(Listing).filter(Listing.is_active == True).count()
    by_source = {}
    for source in ["streeteasy", "zillow", "craigslist"]:
        by_source[source] = db.query(Listing).filter(Listing.source == source).count()

    return {
        "total": total,
        "active": active,
        "by_source": by_source
    }


@router.get("/neighborhoods")
def get_neighborhoods(db: Session = Depends(get_db)):
    """Return unique NTA neighborhoods from listings."""
    neighborhoods = db.query(Listing.neighborhood_nta).distinct().all()
    return sorted([n[0] for n in neighborhoods if n[0]])


@router.get("/neighborhoods/grouped")
def get_neighborhoods_grouped():
    """Return all NYC neighborhoods grouped by borough."""
    from ..services.geo import get_neighborhoods_by_borough
    return get_neighborhoods_by_borough()


@router.get("/{listing_id}", response_model=ListingResponse)
def get_listing(listing_id: int, db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    is_favorite = db.query(Favorite).filter(Favorite.listing_id == listing_id).first() is not None

    return {
        "id": listing.id,
        "external_id": listing.external_id,
        "source": listing.source,
        "url": listing.url,
        "title": listing.title,
        "price": listing.price,
        "bedrooms": listing.bedrooms,
        "bathrooms": listing.bathrooms,
        "neighborhood": listing.neighborhood,
        "neighborhood_nta": listing.neighborhood_nta,
        "latitude": listing.latitude,
        "longitude": listing.longitude,
        "address": listing.address,
        "sqft": listing.sqft,
        "laundry_type": listing.laundry_type,
        "amenities": listing.amenities or [],
        "images": listing.images or [],
        "description": listing.description,
        "first_seen": listing.first_seen,
        "last_seen": listing.last_seen,
        "is_active": listing.is_active,
        "is_favorite": is_favorite
    }
