from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Favorite, Listing
from ..schemas import FavoriteCreate, FavoriteResponse

router = APIRouter()


@router.get("/", response_model=list[FavoriteResponse])
def get_favorites(db: Session = Depends(get_db)):
    favorites = db.query(Favorite).order_by(Favorite.created_at.desc()).all()
    return favorites


@router.post("/", response_model=FavoriteResponse)
def create_favorite(favorite: FavoriteCreate, db: Session = Depends(get_db)):
    # Check if listing exists
    listing = db.query(Listing).filter(Listing.id == favorite.listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Check if already favorited
    existing = db.query(Favorite).filter(Favorite.listing_id == favorite.listing_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Listing already in favorites")

    db_favorite = Favorite(
        listing_id=favorite.listing_id,
        notes=favorite.notes
    )
    db.add(db_favorite)
    db.commit()
    db.refresh(db_favorite)
    return db_favorite


@router.delete("/{favorite_id}")
def delete_favorite(favorite_id: int, db: Session = Depends(get_db)):
    favorite = db.query(Favorite).filter(Favorite.id == favorite_id).first()
    if not favorite:
        raise HTTPException(status_code=404, detail="Favorite not found")

    db.delete(favorite)
    db.commit()
    return {"message": "Favorite removed"}


@router.delete("/by-listing/{listing_id}")
def delete_favorite_by_listing(listing_id: int, db: Session = Depends(get_db)):
    favorite = db.query(Favorite).filter(Favorite.listing_id == listing_id).first()
    if not favorite:
        raise HTTPException(status_code=404, detail="Favorite not found")

    db.delete(favorite)
    db.commit()
    return {"message": "Favorite removed"}
