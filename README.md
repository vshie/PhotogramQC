# PhotogramQC

Windows tool for photogrammetry image QC: scrub survey frames in a browser, mark bad ones, delete them from disk, and see GPS positions on a map.

**Platform:** Windows only (uses `Run-ImageReview.bat`).

---

## 1. Install Python (one-time)

1. Download **Python 3.10+** from [python.org/downloads](https://www.python.org/downloads/windows/).
2. Run the installer.
3. Check **Add python.exe to PATH**.
4. Finish the install, then open a new Command Prompt and confirm:

```bat
py -3 --version
```

If `py` is missing, try:

```bat
python --version
```

You need Python 3.7 or newer. If both commands fail, reinstall Python with PATH enabled.

---

## 2. Get PhotogramQC

Clone or copy this folder somewhere local, for example:

`C:\Users\<you>\Documents\PhotogramQC`

You only need the repo files (not survey images inside the repo). Typical layout:

```text
PhotogramQC/
  Run-ImageReview.bat
  requirements.txt
  README.md
  image_review/
    app.py
    static/
```

---

## 3. Install dependencies (first run)

**Easiest:** double-click `Run-ImageReview.bat`.  
It installs Flask and Pillow automatically, then starts the app.

**Manual (optional):**

```bat
cd C:\Users\<you>\Documents\PhotogramQC
py -3 -m pip install -r requirements.txt
```

---

## 4. Point it at a survey image folder

Images stay in your survey folder. PhotogramQC does not need to live next to them.

### Option A — recommended

From Command Prompt or PowerShell:

```bat
cd C:\Users\<you>\Documents\PhotogramQC
Run-ImageReview.bat "E:\Towfish\survey_20260727"
```

Use your actual image folder path in quotes.

### Option B — drag and drop

1. Open File Explorer to the PhotogramQC folder.
2. Drag your survey folder onto `Run-ImageReview.bat`.

### Option C — classic `combined` layout

If PhotogramQC itself contains a `combined\` subfolder of images, just double-click `Run-ImageReview.bat` (no argument).

### Folder expectations

| Item | Role |
|------|------|
| `*.jpg` / `*.jpeg` / `*.png` / `*.tif` | Images to review (flat folder) |
| `telemetry.csv` (optional) | Map positions — columns `filename` (or `jpg`), `lat`, `lon` |
| EXIF GPS (optional) | Used when telemetry has no match for a frame |

Review state is written next to the images (or next to `combined\`’s parent in classic layout):

- `_review_marked.json` — marked-for-delete list  
- `_review_position.json` — last scrub position  
- `_review_cache\` — resized preview cache  

---

## 5. Use the app

1. Keep the black console window open while reviewing.
2. A browser should open to [http://localhost:5055](http://localhost:5055). If not, open that URL yourself.
3. Review, mark, and delete as needed.
4. When finished: close the browser tab, then press **Ctrl+C** in the console (or close the window).

### Controls

| Key / action | What it does |
|--------------|--------------|
| `←` / `→` | Previous / next image |
| `Shift` + arrows | Jump ×10 |
| Scrubber slider | Jump through the set (map updates while scrubbing) |
| `D` or `Delete` | Toggle mark for deletion |
| Hold `Space` + arrows | Mark every frame you pass |
| `Home` / `End` | First / last image |
| **Delete all marked** | Permanently deletes marked files from disk |

Deletes only affect the image folder you launched against. Copies elsewhere (e.g. Desktop) are not touched.

---

## 6. Map / GPS notes

- Prefer a survey-root `telemetry.csv` with final image names in `filename` (or `jpg`) plus `lat` / `lon`.
- If telemetry is missing for a frame, PhotogramQC falls back to EXIF GPS.
- Map tiles need internet (Esri World Imagery via Leaflet).
- On another PC on your LAN you can open `http://<this-pc-ip>:5055` if Windows Firewall allows Python.

---

## 7. Troubleshooting

| Problem | Fix |
|---------|-----|
| `Python 3 not found` | Install Python and enable **Add to PATH**; open a **new** terminal |
| `pip install failed` | Run `py -3 -m pip install -r requirements.txt` and read the error |
| Browser blank / no images | Confirm the folder path has images; check the console for “Loaded N images” |
| Map empty | Add `telemetry.csv` or ensure EXIF GPS; hard-refresh with Ctrl+F5 after restart |
| Port already in use | Close another PhotogramQC window, or reboot if stuck |
| Changes to code not showing | Stop the console (Ctrl+C) and run `Run-ImageReview.bat` again |

---

## Requirements summary

- Windows 10/11
- Python 3.7+ (3.10+ recommended)
- Flask + Pillow (installed by the batch file or `requirements.txt`)
- Network access for map tiles
