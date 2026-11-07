"use client";

import { FormEvent, useState } from "react";
import type { MapPoint } from "@/lib/types";

type NominatimResult = {
  display_name: string;
  lat: string;
  lon: string;
};

type Props = {
  onPlaceSelect: (point: MapPoint) => void;
  placeholder?: string;
};

export function PlaceSearch({ onPlaceSelect, placeholder = "Search any location in Pune (e.g. Kothrud, Hinjawadi, Station)…" }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<NominatimResult[]>([]);
  const [message, setMessage] = useState("");
  const [isSearching, setIsSearching] = useState(false);

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedQuery = query.trim();
    if (trimmedQuery.length < 2) {
      setMessage("Enter at least two characters.");
      return;
    }

    setIsSearching(true);
    setMessage("");
    try {
      const url = new URL("https://nominatim.openstreetmap.org/search");
      url.search = new URLSearchParams({
        q: `${trimmedQuery}, Pune, Maharashtra, India`,
        format: "jsonv2",
        limit: "6",
        viewbox: "73.50,18.85,74.20,18.25",
        bounded: "0",
      }).toString();
      const response = await fetch(url.toString(), {
        headers: { Accept: "application/json", "User-Agent": "FloodRiskPune/1.0" },
      });
      if (!response.ok) throw new Error("Search service temporary error.");
      let places = (await response.json()) as NominatimResult[];
      
      // Fast local search check
      const localPunes = [
        { name: "Kothrud", lat: "18.5074", lon: "73.8077" },
        { name: "Hinjawadi", lat: "18.5913", lon: "73.7389" },
        { name: "Pune Railway Station", lat: "18.5284", lon: "73.8739" },
        { name: "Shivajinagar", lat: "18.5314", lon: "73.8446" },
        { name: "Swargate", lat: "18.5018", lon: "73.8586" },
        { name: "Baner", lat: "18.5590", lon: "73.7868" },
        { name: "Viman Nagar", lat: "18.5679", lon: "73.9143" },
        { name: "Hadapsar", lat: "18.5089", lon: "73.9260" },
        { name: "Aundh", lat: "18.5602", lon: "73.8062" },
      ].filter((p) => p.name.toLowerCase().includes(trimmedQuery.toLowerCase()));

      // Fallback search if zero results
      if (places.length === 0) {
        if (localPunes.length > 0) {
          places = localPunes.map((p) => ({
            display_name: `${p.name}, Pune, Maharashtra, India`,
            lat: p.lat,
            lon: p.lon,
          }));
        } else {
          const fallbackUrl = new URL("https://nominatim.openstreetmap.org/search");
          fallbackUrl.search = new URLSearchParams({
            q: `${trimmedQuery}, Pune`,
            format: "jsonv2",
            limit: "6",
          }).toString();
          const fallbackRes = await fetch(fallbackUrl.toString(), {
            headers: { Accept: "application/json", "User-Agent": "FloodRiskPune/1.0" },
          });
          if (fallbackRes.ok) {
            places = (await fallbackRes.json()) as NominatimResult[];
          }
        }
      }

      setResults(places);
      if (places.length === 0) setMessage("No locations found. Try another Pune locality or landmark.");
    } catch {
      setMessage("Search service busy. You can also tap directly on the map to set location.");
    } finally {
      setIsSearching(false);
    }
  }

  function handleSelect(place: NominatimResult) {
    onPlaceSelect({
      label: place.display_name.split(",")[0],
      latitude: Number(place.lat),
      longitude: Number(place.lon),
    });
    setResults([]);
    setQuery(place.display_name.split(",")[0]);
  }

  return (
    <section className="relative z-10 w-full max-w-xl" aria-label="Place search">
      <form className="glass-card flex p-1" onSubmit={search}>
        <label className="sr-only" htmlFor="place-search">
          Search a place in Pune
        </label>
        <input
          className="min-w-0 flex-1 rounded-lg border-0 bg-transparent px-3 py-2 text-sm text-slate-900 outline-none placeholder:text-slate-500 focus:ring-2 focus:ring-sky-500"
          id="place-search"
          onChange={(event) => setQuery(event.target.value)}
          placeholder={placeholder}
          value={query}
        />
        <button
          className="btn-primary rounded-lg px-4 py-2 text-xs"
          disabled={isSearching}
          id="place-search-submit"
          type="submit"
        >
          {isSearching ? "Searching…" : "Search"}
        </button>
      </form>

      {message && (
        <p className="mt-1.5 rounded-lg bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-800" role="status">
          {message}
        </p>
      )}

      {results.length > 0 && (
        <ul
          className="animate-slide-down absolute left-0 right-0 top-full mt-1.5 max-h-56 overflow-y-auto rounded-xl border border-slate-200 bg-white p-1 shadow-xl"
          role="listbox"
        >
          {results.map((place) => (
            <li key={`${place.lat}-${place.lon}`}>
              <button
                className="w-full rounded-lg px-3 py-2 text-left text-xs text-slate-700 transition hover:bg-sky-50 hover:text-sky-900"
                onClick={() => handleSelect(place)}
                type="button"
              >
                <span className="font-semibold text-slate-900">{place.display_name.split(",")[0]}</span>
                <span className="block truncate text-[11px] text-slate-500">{place.display_name}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
