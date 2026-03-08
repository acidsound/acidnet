"""Stable public boundary for the headless simulator stack."""

__all__ = [
    "DemoSetup",
    "EventLogFile",
    "SimulatorService",
    "Simulation",
    "SQLiteWorldStore",
    "build_demo_setup",
]


def __getattr__(name: str):
    if name == "Simulation":
        from acidnet.simulator.runtime import Simulation

        return Simulation
    if name in {"EventLogFile", "SQLiteWorldStore"}:
        from acidnet.simulator.storage import EventLogFile, SQLiteWorldStore

        return {"EventLogFile": EventLogFile, "SQLiteWorldStore": SQLiteWorldStore}[name]
    if name == "SimulatorService":
        from acidnet.simulator.service import SimulatorService

        return SimulatorService
    if name in {"DemoSetup", "build_demo_setup"}:
        from acidnet.simulator.world import DemoSetup, build_demo_setup

        return {"DemoSetup": DemoSetup, "build_demo_setup": build_demo_setup}[name]
    raise AttributeError(f"module 'acidnet.simulator' has no attribute {name!r}")
