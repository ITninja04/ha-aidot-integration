#!/usr/bin/env bash
# The per-change gate: lint, format check, tests. Runs on macmini01, the build
# machine for this repo, from the repo root:
#
#   hc run --on macmini01 --cwd Code/ha-aidot-integration scripts/check.sh
#
# Ruff is pinned so a new ruff release cannot fail a change that did not
# touch the code it complains about.
set -euo pipefail

RUFF="uvx -q ruff@0.14.5"

uv sync -q
$RUFF check custom_components tests scripts
$RUFF format --check custom_components tests scripts
uv run pytest -q
python3 -m json.tool custom_components/aidot/manifest.json > /dev/null
python3 -m json.tool custom_components/aidot/translations/en.json > /dev/null
python3 -m json.tool hacs.json > /dev/null
echo "check.sh: all passed"
