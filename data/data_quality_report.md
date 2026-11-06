# Pune Study Zone: Data Quality & QA Report

**Generated:** 2026-11-06 16:59:18 UTC

## 1. Road Segments Quality Summary
- **Total Segments:** 22
- **Total Network Coverage:** 28.03 km
- **Mean Segment Length:** 1274.1 m (Min: 500.0 m, Max: 2900.0 m)
- **Underpasses Identified:** 2
- **Highways Distribution:**
| Highway Class | Count |
| :--- | :--- |
| primary | 12 |
| secondary | 9 |
| tertiary | 1 |

### Segments Missing / Null Fields Check:
| Field | Null Count |
| :--- | :--- |
| segment_id | 0 |
| name | 0 |
| highway | 0 |
| length_m | 0 |
| is_underpass | 0 |
| terrain | 0 |
| flood_history | 0 |
| drainage | 0 |
| coord_count | 0 |

## 2. Historical Flood Hotspots Quality Summary
- **Total Validated Hotspots:** 40
- **Bounding Box:** Lat [18.4550, 18.5685], Lon [73.7850, 73.9280]
- **Mean Rain Threshold:** 20.1 mm/h
- **Mean Source Confidence:** 0.83
### Severity Distribution:
| Severity (1-5) | Count |
| :--- | :--- |
| 2 | 2 |
| 3 | 17 |
| 4 | 16 |
| 5 | 5 |

## 3. Synthetic Citizen Hazard Reports Audit
- **Total Seed Reports:** 50
- **Unique Device Fingerprints:** 35
### Report Types Distribution:
| Hazard Type | Count |
| :--- | :--- |
| waterlogging | 32 |
| blocked_drain | 8 |
| flood | 6 |
| pothole | 4 |

## 4. Definition of Done Compliance Check
- [x] Road segments divided into walkable/drivable lengths with geometry validity
- [x] Curated historical waterlogging dataset reaches >= 30 verified spots (Total: 40)
- [x] Elevation, drainage, terrain, and flood history signals normalized to 0–1
- [x] Reproducible data QA script and calibration report committed