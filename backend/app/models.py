from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class ScrapeRun(Base):
    """Track each scrape execution for auditing and off-market detection."""
    __tablename__ = "scrape_runs"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, index=True)  # "craigslist", "streeteasy", etc.
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String, default="running")  # "running", "completed", "failed"
    listings_found = Column(Integer, default=0)
    listings_new = Column(Integer, default=0)
    listings_updated = Column(Integer, default=0)
    listings_marked_inactive = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    triggered_by = Column(String, default="manual")  # "manual", "scheduled", "api"

    def __repr__(self):
        return f"<ScrapeRun {self.id}: {self.source} - {self.status}>"


class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String, index=True)
    source = Column(String, index=True)  # "streeteasy", "zillow", "craigslist"
    url = Column(String)
    title = Column(String)
    price = Column(Integer, index=True)
    bedrooms = Column(Integer, index=True)
    bathrooms = Column(Float)
    neighborhood = Column(String, index=True)
    neighborhood_nta = Column(String, nullable=True, index=True)  # Official NYC NTA name
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    address = Column(String)
    sqft = Column(Integer, nullable=True)
    laundry_type = Column(String, nullable=True)  # "in_unit", "building", "none", or null
    amenities = Column(JSON, default=list)
    images = Column(JSON, default=list)
    description = Column(Text, nullable=True)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    deactivated_at = Column(DateTime, nullable=True)  # When marked off-market
    last_scrape_run_id = Column(Integer, ForeignKey("scrape_runs.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    favorites = relationship("Favorite", back_populates="listing", cascade="all, delete-orphan")
    last_scrape_run = relationship("ScrapeRun", foreign_keys=[last_scrape_run_id])

    def __repr__(self):
        return f"<Listing {self.id}: {self.title} - ${self.price}>"


class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    listing = relationship("Listing", back_populates="favorites")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False)
    filters = Column(JSON, default=dict)  # {"min_price": 2000, "max_price": 4000, "bedrooms": 2, ...}
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
