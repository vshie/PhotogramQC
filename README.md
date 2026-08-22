# PhotogramQC

Photogrammetry image QC: pick a survey folder, scrub frames in a browser, mark bad ones, delete them from disk, and see GPS positions on a map.

**Downloads:** [latest GitHub Release](https://github.com/vshie/PhotogramQC/releases/latest)

| Computer | File |
| --- | --- |
| Windows 10/11 | `PhotogramQC-*-windows-x64.exe` |
| Mac (Apple Silicon) | `PhotogramQC-*-macos-arm64.zip` |
| Linux Intel/AMD 64-bit | `PhotogramQC-*-linux-x86_64.tar.gz` |
| Linux ARM 64-bit | `PhotogramQC-*-linux-arm64.tar.gz` |

Python is not required to run a release build.

---

## 1. Run the app

### Windows

Double-click `PhotogramQC-*-windows-x64.exe`. You can also drop a survey folder onto the exe.

### Mac (Apple Silicon)

1. Unzip `PhotogramQC-*-macos-arm64.zip`.
2. Right-click `PhotogramQC.app` → **Open** → **Open** again. macOS blocks unsigned apps until you do this once.
3. If that dialog never appears: `xattr -dr com.apple.quarantine PhotogramQC.app` then open the app.

### Linux

```bash
tar -xzf PhotogramQC-*-linux-x86_64.tar.gz   # or linux-arm64
cd PhotogramQC-*
chmod +x PhotogramQC
./PhotogramQC
```

### Once it is open

1. Select the folder that contains the survey pictures.
2. A status window lists the folder, image count, server address, and keyboard controls.
3. Click **Open review in browser**.
4. Review, mark, and delete as needed.
5. Close the status window when you are finished (that stops the server).

The review UI opens at [http://localhost:5055](http://localhost:5055) unless that port is already in use.

---

## 2. Folder expectations

| Item | Role |
| --- | --- |
| `*.jpg` / `*.jpeg` / `*.png` / `*.tif` | Images to review (flat folder). Playback is by capture time, not filename. |
| `telemetry.csv` (preferred) | Time, roll, and map — `filename` (or `jpg`), `timestamp`, `towfish_roll_deg`, `lat`, `lon` |
| Other `*.csv` | Used if `telemetry.csv` is missing and the file has a filename column plus time or roll |
| EXIF GPS / roll (fallback) | Only for frames the CSV does not cover |

Review state is written next to the pictures (or next to a `combined/` folder’s parent in the classic layout):

- `_review_marked.json` — marked-for-delete list (auto-filled on first open from roll)
- `_review_auto_roll.json` — 15° roll window used on first open
- `_review_position.json` — last scrub position
- `_review_cache/` — resized preview cache

---

## 3. Review controls

| Key / action | What it does |
| --- | --- |
| `←` / `→` | Previous / next image |
| `Shift` + arrows | Jump ×10 |
| Scrubber slider | Jump through the set (map updates while scrubbing) |
| `D` or `Delete` | Toggle mark for deletion |
| Hold `Space` + arrows | Mark every frame you pass |
| `Home` / `End` | First / last image |
| **Delete all marked** | Permanently deletes marked files from disk |

Deletes only affect the image folder you selected. Copies elsewhere are not touched.

If the folder has `telemetry.csv` (or another picture CSV) with time and roll, PhotogramQC uses that and does not open each image for EXIF. That is the fast path on every OS.

On the first open of a folder (no `_review_marked.json` yet), it finds the downward-looking roll mode and pre-marks frames whose roll is more than 15° from that mode. Existing marks are never overwritten — delete `_review_marked.json` to re-run the first pass.

---

## 4. Map / GPS notes

- Prefer a survey-root `telemetry.csv` with final image names in `filename` (or `jpg`), plus `timestamp`, `towfish_roll_deg`, and `lat` / `lon`.
- Time aliases also accepted: `time`, `datetime`, `capture_time`, `gps_time`.
- If a frame is missing from the CSV, PhotogramQC falls back to EXIF for that file only.
- Map tiles need internet (Esri World Imagery via Leaflet).
- Another computer on your LAN can open the address shown in the status window if the firewall allows it.

---

## 5. Publish a release (maintainers)

Pushing a version tag builds every OS and attaches the files to a GitHub Release:

```bash
git tag v1.0.0
git push origin v1.0.0
```

The workflow is `.github/workflows/release.yml`. You can also run **Release** by hand under Actions to test builds without publishing.

Update the `VERSION` file when you cut a new tag so the status window matches the download name.

---

## 6. Build locally (optional)

You need Python 3.10+ with Tk, plus the packages in `requirements-build.txt`.

**Windows:** double-click `Build-PhotogramQC.bat` (writes `dist\PhotogramQC.exe`).

**Mac / Linux:**

```bash
./scripts/build-photogramqc.sh
```

That writes `dist/PhotogramQC.app` on Mac, or `dist/PhotogramQC` on Linux.

### Run from source

```bash
python3 -m pip install -r requirements.txt
python3 photogramqc.py
```

On Windows you can double-click `Run-ImageReview.bat`, or:

```bat
py -3 photogramqc.py "E:\Towfish\survey_20260727"
```

---

## 7. Troubleshooting

| Problem | Fix |
| --- | --- |
| Folder dialog, then nothing | The status window should appear next; if it does not, rebuild |
| Browser blank / no images | Confirm the folder has pictures; check the status window count |
| Map empty | Add `telemetry.csv` or ensure EXIF GPS; hard-refresh the browser |
| Port already in use | PhotogramQC tries the next free port and shows the URL in the status window |
| LAN computer cannot connect | Allow PhotogramQC through the firewall |
| Mac says the app is damaged / cannot be opened | Right-click → Open, or run `xattr -dr com.apple.quarantine PhotogramQC.app` |
| Linux window does not appear | You need a desktop session; if you built from source, install `python3-tk` |
