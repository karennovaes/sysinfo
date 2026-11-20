"""Ponto de entrada da interface gráfica do SuporteTools."""

from gui import SystemInfoApp
from gui.helpers import _ensure_admin


def main() -> None:
    # Solicita elevação ANTES de criar a janela. Sem isso, comandos que
    # exigem administrador (w32tm, sc config, reg add) falham com acesso negado.
    _ensure_admin()

    import tkinter as tk

    root = tk.Tk()
    SystemInfoApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
