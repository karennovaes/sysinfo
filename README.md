# 🔧 SuporteTools— Anota AI

Ferramenta de diagnóstico para suporte técnico remoto. Um único executável que coleta informações do sistema, verifica compatibilidade com os requisitos do Anota AI, sincroniza data/hora, testa internet, limpa temporários e oferece atalhos de suporte.

---

## ✨ Funcionalidades

| Recurso | Descrição |
|---|---|
| **Compatibilidade Anota AI** | Verifica processador, RAM, SSD e Windows contra os requisitos mínimos |
| **Informações do Sistema** | Processador, RAM, SO, IP e todos os discos com espaço livre |
| **Monitor de CPU** | Média de uso da CPU em 10 leituras |
| **Data, Hora e NTP** | Sincroniza relógio com servidor NTP automaticamente |
| **Teste de Velocidade** | Mede download, upload e ping |
| **Limpeza de Temporários** | Limpa %TEMP%, C:\Windows\Temp e cache do Anota AI |
| **Comandos de Suporte** | Abre impressoras, baixa drivers e Anota AI Desktop |
| **Segurança** | Validação de URLs, hash SHA-256 e log de auditoria |
| **SAST** | Scan automático de vulnerabilidades com Bandit no CI/CD |

---

## 🎨 Interface

Layout limpo com botões na lateral esquerda e terminal à direita. Cores da marca Anota AI/iFood (vermelho `#EA1D2F` + branco). Barra de progresso durante execução. Relatório otimizado para copiar e colar no chat de suporte.

---

## 🚀 Como usar

### Baixar o executável

1. Acesse a aba **Releases** no GitHub
2. Baixe o `SuporteTools-AnotaAI.exe`
3. Execute — o programa pede permissão de administrador automaticamente

### Rodar pelo código-fonte

```bash
pip install -r requirements.txt
python gui.py          # interface gráfica
python main.py         # modo terminal
```

---

## 🎨 Interface

Layout limpo com botões na lateral esquerda e terminal à direita. Cores da marca Anota AI/iFood (vermelho `#EA1D2F` + branco). Barra de progresso durante execução. Relatório otimizado para copiar e colar no chat de suporte.

---
