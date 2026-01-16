import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import { Icon } from 'leaflet';
import type { Listing } from '../api/client';
import 'leaflet/dist/leaflet.css';

interface ListingMapProps {
  listings: Listing[];
  onFavoriteToggle?: (listing: Listing) => void;
}

// Fix for default marker icons in React-Leaflet
const defaultIcon = new Icon({
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

// NYC center coordinates
const NYC_CENTER: [number, number] = [40.7128, -74.006];

export function ListingMap({ listings, onFavoriteToggle }: ListingMapProps) {
  // Filter listings with valid GPS coordinates
  const mappableListings = listings.filter(
    (l) => l.latitude && l.longitude && l.latitude !== 0 && l.longitude !== 0
  );

  return (
    <div className="h-[600px] rounded-lg overflow-hidden border border-gray-200">
      <MapContainer
        center={NYC_CENTER}
        zoom={11}
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {mappableListings.map((listing) => (
          <Marker
            key={listing.id}
            position={[listing.latitude!, listing.longitude!]}
            icon={defaultIcon}
          >
            <Popup>
              <div className="w-64">
                {listing.images[0] && (
                  <img
                    src={listing.images[0]}
                    alt={listing.title}
                    className="w-full h-32 object-cover rounded mb-2"
                  />
                )}
                <h3 className="font-medium text-sm truncate">{listing.title}</h3>
                <p className="text-lg font-bold text-gray-900">
                  ${listing.price.toLocaleString()}/mo
                </p>
                <p className="text-xs text-gray-600">
                  {listing.bedrooms === 0 ? 'Studio' : `${listing.bedrooms} BR`} •{' '}
                  {listing.bathrooms} BA
                  {listing.neighborhood_nta && ` • ${listing.neighborhood_nta}`}
                </p>
                <div className="mt-2 flex gap-2">
                  <a
                    href={listing.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-blue-600 hover:underline"
                  >
                    View Listing
                  </a>
                  {onFavoriteToggle && (
                    <button
                      onClick={() => onFavoriteToggle(listing)}
                      className="text-xs text-gray-600 hover:text-red-500"
                    >
                      {listing.is_favorite ? '♥ Saved' : '♡ Save'}
                    </button>
                  )}
                </div>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
      {mappableListings.length < listings.length && (
        <p className="text-xs text-gray-500 mt-2 text-center">
          Showing {mappableListings.length} of {listings.length} listings with GPS data
        </p>
      )}
    </div>
  );
}
