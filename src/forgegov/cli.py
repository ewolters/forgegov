"""Command-line interface for forgegov."""

from __future__ import annotations

import argparse
import sys

from . import registry, contracts, pipeline


def cmd_run(args: argparse.Namespace) -> int:
    """Run the governance pipeline."""
    stages = [args.stage] if args.stage else None
    packages = [args.package] if args.package else None

    result = pipeline.run(packages=packages, stages=stages)
    print(result.summary())

    # Write machine-readable report for SVEND compliance integration
    report_path = result.write_report()
    print(f"\nReport: {report_path}")

    return 0 if result.passed else 1


def cmd_check(args: argparse.Namespace) -> int:
    """Check contracts for a specific package or all packages."""
    packages = [args.package] if args.package else None
    scan_result = registry.scan(packages)

    if not scan_result.packages:
        print(f"No packages found: {args.package or 'none installed'}")
        return 1

    contract_result = contracts.check(scan_result)

    if contract_result.passed and not contract_result.warnings:
        print(f"All contracts passed ({len(scan_result.packages)} packages)")
        return 0

    for v in contract_result.violations:
        severity = "ERROR" if v.severity == "error" else "WARN "
        print(f"  [{severity}] {v}")

    errors = len(contract_result.errors)
    warnings = len(contract_result.warnings)
    print(f"\n{errors} errors, {warnings} warnings")
    return 0 if contract_result.passed else 1


def cmd_status(args: argparse.Namespace) -> int:
    """Show ecosystem health status."""
    scan_result = registry.scan()

    print(f"Forge Ecosystem Status")
    print(f"{'=' * 60}")

    if not scan_result.packages:
        print("No forge packages installed.")
        return 0

    # Package table
    name_w = max(len(p.name) for p in scan_result.packages)
    print(f"\n{'Package':<{name_w}}  {'Version':<10}  {'Typed':<6}  {'Cal':<6}  {'__all__':<7}")
    print(f"{'-' * name_w}  {'-' * 10}  {'-' * 6}  {'-' * 6}  {'-' * 7}")
    for p in scan_result.packages:
        typed = "yes" if p.has_py_typed else "no"
        cal = "yes" if p.has_calibration else "no"
        all_exp = "yes" if p.has_all_export else "no"
        print(f"{p.name:<{name_w}}  {p.version:<10}  {typed:<6}  {cal:<6}  {all_exp:<7}")

    if scan_result.missing:
        print(f"\nNot installed: {', '.join(scan_result.missing)}")

    # Quick contract check
    contract_result = contracts.check(scan_result)
    print(f"\nContracts: {len(contract_result.errors)} errors, {len(contract_result.warnings)} warnings")

    return 0


def cmd_compat(args: argparse.Namespace) -> int:
    """Show version compatibility matrix."""
    scan_result = registry.scan()

    if not scan_result.packages:
        print("No forge packages installed.")
        return 0

    print("Forge Compatibility Matrix")
    print(f"{'=' * 40}")
    for p in scan_result.packages:
        print(f"  {p.name}: {p.version}")

    # Cross-import check
    print(f"\nCross-package imports:")
    import importlib
    import ast

    for pkg in scan_result.packages:
        deps = set()
        for _, py_file in contracts._walk_python_files(pkg.location):
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source)
            except Exception:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for other in scan_result.packages:
                            if other.name != pkg.name and (
                                alias.name == other.name
                                or alias.name.startswith(f"{other.name}.")
                            ):
                                deps.add(other.name)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    for other in scan_result.packages:
                        if other.name != pkg.name and (
                            node.module == other.name
                            or node.module.startswith(f"{other.name}.")
                        ):
                            deps.add(other.name)
        if deps:
            print(f"  {pkg.name} -> {', '.join(sorted(deps))}")
        else:
            print(f"  {pkg.name} -> (none)")

    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Read the latest pipeline report (JSON to stdout)."""
    import json
    from pathlib import Path

    report_path = Path.home() / ".forge" / "reports" / "forgegov_latest.json"
    if not report_path.exists():
        print("No report found. Run 'forgegov run' first.")
        return 1

    report = json.loads(report_path.read_text())

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        passed = report.get("passed", False)
        ts = report.get("timestamp", "unknown")
        print(f"Last run: {ts}")
        print(f"Status: {'PASSED' if passed else 'FAILED'}")
        print(f"Packages: {len(report.get('packages', {}))}")
        print(f"Contracts: {report.get('contract_errors', '?')} errors, "
              f"{report.get('contract_warnings', '?')} warnings")
        for stage in report.get("stages", []):
            icon = "PASS" if stage["passed"] else "FAIL"
            print(f"  [{icon}] {stage['stage']} — {stage['detail']}")

    return 0 if report.get("passed", False) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="forgegov",
        description="Governance and CI/CD for the Forge ecosystem",
    )
    sub = parser.add_subparsers(dest="command")

    # forgegov run
    p_run = sub.add_parser("run", help="Run the governance pipeline")
    p_run.add_argument("--stage", choices=pipeline.STAGES, help="Run only this stage")
    p_run.add_argument("--package", help="Target a specific package")

    # forgegov check
    p_check = sub.add_parser("check", help="Check contracts")
    p_check.add_argument("package", nargs="?", help="Package to check (default: all)")

    # forgegov status
    sub.add_parser("status", help="Show ecosystem health")

    # forgegov compat
    sub.add_parser("compat", help="Show compatibility matrix")

    # forgegov report
    p_report = sub.add_parser("report", help="Read latest pipeline report")
    p_report.add_argument("--json", action="store_true", help="Output raw JSON (for SVEND)")

    args = parser.parse_args(argv)

    if args.command == "run":
        return cmd_run(args)
    elif args.command == "check":
        return cmd_check(args)
    elif args.command == "status":
        return cmd_status(args)
    elif args.command == "compat":
        return cmd_compat(args)
    elif args.command == "report":
        return cmd_report(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
