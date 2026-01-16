import { useState, useEffect, useRef } from 'react';
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

  // Neighborhood autocomplete state
  const [neighborhoodInput, setNeighborhoodInput] = useState('');
  const [selectedNeighborhoods, setSelectedNeighborhoods] = useState<string[]>([]);
  const [showNeighborhoodDropdown, setShowNeighborhoodDropdown] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const neighborhoodRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchNeighborhoodsGrouped().then(setNeighborhoodsByBorough).catch(console.error);
  }, []);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (neighborhoodRef.current && !neighborhoodRef.current.contains(e.target as Node)) {
        setShowNeighborhoodDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const finalFilters = {
      ...filters,
      bedrooms: selectedBedrooms.length > 0 ? selectedBedrooms.join(',') : undefined,
      neighborhood_nta: selectedNeighborhoods.length > 0 ? selectedNeighborhoods.join(',') : undefined,
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

  // Filter neighborhoods based on input (excluding already selected)
  const getFilteredNeighborhoods = () => {
    const search = neighborhoodInput.toLowerCase().trim();

    return sortedBoroughs
      .map((borough) => ({
        borough,
        neighborhoods: neighborhoodsByBorough[borough].filter((n) => {
          // Exclude already selected
          if (selectedNeighborhoods.includes(n)) return false;
          // Filter by search term
          if (search && !n.toLowerCase().includes(search)) return false;
          return true;
        }),
      }))
      .filter((group) => group.neighborhoods.length > 0);
  };

  const filteredGroups = getFilteredNeighborhoods();
  const flatFilteredList = filteredGroups.flatMap((g) => g.neighborhoods);

  const selectNeighborhood = (neighborhood: string) => {
    setSelectedNeighborhoods((prev) => [...prev, neighborhood]);
    setNeighborhoodInput('');
    setShowNeighborhoodDropdown(false);
    setHighlightedIndex(-1);
    inputRef.current?.focus();
  };

  const removeNeighborhood = (neighborhood: string) => {
    setSelectedNeighborhoods((prev) => prev.filter((n) => n !== neighborhood));
  };

  const clearAllNeighborhoods = () => {
    setSelectedNeighborhoods([]);
    setNeighborhoodInput('');
    setHighlightedIndex(-1);
  };

  const handleNeighborhoodKeyDown = (e: React.KeyboardEvent) => {
    if (!showNeighborhoodDropdown) {
      if (e.key === 'ArrowDown' || e.key === 'Enter') {
        setShowNeighborhoodDropdown(true);
      }
      return;
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setHighlightedIndex((prev) =>
          prev < flatFilteredList.length - 1 ? prev + 1 : prev
        );
        break;
      case 'ArrowUp':
        e.preventDefault();
        setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : -1));
        break;
      case 'Enter':
        e.preventDefault();
        if (highlightedIndex >= 0 && flatFilteredList[highlightedIndex]) {
          selectNeighborhood(flatFilteredList[highlightedIndex]);
        }
        break;
      case 'Escape':
        setShowNeighborhoodDropdown(false);
        setHighlightedIndex(-1);
        break;
    }
  };

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

        {/* Neighborhood Autocomplete - Multi-select */}
        <div className="relative col-span-2" ref={neighborhoodRef}>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Neighborhoods
          </label>
          <div className="min-h-[42px] px-2 py-1.5 border border-gray-300 rounded-lg focus-within:ring-2 focus-within:ring-gray-900 focus-within:border-transparent flex flex-wrap gap-1 items-center">
            {/* Selected chips */}
            {selectedNeighborhoods.map((n) => (
              <span
                key={n}
                className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-100 text-gray-800 text-xs rounded-md"
              >
                {n}
                <button
                  type="button"
                  onClick={() => removeNeighborhood(n)}
                  className="text-gray-500 hover:text-gray-700"
                >
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </span>
            ))}
            {/* Input */}
            <input
              ref={inputRef}
              type="text"
              placeholder={selectedNeighborhoods.length === 0 ? "Type to search..." : ""}
              value={neighborhoodInput}
              onChange={(e) => {
                setNeighborhoodInput(e.target.value);
                setShowNeighborhoodDropdown(true);
                setHighlightedIndex(-1);
              }}
              onFocus={() => setShowNeighborhoodDropdown(true)}
              onKeyDown={handleNeighborhoodKeyDown}
              className="flex-1 min-w-[100px] outline-none text-sm bg-transparent"
            />
            {/* Clear all button */}
            {selectedNeighborhoods.length > 0 && (
              <button
                type="button"
                onClick={clearAllNeighborhoods}
                className="text-gray-400 hover:text-gray-600 ml-auto"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>

          {/* Dropdown */}
          {showNeighborhoodDropdown && filteredGroups.length > 0 && (
            <div className="absolute z-50 w-full mt-1 bg-white border border-gray-300 rounded-lg shadow-lg max-h-60 overflow-y-auto">
              {filteredGroups.map((group) => (
                <div key={group.borough}>
                  <div className="px-3 py-1.5 text-xs font-semibold text-gray-500 bg-gray-50 sticky top-0">
                    {group.borough}
                  </div>
                  {group.neighborhoods.map((neighborhood) => {
                    const flatIndex = flatFilteredList.indexOf(neighborhood);
                    return (
                      <button
                        key={neighborhood}
                        type="button"
                        onClick={() => selectNeighborhood(neighborhood)}
                        className={`w-full px-3 py-2 text-left text-sm hover:bg-gray-100 ${
                          flatIndex === highlightedIndex ? 'bg-gray-100' : ''
                        }`}
                      >
                        {neighborhood}
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>
          )}

          {showNeighborhoodDropdown && neighborhoodInput && filteredGroups.length === 0 && (
            <div className="absolute z-50 w-full mt-1 bg-white border border-gray-300 rounded-lg shadow-lg p-3 text-sm text-gray-500">
              No neighborhoods found
            </div>
          )}
        </div>

        {/* Search & Clear Buttons */}
        <div className="flex items-end gap-2">
          <button
            type="submit"
            disabled={isLoading}
            className="flex-1 px-4 py-2 bg-gray-900 text-white rounded-lg text-sm font-medium hover:bg-gray-800 disabled:bg-gray-400 transition-colors"
          >
            {isLoading ? 'Searching...' : 'Search'}
          </button>
          <button
            type="button"
            onClick={() => {
              setFilters({ limit: 50 });
              setSelectedBedrooms([]);
              setSelectedNeighborhoods([]);
              setNeighborhoodInput('');
              onSearch({ limit: 50 });
            }}
            className="px-3 py-2 text-gray-600 border border-gray-300 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors"
          >
            Clear
          </button>
        </div>
      </div>
    </form>
  );
}
