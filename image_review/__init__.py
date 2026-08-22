# Package marker for image_review
from pathlib import Path
import sys


def _read_version() -> str:
    candidates = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "VERSION")
    pkg = Path(__file__).resolve().parent
    candidates.append(pkg.parent / "VERSION")
    candidates.append(pkg / "VERSION")
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return text
    return "1.0.0"


__version__ = _read_version()
