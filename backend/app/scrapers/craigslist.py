import asyncio
import random
import re
from typing import Optional, List
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from .base import BaseScraper, ScrapedListing
from ..services.geo import get_neighborhood


class CraigslistScraper(BaseScraper):
    def __init__(self, fetch_details: bool = True, detail_concurrency: int = 2):
        super().__init__()
        self.source_name = "craigslist"
        self.base_url = "https://newyork.craigslist.org/search/apa"
        self.fetch_details = fetch_details  # Whether to visit detail pages for GPS/images
        self.detail_concurrency = detail_concurrency  # How many detail pages to fetch in parallel (keep low to avoid blocks)

    def _build_url(
        self,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        bedrooms: Optional[int] = None,
        offset: int = 0,
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

        # Craigslist uses hash-based pagination: #search=2~thumb~{offset}
        url += f"#search=2~thumb~{offset}"

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
                result = await self._fetch_detail_page_safe(listing, browser_context)
                await asyncio.sleep(random.uniform(0.5, 1.5))  # Rate limit
                return result

        print(f"  Fetching {len(listings)} detail pages ({self.detail_concurrency} parallel)...")

        # Process in parallel
        results = await asyncio.gather(*[fetch_with_semaphore(l) for l in listings])

        return list(results)

    async def _scrape_page(self, page: Page) -> List[ScrapedListing]:
        """Extract all listings from the current page."""
        listings = []
        results = await page.query_selector_all("[data-pid]")

        seen_ids = set()
        for result in results:
            listing = await self._extract_listing_from_result(result, page)
            if listing and listing.price > 0 and listing.external_id not in seen_ids:
                seen_ids.add(listing.external_id)
                listings.append(listing)

        return listings

    async def scrape_batch(
        self,
        browser_context,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        bedrooms: Optional[int] = None,
        max_listings: int = 5000,
    ) -> List[ScrapedListing]:
        """Scrape listings using hash-based pagination and parallel detail fetching.

        Craigslist uses #search=2~thumb~{offset} for pagination.
        Returns fully processed listings ready to save.
        """
        all_listings = []
        seen_ids = set()
        page = await browser_context.new_page()
        empty_pages = 0
        max_empty_pages = 8  # Stop after 8 consecutive empty scrolls

        try:
            # Build base URL (without hash) for initial load
            params = []
            if min_price:
                params.append(f"min_price={min_price}")
            if max_price:
                params.append(f"max_price={max_price}")
            if bedrooms is not None:
                params.append(f"min_bedrooms={bedrooms}")
                params.append(f"max_bedrooms={bedrooms}")

            base_url = self.base_url
            if params:
                base_url += "?" + "&".join(params)

            # Initial page load - force thumb (list) view, not gallery
            initial_url = f"{base_url}#search=2~thumb~0~0~0~0~0"
            print(f"Loading: {initial_url}")
            await page.goto(initial_url, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(2)

            scroll_count = 0
            max_scrolls = 200  # Safety limit

            # Click on page to ensure focus
            await page.click("body")
            await asyncio.sleep(0.5)

            while len(all_listings) < max_listings and empty_pages < max_empty_pages and scroll_count < max_scrolls:
                # Extract listings from current view
                page_listings = await self._scrape_page(page)

                # Filter out duplicates
                new_listings = []
                for listing in page_listings:
                    if listing.external_id not in seen_ids:
                        seen_ids.add(listing.external_id)
                        new_listings.append(listing)

                if new_listings:
                    all_listings.extend(new_listings)
                    empty_pages = 0
                    print(f"  Found {len(new_listings)} new (total: {len(all_listings)}, scroll #{scroll_count})")
                else:
                    empty_pages += 1
                    scroll_info = await page.evaluate("""
                        () => ({
                            scrollY: window.scrollY,
                            bodyHeight: document.body.scrollHeight,
                            hash: window.location.hash,
                            pids: Array.from(document.querySelectorAll('[data-pid]')).slice(0, 5).map(el => el.getAttribute('data-pid'))
                        })
                    """)
                    print(f"  No new listings (empty: {empty_pages}/{max_empty_pages}, scroll #{scroll_count})")
                    print(f"    Debug: scrollY={scroll_info['scrollY']}, hash={scroll_info['hash']}")
                    print(f"    First 5 PIDs: {scroll_info['pids']}")

                # Scroll using JavaScript - most reliable method
                scroll_count += 1
                scroll_amount = random.randint(3000, 5000)  # Larger scrolls to load more content
                await page.evaluate(f"window.scrollBy(0, {scroll_amount})")

                await asyncio.sleep(random.uniform(1.5, 2.5))  # Faster but still rate-limited

            print(f"Extracted {len(all_listings)} unique valid listings")

        finally:
            await page.close()

        # Fetch detail pages in parallel for GPS and images
        if self.fetch_details and all_listings:
            all_listings = await self._fetch_details_parallel(all_listings, browser_context)
            print(f"  Completed all detail pages")

        return all_listings

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
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        # Add stealth script to avoid detection
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            window.chrome = {runtime: {}};
        """)

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
