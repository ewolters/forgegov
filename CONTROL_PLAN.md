# Quality Control Plan — SVEND + Forge Ecosystem

**Date:** 2026-03-29
**Scope:** Full product quality — SVEND platform + forge computation layer
**Standard reference:** OLR-001 (the product standard SVEND implements for customers)

---

## Two Quality Surfaces

### Surface 1: Does the computation produce correct results?

The forge packages are measurement instruments. If forgespc computes wrong control limits, every customer's SPC chart is wrong. If forgedoe generates an unbalanced design matrix, every customer's DOE is invalid.

**Owner:** forgegov (pipeline + audits + calibration)
**Detection:** Automated — golden references, contracts, lint, tests

### Surface 2: Does SVEND correctly implement OLR-001 for customers?

The product promises a process knowledge system with three concerns (Graph, Loop, Compliance). If the graph doesn't accumulate knowledge from investigations, if signals don't route to the Loop, if the FMIS view doesn't derive from the graph — the product is broken even if every individual computation is correct.

**Owner:** SVEND compliance + quality manager review
**Detection:** Mixed — some automated (compliance checks), some requires judgment

---

## Surface 1: Computation Correctness

### Control Points

| Forge Package | OLR-001 Role | Golden Cases | Detection Level |
|--------------|-------------|-------------|-----------------|
| forgespc | SPC monitoring → flags edge staleness (§7.4, §13) | 14 | L3 (auto) |
| forgedoe | DOE calibration → EdgeEvidence with effect sizes (§8) | 6 | L3 (auto) |
| forgestat | Statistical tests → calibrate graph edges (§8) | In progress | L4 (building) |
| forgecal | Validates all computation instruments (§24 equivalent) | N/A — is the validator | L3 (auto) |
| forgeviz | Renders graph health, detection ladders, maturity (§9, §13) | 0 — rendering | L4 (tests) |
| forgesia | Bayesian posteriors on graph edges (Annex B) | Not extracted yet | L6 (unstructured) |
| forgesiop | Supply chain + yield from Cpk (§22) | 10 | L3 (auto) |
| forgedoc | Compliance artifacts from graph data (§17, §23) | 0 — rendering | L4 (tests) |

### Automated Pipeline

```bash
forgegov run          # lint → test → contract → calibrate → integration → certify
forgegov audit        # stubs → markers → untested exports → weak tests
```

### Investment Priority

Move forgesia from L6 to L3. It's the Bayesian belief engine — Annex B of OLR-001 depends on it. Currently embedded in SVEND monolith with no golden references. Extract → calibrate → automate.

---

## Surface 2: Product Implementation of OLR-001

### The Three Concerns — Implementation Status

#### Process Knowledge (GRAPH-001)

The graph is the product. Everything else is an instrument that writes to it or reads from it.

| Requirement | OLR-001 § | SVEND Implementation | Status | Verification |
|-------------|----------|---------------------|--------|-------------|
| Structured process relationships | §4.1 | `graph/models.py` — KnowledgeGraph, Entity, Relationship | Built | Check: graph stores directional cause→effect edges |
| Evidence provenance on edges | §4.2 | Evidence model with source_type, p_value, effect_size, confidence | Built | Check: every EdgeEvidence traces to analysis/investigation |
| Quantified confidence | §4.3 | Bayesian posteriors via forgesia/Synara | Built | Check: posteriors update from evidence, not just from assertion |
| Knowledge gap visibility | §4.4 | Gap report from graph metrics | Partial | Check: uncalibrated edges identifiable, gap ratio computable |
| Staleness detection | §4.5 | SPC shift detection, time-based thresholds | Partial | Check: stale edges flagged, staleness triggers fire on process change |
| Growth from problems | §4.6 | Investigation writeback to graph | Built | Check: concluded investigation creates new nodes/edges |
| Node classification tiers | §4.7 | Critical/major/minor from FMIS | Partial | Check: tier determines evidence minimum and staleness threshold |
| Unified views (FMIS, control plan, process plan) | §5 | FMIS view, control plan derivation | Partial | Check: edit one view, others update |

#### Learning System (LOOP-001)

| Requirement | OLR-001 § | SVEND Implementation | Status | Verification |
|-------------|----------|---------------------|--------|-------------|
| Signal detection — unified capture | §7.1 | `loop/models.py` — Signal with source taxonomy | Built | Check: NCR, SPC alarm, audit finding, customer complaint all enter as Signal |
| Investigation — structured methodology | §7.2 | Investigation engine (CANON-002), scoped subgraph | Built | Check: investigation scopes graph region, produces evidence |
| Standardization — encode as artifacts | §7.3 | Document service, controlled documents linked to FMIS rows | Partial | Check: investigation conclusions become controlled documents |
| Verification — process confirmation | §7.4.1 | Process confirmation model | Partial | Check: PC records update graph edges as evidence |
| Verification — forced failure testing | §7.4.2 | FFT model with detection edge calibration | Planned | Check: FFT results update detection mechanism evidence |
| Knowledge feedback — writeback | §7.5 | Investigation writeback to graph | Built | Check: new edges/nodes created from investigation |

#### Compliance

| Requirement | OLR-001 § | SVEND Implementation | Status | Verification |
|-------------|----------|---------------------|--------|-------------|
| ISO 9001 mapping | §23.1 | Auditor portal with clause-filtered views | Planned | Check: every ISO clause traceable to graph evidence |
| IATF 16949 mapping | §23.2 | — | Not started | — |
| AS9100D mapping | §23.3 | — | Not started | — |
| CAPA as generated report | §7.2 note | forgedoc InvestigationReport builder | Built | Check: CAPA view assembles from investigation data |
| Maturity level assessment | §14, §24 | CI Readiness Score (Harada instrument) | Built | Check: auditor can determine level from graph metrics |

