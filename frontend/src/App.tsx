import { useState, useEffect, useCallback } from 'react';
import {
  fetchListings,
  fetchFavorites,
  fetchStats,
  addFavorite,
  removeFavorite,
} from './api/client';
import type { Listing, ListingFilters, Stats, Favorite } from './api/client';
import { SearchForm } from './components/SearchForm';
import { ListingGrid } from './components/ListingGrid';
import { ListingMap } from './components/ListingMap';

type Tab = 'browse' | 'map' | 'favorites';

const PAGE_SIZE = 50;

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('browse');
  const [listings, setListings] = useState<Listing[]>([]);
  const [mapListings, setMapListings] = useState<Listing[]>([]);
  const [favorites, setFavorites] = useState<Favorite[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentFilters, setCurrentFilters] = useState<ListingFilters>({});
  const [currentPage, setCurrentPage] = useState(1);
  const [totalListings, setTotalListings] = useState(0);

  const loadListings = useCallback(async (filters: ListingFilters = {}, page: number = 1) => {
    setIsLoading(true);
    setError(null);
    setCurrentFilters(filters);
    setCurrentPage(page);
    try {
      // Load paginated listings for browse
      const browseFilters = {
        ...filters,
        skip: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      };
      const data = await fetchListings(browseFilters);
      setListings(data);

      // Load all listings for map (with same filters but no pagination)
      const mapFilters = { ...filters, limit: 10000 };
      const mapData = await fetchListings(mapFilters);
      setMapListings(mapData);
      setTotalListings(mapData.length);
    } catch (err) {
      setError('Failed to load listings');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadFavorites = useCallback(async () => {
    try {
      const data = await fetchFavorites();
      setFavorites(data);
    } catch (err) {
      console.error('Failed to load favorites:', err);
    }
  }, []);

  const loadStats = useCallback(async () => {
    try {
      const data = await fetchStats();
      setStats(data);
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  }, []);

  useEffect(() => {
    loadListings();
    loadFavorites();
    loadStats();
  }, [loadListings, loadFavorites, loadStats]);

  const handleFavoriteToggle = async (listing: Listing) => {
    try {
      if (listing.is_favorite) {
        await removeFavorite(listing.id);
      } else {
        await addFavorite(listing.id);
      }
      // Refresh both listings and favorites
      await Promise.all([loadListings(currentFilters, currentPage), loadFavorites()]);
    } catch (err) {
      console.error('Failed to toggle favorite:', err);
    }
  };

  const handleRefresh = async () => {
    await Promise.all([loadListings(currentFilters, currentPage), loadStats(), loadFavorites()]);
  };

  const handleSearch = (filters: ListingFilters) => {
    loadListings(filters, 1); // Reset to page 1 on new search
  };

  const handlePageChange = (page: number) => {
    loadListings(currentFilters, page);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const totalPages = Math.ceil(totalListings / PAGE_SIZE);

  const favoritesAsListings = favorites.map((f) => ({
    ...f.listing,
    is_favorite: true,
  }));

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <h1 className="text-xl font-bold text-gray-900">Apt Scanner</h1>

            <div className="flex items-center gap-4">
              {stats && (
                <span className="text-sm text-gray-600">
                  {stats.active} active listings
                </span>
              )}
              <button
                onClick={handleRefresh}
                disabled={isLoading}
                className="px-4 py-2 bg-gray-900 text-white rounded-lg text-sm font-medium hover:bg-gray-800 disabled:bg-gray-400 transition-colors"
              >
                {isLoading ? 'Loading...' : 'Refresh'}
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <nav className="flex gap-8">
            <button
              onClick={() => setActiveTab('browse')}
              className={`py-4 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'browse'
                  ? 'border-gray-900 text-gray-900'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              Browse
            </button>
            <button
              onClick={() => setActiveTab('map')}
              className={`py-4 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'map'
                  ? 'border-gray-900 text-gray-900'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              Map
            </button>
            <button
              onClick={() => setActiveTab('favorites')}
              className={`py-4 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'favorites'
                  ? 'border-gray-900 text-gray-900'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              Favorites ({favorites.length})
            </button>
          </nav>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'browse' && (
          <div className="space-y-6">
            <SearchForm onSearch={handleSearch} isLoading={isLoading} />

            {error && (
              <div className="bg-red-50 text-red-700 p-4 rounded-lg">
                {error}
              </div>
            )}

            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-600">
                Showing {((currentPage - 1) * PAGE_SIZE) + 1}-{Math.min(currentPage * PAGE_SIZE, totalListings)} of {totalListings} listings
              </p>
            </div>

            <ListingGrid
              listings={listings}
              onFavoriteToggle={handleFavoriteToggle}
              isLoading={isLoading}
            />

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 pt-4">
                <button
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={currentPage === 1 || isLoading}
                  className="px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Previous
                </button>

                <div className="flex items-center gap-1">
                  {/* Show page numbers */}
                  {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                    let pageNum: number;
                    if (totalPages <= 5) {
                      pageNum = i + 1;
                    } else if (currentPage <= 3) {
                      pageNum = i + 1;
                    } else if (currentPage >= totalPages - 2) {
                      pageNum = totalPages - 4 + i;
                    } else {
                      pageNum = currentPage - 2 + i;
                    }
                    return (
                      <button
                        key={pageNum}
                        onClick={() => handlePageChange(pageNum)}
                        disabled={isLoading}
                        className={`px-3 py-2 text-sm font-medium rounded-md ${
                          currentPage === pageNum
                            ? 'bg-gray-900 text-white'
                            : 'text-gray-700 bg-white border border-gray-300 hover:bg-gray-50'
                        }`}
                      >
                        {pageNum}
                      </button>
                    );
                  })}
                </div>

                <button
                  onClick={() => handlePageChange(currentPage + 1)}
                  disabled={currentPage === totalPages || isLoading}
                  className="px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            )}
          </div>
        )}

        {activeTab === 'map' && (
          <div className="space-y-6">
            <SearchForm onSearch={handleSearch} isLoading={isLoading} />

            {error && (
              <div className="bg-red-50 text-red-700 p-4 rounded-lg">
                {error}
              </div>
            )}

            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-600">
                {mapListings.length} listings on map
              </p>
            </div>

            <ListingMap
              listings={mapListings}
              onFavoriteToggle={handleFavoriteToggle}
            />
          </div>
        )}

        {activeTab === 'favorites' && (
          <div className="space-y-6">
            <h2 className="text-lg font-medium text-gray-900">
              Your Saved Listings
            </h2>

            {favorites.length === 0 ? (
              <div className="text-center py-12">
                <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                </svg>
                <h3 className="mt-2 text-sm font-medium text-gray-900">No favorites yet</h3>
                <p className="mt-1 text-sm text-gray-500">
                  Click the heart icon on listings to save them here.
                </p>
              </div>
            ) : (
              <ListingGrid
                listings={favoritesAsListings}
                onFavoriteToggle={handleFavoriteToggle}
              />
            )}
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
