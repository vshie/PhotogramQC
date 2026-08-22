"""Desktop launcher: pick a folder, show status, open the review UI in a browser."""
from __future__ import annotations

import os
import sys
import threading
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

from image_review import __version__
from image_review import app as review


BG = "#0a1628"
BG_PANEL = "#0f2138"
BG_TRACK = "#152a45"
BLUE = "#2b7fff"
BLUE_BRIGHT = "#5cadff"
CYAN = "#7ef0ff"
TEXT = "#e8f1ff"
TEXT_DIM = "#8aa4c4"
if sys.platform == "win32":
    FONT = "Segoe UI"
elif sys.platform == "darwin":
    FONT = "Helvetica Neue"
else:
    FONT = "DejaVu Sans"
USAGE_ROWS = (
    ("←  →", "Previous / next image"),
    ("Shift + arrows", "Jump ×10"),
    ("Scrubber slider", "Jump through the set (map follows)"),
    ("D or Delete", "Toggle mark for deletion"),
    ("Hold Space + arrows", "Mark every frame you pass"),
    ("Home / End", "First / last image"),
    ("Delete all marked", "Permanently deletes marked files from disk"),
    ("First open", "High-roll frames are pre-marked from telemetry"),
)


def _enable_dpi() -> None:
    if sys.platform != "win32":
        return
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            from ctypes import windll

            windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _settings_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home())
        path = Path(base) / "PhotogramQC"
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "PhotogramQC"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        path = (Path(xdg) if xdg else Path.home() / ".config") / "PhotogramQC"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return Path.home()
    return path


def _last_folder() -> Path | None:
    marker = _settings_dir() / "last_folder.txt"
    try:
        text = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    path = Path(text)
    return path if path.is_dir() else None


def _save_last_folder(folder: Path) -> None:
    try:
        (_settings_dir() / "last_folder.txt").write_text(str(folder), encoding="utf-8")
    except OSError:
        pass


def _folder_from_argv() -> Path | None:
    if len(sys.argv) < 2:
        return None
    raw = Path(sys.argv[1])
    try:
        path = raw.resolve()
    except OSError:
        return None
    return path if path.is_dir() else None


def pick_image_folder(parent: tk.Misc | None = None) -> Path | None:
    initial = _last_folder()
    chosen = filedialog.askdirectory(
        parent=parent,
        title="Select the folder with survey pictures",
        initialdir=str(initial) if initial else None,
        mustexist=True,
    )
    if not chosen:
        return None
    return Path(chosen)


