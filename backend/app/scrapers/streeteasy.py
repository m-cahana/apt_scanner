import asyncio
import re
from typing import Optional
from urllib.parse import urlencode
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from .base import BaseScraper, ScrapedListing


class StreetEasyScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.source_name = "streeteasy"
        self.base_url = "https://streeteasy.com/for-rent/nyc"

    def _build_url(
        self,
        page: int = 1,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        bedrooms: Optional[int] = None,
        neighborhood: Optional[str] = None
    ) -> str:
        filters = []

        if min_price and max_price:
            filters.append(f"price:{min_price}-{max_price}")
        elif min_price:
            filters.append(f"price:{min_price}-")
        elif max_price:
            filters.append(f"price:-{max_price}")

        if bedrooms is not None:
            filters.append(f"beds:{bedrooms}")

        url = self.base_url
        if neighborhood:
            url = f"https://streeteasy.com/for-rent/{neighborhood.lower().replace(' ', '-')}"

        if filters:
            url += "/" + "%7C".join(filters)

        if page > 1:
            url += f"?page={page}"

        return url

    async def _extract_listing_from_card(self, card, page: Page) -> Optional[ScrapedListing]:
        try:
            # Extract listing URL and ID
            link_elem = await card.query_selector("a.listingCard-globalLink")
            if not link_elem:
                return None

            href = await link_elem.get_attribute("href")
            if not href:
                return None

            url = f"https://streeteasy.com{href}" if href.startswith("/") else href

            # Extract external ID from URL
            match = re.search(r'/(\d+)(?:\?|$)', href)
            external_id = match.group(1) if match else href

            # Extract price
            price_elem = await card.query_selector(".listingCard-price, [data-testid='price']")
            price_text = await price_elem.inner_text() if price_elem else "0"
            price = int(re.sub(r'[^\d]', '', price_text)) if price_text else 0

            # Extract address
            address_elem = await card.query_selector(".listingCard-address, [data-testid='address']")
            address = await address_elem.inner_text() if address_elem else "Unknown"
            address = address.strip()

            # Extract title (usually the address or building name)
            title_elem = await card.query_selector(".listingCard-title, h3")
            title = await title_elem.inner_text() if title_elem else address
            title = title.strip()

            # Extract beds/baths
            details_elem = await card.query_selector(".listingCard-bedsBaths, [data-testid='beds-baths']")
            details_text = await details_elem.inner_text() if details_elem else ""

            bedrooms = 0
            bathrooms = 0.0

            bed_match = re.search(r'(\d+)\s*(?:bed|br|BD)', details_text, re.IGNORECASE)
            if bed_match:
                bedrooms = int(bed_match.group(1))
            elif "studio" in details_text.lower():
                bedrooms = 0

            bath_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:bath|ba|BA)', details_text, re.IGNORECASE)
            if bath_match:
                bathrooms = float(bath_match.group(1))

            # Extract neighborhood
            neighborhood_elem = await card.query_selector(".listingCard-neighborhood, [data-testid='neighborhood']")
            neighborhood = await neighborhood_elem.inner_text() if neighborhood_elem else ""
            neighborhood = neighborhood.strip()

            # Extract square footage if available
            sqft = None
            sqft_match = re.search(r'(\d{3,5})\s*(?:sq\.?\s*ft|SF)', details_text, re.IGNORECASE)
            if sqft_match:
                sqft = int(sqft_match.group(1))

            # Extract image
            images = []
            img_elem = await card.query_selector("img")
            if img_elem:
                img_src = await img_elem.get_attribute("src")
                if img_src and not img_src.startswith("data:"):
                    images.append(img_src)

            return ScrapedListing(
                external_id=external_id,
                source=self.source_name,
                url=url,
                title=title,
                price=price,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                neighborhood=neighborhood,
                address=address,
                sqft=sqft,
                images=images,
                amenities=[]
            )

        except Exception as e:
            print(f"Error extracting listing: {e}")
            return None

    async def scrape(
        self,
        max_pages: int = 10,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        bedrooms: Optional[int] = None,
        neighborhood: Optional[str] = None
    ) -> list[ScrapedListing]:
        listings = []
        page = await self.get_page()

        try:
            for page_num in range(1, max_pages + 1):
                url = self._build_url(
                    page=page_num,
                    min_price=min_price,
                    max_price=max_price,
                    bedrooms=bedrooms,
                    neighborhood=neighborhood
                )

                print(f"Scraping: {url}")

                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(2)  # Wait for dynamic content
                except PlaywrightTimeout:
                    print(f"Timeout loading page {page_num}")
                    continue

                # Wait for listing cards to appear
                try:
                    await page.wait_for_selector("[data-testid='listings-list'], .searchCardList", timeout=10000)
                except PlaywrightTimeout:
                    print(f"No listings found on page {page_num}")
                    break

                # Find all listing cards
                cards = await page.query_selector_all(".listingCard, [data-testid='listing-card']")

                if not cards:
                    print(f"No more listings found on page {page_num}")
                    break

                for card in cards:
                    listing = await self._extract_listing_from_card(card, page)
                    if listing and listing.price > 0:
                        listings.append(listing)

                print(f"Page {page_num}: Found {len(cards)} cards, {len(listings)} total listings")

                # Check if there's a next page
                next_button = await page.query_selector(".pagination-next:not(.disabled), [aria-label='Next page']")
                if not next_button:
                    break

                # Small delay between pages to avoid rate limiting
                await asyncio.sleep(1)

        finally:
            await page.close()

        return listings


async def run_streeteasy_scraper(
    max_pages: int = 5,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    bedrooms: Optional[int] = None,
    neighborhood: Optional[str] = None
) -> list[ScrapedListing]:
    async with StreetEasyScraper() as scraper:
        return await scraper.scrape(
            max_pages=max_pages,
            min_price=min_price,
            max_price=max_price,
            bedrooms=bedrooms,
            neighborhood=neighborhood
        )


if __name__ == "__main__":
    # Test the scraper
    async def test():
        listings = await run_streeteasy_scraper(max_pages=2, max_price=4000, bedrooms=1)
        for listing in listings[:5]:
            print(f"{listing.title} - ${listing.price} - {listing.bedrooms}BR - {listing.neighborhood}")

    asyncio.run(test())
