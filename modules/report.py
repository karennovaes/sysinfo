"""Relatório enxuto dos procedimentos executados, pronto para o cliente.

A saída bruta continua no terminal para o agente. Aqui geramos apenas um
resumo curto, em linguagem simples, que o cliente consegue ler e entender.
"""

from __future__ import annotations

import re
from datetime import datetime

# ---------------------------------------------------------------------------
# Extração das seções da saída bruta
# ---------------------------------------------------------------------------

_SEPARATOR_EQ = re.compile(r"^={10,}$")
_SEPARATOR_DASH = re.compile(r"^-{10,}$")


def _clean(line: str) -> str:
    """Remove códigos ANSI e espaços sobrando."""
    return re.sub(r"\x1b\[[0-9;]*m", "", line).strip()


def _extract_sections(raw_output: str) -> list[tuple[str, list[str]]]:
    """Divide a saída bruta em seções no formato TÍTULO entre separadores."""
    sections: list[tuple[str, list[str]]] = []
    current_title: str | None = None
    current_lines: list[str] = []
    pending_title: str | None = None
    separators_seen = 0

    for raw_line in raw_output.splitlines():
        line = _clean(raw_line)
        if _SEPARATOR_EQ.match(line):
            separators_seen += 1
            if separators_seen == 2 and pending_title is not None:
                if current_title is not None:
                    sections.append((current_title, current_lines))
                current_title = pending_title
                current_lines = []
                pending_title = None
                separators_seen = 0
            continue
        if _SEPARATOR_DASH.match(line):
            continue
        if separators_seen == 1:
            if line:
                pending_title = line
            continue
        if current_title is None:
            continue
        if line:
            current_lines.append(line)

    if current_title is not None:
        sections.append((current_title, current_lines))
    return sections


# ---------------------------------------------------------------------------
# Regras por tipo de verificação
# ---------------------------------------------------------------------------

# Cada regra recebe as linhas da seção e devolve uma frase curta para o cliente
# (ou None quando não há nada relevante a dizer).


def _rule_cache(lines: list[str]) -> str | None:
    """Limpeza de cache: quantos arquivos e quanto espaço."""
    for line in lines:
        match = re.search(
            r"(\d+)\s+arquivos?\s+removidos?,\s*([\d.,]+)\s*MB", line, re.IGNORECASE
        )
        if match:
            count, mb = match.group(1), match.group(2)
            if count == "0":
                return "Cache já estava limpo, nada a remover."
            return f"Cache limpo: {count} arquivos removidos ({mb} MB liberados)."
    return None


def _rule_time(lines: list[str]) -> str | None:
    """Sincronização de hora: sucesso ou falha."""
    joined = " ".join(lines).casefold()
    if "resultado:" in joined:
        if "configurados e sincronizados" in joined:
            return "Data e hora sincronizadas com o servidor oficial."
        if "falharam" in joined or "falha" in joined:
            return "Não foi possível ajustar a data e hora automaticamente."
    if "sincronizado com sucesso" in joined:
        return "Data e hora sincronizadas com o servidor oficial."
    return None


def _rule_compatibility(lines: list[str]) -> str | None:
    """Compatibilidade: lista o que está fora do recomendado."""
    problems: list[str] = []
    for line in lines:
        lowered = line.casefold()
        if "incompat" in lowered or "abaixo" in lowered or "insuficiente" in lowered:
            label = line.split(":")[0].strip()
            if label and label not in problems:
                problems.append(label)
    if problems:
        return "Configuração abaixo do recomendado: " + ", ".join(problems) + "."
    if any("compat" in line.casefold() for line in lines):
        return "Computador compatível com o Anota AI."
    return None


def _rule_antivirus(lines: list[str]) -> str | None:
    """Antivírus: ativo ou não."""
    joined = " ".join(lines).casefold()
    if "desativad" in joined or "desligad" in joined:
        return "Antivírus desativado — recomenda-se manter a proteção ativa."
    if "ativad" in joined or "protegid" in joined:
        return "Antivírus ativo e protegendo o computador."
    return None


def _rule_events(lines: list[str]) -> str | None:
    """Eventos do Windows: quantidade de erros críticos."""
    for line in lines:
        match = re.search(r"(\d+)\s+erros?", line, re.IGNORECASE)
        if match:
            count = int(match.group(1))
            if count == 0:
                return "Nenhum erro crítico registrado no Windows."
            return f"{count} erro(s) registrado(s) no Windows."
    return None


def _rule_update(lines: list[str]) -> str | None:
    """Windows Update: pendências."""
    joined = " ".join(lines).casefold()
    if "nenhuma atualiza" in joined or "tudo atualizado" in joined:
        return "Windows atualizado."
    for line in lines:
        match = re.search(r"(\d+)\s+atualiza", line, re.IGNORECASE)
        if match:
            count = int(match.group(1))
            if count == 0:
                return "Windows atualizado."
            return f"{count} atualização(ões) do Windows pendente(s)."
    return None


