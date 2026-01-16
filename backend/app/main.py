from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .database import engine, Base
from .api import listings, favorites, alerts, scraper, monitoring


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Apartment Scanner",
    description="Aggregates apartment listings from StreetEasy, Zillow, and Craigslist",
    version="0.1.0",
    lifespan=lifespan
)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(listings.router, prefix="/api/listings", tags=["listings"])
app.include_router(favorites.router, prefix="/api/favorites", tags=["favorites"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(scraper.router, prefix="/api/scraper", tags=["scraper"])
app.include_router(monitoring.router, prefix="/api/monitoring", tags=["monitoring"])


@app.get("/")
async def root():
    return {"message": "Apartment Scanner API", "version": "0.1.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
