from __future__ import annotations
import json
from pathlib import Path
from .schema import ScenarioSpec

_PRESETS_DIR = Path(__file__).parent / "presets"


def load_scenario(path: str | Path) -> ScenarioSpec:
    data = json.loads(Path(path).read_text())
    return ScenarioSpec.model_validate(data)


def load_preset(name: str) -> ScenarioSpec:
    path = _PRESETS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Preset not found: {name}")
    return load_scenario(path)


def list_presets() -> list[str]:
    if not _PRESETS_DIR.exists():
        return []
    return sorted(p.stem for p in _PRESETS_DIR.glob("*.json"))
