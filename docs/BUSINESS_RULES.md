# Business Rules & Simulation Formulas

This document details every mathematical rule, causal formula, and threshold used in the YottaFlex synthetic logistics engine, accompanied by a complete end-to-end worked example of a single shipment.

---

## 1. Mathematical Formulas

### Rule 1: Planned Leg Transit Time
$$\text{Distance}(\text{fac}_A, \text{fac}_B) = \sqrt{(x_B - x_A)^2 + (y_B - y_A)^2} \times C_{\text{mode}}$$
$$T_{\text{planned}} = \frac{\text{Distance}}{V_{\text{mode}}}$$
- Mode circuity factors: Road = $1.25$, Rail = $1.15$, Air = $1.02$, Sea = $1.30$.
- Mode base speeds: Road = $65-75\text{ km/h}$, Rail = $42-55\text{ km/h}$, Air = $480-520\text{ km/h}$, Sea = $24-28\text{ km/h}$.

### Rule 2: Carrier Noise Multiplier
$$N_{\text{carrier}} \sim \text{Lognormal}(\mu_{\text{tier}}, \sigma^2_{\text{tier}})$$
- Tier 1: $\mu = -0.005, \sigma = 0.05$ (Mean $\approx 1.00$, tightly centered)
- Tier 2: $\mu = 0.015, \sigma = 0.12$ (Mean $\approx 1.02$)
- Tier 3: $\mu = 0.050, \sigma = 0.22$ (Mean $\approx 1.08$, high variance tail)

### Rule 3: Weather Multiplier
For leg interval $[t_{\text{depart}}, t_{\text{arrive}}]$ intersecting regional weather disturbances $W_k$:
$$M_{\text{weather}} = 1.0 + \sum_{k \in \text{Overlapping}} \left( (S_k - 1.0) \times \frac{\Delta t_{L \cap W_k}}{T_{\text{planned}}} \right)$$
Where $S_k \in [1.05, 2.10]$ is the speed degradation factor for severity 1 through 5.

### Rule 4: Actual Transit Time & Arrival
$$T_{\text{actual}} = \max(0.2\text{h}, T_{\text{planned}} \times N_{\text{carrier}} \times M_{\text{weather}})$$
$$t_{\text{actual\_arrive}} = t_{\text{actual\_depart}} + T_{\text{actual}}$$

### Rule 5: Facility Queue Dwell & Operating Calendars
At intermediate facility $F$:
$$W_{\text{queue}} = \frac{\text{QueueLength}(F)}{\text{ThroughputPerHour}(F)} \times \kappa$$
$$t_{\text{earliest\_next}} = t_{\text{actual\_arrive}} + W_{\text{queue}} + T_{\text{base\_dwell}}$$
$$t_{\text{next\_depart}} = \text{get\_next\_open\_time}(\text{Type}_F, t_{\text{earliest\_next}})$$

### Rule 6: Telemetry Ingestion Lag
$$t_{\text{ingestion}} = t_{\text{event}} + L_{\text{lag}}$$
Where $L_{\text{lag}}$ is sampled from a 3-tier mixture:
- 82% Cellular IoT: $\text{Gamma}(k=2.0, \theta=0.15\text{h}) \implies 5-30\text{ minutes}$
- 15% Batch Dock: $\text{Lognormal}(\mu=1.2, \sigma=0.6\text{h}) \implies 1.5-6\text{ hours}$
- 3% Dead Zone Sync: $\text{Exponential}(\beta=18.0\text{h}) \implies 12-48+\text{ hours}$

### Rule 7: Delay Label Classification & Decomposition
$$\text{DelayHours} = \frac{t_{\text{actual\_delivery}} - t_{\text{promised}}}{3600}$$
- If $\text{DelayHours} \le \text{GraceHours} \implies \mathbf{ON\_TIME}$
- If $\text{GraceHours} < \text{DelayHours} \le \text{SeverelyDelayedHours} \implies \mathbf{DELAYED}$
- If $\text{DelayHours} > \text{SeverelyDelayedHours} \implies \mathbf{SEVERELY\_DELAYED}$

For delayed shipments ($\text{DelayHours} > 0$), positive delay decomposes into reconciled components:
$$\text{DelayHours} = \Delta_{\text{weather}} + \Delta_{\text{queue}} + \Delta_{\text{carrier}} + \Delta_{\text{calendar}} + \Delta_{\text{reroute}} + \Delta_{\text{late\_pickup}}$$

