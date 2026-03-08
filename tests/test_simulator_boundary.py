from __future__ import annotations

import ast
from pathlib import Path
import tomllib

import acidnet.engine as engine
import acidnet.engine.simulation as engine_simulation
import acidnet.models.core as models_core
import acidnet.storage.event_log_file as storage_event_log_file
import acidnet.storage.sqlite_store as storage_sqlite_store
import acidnet.world.demo as world_demo
from acidnet.models import PlayerState as ShimPlayerState
from acidnet.simulator import DemoSetup, EventLogFile, SQLiteWorldStore, Simulation, SimulatorService, build_demo_setup
from acidnet.simulator.models import PlayerState
from acidnet.simulator.runtime import CONSUMPTION_VALUE, FOOD_ITEMS, Simulation as RuntimeSimulation, TradeOption, TurnEvent, TurnResult
from acidnet.simulator.service import SimulatorService as BoundarySimulatorService
from acidnet.simulator.storage import (
    EventLogFile as BoundaryEventLogFile,
    SQLiteWorldStore as BoundarySQLiteWorldStore,
    SYSTEM_PROMPT_PRESET_ID,
    SYSTEM_PROMPT_SETTING_KEY,
)
from acidnet.simulator.world import DemoSetup as BoundaryDemoSetup, build_demo_setup as boundary_build_demo_setup
from acidnet.storage import EventLogFile as ShimEventLogFile, SQLiteWorldStore as ShimSQLiteWorldStore
from acidnet.world import DemoSetup as ShimDemoSetup, build_demo_setup as shim_build_demo_setup

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_MODULES = {
    "acidnet.engine",
    "acidnet.engine.simulation",
    "acidnet.models",
    "acidnet.models.core",
    "acidnet.world",
    "acidnet.world.demo",
    "acidnet.storage",
    "acidnet.storage.sqlite_store",
    "acidnet.storage.event_log_file",
}
FORBIDDEN_DEEP_SIMULATOR_MODULES = {
    "acidnet.simulator.core",
    "acidnet.simulator.demo",
    "acidnet.simulator.event_log_file",
    "acidnet.simulator.simulation",
    "acidnet.simulator.sqlite_store",
}
ALLOWED_LEGACY_IMPORT_FILES = {
    Path("src/acidnet/engine/__init__.py"),
    Path("src/acidnet/engine/simulation.py"),
    Path("src/acidnet/models/__init__.py"),
    Path("src/acidnet/models/core.py"),
    Path("src/acidnet/world/__init__.py"),
    Path("src/acidnet/world/demo.py"),
    Path("src/acidnet/storage/__init__.py"),
    Path("src/acidnet/storage/sqlite_store.py"),
    Path("src/acidnet/storage/event_log_file.py"),
    Path("tests/test_simulator_boundary.py"),
}
ALLOWED_DEEP_SIMULATOR_IMPORT_FILES = {
    Path("src/acidnet/simulator/models.py"),
    Path("src/acidnet/simulator/runtime.py"),
    Path("src/acidnet/simulator/service.py"),
    Path("src/acidnet/simulator/storage.py"),
    Path("src/acidnet/simulator/world.py"),
}
SHIM_IMPORT_ALLOWLIST = {
    Path("src/acidnet/engine/__init__.py"): {"acidnet.simulator.runtime"},
    Path("src/acidnet/engine/simulation.py"): {"acidnet.simulator.runtime"},
    Path("src/acidnet/models/__init__.py"): {"acidnet.simulator.models"},
    Path("src/acidnet/models/core.py"): {"acidnet.simulator.models"},
    Path("src/acidnet/world/__init__.py"): {"acidnet.simulator.world"},
    Path("src/acidnet/world/demo.py"): {"acidnet.simulator.world"},
    Path("src/acidnet/storage/__init__.py"): {"acidnet.simulator.storage", "acidnet.storage.vector_store"},
    Path("src/acidnet/storage/sqlite_store.py"): {"acidnet.simulator.storage"},
    Path("src/acidnet/storage/event_log_file.py"): {"acidnet.simulator.storage"},
}
FORBIDDEN_SIMULATOR_BACK_IMPORT_PREFIXES = (
    "acidnet.cli",
    "acidnet.engine",
    "acidnet.eval",
    "acidnet.frontend",
    "acidnet.models",
    "acidnet.storage",
    "acidnet.training",
    "acidnet.world",
)


def _iter_python_files() -> list[Path]:
    repo_files = list((ROOT / "src").rglob("*.py"))
    repo_files.extend((ROOT / "tests").rglob("*.py"))
    repo_files.extend(path for path in ROOT.glob("*.py") if path.is_file())
    return sorted(repo_files)


def _iter_imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.append(node.module)
        elif isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
    return modules


