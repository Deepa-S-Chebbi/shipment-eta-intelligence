# Source Manifest: Synthetic Data Governance & Attribution

According to the YottaFlex AI project constraints:
> "External data is optional. Default to fully synthetic data. If any public reference data is used, record URL, version, retrieval date, license, attribution, transformations, and discarded fields in `docs/SOURCE_MANIFEST.md`. If suitability is unclear, use synthetic data only."

---

### Data Provenance Summary

- **Strategy**: 100% Fully Synthetic Causal Modeling.
- **External Third-Party Datasets**: None utilized. No proprietary or personal identifiable information (PII) is included or scraped.
- **Generator Engine**: Deterministic Python pipeline using NumPy `SeedSequence` (Master Seed: `20261022`).
- **Physical Calibrations**: Real-world logistics characteristics (lognormal transit distributions, Pareto-like facility queue dwell times, Poisson event frequencies, and regional storm corridors) are parameterized mathematically based on published industry benchmarks in logistics engineering rather than direct external data copies.

---

### Synthetic Domain Entity Generators

| Entity Stream | Generating Function / Model | Calibration Basis | Discarded / PII Exclusions |
|---|---|---|---|
| `Facility` | Synthetic 2D grid $[0, 1000] \times [0, 1000]$ with clustered regional hubs | Real-world continental hub-and-spoke geography | No real-world addresses, real phone numbers, or employee names |
| `Carrier` | Mode-specific speeds (Road 70km/h, Rail 50km/h, Air 500km/h, Sea 25km/h) + reliability tiers | Freight industry standard transit tables | Fictional carrier brand entities (`AlphaHaul`, `ApexFreight`, etc.) |
| `WeatherEvent` | Quadrant-based moving storm, snow, fog, and rain envelopes | Regional meteorological hazard frequency distributions | No third-party weather API data or copyrighted forecasts |
| `FacilityQueue` | Hourly Poisson arrival and M/M/c queueing model with peak congestion hours | Operations research queueing theory (Erlang-C / M/M/s) | N/A |
| `TrackingEvent` | Physics simulation of vehicle progress + 3-component telemetry lag mixture | Cellular scanner upload latency empirical telemetry profiles | No GPS hardware IMEI or driver identifiers |
