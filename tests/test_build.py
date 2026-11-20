"""Testes de build — validam que o projeto compila e esta pronto para PyInstaller."""

import ast
import os
import re
import sys
import py_compile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Arquivos que devem compilar sem erro
GUI_FILES = [
    "app.py",
    "gui/__init__.py",
    "gui/main_window.py",
    "gui/helpers.py",
    "gui/styles.py",
    "gui/computer_tab.py",
    "gui/program_tab.py",
    "gui/network_tab.py",
    "gui/printer_tab.py",
]
MODULE_FILES = [
    "modules/__init__.py",
    "modules/config.py",
    "modules/theme.py",
    "modules/security.py",
    "modules/temp_cleaner.py",
    "modules/speedtest.py",
    "modules/datetime_sync.py",
    "modules/anota_process.py",
    "modules/uninstaller.py",
    "modules/maintenance.py",
    "modules/network_tools.py",
    "modules/printer_diagnostics.py",
    "modules/resource_monitor.py",
    "modules/windows_events.py",
    "modules/windows_update.py",
    "modules/whatsapp_status.py",
    "modules/compatibility_check.py",
    "modules/system_info.py",
    "modules/cpu_monitor.py",
    "modules/report.py",
]
ALL_FILES = GUI_FILES + MODULE_FILES


def test_all_compile():
    """Todos os arquivos devem compilar sem erro de sintaxe."""
    for f in ALL_FILES:
        path = os.path.join(ROOT, f)
        if not os.path.exists(path):
            raise AssertionError(f"Arquivo nao existe: {f}")
        try:
            py_compile.compile(path, doraise=True)
        except py_compile.PyCompileError as e:
            raise AssertionError(f"Erro de compilacao em {f}: {e}")
    print(f"PASSOU: {len(ALL_FILES)} arquivos compilam sem erro")


def test_no_relative_imports():
    """Imports relativos (from .X) nao funcionam no PyInstaller onefile."""
    for f in GUI_FILES:
        if f.endswith("__init__.py"):
            continue  # __init__.py usa imports relativos por natureza do pacote
        path = os.path.join(ROOT, f)
        if not os.path.exists(path):
            continue
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    raise AssertionError(
                        f"Import relativo em {f} linha {node.lineno}: "
                        f"from {'.' * node.level}{node.module or ''}"
                    )
    print("PASSOU: nenhum import relativo nos arquivos gui/")


def test_main_window_file_name():
    """Deve existir main_window.py (nao main_windows.py)."""
    assert os.path.exists(os.path.join(ROOT, "gui", "main_window.py")), "main_window.py nao existe"
    assert not os.path.exists(os.path.join(ROOT, "gui", "main_windows.py")), "main_windows.py ainda existe!"
    print("PASSOU: arquivo se chama main_window.py (sem 's')")


def test_theme_exports_all():
    """Todos os nomes usados com 'from modules.theme import *' devem existir em __all__."""
    theme_path = os.path.join(ROOT, "modules", "theme.py")
    theme_src = open(theme_path, encoding="utf-8").read()

    # Extrair __all__
    all_match = re.search(r"__all__\s*=\s*\[(.*?)\]", theme_src, re.DOTALL)
    assert all_match, "theme.py nao tem __all__"
    all_names = set(re.findall(r'"(\w+)"', all_match.group(1)))

    # Extrair nomes definidos
    tree = ast.parse(theme_src)
    defined = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    defined.add(t.id)

    missing = all_names - defined
    assert not missing, f"__all__ contem nomes nao definidos: {missing}"
    print(f"PASSOU: __all__ do theme.py tem {len(all_names)} nomes validos")


def test_env_get_two_args():
    """os.environ.get nao deve receber 3 argumentos (bug do Mapping.get)."""
    for f in ALL_FILES:
        path = os.path.join(ROOT, f)
        if not os.path.exists(path):
            continue
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "get":
                        if isinstance(node.func.value, ast.Attribute):
                            if node.func.value.attr == "environ":
                                if len(node.args) > 2:
                                    raise AssertionError(
                                        f"os.environ.get com 3+ args em {f} linha {node.lineno}"
                                    )
    print("PASSOU: nenhum os.environ.get com mais de 2 argumentos")


def test_self_in_methods():
    """Metodos de classe devem ter self como primeiro parametro."""
    for f in GUI_FILES:
        path = os.path.join(ROOT, f)
        if not os.path.exists(path):
            continue
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        if item.args.args:
                            first = item.args.args[0].arg
                            # Metodos magicos __X__ ou estaticos podem nao ter self
                            if not item.name.startswith("__") and not any(
                                isinstance(d, ast.Name) and d.id == "staticmethod"
                                for d in item.decorator_list
                            ):
                                if first not in ("self", "cls"):
                                    raise AssertionError(
                                        f"Metodo {item.name} em {f} sem self/cls (linha {item.lineno})"
                                    )
    print("PASSOU: todos os metodos tem self ou cls")


def test_app_entry_point():
    """app.py deve importar de gui (nao de gui.py)."""
    path = os.path.join(ROOT, "app.py")
    src = open(path, encoding="utf-8").read()
    assert "from gui import" in src, "app.py deveria importar de gui/"
    assert "_ensure_admin" in src, "app.py deveria chamar _ensure_admin()"
    print("PASSOU: app.py importa de gui/ e chama _ensure_admin")


def test_requirements_no_speedtest_cli():
    """speedtest-cli nao deve estar no requirements (usamos curl agora)."""
    path = os.path.join(ROOT, "requirements.txt")
    src = open(path, encoding="utf-8").read()
    assert "speedtest-cli" not in src.lower(), "speedtest-cli ainda no requirements.txt"
    assert "psutil" in src, "psutil deveria estar no requirements"
    print("PASSOU: requirements.txt sem speedtest-cli")


if __name__ == "__main__":
    tests = [
        test_all_compile,
        test_no_relative_imports,
        test_main_window_file_name,
        test_theme_exports_all,
        test_env_get_two_args,
        test_self_in_methods,
        test_app_entry_point,
        test_requirements_no_speedtest_cli,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"FALHOU: {t.__name__}: {e}")
            failed += 1
    print(f"\n=== {passed} passaram, {failed} falharam ===")
    if failed:
        sys.exit(1)