def _rule_speed(lines: list[str]) -> str | None:
    """Teste de velocidade: download, upload e ping."""
    for line in lines:
        match = re.search(
            r"([\d.,]+)\s*Mbps\s*download.*?([\d.,]+)\s*Mbps\s*upload.*?([\d.,]+)\s*ms",
            line,
            re.IGNORECASE,
        )
        if match:
            down, up, ping = match.groups()
            return f"Internet: {down} Mbps de download, {up} Mbps de upload, {ping} ms."
    return None


def _rule_processes(lines: list[str]) -> str | None:
    """Processos do Anota AI: rodando ou não."""
    joined = " ".join(lines).casefold()
    if "nenhum" in joined and "processo" in joined:
        return "Anota AI não está em execução no momento."
    for line in lines:
        match = re.search(r"(\d+)\s+processos?", line, re.IGNORECASE)
        if match:
            count = int(match.group(1))
            if count == 0:
                return "Anota AI não está em execução no momento."
            return f"Anota AI em execução ({count} processo(s))."
    return None


def _rule_whatsapp(lines: list[str]) -> str | None:
    """Status do WhatsApp: conectado ou não."""
    joined = " ".join(lines).casefold()
    if "desconectad" in joined or "não conectad" in joined or "nao conectad" in joined:
        return "WhatsApp desconectado — é preciso ler o QR Code novamente."
    if "conectad" in joined:
        return "WhatsApp conectado."
    return None


def _rule_printer(lines: list[str]) -> str | None:
    """Diagnóstico de impressoras: resumo do health score."""
    for line in lines:
        match = re.search(r"health\s*score[:\s]*(\d+)", line, re.IGNORECASE)
        if match:
            score = int(match.group(1))
            if score >= 80:
                return f"Impressora saudável (nota {score}/100)."
            if score >= 50:
                return f"Impressora com atenção (nota {score}/100)."
            return f"Impressora com problemas (nota {score}/100)."
    joined = " ".join(lines).casefold()
    if "nenhuma impressora" in joined:
        return "Nenhuma impressora instalada."
    return None


def _rule_network(lines: list[str]) -> str | None:
    """Rede: proxy, VPN, firewall."""
    joined = " ".join(lines).casefold()
    if "proxy ativo" in joined or "proxy habilitado" in joined:
        return "Proxy ativo na máquina — pode interferir na conexão."
    if "vpn" in joined and ("conectad" in joined or "ativa" in joined):
        return "VPN ativa — pode interferir na conexão."
    if "firewall" in joined and "desativad" in joined:
        return "Firewall do Windows desativado."
    return None


def _rule_uninstall(lines: list[str]) -> str | None:
    """Desinstalação: concluída ou não."""
    joined = " ".join(lines).casefold()
    if "desinstala" in joined and ("conclu" in joined or "removid" in joined):
        return "Anota AI desinstalado completamente."
    return None


def _rule_download(lines: list[str]) -> str | None:
    """Download: concluído."""
    for line in lines:
        if "download concluído" in line.casefold():
            return "Download concluído."
    return None


_RULES = (
    ("LIMPEZA", _rule_cache),
    ("SINCRONIZA", _rule_time),
    ("COMPATIBILIDADE", _rule_compatibility),
    ("ANTIV", _rule_antivirus),
    ("EVENTOS", _rule_events),
    ("WINDOWS UPDATE", _rule_update),
    ("VELOCIDADE", _rule_speed),
    ("PROCESSOS", _rule_processes),
    ("WHATSAPP", _rule_whatsapp),
    ("IMPRESSORA", _rule_printer),
    ("REDE", _rule_network),
    ("DESINSTALA", _rule_uninstall),
    ("DOWNLOAD", _rule_download),
)


def _summarize_section(title: str, lines: list[str]) -> str | None:
    """Aplica a regra correspondente ao título da seção."""
    upper = title.upper()
    for marker, rule in _RULES:
        if marker in upper:
            return rule(lines)
    return None


# ---------------------------------------------------------------------------
# Montagem do relatório
# ---------------------------------------------------------------------------


def build_report(raw_output: str, client_name: str = "") -> str:
    """Monta um relatório curto, em linguagem simples, para o cliente."""
    sections = _extract_sections(raw_output)
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    items: list[str] = []
    for title, lines in sections:
        summary = _summarize_section(title, lines)
        if summary and summary not in items:
            items.append(summary)

    header = "RELATÓRIO DE ATENDIMENTO"
    if client_name.strip():
        header += f" — {client_name.strip()}"

    output = [header, f"Data: {now}", ""]
    if not items:
        output.append("Nenhum procedimento registrado nesta sessão.")
        return "\n".join(output)

    for item in items:
        output.append(f"• {item}")

    return "\n".join(output)


def display_report(raw_output: str, client_name: str = "") -> None:
    """Imprime o relatório enxuto."""
    print(build_report(raw_output, client_name))
