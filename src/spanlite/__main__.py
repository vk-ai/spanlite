"""python -m spanlite — currently exposes regression-pack utilities."""

from __future__ import annotations

from spanlite.promote import _cli, main

__all__ = ["main", "_cli"]

if __name__ == "__main__":
    main()
