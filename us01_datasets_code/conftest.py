import os
import sys
from pathlib import Path

US01_ROOT = str(Path(__file__).resolve().parent)

if US01_ROOT in sys.path:
    sys.path.remove(US01_ROOT)

sys.path.insert(0, US01_ROOT)

# Ensure the US-01 package is used, not the root project's package.
for name in list(sys.modules):
    if name == "datasets" or name.startswith("datasets."):
        del sys.modules[name]
