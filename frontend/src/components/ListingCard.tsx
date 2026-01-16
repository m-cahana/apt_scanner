import type { Listing } from '../api/client';

interface ListingCardProps {
  listing: Listing;
  onFavoriteToggle: (listing: Listing) => void;
}

export function ListingCard({ listing, onFavoriteToggle }: ListingCardProps) {
  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0,
    }).format(price);
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const sourceColors: Record<string, string> = {
    craigslist: 'bg-purple-100 text-purple-800',
    streeteasy: 'bg-blue-100 text-blue-800',
    zillow: 'bg-green-100 text-green-800',
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow">
      {/* Image */}
      <div className="aspect-[4/3] bg-gray-100 relative">
        {listing.images.length > 0 ? (
          <img
            src={listing.images[0]}
            alt={listing.title}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-gray-400">
            <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 22V12h6v10" />
            </svg>
          </div>
        )}

        {/* Favorite button */}
        <button
          onClick={(e) => {
            e.preventDefault();
            onFavoriteToggle(listing);
          }}
          className={`absolute top-2 right-2 p-2 rounded-full ${
            listing.is_favorite
              ? 'bg-red-500 text-white'
              : 'bg-white/90 text-gray-600 hover:text-red-500'
          } transition-colors`}
        >
          <svg className="w-5 h-5" fill={listing.is_favorite ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
          </svg>
        </button>

        {/* Source badge */}
        <span className={`absolute top-2 left-2 px-2 py-1 text-xs font-medium rounded ${sourceColors[listing.source] || 'bg-gray-100 text-gray-800'}`}>
          {listing.source}
        </span>
      </div>

      {/* Content */}
      <div className="p-4">
        <div className="flex justify-between items-start mb-2">
          <span className="text-2xl font-bold text-gray-900">
            {formatPrice(listing.price)}
          </span>
          <span className="text-sm text-gray-500">
            {formatDate(listing.first_seen)}
          </span>
        </div>

        <h3 className="font-medium text-gray-900 mb-1 line-clamp-1">
          {listing.title}
        </h3>

        {listing.neighborhood && (
          <p className="text-sm text-gray-600 mb-2">{listing.neighborhood}</p>
        )}

        <div className="flex items-center gap-4 text-sm text-gray-600">
          <span>{listing.bedrooms} bed</span>
          {listing.bathrooms > 0 && <span>{listing.bathrooms} bath</span>}
          {listing.sqft && <span>{listing.sqft.toLocaleString()} sqft</span>}
          {listing.laundry_type && (
            <span className={listing.laundry_type === 'none' ? 'text-gray-400' : ''}>
              {listing.laundry_type === 'in_unit' ? 'W/D' :
               listing.laundry_type === 'building' ? 'Laundry' : 'No laundry'}
            </span>
          )}
        </div>

        <a
          href={listing.url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 block text-center py-2 px-4 bg-gray-900 text-white rounded-lg text-sm font-medium hover:bg-gray-800 transition-colors"
        >
          View Listing
        </a>
      </div>
    </div>
  );
}
