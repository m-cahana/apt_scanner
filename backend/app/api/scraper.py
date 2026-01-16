from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..services.scraper_service import run_scrape_and_store

router = APIRouter()

# Store for tracking scrape status
scrape_status = {"running": False, "last_result": None}


async def _run_scrape(
    db: Session,
    source: str,
    max_pages: int,
    min_price: Optional[int],
    max_price: Optional[int],
    bedrooms: Optional[int],
    neighborhood: Optional[str]
):
    global scrape_status
    scrape_status["running"] = True
    try:
        result = await run_scrape_and_store(
            db=db,
            source=source,
            max_pages=max_pages,
            min_price=min_price,
            max_price=max_price,
            bedrooms=bedrooms,
            neighborhood=neighborhood
        )
        scrape_status["last_result"] = result
    except Exception as e:
        scrape_status["last_result"] = {"error": str(e)}
    finally:
        scrape_status["running"] = False


@router.post("/run")
async def trigger_scrape(
    background_tasks: BackgroundTasks,
    source: str = "streeteasy",
    max_pages: int = 5,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    bedrooms: Optional[int] = None,
    neighborhood: Optional[str] = None,
    db: Session = Depends(get_db)
):
    if scrape_status["running"]:
        return {"message": "Scrape already in progress", "status": "running"}

    # Run scrape synchronously for now (can be made async/background)
    result = await run_scrape_and_store(
        db=db,
        source=source,
        max_pages=max_pages,
        min_price=min_price,
        max_price=max_price,
        bedrooms=bedrooms,
        neighborhood=neighborhood
    )

    return {"message": "Scrape completed", "result": result}


@router.get("/status")
async def scrape_status_endpoint():
    return scrape_status
