from __future__ import annotations

from .apple_container import AppleContainerEngine
from .base import Engine, EngineError
from .podman_machine import PodmanMachineEngine

# Preference order: Apple `container` is primary (ADR-0002); `podman machine` is
# the drop-in fallback.
_ENGINE_CLASSES = (AppleContainerEngine, PodmanMachineEngine)


def detect_engine() -> Engine:
    for engine_cls in _ENGINE_CLASSES:
        engine = engine_cls()
        if engine.is_available():
            return engine
    raise EngineError("No supported outer engine found (need `container` or `podman`)")


__all__ = ["Engine", "EngineError", "detect_engine", "AppleContainerEngine", "PodmanMachineEngine"]
