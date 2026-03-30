# ForgeGov -- Ecosystem Governance

## What It Is

CI/CD and contract enforcement for the Forge package ecosystem. Ensures every forge package stays pure (no web frameworks, no subprocess, no network calls), passes tests, calibrates against golden references, and integrates cleanly with the rest of the ecosystem.

## Architecture

```
forgegov/
  registry.py    -- Discovers forge* packages via importlib/pkg_resources
  contracts.py   -- AST-walks source files checking banned imports/calls
  pipeline.py    -- Orchestrates stages: lint -> test -> calibrate -> integration -> certify
  audits.py      -- Quality checks: stubs, markers, untested exports, test quality
  cli.py         -- Click CLI: run, check, audit, status, compat, report
```

## Running Tests

```bash
cd ~/forgegov
python3 -m pytest tests/ -q          # 82 tests
python3 -m ruff check .              # lint
```

## Key Design Decisions

- **Zero dependencies** -- forgegov imports nothing outside stdlib. forgecal/forgedoc are optional for calibrate/certify stages.
- **AST-based contract checking** -- parses Python source with `ast` module to detect banned imports. No execution needed.
- **Pipeline stages are composable** -- can run full pipeline or single stage via `--stage`. Each stage returns a `StageResult`.
- **Audit is separate from pipeline** -- audits inspect code quality (stub detection, marker coverage) independently of test execution.
- **Registry uses importlib** -- discovers all `forge*` packages installed in the environment. No hardcoded package list.
- **CLI via Click** -- `forgegov` entry point defined in pyproject.toml `[project.scripts]`.
