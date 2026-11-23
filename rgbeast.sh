#!/bin/sh
# Lanzador de desarrollo de RGBEAST.
cd "$(dirname "$(readlink -f "$0")")" && exec .venv/bin/python -m rgbeast.app "$@"
