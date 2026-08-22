"""First-pass mark-for-delete from towfish roll (downward-looking frames)."""
from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import Iterable, Optional

MIN_THRESHOLD_DEG = 5.0
MAX_THRESHOLD_DEG = 10.0
# Walk the 0.5° histogram while a bin stays at least this fraction of the peak.
LOBE_FLOOR_FRAC = 0.15

_DESC_ROLL_RE = re.compile(r"roll=([+-]?\d+(?:\.\d+)?)\s*deg", re.IGNORECASE)
_XMP_ROLL_RE = re.compile(br"<Camera:Roll>([+-]?\d+(?:\.\d+)?)</Camera:Roll>")


def wrap180(deg: float) -> float:
    """Wrap degrees to (-180, 180]. Leaves already-in-range values unchanged."""
    x = float(deg)
    while x <= -180.0:
        x += 360.0
    while x > 180.0:
        x -= 360.0
    return x


def parse_float(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return wrap180(float(value))
    except (TypeError, ValueError):
        return None


def choose_threshold(
    rolls: Iterable[float],
    min_t: float = MIN_THRESHOLD_DEG,
    max_t: float = MAX_THRESHOLD_DEG,
) -> dict:
    """Pick a 5–10° window from the main lobe of the roll histogram.

    Downward-looking survey frames cluster near 0° (or a small bias). Turns
    and inversions sit in the tails. The threshold is the half-width of the
    main 0.5° lobe, clamped to [min_t, max_t].
    """
    values = [wrap180(r) for r in rolls]
    if len(values) < 8:
        mode = 0.0
        threshold = max_t
        return {
            "mode_deg": mode,
            "threshold_deg": threshold,
            "lobe_lo_deg": mode - threshold,
            "lobe_hi_deg": mode + threshold,
            "sample_count": len(values),
        }

    bins = Counter(int(math.floor(r * 2.0)) for r in values)
    mode_bin, mode_n = max(bins.items(), key=lambda kv: kv[1])
    mode = (mode_bin + 0.5) / 2.0
    floor = max(1, int(LOBE_FLOOR_FRAC * mode_n))
    left = mode_bin
    right = mode_bin
    while bins.get(left - 1, 0) >= floor:
        left -= 1
    while bins.get(right + 1, 0) >= floor:
        right += 1
    lobe_lo = left / 2.0
    lobe_hi = (right + 1) / 2.0
    half = max(abs(lobe_lo - mode), abs(lobe_hi - mode))
    threshold = min(max_t, max(min_t, round(half * 2.0) / 2.0))
    return {
        "mode_deg": round(mode, 3),
        "threshold_deg": float(threshold),
        "lobe_lo_deg": round(lobe_lo, 3),
        "lobe_hi_deg": round(lobe_hi, 3),
        "sample_count": len(values),
    }


def exceeds_threshold(roll_deg: float, mode_deg: float, threshold_deg: float) -> bool:
    return abs(wrap180(roll_deg) - mode_deg) > threshold_deg


def suggest_marks(entries: Iterable[dict]) -> dict:
    """Return names to mark plus histogram-derived threshold metadata."""
    rolled = []
    for entry in entries:
        roll = entry.get("roll_deg")
        if roll is None:
            continue
        rolled.append((entry["name"], float(roll)))

    meta = choose_threshold(r for _, r in rolled)
    mode = meta["mode_deg"]
    threshold = meta["threshold_deg"]
    names = [name for name, roll in rolled if exceeds_threshold(roll, mode, threshold)]
    meta.update(
        {
            "matched": len(rolled),
            "marked": len(names),
            "kept": len(rolled) - len(names),
            "names": names,
        }
    )
    return meta


def roll_from_description(desc) -> Optional[float]:
    """Parse `roll=+5.7deg` from an EXIF ImageDescription string."""
    if desc in (None, ""):
        return None
    if isinstance(desc, bytes):
        desc = desc.decode("utf-8", "replace")
    match = _DESC_ROLL_RE.search(str(desc))
    if not match:
        return None
    return parse_float(match.group(1))


def roll_from_image(path: Path) -> Optional[float]:
    """Read Camera:Roll from EXIF ImageDescription or a short XMP prefix."""
    try:
        from PIL import Image
    except ImportError:
        Image = None  # type: ignore

    if Image is not None:
        try:
            with Image.open(path) as im:
                exif = im.getexif() if hasattr(im, "getexif") else None
                desc = exif.get(270) if exif else None
            roll = roll_from_description(desc)
            if roll is not None:
                return roll
        except Exception:
            pass

    try:
        with path.open("rb") as handle:
            head = handle.read(16384)
        match = _XMP_ROLL_RE.search(head)
        if match:
            return parse_float(match.group(1).decode("ascii"))
    except OSError:
        pass
    return None
