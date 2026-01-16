import asyncio
import re
from typing import Optional, List
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from .base import BaseScraper, ScrapedListing
from ..services.geo import get_neighborhood


class CraigslistScraper(BaseScraper):
    def __init__(self, fetch_details: bool = True, detail_concurrency: int = 5):
        super().__init__()
        self.source_name = "craigslist"
        self.base_url = "https://newyork.craigslist.org/search/apa"
        self.fetch_details = fetch_details  # Whether to visit detail pages for GPS/images
        self.detail_concurrency = detail_concurrency  # How many detail pages to fetch in parallel

    def _build_url(
        self,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        bedrooms: Optional[int] = None,
    ) -> str:
        params = []

        if min_price:
            params.append(f"min_price={min_price}")
        if max_price:
            params.append(f"max_price={max_price}")
        if bedrooms is not None:
            params.append(f"min_bedrooms={bedrooms}")
            params.append(f"max_bedrooms={bedrooms}")

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

    async def _fetch_detail_page_safe(
        self,
        listing: ScrapedListing,
        browser_context
    ) -> ScrapedListing:
        """Fetch detail page in a new tab, with error handling."""
        detail_page = None
        try:
            detail_page = await browser_context.new_page()
            listing = await self._fetch_detail_page(listing, detail_page)

            # Classify neighborhood using GPS if available
            if listing.latitude and listing.longitude:
                nta_name = get_neighborhood(listing.latitude, listing.longitude)
                if nta_name:
                    listing.neighborhood = nta_name
        except Exception as e:
            print(f"    Error fetching {listing.external_id}: {e}")
        finally:
            if detail_page:
                await detail_page.close()

        return listing

    async def _fetch_details_parallel(
        self,
        listings: List[ScrapedListing],
        browser_context
    ) -> List[ScrapedListing]:
        """Fetch detail pages in parallel with limited concurrency."""
        semaphore = asyncio.Semaphore(self.detail_concurrency)

        async def fetch_with_semaphore(listing: ScrapedListing) -> ScrapedListing:
            async with semaphore:
                return await self._fetch_detail_page_safe(listing, browser_context)

        print(f"  Fetching {len(listings)} detail pages ({self.detail_concurrency} parallel)...")

        # Process in parallel
        results = await asyncio.gather(*[fetch_with_semaphore(l) for l in listings])

        return list(results)

    async def _scroll_and_load_listings(
        self,
        page: Page,
        max_listings: int = 5000,
        scroll_pause: float = 1.0
    ) -> List:
        """Scroll down the page to load all listings via infinite scroll."""
        all_pids = set()
        no_new_count = 0
        max_no_new = 5  # Stop after 5 scrolls with no new listings

        while len(all_pids) < max_listings and no_new_count < max_no_new:
            # Get current listings
            results = await page.query_selector_all("[data-pid]")
            current_pids = set()
            for r in results:
                pid = await r.get_attribute("data-pid")
                if pid:
                    current_pids.add(pid)

            new_pids = current_pids - all_pids
            if new_pids:
                all_pids.update(new_pids)
                no_new_count = 0
                print(f"  Loaded {len(all_pids)} listings so far...")
            else:
                no_new_count += 1

            # Scroll down
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(scroll_pause)

        return await page.query_selector_all("[data-pid]")

    async def scrape_batch(
        self,
        browser_context,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        bedrooms: Optional[int] = None,
        max_listings: int = 5000,
    ) -> List[ScrapedListing]:
        """Scrape listings using infinite scroll and parallel detail fetching.

        Returns fully processed listings ready to save.
        """
        listings = []
        page = await browser_context.new_page()

        try:
            url = self._build_url(
                min_price=min_price,
                max_price=max_price,
                bedrooms=bedrooms
            )

            print(f"Scraping: {url}")

            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            # Scroll to load all listings
            print("Loading listings via scroll...")
            results = await self._scroll_and_load_listings(page, max_listings)

            if not results:
                print("No listings found")
                return []

            print(f"Found {len(results)} listing elements, extracting data...")

            # Extract basic info from search results
            seen_ids = set()
            for result in results:
                listing = await self._extract_listing_from_result(result, page)
                if listing and listing.price > 0 and listing.external_id not in seen_ids:
                    seen_ids.add(listing.external_id)
                    listings.append(listing)

            print(f"Extracted {len(listings)} unique valid listings")

        finally:
            await page.close()

        # Fetch detail pages in parallel for GPS and images
        if self.fetch_details and listings:
            listings = await self._fetch_details_parallel(listings, browser_context)
            print(f"  Completed all detail pages")

        return listings

    async def scrape(
        self,
        max_listings: int = 5000,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        bedrooms: Optional[int] = None,
        **kwargs  # Accept but ignore old params like max_pages, neighborhood
    ) -> List[ScrapedListing]:
        """Scrape listings using infinite scroll.

        Args:
            max_listings: Maximum number of listings to load via scrolling
            min_price: Minimum price filter
            max_price: Maximum price filter
            bedrooms: Number of bedrooms filter
        """
        context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )

        try:
            return await self.scrape_batch(
                browser_context=context,
                min_price=min_price,
                max_price=max_price,
                bedrooms=bedrooms,
                max_listings=max_listings
            )
        finally:
            await context.close()


async def run_craigslist_scraper(
    max_listings: int = 5000,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    bedrooms: Optional[int] = None,
    detail_concurrency: int = 5,
    **kwargs  # Accept old params like max_pages for backwards compatibility
) -> List[ScrapedListing]:
    """Run the Craigslist scraper.

    Args:
        max_listings: Maximum listings to load via scroll (default 5000)
        min_price: Minimum price filter
        max_price: Maximum price filter
        bedrooms: Number of bedrooms filter
        detail_concurrency: How many detail pages to fetch in parallel
    """
    async with CraigslistScraper(detail_concurrency=detail_concurrency) as scraper:
        return await scraper.scrape(
            max_listings=max_listings,
            min_price=min_price,
            max_price=max_price,
            bedrooms=bedrooms
        )


if __name__ == "__main__":
    async def test():
        listings = await run_craigslist_scraper(max_listings=100, max_price=4000, bedrooms=1)
        print(f"Found {len(listings)} listings")
        for listing in listings[:5]:
            print(f"{listing.title[:50]} - ${listing.price} - {listing.bedrooms}BR - {listing.neighborhood}")
            if listing.latitude:
                print(f"  GPS: {listing.latitude}, {listing.longitude}")

    asyncio.run(test())
