# ForgeGov

Ecosystem governance for Forge packages. Discovers installed packages, enforces structural contracts (no Django/subprocess/network imports), runs CI/CD pipelines, and performs automated quality audits.

## Install

```bash
pip install forgegov
```

## Quick Start

```python
from forgegov import scan, check, run

# Discover forge packages
packages = scan()

# Check contracts
violations = check(packages)

# Run full pipeline (lint -> test -> calibrate -> integration -> certify)
result = run(packages)
print(result.passed, result.failed)
```

## CLI

```bash
forgegov run                  # Full pipeline
forgegov run --stage test     # Single stage
forgegov check forgespc       # Contract check on one package
forgegov audit                # Quality audit
forgegov status               # Quick health report
forgegov compat               # Compatibility matrix
forgegov report               # Generate report (requires forgedoc)
```

## Modules

| Module | Purpose |
|---|---|
| `registry` | Package discovery, `PackageInfo`, `ScanResult` |
| `contracts` | Import guards (no Django/subprocess/network), structural rules |
| `pipeline` | Multi-stage CI/CD: lint, test, calibrate, integration, certify |
| `audits` | Stubs, markers, untested exports, test quality, regression |
| `cli` | Click-based CLI entry point |

## Dependencies

- None (stdlib only)
- Optional: `forgecal` (calibrate stage), `forgedoc` (certify/report stage)

## Tests

```bash
python3 -m pytest tests/ -q
```

82 tests covering registry, contracts, pipeline, audits, and CLI.

## Related Docs

- `QUALITY_AGENT.md` -- quality agent design
- `CONTROL_PLAN.md` -- control plan specification

## License

MIT