### Detection Mechanism Hierarchy (§9)

OLR-001 defines an 8-level detection ladder. SVEND must implement the visualization and tracking.

| Detection Level | What SVEND Shows | Implementation | Status |
|----------------|-----------------|----------------|--------|
| L1-2 (source prevention, auto arrest) | Poka-yoke status on equipment nodes | Graph edge type | Planned |
| L3 (auto detect + segregate) | Vision system / automated inspection status | Graph edge with FFT evidence | Planned |
| L4 (auto alert + human) | SPC alarms, andon signals | SPC → Signal routing | Built |
| L5 (structured inspection) | Control plan items with schedule | Control plan view | Partial |
| L6-8 (unstructured/downstream/undetectable) | Gaps to invest in | Gap report | Partial |
| Distribution chart | % of critical chars at each level | forgeviz detection_ladder chart | Built |
| Investment tracking | Movement up the ladder over time | Trend on detection distribution | Planned |

### Knowledge Health Metrics (§13)

These are the dashboard metrics that leadership sees. They replace management review.

| Metric | OLR-001 § | Computation Source | SVEND Surface | Status |
|--------|----------|-------------------|---------------|--------|
| Calibration rate | §13.1 | Graph: calibrated edges / total edges | Dashboard + API | Partial |
| Staleness rate | §13.2 | Graph: stale edges / calibrated edges | Dashboard + API | Partial |
| Contradiction rate | §13.3 | Graph: edges with conflicting evidence / total | Dashboard + API | Planned |
| Signal resolution velocity | §13.4 | Loop: time from Signal to knowledge update | Dashboard + API | Partial |
| Knowledge gap ratio | §13.5 | Graph: assertion-only edges / total | Dashboard + API | Partial |
| Proactive/reactive ratio | §13.6 | Signals: internal detection vs customer report | Dashboard + API | Planned |
| Detection distribution | §13.7 | Detection ladder level counts on critical chars | forgeviz chart | Built |

### Supplier Integration (§22)

| Requirement | OLR-001 § | SVEND Implementation | Status |
|-------------|----------|---------------------|--------|
| Supplier evidence as knowledge input | §22.1 | CoA portal → graph edge evidence | Spec'd (object_271/supplier_accountability.md) |
| Supplier claims as signal source | §22.2 | SupplierClaim → Signal routing | Spec'd |
| Supplier response quality | §22.3 | Response portal with pattern analysis | Spec'd |
| Incoming material → node evidence | §22.4 | CoA data → SPC → graph | Spec'd |

### Pre-Production Knowledge Design (§6)

| Step | OLR-001 § | SVEND Implementation | Status |
|------|----------|---------------------|--------|
| QFD → graph structure | §6.1 | QFD view derives specification nodes | Planned |
| 3P → nodes and assertions | §6.2 | Process design → FMIS rows | Planned |
| Moonshining → evidence | §6.3 | Investigation during pre-production | Planned (Loop works, UI pathway needed) |
| Special process qualification | §6.4 | DOE → high-strength evidence | Built (forgedoe) |
| Configuration boundaries | §6.5 | Product variants → affected nodes | Planned |
| First article verification | §6.6 | Full-chain validation | Planned |
| Control plan from graph | §6.7 | Control plan view derived from FMIS | Partial |

---

## Maturity Assessment — SVEND Product

**Current: between Level 1 and Level 2**

| Criterion | Assessment |
|-----------|-----------|
| Graph stores structured process knowledge | Yes — GRAPH-001 implemented |
| Evidence provenance on edges | Yes — Evidence model with source tracing |
| Learning system operational | Yes — Loop handles signals → investigation → writeback |
| Knowledge health computable | Partial — some metrics built, not all |
| Unified views (FMIS = control plan = process plan) | Partial — FMIS exists, control plan derivation incomplete |
| Detection hierarchy tracked | Partial — forgeviz chart built, tracking not wired |
| Supplier integration | Spec'd, not built |
| Pre-production knowledge design (3P/QFD) | Planned |
| Maturity self-assessment | CI Readiness Score exists, not mapped to OLR-001 levels |

**To reach Level 2 (product can certify customers at Level 2):**
- Complete knowledge health metrics dashboard
- Wire detection hierarchy tracking
- Control plan derivation from graph
- Process confirmation as evidence source

**To reach Level 3:**
- Unified views (edit FMIS → control plan updates)
- Supplier integration (claims as signals, CoA as evidence)
- Forced failure testing model
- Automated staleness triggers from process changes

---

## Quality Manager Responsibilities

### Forge side (computation correctness)
- `forgegov run` — pipeline must be green
- `forgegov audit` — surface code quality issues
- Review packages on "done" claims — challenge assertions
- Catch cross-session conflicts

### SVEND side (product correctness)
- Verify that forge computation reaches the graph correctly (integration layer)
- Verify that the Loop works end-to-end (signal → investigation → writeback → graph update)
- Verify that OLR-001 features work as specified (detection ladder, health metrics, unified views)
- Track which OLR-001 sections are implemented vs planned vs not started
- Flag when a forge package change breaks a product capability

### The bridge
- `run_compliance --check forge_ecosystem` — confirms computation layer is healthy
- When forge packages change API, verify SVEND integration layer still calls correctly
- When SVEND adds OLR-001 features, verify they use forge packages (not reimplementing computation)
