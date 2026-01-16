const API_BASE = '/api';

export interface Listing {
  id: number;
  external_id: string;
  source: string;
  url: string;
  title: string;
  price: number;
  bedrooms: number;
  bathrooms: number;
  neighborhood: string;
  neighborhood_nta: string | null;
  latitude: number | null;
  longitude: number | null;
  address: string;
  sqft: number | null;
  laundry_type: string | null;
  amenities: string[];
  images: string[];
  description: string | null;
  first_seen: string;
  last_seen: string;
  is_active: boolean;
  is_favorite: boolean;
}

export interface ListingFilters {
  min_price?: number;
  max_price?: number;
  bedrooms?: string; // Comma-separated, e.g. "0,1,2"
  bathrooms?: number;
  neighborhood?: string;
  neighborhood_nta?: string;
  source?: string;
  is_active?: boolean;
  skip?: number;
  limit?: number;
}

export interface Favorite {
  id: number;
  listing_id: number;
  notes: string | null;
  created_at: string;
  listing: Listing;
}

export interface Stats {
  total: number;
  active: number;
  by_source: Record<string, number>;
}

export interface ScrapeResult {
  source: string;
  scraped: number;
  new: number;
  updated: number;
}

export async function fetchListings(filters: ListingFilters = {}): Promise<Listing[]> {
  const params = new URLSearchParams();

  if (filters.min_price) params.set('min_price', String(filters.min_price));
  if (filters.max_price) params.set('max_price', String(filters.max_price));
  if (filters.bedrooms) params.set('bedrooms', filters.bedrooms);
  if (filters.bathrooms) params.set('bathrooms', String(filters.bathrooms));
  if (filters.neighborhood) params.set('neighborhood', filters.neighborhood);
  if (filters.neighborhood_nta) params.set('neighborhood_nta', filters.neighborhood_nta);
  if (filters.source) params.set('source', filters.source);
  if (filters.is_active !== undefined) params.set('is_active', String(filters.is_active));
  if (filters.skip) params.set('skip', String(filters.skip));
  if (filters.limit) params.set('limit', String(filters.limit));

  const response = await fetch(`${API_BASE}/listings/?${params}`);
  if (!response.ok) throw new Error('Failed to fetch listings');
  return response.json();
}

export async function fetchListing(id: number): Promise<Listing> {
  const response = await fetch(`${API_BASE}/listings/${id}`);
  if (!response.ok) throw new Error('Failed to fetch listing');
  return response.json();
}

export async function fetchStats(): Promise<Stats> {
  const response = await fetch(`${API_BASE}/listings/stats`);
  if (!response.ok) throw new Error('Failed to fetch stats');
  return response.json();
}

export async function fetchNeighborhoods(): Promise<string[]> {
  const response = await fetch(`${API_BASE}/listings/neighborhoods`);
  if (!response.ok) throw new Error('Failed to fetch neighborhoods');
  return response.json();
}

export async function fetchNeighborhoodsGrouped(): Promise<Record<string, string[]>> {
  const response = await fetch(`${API_BASE}/listings/neighborhoods/grouped`);
  if (!response.ok) throw new Error('Failed to fetch grouped neighborhoods');
  return response.json();
}

export async function fetchFavorites(): Promise<Favorite[]> {
  const response = await fetch(`${API_BASE}/favorites/`);
  if (!response.ok) throw new Error('Failed to fetch favorites');
  return response.json();
}

export async function addFavorite(listingId: number, notes?: string): Promise<Favorite> {
  const response = await fetch(`${API_BASE}/favorites/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ listing_id: listingId, notes }),
  });
  if (!response.ok) throw new Error('Failed to add favorite');
  return response.json();
}

export async function removeFavorite(listingId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/favorites/by-listing/${listingId}`, {
    method: 'DELETE',
  });
  if (!response.ok) throw new Error('Failed to remove favorite');
}

export async function triggerScrape(
  source: string = 'craigslist',
  maxPages: number = 3
): Promise<{ message: string; result: ScrapeResult }> {
  const response = await fetch(
    `${API_BASE}/scraper/run?source=${source}&max_pages=${maxPages}`,
    { method: 'POST' }
  );
  if (!response.ok) throw new Error('Failed to trigger scrape');
  return response.json();
}
