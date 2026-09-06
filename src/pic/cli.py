from __future__ import annotations

import argparse
import sys

from .engines import EngineError, detect_engine

DEFAULT_WORKSPACE = "global"


def machine_name(workspace: str) -> str:
    return f"pic-{workspace}"


def cmd_launch(args: argparse.Namespace) -> int:
    engine = detect_engine()
    name = machine_name(args.workspace)
    print(f"Launching machine '{name}' via engine '{engine.name}'...")
    engine.create(name)
    print(f"Machine '{name}' is up.")
    return 0


def cmd_teardown(args: argparse.Namespace) -> int:
    engine = detect_engine()
    name = machine_name(args.workspace)
    print(f"Tearing down machine '{name}' via engine '{engine.name}'...")
    engine.destroy(name)
    print(f"Machine '{name}' torn down.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pic")
    subparsers = parser.add_subparsers(dest="command", required=True)

    launch = subparsers.add_parser("launch", help="Launch a workspace machine")
    launch.add_argument("--workspace", default=DEFAULT_WORKSPACE)
    launch.set_defaults(func=cmd_launch)

    teardown = subparsers.add_parser("teardown", help="Tear down a workspace machine")
    teardown.add_argument("--workspace", default=DEFAULT_WORKSPACE)
    teardown.set_defaults(func=cmd_teardown)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except EngineError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
