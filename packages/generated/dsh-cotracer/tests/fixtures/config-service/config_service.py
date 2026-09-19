"""
Configuration service: layered config resolution for the application.

Layers, lowest to highest priority:
1. defaults (built into the schema)
2. config file (config.json)
3. environment variables (CONFIG_SERVICE_*)
4. CLI overrides (--key=value)
"""

import json
import os
import re
from pathlib import Path

ENV_PREFIX = "CONFIG_SERVICE_"

DEFAULTS = {
    "host": "0.0.0.0",
    "port": 8080,
    "log_level": "info",
    "max_retries": 3,
}


def normalize(key: str) -> str:
    """Normalize a config key: lowercase, dashes become underscores."""
    return re.sub(r"-", "_", key).lower()


def _load_file(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _load_env() -> dict:
    values: dict[str, str] = {}
    for key, value in os.environ.items():
        if key.startswith(ENV_PREFIX):
            values[normalize(key[len(ENV_PREFIX):])] = value
    return values


def _parse_value(raw: str) -> int | float | bool | str:
    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    try:
        return int(raw)
    except ValueError:
        try:
            return float(raw)
        except ValueError:
            return raw


class ConfigService:
    """Resolve configuration from the layered sources."""

    def __init__(self, config_file: Path | None = None, cli_overrides: dict[str, str] | None = None):
        self._schema_keys = set(normalize(key) for key in DEFAULTS)
        layers = [DEFAULTS, _load_file(config_file), _load_env()]
        self._values: dict[str, object] = {}
        for layer in layers:
            for key, value in layer.items():
                normalized = normalize(key)
                if normalized not in self._schema_keys:
                    continue
                if isinstance(value, str):
                    value = _parse_value(value)
                self._values[normalized] = value
        # CLI overrides: highest priority; parse strings to typed values.
        for key, value in (cli_overrides or {}).items():
            normalized = normalize(key)
            if normalized in self._schema_keys:
                # BUG: stores the RAW key instead of the normalized key, so
                # lookups through normalize() (get/env/config) never see the
                # CLI value and silently fall back to the default.
                self._values[key] = _parse_value(value)

    def get(self, key: str):
        normalized = normalize(key)
        return self._values.get(normalized, DEFAULTS.get(normalized))


def resolve(overrides: dict[str, str] | None = None) -> ConfigService:
    return ConfigService(config_file=Path(__file__).parent / "config.json", cli_overrides=overrides)