class StatusWindow:
    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.server: review.ReviewServer | None = None
        self.urls: list[str] = []
        self._closed = False
        self._scan_latest = None
        self._scan_scheduled = False
        self._progress_frac = 0.0

        self.root = tk.Tk()
        self.root.title("PhotogramQC")
        self.root.configure(bg=BG)
        self.root.minsize(460, 620)
        self.root.geometry("520x700")
        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(80, self._start_session)

    def _build(self) -> None:
        header = tk.Frame(self.root, bg=BG_PANEL)
        header.pack(fill="x")
        tk.Label(
            header,
            text="PhotogramQC",
            font=(FONT, 16, "bold"),
            fg=BLUE_BRIGHT,
            bg=BG_PANEL,
        ).pack(anchor="w", padx=18, pady=(16, 0))
        tk.Label(
            header,
            text="Photogrammetry image QC  ·  v%s" % __version__,
            font=(FONT, 10),
            fg=TEXT_DIM,
            bg=BG_PANEL,
        ).pack(anchor="w", padx=18, pady=(2, 16))

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True)

        self._section(body, "Image folder")
        self.folder_var = tk.StringVar(value=str(self.folder))
        self._wrap_label(body, self.folder_var)

        self.counts_var = tk.StringVar(value="Listing pictures…")
        tk.Label(
            body,
            textvariable=self.counts_var,
            font=(FONT, 11),
            fg=CYAN,
            bg=BG,
            justify="left",
        ).pack(anchor="w", padx=18, pady=(8, 0))

        self.progress_frame = tk.Frame(body, bg=BG)
        self.progress_frame.pack(fill="x", padx=18, pady=(8, 0))
        self.progress = tk.Canvas(
            self.progress_frame,
            height=12,
            bg=BG_TRACK,
            highlightthickness=0,
            bd=0,
        )
        self.progress.pack(fill="x")
        self._bar = self.progress.create_rectangle(0, 0, 0, 12, fill=BLUE, width=0)
        self.progress.bind("<Configure>", lambda _e: self._redraw_progress())

        self.extra_var = tk.StringVar(value="")
        tk.Label(
            body,
            textvariable=self.extra_var,
            font=(FONT, 9),
            fg=TEXT_DIM,
            bg=BG,
            justify="left",
            wraplength=470,
        ).pack(anchor="w", padx=18, pady=(2, 0))

        self._section(body, "Server")
        self.server_var = tk.StringVar(value="Starting…")
        tk.Label(
            body,
            textvariable=self.server_var,
            font=(FONT, 10),
            fg=TEXT,
            bg=BG,
            justify="left",
        ).pack(anchor="w", padx=18)

        self.open_btn = tk.Button(
            body,
            text="Open review in browser",
            command=self._open_browser,
            font=(FONT, 11, "bold"),
            bg=BLUE,
            fg="#ffffff",
            activebackground=BLUE_BRIGHT,
            activeforeground="#ffffff",
            disabledforeground=TEXT_DIM,
            relief="flat",
            cursor="hand2",
            padx=16,
            pady=10,
            state="disabled",
        )
        self.open_btn.pack(fill="x", padx=18, pady=(14, 4))

        self._section(body, "How to review")
        usage = tk.Frame(body, bg=BG)
        usage.pack(fill="x", padx=18, pady=(0, 8))
        usage.columnconfigure(1, weight=1)
        for i, (keys, desc) in enumerate(USAGE_ROWS):
            tk.Label(
                usage,
                text=keys,
                font=(FONT, 9, "bold"),
                fg=BLUE_BRIGHT,
                bg=BG,
                anchor="w",
            ).grid(row=i, column=0, sticky="nw", pady=2, padx=(0, 12))
            tk.Label(
                usage,
                text=desc,
                font=(FONT, 9),
                fg=TEXT,
                bg=BG,
                anchor="w",
                justify="left",
            ).grid(row=i, column=1, sticky="nw", pady=2)

        tk.Label(
            body,
            text=(
                "Review marks are saved next to the pictures. "
                "Deletes only affect this folder. Map tiles need internet. "
                "Close this window to stop the server."
            ),
            font=(FONT, 8),
            fg=TEXT_DIM,
            bg=BG,
            justify="left",
            wraplength=470,
        ).pack(anchor="w", padx=18, pady=(8, 0))

        self.status_var = tk.StringVar(value="Starting…")
        footer = tk.Frame(self.root, bg=BG_PANEL)
        footer.pack(fill="x", side="bottom")
        tk.Label(
            footer,
            textvariable=self.status_var,
            font=(FONT, 9),
            fg=TEXT_DIM,
            bg=BG_PANEL,
            anchor="w",
        ).pack(fill="x", padx=18, pady=10)

    def _section(self, parent: tk.Misc, title: str) -> None:
        tk.Label(
            parent,
            text=title.upper(),
            font=(FONT, 8, "bold"),
            fg=TEXT_DIM,
            bg=BG,
        ).pack(anchor="w", padx=18, pady=(16, 4))

    def _wrap_label(self, parent: tk.Misc, variable: tk.StringVar) -> None:
        tk.Label(
            parent,
            textvariable=variable,
            font=(FONT, 10),
            fg=TEXT,
            bg=BG,
            justify="left",
            wraplength=470,
        ).pack(anchor="w", padx=18)

    def _ui(self, fn) -> None:
        if self._closed:
            return
        self.root.after(0, fn)

    def _start_session(self) -> None:
        self.status_var.set("Listing pictures…")
        self._set_progress_frac(0)
        thread = threading.Thread(target=self._boot_worker, daemon=True)
        thread.start()

    def _on_scan_progress(self, done: int, total: int, message: str) -> None:
        self._scan_latest = (done, total, message)
        if self._scan_scheduled or self._closed:
            return
        self._scan_scheduled = True
        self._ui(self._flush_scan_progress)

    def _flush_scan_progress(self) -> None:
        self._scan_scheduled = False
        if self._closed or not self._scan_latest:
            return
        done, total, message = self._scan_latest
        if total > 0:
            self.counts_var.set("Scanning %s / %s" % (_fmt(done), _fmt(total)))
            self._set_progress_frac(float(done) / float(total))
        else:
            self.counts_var.set(message or "Listing pictures…")
            self._set_progress_frac(0)
        if message:
            self.status_var.set(message)

    def _set_progress_frac(self, frac: float) -> None:
        self._progress_frac = max(0.0, min(1.0, frac))
        self._redraw_progress()

    def _redraw_progress(self) -> None:
        if not hasattr(self, "progress"):
            return
        width = self.progress.winfo_width()
        height = self.progress.winfo_height()
        if width < 2:
            width = 470
        if height < 2:
            height = 12
        fill = int(width * getattr(self, "_progress_frac", 0.0))
        self.progress.coords(self._bar, 0, 0, fill, height)

    def _boot_worker(self) -> None:
        try:
            review.configure_paths(self.folder)
            _save_last_folder(self.folder)
            review._build_catalog(progress=self._on_scan_progress)
            info = review.session_info()
            self._ui(lambda: self._show_catalog(info))

            port = review.find_open_port(review.DEFAULT_PORT)
            server = review.ReviewServer(port=port)
            server.start()
            self.server = server
            self.urls = review.discover_urls(port)
            self._ui(lambda: self._show_ready(info))
        except Exception as exc:
            self._ui(lambda: self._show_error(exc))

    def _show_catalog(self, info: dict) -> None:
        count = int(info.get("count") or 0)
        marked = int(info.get("marked") or 0)
        self.counts_var.set("%s images  ·  %s marked" % (_fmt(count), _fmt(marked)))
        bits = []
        csv_name = info.get("csv_name")
        exif_reads = int(info.get("exif_reads") or 0)
        if csv_name:
            if exif_reads == 0:
                bits.append("%s used for time and roll (skipped picture EXIF)" % csv_name)
            else:
                bits.append(
                    "%s used for time and roll · EXIF on %s unmatched frames"
                    % (csv_name, _fmt(exif_reads))
                )
        else:
            bits.append("no picture CSV — time and roll come from EXIF when present")
        bits.append("playback is by capture time, not filename")
        roll = info.get("roll_filter") or {}
        if roll.get("matched"):
            threshold = roll.get("threshold_deg")
            roll_marked = roll.get("marked")
            if roll.get("applied"):
                bits.append(
                    "auto-marked %s frames with |roll| > %s°"
                    % (_fmt(int(roll_marked or 0)), _fmt_deg(threshold))
                )
            else:
                bits.append(
                    "roll filter would mark %s at ±%s° (existing marks kept)"
                    % (_fmt(int(roll_marked or 0)), _fmt_deg(threshold))
                )
        bits.append("review files saved in %s" % info.get("survey_root"))
        self.extra_var.set(" · ".join(bits))
        self._set_progress_frac(1)
        self.status_var.set("Starting local server…")

    def _show_ready(self, info: dict) -> None:
        if self.urls:
            self.server_var.set("\n".join(self.urls))
        else:
            self.server_var.set("http://localhost:%d" % review.DEFAULT_PORT)
        count = int(info.get("count") or 0)
        if count == 0:
            self.status_var.set("Ready — no pictures found in this folder")
            self.counts_var.set("0 images  ·  0 marked")
        else:
            self.status_var.set("Ready — open the review in your browser")
        self.open_btn.configure(state="normal")
        self.progress_frame.pack_forget()

    def _show_error(self, exc: Exception) -> None:
        self.server_var.set("Server did not start")
        self.status_var.set("Error")
        self.counts_var.set(str(exc))
        self.open_btn.configure(state="disabled")
        self.progress_frame.pack_forget()
        messagebox.showerror("PhotogramQC", str(exc), parent=self.root)

    def _open_browser(self) -> None:
        url = self.urls[0] if self.urls else "http://localhost:%d" % review.DEFAULT_PORT
        try:
            webbrowser.open(url)
            self.status_var.set("Opened %s" % url)
        except Exception as exc:
            messagebox.showerror(
                "PhotogramQC",
                "Could not open the browser:\n%s\n\nOpen this address yourself:\n%s"
                % (exc, url),
                parent=self.root,
            )

    def _on_close(self) -> None:
        self._closed = True
        if self.server is not None:
            self.server.stop()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def _fmt(n: int) -> str:
    return "{:,}".format(n)


def _fmt_deg(value) -> str:
    try:
        return "%.1f" % float(value)
    except (TypeError, ValueError):
        return "?"


def main() -> None:
    _enable_dpi()

    folder = _folder_from_argv()
    if folder is None:
        picker = tk.Tk()
        picker.withdraw()
        folder = pick_image_folder(picker)
        picker.destroy()

    if folder is None:
        return

    StatusWindow(folder).run()


if __name__ == "__main__":
    main()
