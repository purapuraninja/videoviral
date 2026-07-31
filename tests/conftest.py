"""Shared pytest fixtures."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make every VVF src package importable without installs in the test env.
ROOT = Path(__file__).resolve().parents[1]
for rel in [
    "packages/contracts/src",
    "packages/database/src",
    "packages/shared/src",
    "integrations/wigolo/src",
    "integrations/money-printer-turbo/src",
    "apps/api/src",
    "apps/discovery-worker/src",
    "apps/local-render-agent/src",
]:
    p = str(ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

# Provide minimal env defaults so Settings / clients don't fail at import.
os.environ.setdefault("VVF_SECRET_KEY", "test-secret-key-for-tests")
os.environ.setdefault("VVF_ENV", "development")
