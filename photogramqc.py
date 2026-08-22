"""PhotogramQC desktop entry point."""
import sys
import traceback


def main() -> None:
    from image_review.desktop import main as desktop_main

    desktop_main()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("PhotogramQC", traceback.format_exc())
        except Exception:
            pass
        sys.exit(1)

