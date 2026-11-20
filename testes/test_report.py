"""Testes do módulo report.py — parsing e classificação do relatório enxuto."""

import sys
sys.path.insert(0, "..")

from modules.report import build_report, _extract_sections


# --- Helpers ---

def _section(title, *lines):
    """Gera uma seção no formato de saída do _run_sections."""
    sep = "=" * 59
    dash = "-" * 59
    body = "\n".join(lines)
    return f"\n{sep}\n{title}\n{sep}\n{body}\n{dash}\n"


def assert_eq(actual, expected, msg=""):
    if actual != expected:
        raise AssertionError(f"{msg}\n  esperado: {expected!r}\n  obtido:   {actual!r}")


def assert_contains(haystack, needle, msg=""):
    if needle not in haystack:
        raise AssertionError(f"{msg}\n  deveria conter: {needle!r}\n  em: {haystack!r}")


def assert_not_contains(haystack, needle, msg=""):
    if needle in haystack:
        raise AssertionError(f"{msg}\n  NAO deveria conter: {needle!r}\n  em: {haystack!r}")


# --- Testes ---

def test_empty_output():
    """Saída vazia deve gerar 'Nenhum procedimento'."""
    r = build_report("")
    assert_contains(r, "Nenhum procedimento", "saida vazia")


def test_all_ok():
    """Tudo OK — nenhum 'ATENCAO' no relatório."""
    raw = _section("LIMPEZA DE CACHE", "Limpeza: 50 arquivos removidos, 12.0 MB liberados")
    raw += _section("VERIFICACAO DE COMPATIBILIDADE", "Processador: compativel", "RAM: 16 GB compativel")
    r = build_report(raw)
    assert_not_contains(r, "ATENCAO", "tudo OK nao deveria ter atencao")
    assert_contains(r, "Cache limpo", "deveria ter cache")
    assert_contains(r, "compat", "deveria ter compativel")


def test_problems_detected():
    """Saída com problemas deve ter 'ATENCAO'."""
    raw = _section("STATUS DO WHATSAPP", "WhatsApp desconectado")
    raw += _section("VERIFICACAO DE COMPATIBILIDADE", "Processador: incompativel", "RAM: 4 GB incompativel")
    r = build_report(raw)
    assert_contains(r, "WhatsApp desconectado", "deveria ter whatsapp")
    assert_contains(r, "abaixo do recomendado", "deveria ter compatibilidade")


def test_negation_not_problem():
    """'nenhum expirado' deve ser OK, nao problema."""
    raw = _section("SINCRONIZACAO DE HORA", "Certificados SSL: nenhum expirado")
    r = build_report(raw)
    assert_not_contains(r, "ATENCAO", "nenhum expirado nao e problema")


def test_speedtest_format():
    """Teste de velocidade deve gerar frase com download, upload e ping."""
    raw = _section("TESTE DE VELOCIDADE", "Internet: 100.5 Mbps download, 50.2 Mbps upload, 15ms ping")
    r = build_report(raw)
    assert_contains(r, "100.5 Mbps de download", "deveria ter download")
    assert_contains(r, "50.2 Mbps de upload", "deveria ter upload")
    assert_contains(r, "15", "deveria ter ping")


def test_cache_zero():
    """Cache com 0 arquivos deve dizer 'ja estava limpo'."""
    raw = _section("LIMPEZA DE CACHE", "Limpeza: 0 arquivos removidos, 0.0 MB liberados")
    r = build_report(raw)
    assert_contains(r.lower(), "limpo", "0 arquivos = limpo")
    assert_contains(r, "nada a remover", "0 arquivos = limpo")


def test_windows_update_pending():
    """Windows Update com pendências."""
    raw = _section("WINDOWS UPDATE", "3 atualizacoes pendentes")
    r = build_report(raw)
    assert_contains(r, "3 atualiza", "deveria ter pendentes")
    assert_contains(r, "pendente", "deveria ter pendentes")


def test_windows_update_none():
    """Windows Update sem pendências."""
    raw = _section("WINDOWS UPDATE", "Nenhuma atualizacao pendente")
    r = build_report(raw)
    assert_contains(r, "Windows atualizado", "sem pendencias = atualizado")


def test_events_zero():
    """Eventos do Windows sem erros."""
    raw = _section("EVENTOS DO WINDOWS", "0 erros encontrados")
    r = build_report(raw)
    assert_contains(r, "Nenhum erro cr", "0 erros = nenhum")


def test_events_some():
    """Eventos do Windows com erros."""
    raw = _section("EVENTOS DO WINDOWS", "5 erros encontrados")
    r = build_report(raw)
    assert_contains(r, "5 erro", "deveria ter erros")


def test_antivirus_active():
    raw = _section("STATUS DO ANTIVIRUS", "Antivirus ativo e protegendo")
    r = build_report(raw)
    assert_contains(r, "ativo e protegendo", "deveria estar ativo")


def test_antivirus_disabled():
    raw = _section("STATUS DO ANTIVIRUS", "Antivirus desativado")
    r = build_report(raw)
    assert_contains(r, "desativado", "deveria estar desativado")
    assert_contains(r, "recomenda", "deveria recomendar ativar")


def test_client_name():
    raw = _section("LIMPEZA DE CACHE", "Limpeza: 10 arquivos removidos, 2.0 MB liberados")
    r = build_report(raw, "Mercado Bela Vista")
    assert_contains(r, "Mercado Bela Vista", "deveria ter nome do cliente")


def test_dedup():
    """Seções duplicadas nao devem gerar linhas repetidas."""
    raw = _section("LIMPEZA DE CACHE", "Limpeza: 10 arquivos removidos, 2.0 MB liberados")
    raw += _section("LIMPEZA DE CACHE", "Limpeza: 10 arquivos removidos, 2.0 MB liberados")
    r = build_report(raw)
    # So deve aparecer uma vez
    count = r.count("Cache limpo")
    assert_eq(count, 1, "deveria aparecer so uma vez")


if __name__ == "__main__":
    tests = [
        test_empty_output, test_all_ok, test_problems_detected,
        test_negation_not_problem, test_speedtest_format, test_cache_zero,
        test_windows_update_pending, test_windows_update_none,
        test_events_zero, test_events_some, test_antivirus_active,
        test_antivirus_disabled, test_client_name, test_dedup,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASSOU: {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FALHOU: {t.__name__}: {e}")
            failed += 1
    print(f"\n=== {passed} passaram, {failed} falharam ===")
    if failed:
        sys.exit(1)
