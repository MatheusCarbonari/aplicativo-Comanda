"""Inicia um comando somente após o processo entrar no Job Object do teste."""

import subprocess
import sys


def main() -> int:
    if sys.stdin.buffer.readline() != b"iniciar\n":
        return 2
    return subprocess.call(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
