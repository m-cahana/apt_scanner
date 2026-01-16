from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass
from playwright.async_api import async_playwright, Browser, Page, Playwright
import asyncio


@dataclass
class ScrapedListing:
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
    amenities: list[str] = None
    images: list[str] = None
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    def __post_init__(self):
        if self.amenities is None:
            self.amenities = []
        if self.images is None:
            self.images = []


class BaseScraper(ABC):
    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.source_name: str = "unknown"

    async def start(self):
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(headless=True)

    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def get_page(self) -> Page:
        if not self.browser:
            await self.start()
        context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        return await context.new_page()

    @abstractmethod
    async def scrape(
        self,
        max_pages: int = 10,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        bedrooms: Optional[int] = None,
        neighborhood: Optional[str] = None
    ) -> list[ScrapedListing]:
        pass

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
