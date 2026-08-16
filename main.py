"""Windows TXT novel reader MVP entry point."""

from __future__ import annotations

from reader.platform.dpi_awareness import configure as configure_dpi_awareness
from reader.platform.tk_runtime import configure as configure_tk_runtime

configure_dpi_awareness()
configure_tk_runtime()

import tkinter as tk

from reader.app import ReaderApp


def main() -> None:
    root = tk.Tk()
    ReaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
