"""Ponto de entrada da interface gráfica do SuporteTools."""

from gui import SystemInfoApp
from gui.helpers import _ensure_admin


def main() -> None:
    _ensure_admin() 
    import tkinter as tk

    root = tk.Tk()
    SystemInfoApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
