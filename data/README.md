# Data inventory

| Location | Purpose | Commit policy |
| --- | --- | --- |
| `seeds/demo_segments.geojson` | Small deterministic Pune presentation dataset | Commit |
| `known_flood_locations.csv` | Illustrative validation seed list | Commit only verified, licensed records |
| `raw/` | OSM download, DEMs, drainage source layers | Do not commit |
| `processed/` | Segmented/enriched city data | Do not commit by default |
| `cache/` | Download and job cache | Do not commit |

Record source URL, date, licence, CRS, and zone boundary alongside every real data
import. Never describe the seeded examples as verified historic incidents in a demo.
