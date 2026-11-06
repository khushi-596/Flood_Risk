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
};

export function PlaceSearch({ onPlaceSelect }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<NominatimResult[]>([]);
  const [message, setMessage] = useState("");
  const [isSearching, setIsSearching] = useState(false);

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedQuery = query.trim();
    if (trimmedQuery.length < 3) {
      setMessage("Enter at least three characters.");
      return;
    }

    setIsSearching(true);
    setMessage("");
    try {
      const url = new URL("https://nominatim.openstreetmap.org/search");
      url.search = new URLSearchParams({
        q: `${trimmedQuery}, Pune, India`,
        format: "jsonv2",
        limit: "5",
        bounded: "1",
        viewbox: "73.80,18.60,73.93,18.48",
      }).toString();
      const response = await fetch(url.toString(), { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error("Place search is unavailable.");
      const places = (await response.json()) as NominatimResult[];
      setResults(places);
      if (places.length === 0) setMessage("No matching place in the Pune demo zone.");
    } catch {
      setMessage("Search is unavailable. Click the map to choose a point instead.");
    } finally {
      setIsSearching(false);
    }
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
          placeholder="Search a start or end point in Pune"
          value={query}
        />
        <button
          className="btn-primary rounded-lg px-4 py-2 text-xs"
          disabled={isSearching}
          id="place-search-btn"
          type="submit"
        >
          {isSearching ? "Searching" : "Search"}
        </button>
      </form>
      {message && (
        <p className="glass-card mt-2 px-3 py-2 text-xs text-slate-700 animate-fade-in">
          {message}
        </p>
      )}
      {results.length > 0 && (
        <ul className="mt-2 overflow-hidden rounded-xl bg-white shadow-lg ring-1 ring-slate-200 animate-slide-down">
          {results.map((result) => (
            <li key={`${result.lat}-${result.lon}`}>
              <button
                className="w-full border-b border-slate-100 px-3 py-2.5 text-left text-sm text-slate-700 transition-colors hover:bg-sky-50"
                id={`place-result-${result.lat}-${result.lon}`}
                onClick={() => {
                  onPlaceSelect({
                    longitude: Number(result.lon),
                    latitude: Number(result.lat),
                    label: result.display_name,
                  });
                  setResults([]);
                  setQuery(result.display_name.split(",")[0] ?? result.display_name);
                }}
                type="button"
              >
                {result.display_name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
