"""Command-line interface. The real `diagnose` command lands in Wave 1."""

import argparse

from . import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="examdiag",
        description="Find the root-cause concept behind every wrong answer.",
    )
    parser.add_argument("--version", action="version", version=f"examdiag {__version__}")
    parser.add_argument("command", nargs="?", help="diagnose (available from Wave 1)")
    args = parser.parse_args(argv)
    if args.command == "diagnose":
        print("`examdiag diagnose` ships in Wave 1 — engine + data are landing in Wave 0.")
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
