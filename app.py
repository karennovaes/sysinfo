"""Ponto de entrada da interface gráfica do SuporteTools."""

from gui import SystemInfoApp


def main() -> None:
    import tkinter as tk

    root = tk.Tk()
    SystemInfoApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
