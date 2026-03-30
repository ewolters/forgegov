# ForgeGov Quality Control Plan

**Date:** 2026-03-29
**Standard:** OLR-001 (Organizational Learning Rate) — applied to the Forge ecosystem itself
**Scope:** The forge computation packages + forgegov + SVEND compliance bridge

---

## Context

Object 271 establishes that SVEND is a process knowledge system built on three concerns: Process Knowledge (the graph), Learning System (the Loop), and Compliance. The forge ecosystem IS the computation layer that produces calibrated evidence for the graph.

This control plan applies OLR-001's own principles to the forge ecosystem. We eat our own cooking — every forge package is a measurement instrument that requires calibration, verification, and knowledge maintenance.

---

## Knowledge Structure

The forge ecosystem's "process" is: **code goes in, correct computation comes out**. The knowledge we maintain is: which computations are correct, proven, and current.

### Nodes (What We Know About)

| Node | Type | Classification |
|------|------|---------------|
| Each exported function in each forge package | Process parameter | Per function — critical if used in calibration, major otherwise |
| Each golden reference case in forgecal | Specification | Critical — these ARE the truth |
| Each contract rule in forgegov | Control method | Major |
| Each test in each package | Detection mechanism | Major |
| The SVEND bridge check | Integration point | Critical |

### Edges (What We Claim)

| Edge | Evidence Source | Current State |
|------|---------------|---------------|
| "forgespc.xbar_r_chart produces correct control limits" | Golden case CAL-SPC-* | Calibrated (14/14) |
| "forgedoe.full_factorial produces correct design matrices" | Golden case CAL-DOE-* | Calibrated (6/6) |
| "forgesiop.economic_order_quantity matches Wilson formula" | Golden case CAL-SIOP-* | Calibrated (10/10) |
| "No forge package imports Django" | AST scan (forgegov contracts) | Verified continuously |
| "No forge package executes commands" | AST scan (forgegov contracts) | Verified continuously |
| "All forge packages pass their test suites" | pytest (forgegov pipeline) | Verified continuously |
| "All forge packages are lint clean" | ruff (forgegov pipeline) | Verified continuously |
| "SVEND reads forgegov report correctly" | Bridge check | Verified continuously |

---

## Control Plan — Detection Mechanisms

| What | Detection Level | Method | Frequency | Reaction |
|------|----------------|--------|-----------|----------|
| **Statistical correctness** | L3 (auto detect + segregate) | forgecal golden references via `forgegov run --stage calibrate` | Every pipeline run | Failing case blocks pipeline, report shows FAIL |
| **Framework leakage** | L1 (source prevention) | AST scan bans Django/Flask/subprocess/etc. — cannot import | Every pipeline run | Contract violation = error |
| **Command execution** | L1 (source prevention) | AST scan bans subprocess, os.system/exec | Every pipeline run | Contract violation = error |
| **Network I/O** | L1 (source prevention) | AST scan bans requests/httpx/boto3 | Every pipeline run | Contract violation = error |
| **Unauthorized file I/O** | L3 (auto detect) | AST scan flags open()/Path.read/write outside designated modules | Every pipeline run | Contract violation = error |
| **Test regression** | L4 (auto alert + human) | pytest across all packages | Every pipeline run | Failure blocks pipeline |
| **Lint violations** | L4 (auto alert + human) | ruff across all packages | Every pipeline run | Failure blocks pipeline |
| **Stubs in production code** | L5 (structured inspection) | `forgegov audit --audit stubs` | On review | Finding reported, human investigates |
| **TODO/FIXME markers** | L5 (structured inspection) | `forgegov audit --audit markers` | On review | Finding reported, human prioritizes |
| **Untested exports** | L5 (structured inspection) | `forgegov audit --audit untested_exports` | On review | Finding reported, human adds tests |
| **Weak tests** | L5 (structured inspection) | `forgegov audit --audit test_quality` | On review | Finding reported, human strengthens |
| **Wrong math** | L6 (unstructured observation) | Quality manager reads code | On "done" claims | Fix or flag to developer |
| **Incomplete implementations** | L6 (unstructured observation) | Quality manager reads code | On "done" claims | Fix or flag to developer |
| **Cross-session conflicts** | L4 (auto + human) | Regression audit + pipeline diff | After parallel sessions | Quality manager investigates |

