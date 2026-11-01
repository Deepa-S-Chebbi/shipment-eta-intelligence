# Reproducibility Verification Report

**Audit Timestamp**: 2026-11-01T17:12:19.965886+00:00  
**Master Seed**: `20261022`  
**Scale**: `1.0`  
**Run 1 Execution Time**: 237.34s  
**Run 2 Execution Time**: 251.64s  
**Overall Status**: BIT-FOR-BIT IDENTICAL (100% REPRODUCIBLE)  

---

## Dual-Run Bitwise Comparison

| File Name | Run 1 Rows | Run 2 Rows | SHA-256 Checksum (Run 1) | SHA-256 Match | Verification Status |
|---|---|---|---|---|---|
| `carrier_calendars.csv` | 42 | 42 | `b35425f7bdd77873...` | MATCH | IDENTICAL |
| `carriers.csv` | 6 | 6 | `dbd66f3cb53ba3d8...` | MATCH | IDENTICAL |
| `delay_reasons.csv` | 6 | 6 | `ce1b06477adb5900...` | MATCH | IDENTICAL |
| `eta_estimates.csv` | 750123 | 750123 | `26e6be463095f0ad...` | MATCH | IDENTICAL |
| `facilities.csv` | 100 | 100 | `02480000a351b5cb...` | MATCH | IDENTICAL |
| `facility_calendars.csv` | 700 | 700 | `b929596bc3806e52...` | MATCH | IDENTICAL |
| `facility_queues.csv` | 3000 | 3000 | `57d0848614edfc86...` | MATCH | IDENTICAL |
| `ground_truth.csv` | 5737 | 5737 | `0c8eb20800b726e6...` | MATCH | IDENTICAL |
| `ground_truth.json` | 5737 | 5737 | `57165a8712f4753a...` | MATCH | IDENTICAL |
| `logistics.sqlite` | 1913762 | 1913762 | `c02a90fdbbfe613d...` | MATCH | IDENTICAL |
| `route_changes.csv` | 201 | 201 | `7c6724bdbea8a674...` | MATCH | IDENTICAL |
| `route_leg_templates.csv` | 46 | 46 | `8fbf293b79c70511...` | MATCH | IDENTICAL |
| `routes.csv` | 25 | 25 | `909cb3b7a2ec5330...` | MATCH | IDENTICAL |
| `seed.sql` | 1913762 | 1913762 | `d143c37b475e73bf...` | MATCH | IDENTICAL |
| `service_levels.csv` | 4 | 4 | `9db727f3f5e84980...` | MATCH | IDENTICAL |
| `shipment_delay_reasons.csv` | 162858 | 162858 | `021ee1e4105a078c...` | MATCH | IDENTICAL |
| `shipment_legs.csv` | 92291 | 92291 | `3bf992ebf37a2200...` | MATCH | IDENTICAL |
| `shipment_status_history.csv` | 150000 | 150000 | `677f8c4f3ba10a43...` | MATCH | IDENTICAL |
| `shipments.csv` | 50000 | 50000 | `e9fa54688cd7f9ce...` | MATCH | IDENTICAL |
| `tracking_events.csv` | 300000 | 300000 | `9c3254c90a6e5b27...` | MATCH | IDENTICAL |
| `weather_event_facilities.csv` | 5937 | 5937 | `640f442c746996d1...` | MATCH | IDENTICAL |
| `weather_event_legs.csv` | 397423 | 397423 | `76ec72cc0bd58fae...` | MATCH | IDENTICAL |
| `weather_events.csv` | 1000 | 1000 | `5db67c93194bc826...` | MATCH | IDENTICAL |

---

## Technical Safeguards for Determinism

1. **Independent RNG Streams**: Master seed `20261022` is partitioned using `numpy.random.SeedSequence.spawn`, ensuring modifications to one entity generator never shuffle the random trajectory of others.
2. **Zero System-Clock Dependencies**: No non-deterministic `datetime.now()` calls exist in generation logic. Timestamps derive from a static epoch (`2026-03-01T00:00:00Z`).
3. **Stable Sorting**: Tables are explicitly sorted across composite primary keys prior to export, preventing unordered dictionary/set nondeterminism across runs or platforms.
4. **No Python hash() Iteration**: Set lookups avoid Python's randomized hash seed (`PYTHONHASHSEED`).