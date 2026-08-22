#!/usr/bin/env python3
"""Local image review tool for photogrammetry combined folders."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import threading
import time
import webbrowser
from io import BytesIO
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory
from PIL import Image

try:
    _RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    _RESAMPLE = Image.LANCZOS

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"

# Survey root is parent of image_review/; combined folder passed as argv or sibling.
SURVEY_ROOT = APP_DIR.parent
COMBINED_DIR = SURVEY_ROOT / "combined"
MANIFEST_PATH = SURVEY_ROOT / "_combine_manifest.csv"
MARKED_PATH = SURVEY_ROOT / "_review_marked.json"
POSITION_PATH = SURVEY_ROOT / "_review_position.json"
CACHE_DIR = SURVEY_ROOT / "_review_cache"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")

# In-memory catalog + mark set
_catalog: list[dict] = []
_by_name: dict[str, dict] = {}
_marked: set[str] = set()
_delete_progress = {
    "active": False,
    "done": 0,
    "total": 0,
    "deleted": 0,
    "errors": 0,
    "message": "",
}


def _load_marked() -> set[str]:
    if not MARKED_PATH.is_file():
        return set()
    try:
        data = json.loads(MARKED_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return set(str(x) for x in data)
        if isinstance(data, dict) and "marked" in data:
            return set(str(x) for x in data["marked"])
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return set()


def _save_marked() -> None:
    MARKED_PATH.write_text(
        json.dumps(sorted(_marked), indent=2),
        encoding="utf-8",
    )


def _load_position() -> dict:
    if not POSITION_PATH.is_file():
        return {"index": 0, "name": None}
    try:
        data = json.loads(POSITION_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            idx = data.get("index", 0)
            try:
                idx = int(idx)
            except (TypeError, ValueError):
                idx = 0
            name = data.get("name")
            return {"index": max(0, idx), "name": str(name) if name else None}
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return {"index": 0, "name": None}


def _save_position(index: int, name: str | None) -> None:
    POSITION_PATH.write_text(
        json.dumps({"index": int(index), "name": name}, indent=2),
        encoding="utf-8",
    )


def _resolve_position() -> dict:
    """Return clamped index + name from saved position against current catalog."""
    pos = _load_position()
    if not _catalog:
        return {"index": 0, "name": None}
    name = pos.get("name")
    if name:
        for i, entry in enumerate(_catalog):
            if entry["name"] == name:
                return {"index": i, "name": name}
    idx = min(max(0, int(pos.get("index") or 0)), len(_catalog) - 1)
    return {"index": idx, "name": _catalog[idx]["name"]}


def _telemetry_lookup(telemetry_path: Path) -> dict[str, dict]:
    """Map image filename -> telemetry fields (jpg or filename column)."""
    out: dict[str, dict] = {}
    if not telemetry_path.is_file():
        return out
    try:
        with telemetry_path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                jpg = (
                    (row.get("jpg") or row.get("filename") or row.get("name") or "")
                    .strip()
                )
                if not jpg:
                    continue
                # Basename only — survey-root CSV uses final names.
                jpg = Path(jpg).name
                try:
                    lat = float(row["lat"]) if row.get("lat") not in (None, "") else None
                    lon = float(row["lon"]) if row.get("lon") not in (None, "") else None
                except (KeyError, ValueError, TypeError):
                    lat, lon = None, None
                depth = None
                heading = None
                seq = None
                try:
                    if row.get("depth_m") not in (None, ""):
                        depth = float(row["depth_m"])
                except (ValueError, TypeError):
                    pass
                try:
                    if row.get("towfish_heading_deg") not in (None, ""):
                        heading = float(row["towfish_heading_deg"])
                except (ValueError, TypeError):
                    pass
                try:
                    if row.get("seq") not in (None, ""):
                        seq = int(float(row["seq"]))
                except (ValueError, TypeError):
                    pass
                out[jpg] = {
                    "lat": lat,
                    "lon": lon,
                    "depth_m": depth,
                    "heading_deg": heading,
                    "timestamp": (row.get("timestamp") or "").strip() or None,
                    "seq": seq,
                    "source_folder": (
                        (row.get("source_folder") or row.get("source_tag") or "").strip()
                        or None
                    ),
                    "waypoint": (row.get("waypoint") or row.get("wp") or "").strip() or None,
                }
    except OSError:
        pass
    return out


def _exif_gps(path: Path) -> tuple[float | None, float | None]:
    """Return (lat, lon) from EXIF GPS if present."""
    try:
        with Image.open(path) as im:
            exif = im._getexif() if hasattr(im, "_getexif") else None
            if not exif:
                return None, None
            gps = exif.get(34853)  # GPSInfo
            if not isinstance(gps, dict):
                return None, None

            def _to_deg(values):
                d, m, s = values
                return float(d) + float(m) / 60.0 + float(s) / 3600.0

            lat_vals = gps.get(2)
            lon_vals = gps.get(4)
            if not lat_vals or not lon_vals:
                return None, None
            lat = _to_deg(lat_vals)
            lon = _to_deg(lon_vals)
            if (gps.get(1) or "").upper() == "S":
                lat = -lat
            if (gps.get(3) or "").upper() == "W":
                lon = -lon
            return lat, lon
    except Exception:
        return None, None


def _build_catalog() -> list[dict]:
    """Scan image folder; GPS from survey telemetry, manifest join, or EXIF."""
    global _catalog, _by_name, _marked

    _marked = _load_marked()
    telem_cache: dict[str, dict[str, dict]] = {}  # dir path -> jpg -> fields

    # Prefer survey-root telemetry.csv keyed by final filename (new single-folder layout).
    root_telem = _telemetry_lookup(SURVEY_ROOT / "telemetry.csv")
    if not root_telem and COMBINED_DIR != SURVEY_ROOT:
        root_telem = _telemetry_lookup(COMBINED_DIR / "telemetry.csv")

    # Manifest: new_name -> original_path, source, waypoint, seq
    manifest_by_new: dict[str, dict] = {}
    if MANIFEST_PATH.is_file():
        with MANIFEST_PATH.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                new_name = (row.get("new_name") or "").strip()
                if new_name:
                    manifest_by_new[new_name] = row

    images = sorted(
        [
            p
            for p in COMBINED_DIR.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS
        ],
        key=lambda p: p.name.lower(),
    )

    catalog: list[dict] = []
    for img in images:
        name = img.name
        row = manifest_by_new.get(name, {})
        original_path = (row.get("original_path") or "").strip()
        source_folder = (row.get("source_folder") or "").strip()
        waypoint = (row.get("waypoint") or "").strip()
        try:
            seq = int(row["seq"]) if row.get("seq") not in (None, "") else None
        except (ValueError, TypeError):
            seq = None

        lat = lon = depth = heading = timestamp = None

        telem = root_telem.get(name)
        if telem:
            lat = telem.get("lat")
            lon = telem.get("lon")
            depth = telem.get("depth_m")
            heading = telem.get("heading_deg")
            timestamp = telem.get("timestamp")
            if seq is None:
                seq = telem.get("seq")
            if not source_folder and telem.get("source_folder"):
                source_folder = telem["source_folder"]
            if not waypoint and telem.get("waypoint"):
                waypoint = telem["waypoint"]

        if (lat is None or lon is None) and original_path:
            orig = Path(original_path)
            telem_dir = str(orig.parent)
            if telem_dir not in telem_cache:
                telem_cache[telem_dir] = _telemetry_lookup(orig.parent / "telemetry.csv")
            telem = telem_cache[telem_dir].get(orig.name) or telem_cache[telem_dir].get(
                (row.get("original_name") or "").strip()
            )
            if telem:
                if lat is None:
                    lat = telem.get("lat")
                if lon is None:
                    lon = telem.get("lon")
                if depth is None:
                    depth = telem.get("depth_m")
                if heading is None:
                    heading = telem.get("heading_deg")
                if timestamp is None:
                    timestamp = telem.get("timestamp")

        if lat is None or lon is None:
            elat, elon = _exif_gps(img)
            if lat is None:
                lat = elat
            if lon is None:
                lon = elon

        entry = {
            "name": name,
            "seq": seq,
            "source_folder": source_folder or None,
            "waypoint": waypoint or None,
            "lat": lat,
            "lon": lon,
            "depth_m": depth,
            "heading_deg": heading,
            "timestamp": timestamp,
            "marked": name in _marked,
        }
        catalog.append(entry)

    # Drop marks for files that no longer exist
    existing = {e["name"] for e in catalog}
    stale = _marked - existing
    if stale:
        _marked -= stale
        _save_marked()
        for e in catalog:
            e["marked"] = e["name"] in _marked

    _catalog = catalog
    _by_name = {e["name"]: e for e in catalog}
    return catalog


def _safe_name(name: str) -> str | None:
    """Reject path traversal; return basename if file exists in combined."""
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        return None
    # Normalize to basename only
    name = Path(name).name
    path = COMBINED_DIR / name
    if not path.is_file():
        return None
    return name


def _cache_path(name: str, width: int) -> Path:
    key = hashlib.md5(f"{name}:{width}".encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{key}.jpg"


def _resized_jpeg(src: Path, width: int) -> bytes:
    CACHE_DIR.mkdir(exist_ok=True)
    cached = _cache_path(src.name, width)
    if cached.is_file() and cached.stat().st_mtime >= src.stat().st_mtime:
        return cached.read_bytes()

    with Image.open(src) as im:
        im = im.convert("RGB")
        w, h = im.size
        if w > width:
            new_h = max(1, int(round(h * (width / float(w)))))
            im = im.resize((width, new_h), _RESAMPLE)
        buf = BytesIO()
        im.save(buf, format="JPEG", quality=82, optimize=True)
        data = buf.getvalue()
    try:
        cached.write_bytes(data)
    except OSError:
        pass
    return data


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/api/catalog")
def api_catalog():
    if not _catalog:
        _build_catalog()
    return jsonify(
        {
            "combined": str(COMBINED_DIR),
            "count": len(_catalog),
            "marked_count": len(_marked),
            "position": _resolve_position(),
            "images": _catalog,
        }
    )


@app.route("/api/position", methods=["GET", "POST"])
def api_position():
    if not _catalog:
        _build_catalog()
    if request.method == "GET":
        return jsonify(_resolve_position())

    body = request.get_json(force=True, silent=True) or {}
    name = body.get("name")
    idx = body.get("index", 0)
    try:
        idx = int(idx)
    except (TypeError, ValueError):
        idx = 0
    if name:
        safe = Path(str(name)).name
        for i, entry in enumerate(_catalog):
            if entry["name"] == safe:
                idx = i
                name = safe
                break
        else:
            name = None
    if not _catalog:
        _save_position(0, None)
        return jsonify({"index": 0, "name": None})
    idx = min(max(0, idx), len(_catalog) - 1)
    if not name:
        name = _catalog[idx]["name"]
    _save_position(idx, name)
    return jsonify({"index": idx, "name": name})


@app.route("/api/image/<path:name>")
def api_image(name: str):
    safe = _safe_name(name)
    if not safe:
        return jsonify({"error": "not found"}), 404
    src = COMBINED_DIR / safe
    width = request.args.get("w", type=int)
    if width and width > 0:
        width = min(width, 4000)
        try:
            data = _resized_jpeg(src, width)
            return Response(data, mimetype="image/jpeg")
        except OSError as exc:
            return jsonify({"error": str(exc)}), 500
    return send_from_directory(COMBINED_DIR, safe)


@app.route("/api/mark", methods=["POST"])
def api_mark():
    body = request.get_json(force=True, silent=True) or {}
    name = body.get("name")
    marked = bool(body.get("marked"))
    safe = _safe_name(str(name) if name else "")
    if not safe:
        return jsonify({"error": "not found"}), 404
    if marked:
        _marked.add(safe)
    else:
        _marked.discard(safe)
    if safe in _by_name:
        _by_name[safe]["marked"] = marked
    _save_marked()
    return jsonify({"name": safe, "marked": marked, "marked_count": len(_marked)})


@app.route("/api/delete_progress")
def api_delete_progress():
    return jsonify(_delete_progress)


@app.route("/api/delete", methods=["POST"])
def api_delete():
    global _catalog, _by_name, _delete_progress

    body = request.get_json(force=True, silent=True) or {}
    names = body.get("names")
    if names is None:
        names = sorted(_marked)
    if not isinstance(names, list):
        return jsonify({"error": "names must be a list"}), 400

    total = len(names)
    print("DELETE start: %d files" % total, flush=True)
    _delete_progress = {
        "active": True,
        "done": 0,
        "total": total,
        "deleted": 0,
        "errors": 0,
        "message": "Deleting files…",
    }

    deleted = []
    errors = []
    for i, name in enumerate(names, start=1):
        raw = Path(str(name)).name
        if not raw or raw in (".", "..") or "/" in str(name) or "\\" in str(name):
            errors.append("invalid name: %s" % name)
            _delete_progress["errors"] = len(errors)
            _delete_progress["done"] = i
            continue
        path = COMBINED_DIR / raw
        try:
            if path.is_file():
                path.unlink()
            # Missing file counts as deleted (e.g. previous interrupted run)
            deleted.append(raw)
            _marked.discard(raw)
        except OSError as exc:
            errors.append("%s: %s" % (raw, exc))
            _delete_progress["errors"] = len(errors)

        _delete_progress["done"] = i
        _delete_progress["deleted"] = len(deleted)
        if i == 1 or i == total or i % 25 == 0:
            msg = "Deleted %d / %d" % (len(deleted), total)
            _delete_progress["message"] = msg
            print(msg, flush=True)

    print("Updating catalog in memory…", flush=True)
    _delete_progress["message"] = "Updating catalog…"
    deleted_set = set(deleted)
    _catalog = [e for e in _catalog if e["name"] not in deleted_set]
    for e in _catalog:
        e["marked"] = e["name"] in _marked
    _by_name = {e["name"]: e for e in _catalog}
    _save_marked()

    _delete_progress = {
        "active": False,
        "done": total,
        "total": total,
        "deleted": len(deleted),
        "errors": len(errors),
        "message": "Done",
    }
    print(
        "DELETE done: %d removed, %d errors, %d remaining"
        % (len(deleted), len(errors), len(_catalog)),
        flush=True,
    )
    return jsonify(
        {
            "deleted": deleted,
            "errors": errors,
            "count": len(_catalog),
            "marked_count": len(_marked),
            "images": _catalog,
        }
    )


@app.route("/api/reload", methods=["POST"])
def api_reload():
    catalog = _build_catalog()
    return jsonify(
        {
            "count": len(catalog),
            "marked_count": len(_marked),
            "images": catalog,
        }
    )


def main() -> None:
    global COMBINED_DIR, MANIFEST_PATH, MARKED_PATH, POSITION_PATH, CACHE_DIR, SURVEY_ROOT

    if len(sys.argv) > 1:
        COMBINED_DIR = Path(sys.argv[1]).resolve()
    else:
        COMBINED_DIR = (SURVEY_ROOT / "combined").resolve()

    if not COMBINED_DIR.is_dir():
        print(f"Combined folder not found: {COMBINED_DIR}")
        print("Run the combine script first, or pass the combined path as an argument.")
        sys.exit(1)

    # Flat survey folder (images + telemetry.csv here) vs classic survey/combined/.
    if (COMBINED_DIR / "telemetry.csv").is_file() or (COMBINED_DIR / "image_review").is_dir():
        SURVEY_ROOT = COMBINED_DIR
    else:
        SURVEY_ROOT = COMBINED_DIR.parent
    MANIFEST_PATH = SURVEY_ROOT / "_combine_manifest.csv"
    MARKED_PATH = SURVEY_ROOT / "_review_marked.json"
    POSITION_PATH = SURVEY_ROOT / "_review_position.json"
    CACHE_DIR = SURVEY_ROOT / "_review_cache"

    print("Combined: %s" % COMBINED_DIR)
    print("Building catalog (may take a minute on a network share)...")
    n = len(_build_catalog())
    print("Loaded %d images (%d previously marked)" % (n, len(_marked)))

    host = "0.0.0.0"
    port = 5055
    local_urls = ["http://localhost:%d" % port]
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            lan_ip = s.getsockname()[0]
        if lan_ip and not lan_ip.startswith("127."):
            local_urls.append("http://%s:%d" % (lan_ip, port))
    except OSError:
        pass

    print("Ready on the local network:")
    for u in local_urls:
        print("  %s" % u)
    print("(Allow Python through Windows Firewall if other PCs cannot connect.)")

    def _open_browser():
        time.sleep(0.8)
        try:
            webbrowser.open(local_urls[0])
        except Exception:
            pass

    threading.Thread(target=_open_browser, daemon=True).start()
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
