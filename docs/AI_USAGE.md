# AI Usage & Governance Disclosure

In compliance with the YottaFlex AI project submission requirements, this document outlines the extent, methodologies, and human engineering oversight applied in utilizing AI coding tools (Claude Code / Google Antigravity).

---

### 1. Where AI Accelerated the Work
- **Boilerplate Scaffolding**: Rapid construction of relational schema mappings, dataclass definitions, and zero-padded ID regex patterns across 19 relational entities.
- **Test Generation**: Automated drafting of parameterized test suites covering edge cases, regex validators, and foreign key traversals.
- **SQL DDL & SQLite Loader Construction**: Generation of strict foreign-key enforced DDL statements matching the JSON schema definitions.
- **Streamlit Layout**: Prototyping multi-tab dashboard component wrappers and glassmorphism CSS stylings.

### 2. Critical Areas Requiring Heavy Personal Oversight & Refinement
- **RNG Decoupling & SeedSequence Hierarchy**: Ensuring that NumPy's `np.random.SeedSequence.spawn` created truly independent generators for each domain, preventing random trajectory shifts across entities when modifying parameters.
- **Event Calibration Infinite-Loop Fix**: Personally diagnosing and fixing a subtle edge-case in event pruning where `while excess > 0` looped endlessly when only non-prunable scans remained. Refactored into a single-pass $O(N)$ candidate filter.
- **NumPy 2.x `rng.choice` List-of-Dicts Coercion**: Fixing a performance hang caused by `np.random.default_rng().choice` coercing lists of dictionaries into structured ndarrays. Refactored into direct integer indexing.
- **Compact Minute UTC ID Collision Prevention**: Discovering that formatting timestamps to minute resolution (`YYYYMMDDTHHMM`) caused duplicate primary keys when multiple scans occurred in the same minute. Added minute-level deduplication to guarantee 100% primary key uniqueness.
- **Strict Leakage Boundary**: Ensuring that `features_cutoff_time` and all candidate feature events were strictly gated by `ingestion_time <= prediction_time` rather than `event_time`.

### 3. Verification & Governance Evidence
- Every single line of code was executed, tested with `pytest`, and verified against real command outputs.
- 100% bit-for-bit reproducibility verified across independent generation runs (`scripts/repro_check.py`).
- Complete prompt history preserved in `prompt_history/`.

---

### 4. Reviewer Feedback & Code Refinement Oversight
Following comprehensive reviewer feedback, several critical areas were personally diagnosed, audited, and overhauled:
1. **End-to-End Leakage Trap Real Model Training**: Eliminated all formula-based approximations in `src/eta_data/evaluate.py`. Implemented actual feature construction from telematics events, trained genuine `HistGradientBoostingRegressor` and `HistGradientBoostingClassifier` models for both safe (`ingestion_time <= prediction_time`) and leaky (`event_time <= prediction_time`) baselines, and computed the horizon error curve from real residual arrays.
2. **Deterministic Duplicate Scans & Waypoints**: Fixed event generation in `src/eta_data/transactions/events.py` by ensuring duplicate scans (~2.5% rate) point backwards with valid `is_duplicate_of` links and guaranteed chronological ordering (`dup_ing_time >= dup_ev_time`), plus explicit `DELAY_SCAN` and `IN_TRANSIT_SCAN` waypoint pings.
3. **Unbiased Event Pruning**: Replaced backward shipment ID iteration with seeded `rng_events.permutation` across all shipments and dates to eliminate geographical and chronological pruning bias.
4. **CRLF vs LF Line-Ending Normalization**: Enforced `\n` line terminators (`lineterminator="\n"`, `newline="\n"`) across all CSV, SQL, JSON, and SQLite exporters, and committed `.gitattributes` (`* text eol=lf`) to guarantee bitwise SHA-256 reproducibility on fresh clones across Windows, macOS, and Linux.
5. **Dynamic Validation Precision & Recall**: Replaced static report counting with exact set-based confusion matrix computation ($TP, FP, FN$) in `src/eta_data/validate.py` to audit injected anomalies against ground truth with 100% precision and recall.
6. **Realistic Supply Chain Distributions**: Re-calibrated route planned hours, staging delays, and dominant weather slowdowns so that 120H freight arrives realistically (15-25h before deadline) and on-time delivery rates land consistently at 75-82% with `DELAYED > SEVERELY_DELAYED`.
