#!/usr/bin/env python3
"""
Log Parser module entry point.

Allows the module to be executed as:
    python -m log_parser dockerfile /path/to/Dockerfile
"""

from .cli import main

if __name__ == '__main__':
    main()