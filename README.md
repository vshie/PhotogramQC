# PhotogramQC

Local Flask image QC tool for photogrammetry surveys. Review survey frames in a browser, mark or delete bad images, and see positions on a map.

## Run

- Double-click `Run-ImageReview.bat`, or pass an image folder: `Run-ImageReview.bat "D:\path\to\images"`
- Or: `python image_review/app.py PATH`

If no folder is given, the batch file uses `.\combined` when present, otherwise the current directory.

## GPS

Positions come from `telemetry.csv` (matched on the filename column) when available, otherwise from image EXIF GPS.

## Requirements

- Python 3.7+
- Dependencies: Flask and Pillow (`pip install -r requirements.txt`, or let the batch file install them)
