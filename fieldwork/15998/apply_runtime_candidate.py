#!/usr/bin/env python3
"""Apply the base-complete Meson #15998 runtime-deferred candidate.

This is the authoritative entry point for an immutable public-base checkout.
`apply_deferred_candidate.py` contains the implementation/test transformations;
this wrapper first adds CUDA to the standard-classification loop that is absent
from the public base.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import apply_deferred_candidate as deferred


def apply_candidate(root: Path) -> None:
    interpreter = root / "mesonbuild/cmake/interpreter.py"
    deferred.replace_once(
        interpreter,
        """        for i in T.cast('T.Tuple[Language, ...]', ('c', 'cpp')):
""",
        """        for i in T.cast('T.Tuple[Language, ...]', ('c', 'cpp', 'cuda')):
""",
        "include CUDA in standard classification",
    )
    deferred.apply_candidate(root)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('--tests-only', action='store_true')
    args = parser.parse_args()

    root = args.root.resolve()
    deferred.apply_tests(root)
    if not args.tests_only:
        apply_candidate(root)


if __name__ == '__main__':
    main()