### Detection Level Summary

| Level | Count | Characteristics |
|-------|-------|----------------|
| L1 (source prevention) | 3 | Framework leaks, command exec, network — **cannot happen** |
| L3 (auto detect + segregate) | 2 | Calibration failures, unauthorized I/O |
| L4 (auto alert + human) | 3 | Test regression, lint, cross-session |
| L5 (structured inspection) | 4 | Stubs, markers, untested exports, weak tests |
| L6 (unstructured observation) | 2 | Wrong math, incomplete implementations |

**Investment direction:** Move L6 items up. Wrong math detection → L3 via more golden reference cases in forgecal. Incomplete implementation detection → L5 via more audit checks.

---

## Calibration Schedule

| Instrument | Calibration Method | Frequency | Owner |
|-----------|-------------------|-----------|-------|
| forgecal golden cases | Self-referential — golden cases ARE the calibration | Verified every `forgegov run` | forgecal |
| forgegov contract scanner | Test suite with synthetic violations (test_contracts.py) | Every commit | forgegov tests |
| forgegov audit checks | Test suite with synthetic code (test_audits.py) | Every commit | forgegov tests |
| SVEND bridge check | `run_compliance --check forge_ecosystem` | Daily (SVEND compliance schedule) | SVEND |
| Quality manager judgment | Precedent log (Known Issues in QUALITY_AGENT.md) | After each review session | Quality manager |

---

## Staleness Triggers

| Event | What Goes Stale | Action |
|-------|----------------|--------|
| New forge package extracted from SVEND | All: need calibration adapter, contract check, tests | Add `calibration.py`, verify contracts, add to registry |
| Forge package API change (new/removed exports) | Calibration cases may reference old API | Re-run calibration, update golden cases |
| forgecal schema change | All adapters | Verify all `get_calibration_adapter()` still work |
| S1 adds new modules to a package | Lint, `__all__`, test coverage | Quality manager runs `forgegov run` + `forgegov audit` |
| SVEND compliance check changes | Bridge check assumptions | Verify `check_forge_ecosystem()` still reads report correctly |
| New banned import category added to contracts | All packages need re-scan | `forgegov run --stage contract` |

---

## Maturity Assessment — Forge Ecosystem

**Current level: 2 (Learning)**

Evidence is accumulating. Calibration cases exist and pass. The learning system (forgegov) is actively discovering and fixing issues. Knowledge health is improving.

| Criterion | Status |
|-----------|--------|
| Process knowledge structured | Yes — packages, exports, golden cases documented |
| Evidence accumulating | Yes — 30 golden cases across 3 packages, passing |
| Investigations producing knowledge | Yes — found gage.py crash, reorder.py math error, monte carlo incompleteness, box plot quantile error |
| Knowledge health improving | Yes — 0 contract errors, lint clean, all tests pass |
| Staleness managed | Partial — no automated staleness triggers yet |
| Contradictions resolved | Yes — when findings arise, they're fixed same session |
| Predictive capability | No — not yet predicting "this change will break X" |

**To reach Level 3 (Sustaining):** Automated staleness triggers, sustained health over multiple sessions, forgecal drift detection in production use.

**To reach Level 4 (Predictive):** Regression prediction from code changes (would require static analysis that understands computation semantics, not just structure).

---

## Improvement Targets

### Near-term (move L6 → L5/L3)

1. **More golden reference cases** — every exported function in forgespc/forgedoe/forgesiop should have at least one golden case. Currently: 30 cases across 3 packages. Target: 100+.
2. **Return shape validation** — audit that checks similar functions return consistent dict structures (new forgegov audit).
3. **Import-time vs call-time safety** — audit that actually calls exported functions with minimal args to catch missing imports (the gage.py pattern).

### Medium-term

4. **Automated staleness triggers** — when a package's `__init__.py` changes (new exports), flag that calibration cases may be stale.
5. **Drift detection in CI** — `forgecal.drift` runs on every `forgegov run`, compares against history.
6. **Cross-package type checking** — ensure forge packages that depend on each other (forgespc → forgecal) have compatible interfaces.

### Long-term

7. **Forge ecosystem as OLR-001 reference implementation** — the control plan you're reading IS the process knowledge structure for the forge build process, applied using OLR-001 principles. If the standard works for governing software computation packages, it works for governing any process.
