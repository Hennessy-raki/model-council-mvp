from __future__ import annotations

import json
from pathlib import Path
import sys

repository = Path(__file__).resolve().parent.parent
if str(repository) not in sys.path:
    sys.path.insert(0, str(repository))

from model_council.release import ReleaseVerifier

if __name__ == "__main__":
    result = ReleaseVerifier(repository).verify()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "passed" else 1)
