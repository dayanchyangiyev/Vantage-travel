import { useEffect, useRef, useState } from 'react';
import { GeoName, searchGeoNames } from '../lib/geonames';

interface GeoAutocompleteProps {
  value: string;
  onChange: (value: string) => void;
  type: 'country' | 'destination';
  placeholder?: string;
  id?: string;
}

export default function GeoAutocomplete({
  value,
  onChange,
  type,
  placeholder,
  id,
}: GeoAutocompleteProps) {
  const [inputValue, setInputValue] = useState(value);
  const [suggestions, setSuggestions] = useState<GeoName[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setInputValue(value);
  }, [value]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setInputValue(val);
    onChange(val);

    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (val.length < 2) {
      setSuggestions([]);
      setIsOpen(false);
      return;
    }

    debounceRef.current = setTimeout(async () => {
      const results = await searchGeoNames(val, type);
      setSuggestions(results);
      setIsOpen(results.length > 0);
    }, 300);
  };

  const handleSelect = (place: GeoName) => {
    const isCountryResult = place.fcode === 'PCLI';
    const label =
      type === 'country' || isCountryResult
        ? place.name
        : place.countryName
          ? `${place.name}, ${place.countryName}`
          : place.name;

    setInputValue(label);
    onChange(label);
    setSuggestions([]);
    setIsOpen(false);
  };

  return (
    <div ref={containerRef} className="relative">
      <input
        id={id}
        type="text"
        value={inputValue}
        placeholder={placeholder}
        autoComplete="off"
        className="w-full bg-transparent border-b border-zinc-200 py-6 text-2xl focus:border-zinc-950 outline-none transition-colors placeholder:text-zinc-200 font-light"
        onChange={handleChange}
        onFocus={() => suggestions.length > 0 && setIsOpen(true)}
      />

      {isOpen && suggestions.length > 0 && (
        <ul className="absolute z-50 top-full left-0 right-0 bg-white border border-zinc-100 shadow-md max-h-60 overflow-y-auto">
          {suggestions.map((place) => (
            <li
              key={place.geonameId}
              onMouseDown={() => handleSelect(place)}
              className="flex items-baseline justify-between px-5 py-3 cursor-pointer hover:bg-zinc-50 border-b border-zinc-50 last:border-0 transition-colors"
            >
              <span className="text-sm font-light text-zinc-900">
                {place.name}
                {type === 'destination' && place.fcode !== 'PCLI' && place.countryName && (
                  <span className="ml-2 text-[10px] uppercase tracking-widest text-zinc-400">
                    {place.countryName}
                  </span>
                )}
              </span>
              {place.adminName1 && place.fcode !== 'PCLI' && (
                <span className="text-[10px] text-zinc-300 ml-4 shrink-0">{place.adminName1}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
