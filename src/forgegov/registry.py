"""Package discovery and version scanning for the Forge ecosystem."""

from __future__ import annotations

import importlib
import importlib.metadata
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

KNOWN_PACKAGES = [
    "forgecal",
    "forgecausal",
    "forgedoc",
    "forgedoe",
    "forgeml",
    "forgepbs",
    "forgespc",
    "forgestat",
    "forgebay",
    "forgesia",
    "forgesiop",
    "forgeviz",
]


@dataclass
class PackageInfo:
    """Discovered forge package metadata."""

    name: str
    version: str
    location: Path
    has_init: bool
    has_version: bool
    has_py_typed: bool
    has_calibration: bool
    has_all_export: bool
    modules: list[str] = field(default_factory=list)


@dataclass
class ScanResult:
    """Result of scanning the Forge ecosystem."""

    packages: list[PackageInfo] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def installed_names(self) -> list[str]:
        return [p.name for p in self.packages]

    @property
    def versions(self) -> dict[str, str]:
        return {p.name: p.version for p in self.packages}

    def missing_calibration(self) -> list[str]:
        return [p.name for p in self.packages if not p.has_calibration]

    def get(self, name: str) -> PackageInfo | None:
        for p in self.packages:
            if p.name == name:
                return p
        return None


def _find_package_location(name: str) -> Path | None:
    """Find the source directory of an installed package."""
    try:
        mod = importlib.import_module(name)
        if hasattr(mod, "__file__") and mod.__file__:
            return Path(mod.__file__).parent
        if hasattr(mod, "__path__"):
            return Path(mod.__path__[0])
    except Exception:
        pass
    return None


def _discover_modules(pkg_dir: Path) -> list[str]:
    """List Python modules in a package directory (non-recursive top-level)."""
    modules = []
    for item in sorted(pkg_dir.iterdir()):
        if item.is_file() and item.suffix == ".py" and item.name != "__init__.py":
            modules.append(item.stem)
        elif item.is_dir() and (item / "__init__.py").exists():
            modules.append(item.name)
    return modules


def scan(packages: list[str] | None = None) -> ScanResult:
    """Scan for installed forge packages and collect metadata.

    Args:
        packages: Specific package names to scan. Defaults to KNOWN_PACKAGES.

    Returns:
        ScanResult with discovered packages and missing package names.
    """
    scan_list = packages or KNOWN_PACKAGES
    result = ScanResult()

    for name in scan_list:
        try:
            mod = importlib.import_module(name)
        except ImportError:
            result.missing.append(name)
            continue

        location = _find_package_location(name)
        if location is None:
            result.missing.append(name)
            continue

        version = getattr(mod, "__version__", "unknown")
        has_version = hasattr(mod, "__version__")
        has_all = hasattr(mod, "__all__")
        has_py_typed = (location / "py.typed").exists()

        has_calibration = False
        try:
            importlib.import_module(f"{name}.calibration")
            has_calibration = True
        except ImportError:
            pass

        modules = _discover_modules(location) if location.is_dir() else []

        info = PackageInfo(
            name=name,
            version=version,
            location=location,
            has_init=True,
            has_version=has_version,
            has_py_typed=has_py_typed,
            has_calibration=has_calibration,
            has_all_export=has_all,
            modules=modules,
        )
        result.packages.append(info)
        logger.debug("Discovered %s %s at %s", name, version, location)

    return result
