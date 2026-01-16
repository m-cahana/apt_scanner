import { useState, useEffect } from 'react';
import type { ListingFilters } from '../api/client';
import { fetchNeighborhoodsGrouped } from '../api/client';

interface SearchFormProps {
  onSearch: (filters: ListingFilters) => void;
  isLoading?: boolean;
}

// Borough order for display
const BOROUGH_ORDER = ['Manhattan', 'Brooklyn', 'Queens', 'Bronx', 'Staten Island'];

export function SearchForm({ onSearch, isLoading }: SearchFormProps) {
  const [filters, setFilters] = useState<ListingFilters>({
    limit: 50,
  });
  const [selectedBedrooms, setSelectedBedrooms] = useState<number[]>([]);
  const [neighborhoodsByBorough, setNeighborhoodsByBorough] = useState<Record<string, string[]>>({});

  useEffect(() => {
    fetchNeighborhoodsGrouped().then(setNeighborhoodsByBorough).catch(console.error);
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const finalFilters = {
      ...filters,
      bedrooms: selectedBedrooms.length > 0 ? selectedBedrooms.join(',') : undefined,
    };
    onSearch(finalFilters);
  };

  const handleChange = (field: keyof ListingFilters, value: string) => {
    setFilters((prev) => ({
      ...prev,
      [field]: value === '' ? undefined : parseInt(value),
    }));
  };

  const toggleBedroom = (br: number) => {
    setSelectedBedrooms((prev) =>
      prev.includes(br) ? prev.filter((b) => b !== br) : [...prev, br].sort()
    );
  };

  const bedroomOptions = [
    { value: 0, label: 'Studio' },
    { value: 1, label: '1 BR' },
    { value: 2, label: '2 BR' },
    { value: 3, label: '3 BR' },
    { value: 4, label: '4+' },
  ];

  // Sort boroughs in display order
  const sortedBoroughs = Object.keys(neighborhoodsByBorough).sort(
    (a, b) => BOROUGH_ORDER.indexOf(a) - BOROUGH_ORDER.indexOf(b)
  );

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {/* Min Price */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Min Price
          </label>
          <input
            type="number"
            placeholder="$0"
            value={filters.min_price || ''}
            onChange={(e) => handleChange('min_price', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-gray-900 focus:border-transparent"
          />
        </div>

        {/* Max Price */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Max Price
          </label>
          <input
            type="number"
            placeholder="No max"
            value={filters.max_price || ''}
            onChange={(e) => handleChange('max_price', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-gray-900 focus:border-transparent"
          />
        </div>

        {/* Bedrooms - Multi-select */}
        <div className="col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Bedrooms
          </label>
          <div className="flex flex-wrap gap-1">
            {bedroomOptions.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => toggleBedroom(opt.value)}
                className={`px-3 py-1.5 text-sm rounded-md border transition-colors ${
                  selectedBedrooms.includes(opt.value)
                    ? 'bg-gray-900 text-white border-gray-900'
                    : 'bg-white text-gray-700 border-gray-300 hover:border-gray-400'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Neighborhood Dropdown - Grouped by Borough */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Neighborhood
          </label>
          <select
            value={filters.neighborhood_nta || ''}
            onChange={(e) => setFilters((prev) => ({ ...prev, neighborhood_nta: e.target.value || undefined }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-gray-900 focus:border-transparent"
          >
            <option value="">All Neighborhoods</option>
            {sortedBoroughs.map((borough) => (
              <optgroup key={borough} label={borough}>
                {neighborhoodsByBorough[borough].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>

        {/* Search Button */}
        <div className="flex items-end">
          <button
            type="submit"
            disabled={isLoading}
            className="w-full px-4 py-2 bg-gray-900 text-white rounded-lg text-sm font-medium hover:bg-gray-800 disabled:bg-gray-400 transition-colors"
          >
            {isLoading ? 'Searching...' : 'Search'}
          </button>
        </div>
      </div>
    </form>
  );
}
