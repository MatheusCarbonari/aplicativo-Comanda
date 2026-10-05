#!/usr/bin/env python
"""Ponto de entrada das ferramentas administrativas do Django."""

import os
import sys


def main() -> None:
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE",
        "restaurante.infraestrutura.configuracao",
    )

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