---

## 2. End-to-End Worked Example: Shipment `SHP-2026-000042`

### Step 1: Initialization & Planning
- **Shipment ID**: `SHP-2026-000042`
- **Origin Facility**: `FAC-003` (North Depot, Coordinates: $x=220, y=780$)
- **Destination Facility**: `FAC-014` (East Warehouse, Coordinates: $x=810, y=620$)
- **Service Level**: `SL-EXP-48H` (Target: 48.0h, Grace: 4.0h, Severe: 12.0h)
- **Order Created**: `2026-03-05T08:00:00Z`
- **Promised Delivery**: `2026-03-07T08:00:00Z` ($+48.0\text{h}$)

### Step 2: Route Plan (2 Legs via Regional Hub `FAC-001`)
- **Leg 1**: `FAC-003` $\to$ `FAC-001` (Road, Carrier `CAR-002`, Tier 2, 68 km/h).
  - Distance: $\sqrt{(310-220)^2 + (720-780)^2} \times 1.25 = 135.2\text{ km}$.
  - Planned Transit: $135.2 / 68 = 1.99\text{ hours}$.
  - Planned Depart: `2026-03-05T09:30:00Z` | Planned Arrive: `2026-03-05T11:29:00Z`.
- **Leg 2**: `FAC-001` $\to$ `FAC-014` (Road, Carrier `CAR-001`, Tier 1, 72 km/h).
  - Distance: $\sqrt{(810-310)^2 + (620-720)^2} \times 1.25 = 637.4\text{ km}$.
  - Planned Transit: $637.4 / 72 = 8.85\text{ hours}$.
  - Planned Depart: `2026-03-05T12:30:00Z` | Planned Arrive: `2026-03-05T21:21:00Z`.

### Step 3: Simulation Execution (Causal Delays Encountered)
1. **Origin Dispatch**:
   - Supplier staging hold: $+1.5\text{h}$ dispatch delay.
   - Actual Pickup / Leg 1 Depart: `2026-03-05T11:00:00Z` (1.5h late pickup).
2. **Leg 1 Transit**:
   - Carrier Tier 2 noise multiplier: $N = 1.04$.
   - Weather: Clear ($M_{\text{weather}} = 1.0$).
   - Actual Transit: $1.99 \times 1.04 = 2.07\text{h}$.
   - Leg 1 Arrive at `FAC-001`: `2026-03-05T13:04:00Z`.
3. **Hub Dwell & Congestion**:
   - Active queue length: 65 units; throughput: 20 units/hr $\implies$ Queue wait $= 3.25\text{h}$.
   - Earliest Leg 2 departure: `13:04 + 3.25h + 0.5h dwell = 16:49:00Z`.
   - `FAC-001` is a 24/7 HUB $\implies$ Actual Leg 2 Depart: `2026-03-05T16:49:00Z`.
4. **Leg 2 Transit with Blizzard Disruption**:
   - Storm `WX-0018` active over East corridor (Severity 4, speed multiplier $1.65$).
   - Overlap with transit: 6.0 hours.
   - Weighted weather multiplier: $1.0 + (1.65 - 1.0) \times (6.0 / 8.85) = 1.44$.
   - Carrier Tier 1 noise: $N = 1.01$.
   - Actual Transit: $8.85 \times 1.01 \times 1.44 = 12.87\text{ hours}$ (Delay: $+4.02\text{h}$).
   - Leg 2 Arrive at `FAC-014`: `2026-03-06T05:41:00Z`.
5. **Destination Terminal Dwell & Calendar Opening**:
   - `FAC-014` is a WAREHOUSE (opens at 07:00:00).
   - Arrival occurred at 05:41:00 $\implies$ held at gate until 07:00:00 ($+1.32\text{h}$ calendar delay).
   - Final local delivery completed: `2026-03-06T08:15:00Z`.

### Step 4: Outcome & Delay Attribution
- **Actual Delivery**: `2026-03-06T08:15:00Z`
- **Promised Delivery**: `2026-03-07T08:00:00Z`
- **Observed Delay**: $-23.75\text{ hours}$ (Arrived nearly 24 hours early relative to standard 48h SLA).
- **Final Delay Label**: `ON_TIME`.
