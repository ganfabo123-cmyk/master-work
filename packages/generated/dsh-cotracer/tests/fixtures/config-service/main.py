"""
Entry point: parse CLI overrides, resolve config, and report the effective
values. The CLI override for max_retries never takes effect (see
config_service.py).
"""

import sys

from config_service import resolve


def parse_cli(argv) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for arg in argv:
        if arg.startswith("--") and "=" in arg:
            key, _, value = arg[2:].partition("=")
            overrides[key] = value
    return overrides


def main(argv) -> None:
    overrides = parse_cli(argv)
    config = resolve(overrides)
    print("host       :", config.get("host"))
    print("port       :", config.get("port"))
    print("log_level  :", config.get("log_level"))
    print("max_retries:", config.get("max_retries"))


if __name__ == "__main__":
    main(sys.argv[1:])