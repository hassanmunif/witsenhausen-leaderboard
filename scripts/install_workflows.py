#!/usr/bin/env python3
"""Copy the CI workflows from ci/workflows/ into .github/workflows/.

GitHub only runs workflows stored in .github/workflows/.  Run this once
before your first push:   python scripts/install_workflows.py
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = ROOT / "ci" / "workflows"
dst = ROOT / ".github" / "workflows"
dst.mkdir(parents=True, exist_ok=True)
for f in sorted(src.glob("*.yml")):
    shutil.copy2(f, dst / f.name)
    print(f"copied {f.relative_to(ROOT)} -> {(dst / f.name).relative_to(ROOT)}")
