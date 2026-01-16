from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ListingBase(BaseModel):
    external_id: str
    source: str
    url: str
    title: str
    price: int
    bedrooms: int
    bathrooms: float
    neighborhood: str
    address: str
    sqft: Optional[int] = None
    amenities: list[str] = []
    images: list[str] = []
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    neighborhood_nta: Optional[str] = None


class ListingCreate(ListingBase):
    pass


class ListingResponse(ListingBase):
    id: int
    first_seen: datetime
    last_seen: datetime
    is_active: bool
    is_favorite: bool = False

    class Config:
        from_attributes = True


class ListingFilters(BaseModel):
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    neighborhood: Optional[str] = None
    neighborhood_nta: Optional[str] = None
    source: Optional[str] = None
    is_active: bool = True


class FavoriteCreate(BaseModel):
    listing_id: int
    notes: Optional[str] = None


class FavoriteResponse(BaseModel):
    id: int
    listing_id: int
    notes: Optional[str]
    created_at: datetime
    listing: ListingResponse

    class Config:
        from_attributes = True


class AlertCreate(BaseModel):
    email: str
    filters: dict = {}


class AlertResponse(BaseModel):
    id: int
    email: str
    filters: dict
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