def test_public_simulator_boundary_matches_compatibility_shims() -> None:
    assert Simulation is RuntimeSimulation
    assert engine.Simulation is RuntimeSimulation
    assert engine_simulation.Simulation is RuntimeSimulation
    assert engine_simulation.TurnResult is TurnResult
    assert engine_simulation.TradeOption is TradeOption
    assert engine_simulation.TurnEvent is TurnEvent
    assert engine_simulation.FOOD_ITEMS is FOOD_ITEMS
    assert engine_simulation.CONSUMPTION_VALUE is CONSUMPTION_VALUE

    assert ShimPlayerState is PlayerState
    assert models_core.PlayerState is PlayerState

    assert DemoSetup is BoundaryDemoSetup
    assert ShimDemoSetup is BoundaryDemoSetup
    assert world_demo.DemoSetup is BoundaryDemoSetup
    assert build_demo_setup is boundary_build_demo_setup
    assert shim_build_demo_setup is boundary_build_demo_setup
    assert world_demo.build_demo_setup is boundary_build_demo_setup

    assert EventLogFile is BoundaryEventLogFile
    assert ShimEventLogFile is BoundaryEventLogFile
    assert storage_event_log_file.EventLogFile is BoundaryEventLogFile
    assert SQLiteWorldStore is BoundarySQLiteWorldStore
    assert ShimSQLiteWorldStore is BoundarySQLiteWorldStore
    assert storage_sqlite_store.SQLiteWorldStore is BoundarySQLiteWorldStore
    assert storage_sqlite_store.SYSTEM_PROMPT_SETTING_KEY == SYSTEM_PROMPT_SETTING_KEY
    assert storage_sqlite_store.SYSTEM_PROMPT_PRESET_ID == SYSTEM_PROMPT_PRESET_ID
    assert SimulatorService is BoundarySimulatorService


def test_repo_avoids_legacy_split_imports_outside_shims() -> None:
    offenders: dict[str, list[str]] = {}
    for path in _iter_python_files():
        relative_path = path.relative_to(ROOT)
        if relative_path in ALLOWED_LEGACY_IMPORT_FILES:
            continue
        forbidden = sorted(module for module in _iter_imported_modules(path) if module in FORBIDDEN_MODULES)
        if forbidden:
            offenders[str(relative_path)] = forbidden

    assert not offenders


def test_compatibility_shims_only_use_public_simulator_subsurfaces() -> None:
    offenders: dict[str, list[str]] = {}
    for relative_path, allowed_imports in SHIM_IMPORT_ALLOWLIST.items():
        modules = _iter_imported_modules(ROOT / relative_path)
        simulator_imports = sorted(
            module
            for module in modules
            if module.startswith("acidnet.simulator") and module not in allowed_imports
        )
        if simulator_imports:
            offenders[str(relative_path)] = simulator_imports

    assert not offenders


def test_repo_avoids_deep_simulator_imports_outside_public_subsurfaces() -> None:
    offenders: dict[str, list[str]] = {}
    for path in _iter_python_files():
        relative_path = path.relative_to(ROOT)
        if relative_path in ALLOWED_DEEP_SIMULATOR_IMPORT_FILES:
            continue
        forbidden = sorted(module for module in _iter_imported_modules(path) if module in FORBIDDEN_DEEP_SIMULATOR_MODULES)
        if forbidden:
            offenders[str(relative_path)] = forbidden

    assert not offenders


def test_simulator_package_has_no_back_imports_to_outer_layers() -> None:
    offenders: dict[str, list[str]] = {}
    for path in sorted((ROOT / "src" / "acidnet" / "simulator").glob("*.py")):
        relative_path = path.relative_to(ROOT)
        forbidden = sorted(
            module
            for module in _iter_imported_modules(path)
            if module.startswith(FORBIDDEN_SIMULATOR_BACK_IMPORT_PREFIXES)
        )
        if forbidden:
            offenders[str(relative_path)] = forbidden

    assert not offenders


def test_runtime_entrypoints_target_split_safe_modules() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = pyproject["project"]["scripts"]
    assert scripts["acidnet"] == "acidnet.cli:main"
    assert scripts["acidnet-web"] == "acidnet.frontend.web_app:main"
    assert "acidnet-gui" not in scripts
    assert not (ROOT / "run_acidnet_gui.py").exists()
    assert not (ROOT / "run_dev_world.ps1").exists()

    run_acidnet_imports = _iter_imported_modules(ROOT / "run_acidnet.py")
    run_acidnet_web_imports = _iter_imported_modules(ROOT / "run_acidnet_web.py")
    assert "acidnet.cli" in run_acidnet_imports
    assert "acidnet.frontend.web_app" in run_acidnet_web_imports
