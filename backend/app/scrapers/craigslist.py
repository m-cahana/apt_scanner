import asyncio
import re
from typing import Optional
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from .base import BaseScraper, ScrapedListing
from ..services.geo import get_neighborhood


class CraigslistScraper(BaseScraper):
    def __init__(self, fetch_details: bool = True):
        super().__init__()
        self.source_name = "craigslist"
        self.base_url = "https://newyork.craigslist.org/search/apa"
        self.fetch_details = fetch_details  # Whether to visit detail pages for GPS/images

    def _build_url(
        self,
        page: int = 0,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        bedrooms: Optional[int] = None,
        neighborhood: Optional[str] = None
    ) -> str:
        params = []

        if min_price:
            params.append(f"min_price={min_price}")
        if max_price:
            params.append(f"max_price={max_price}")
        if bedrooms is not None:
            params.append(f"min_bedrooms={bedrooms}")
            params.append(f"max_bedrooms={bedrooms}")

        # Craigslist uses offset-based pagination (120 results per page)
        if page > 0:
            params.append(f"s={page * 120}")

        url = self.base_url
        if params:
            url += "?" + "&".join(params)

        return url

    async def _extract_listing_from_result(self, result, page: Page) -> Optional[ScrapedListing]:
        try:
            # Get external ID from data-pid attribute
            external_id = await result.get_attribute("data-pid")
            if not external_id:
                return None

            # Get link and title
            link_elem = await result.query_selector("a.main, a")
            if not link_elem:
                return None

            href = await link_elem.get_attribute("href")
            if not href:
                return None

            # Get title
            title_elem = await result.query_selector(".title, .posting-title")
            title = ""
            if title_elem:
                title = await title_elem.inner_text()
            else:
                # Try to get from img alt
                img = await result.query_selector("img")
                if img:
                    title = await img.get_attribute("alt") or ""

            # Extract price
            price_elem = await result.query_selector(".price, .priceinfo")
            price_text = await price_elem.inner_text() if price_elem else "0"
            price = int(re.sub(r'[^\d]', '', price_text)) if price_text else 0

            # Extract location/neighborhood from meta
            location_elem = await result.query_selector(".meta .location, .meta")
            neighborhood = ""
            if location_elem:
                meta_text = await location_elem.inner_text()
                # Location is often in parentheses
                loc_match = re.search(r'\(([^)]+)\)', meta_text)
                if loc_match:
                    neighborhood = loc_match.group(1)

            # Extract bedrooms/bathrooms from title or meta
            bedrooms = 0
            bathrooms = 0.0
            full_text = title.lower()

            # Also get meta text for parsing
            meta_elem = await result.query_selector(".meta")
            if meta_elem:
                meta_text = await meta_elem.inner_text()
                full_text += " " + meta_text.lower()

            # Look for patterns like "1br", "2 bed", etc.
            bed_match = re.search(r'(\d+)\s*(?:br|bed|bedroom)', full_text)
            if bed_match:
                bedrooms = int(bed_match.group(1))

            bath_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:ba|bath|bathroom)', full_text)
            if bath_match:
                bathrooms = float(bath_match.group(1))

            # Get thumbnail image if available
            images = []
            img_elem = await result.query_selector("img")
            if img_elem:
                img_src = await img_elem.get_attribute("src")
                if img_src and not img_src.startswith("data:"):
                    images.append(img_src)

            return ScrapedListing(
                external_id=external_id,
                source=self.source_name,
                url=href,
                title=title.strip(),
                price=price,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                neighborhood=neighborhood,
                address="",  # Craigslist doesn't show full address in results
                sqft=None,
                images=images,
                amenities=[]
            )

        except Exception as e:
            print(f"Error extracting listing: {e}")
            return None

    async def _fetch_detail_page(self, listing: ScrapedListing, page: Page) -> ScrapedListing:
        """Visit the detail page to get GPS coordinates and full image gallery."""
        try:
            await page.goto(listing.url, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(1)

            # Extract GPS coordinates from map element
            map_elem = await page.query_selector("#map")
            if map_elem:
                lat_str = await map_elem.get_attribute("data-latitude")
                lon_str = await map_elem.get_attribute("data-longitude")
                if lat_str and lon_str:
                    try:
                        listing.latitude = float(lat_str)
                        listing.longitude = float(lon_str)
                    except ValueError:
                        pass

            # Extract all images from the gallery
            images = []
            # Try multiple selectors for images
            img_elems = await page.query_selector_all(".gallery img, .swipe img, .iw img, [id*='image'] img")
            for img in img_elems:
                src = await img.get_attribute("src")
                if src and not src.startswith("data:") and src not in images:
                    # Convert thumbnail URLs to full-size if possible
                    # Craigslist uses 50x50, 300x300, 600x450 sizes
                    src = re.sub(r'_\d+x\d+\.', '_600x450.', src)
                    images.append(src)

            # Also check for links to images
            if not images:
                thumb_links = await page.query_selector_all("a.thumb")
                for link in thumb_links:
                    href = await link.get_attribute("href")
                    if href and href.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                        images.append(href)

            if images:
                listing.images = images

            # Try to extract address from posting body
            address_elem = await page.query_selector(".mapaddress")
            if address_elem:
                address = await address_elem.inner_text()
                listing.address = address.strip()

            # Extract laundry info from attribute groups
            attr_elems = await page.query_selector_all(".attrgroup span")
            for attr in attr_elems:
                text = (await attr.inner_text()).lower()
                if "w/d in unit" in text or "washer/dryer in unit" in text:
                    listing.laundry_type = "in_unit"
                    break
                elif "laundry in bldg" in text or "laundry on site" in text:
                    listing.laundry_type = "building"
                    break
                elif "no laundry" in text:
                    listing.laundry_type = "none"
                    break

        except PlaywrightTimeout:
            print(f"Timeout fetching detail page: {listing.url}")
        except Exception as e:
            print(f"Error fetching detail page: {e}")

        return listing

    async def scrape(
        self,
        max_pages: int = 5,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        bedrooms: Optional[int] = None,
        neighborhood: Optional[str] = None
    ) -> list[ScrapedListing]:
        listings = []
        page = await self.get_page()

        try:
            for page_num in range(max_pages):
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
                    await asyncio.sleep(2)
                except PlaywrightTimeout:
                    print(f"Timeout loading page {page_num}")
                    continue

                # Find all listing results - Craigslist uses data-pid for listing cards
                results = await page.query_selector_all(".cl-search-result[data-pid], .gallery-card[data-pid], [data-pid]")

                if not results:
                    print(f"No more listings found on page {page_num}")
                    break

                for result in results:
                    listing = await self._extract_listing_from_result(result, page)
                    if listing and listing.price > 0:
                        listings.append(listing)

                print(f"Page {page_num}: Found {len(results)} results, {len(listings)} total listings")

                # Small delay between pages
                await asyncio.sleep(1)

            # Fetch detail pages for GPS and images if enabled
            if self.fetch_details and listings:
                print(f"Fetching detail pages for {len(listings)} listings...")
                for i, listing in enumerate(listings):
                    try:
                        listing = await self._fetch_detail_page(listing, page)

                        # Classify neighborhood using GPS if available
                        if listing.latitude and listing.longitude:
                            nta_name = get_neighborhood(listing.latitude, listing.longitude)
                            if nta_name:
                                # Store original neighborhood text, use NTA for filtering
                                listing.neighborhood = nta_name
                    except Exception as e:
                        print(f"  Error processing listing {i}: {e}")
                        # Continue with next listing, don't crash entire scrape

                    if (i + 1) % 10 == 0:
                        print(f"  Processed {i + 1}/{len(listings)} detail pages")

                    # Small delay to avoid rate limiting
                    await asyncio.sleep(0.5)

        finally:
            await page.close()

        return listings


async def run_craigslist_scraper(
    max_pages: int = 3,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    bedrooms: Optional[int] = None,
    neighborhood: Optional[str] = None
) -> list[ScrapedListing]:
    async with CraigslistScraper() as scraper:
        return await scraper.scrape(
            max_pages=max_pages,
            min_price=min_price,
            max_price=max_price,
            bedrooms=bedrooms,
            neighborhood=neighborhood
        )


if __name__ == "__main__":
    async def test():
        listings = await run_craigslist_scraper(max_pages=1, max_price=4000, bedrooms=1)
        for listing in listings[:5]:
            print(f"{listing.title[:50]} - ${listing.price} - {listing.bedrooms}BR - {listing.neighborhood}")

    asyncio.run(test())
