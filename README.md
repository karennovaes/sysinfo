# Diagnóstico do Sistema

Aplicativo de terminal que coleta informações do computador e da conexão de internet.

## Funcionalidades

- **Informações do sistema:** processador, placa-mãe, núcleos, RAM, versão do Windows, disco, hostname e IP local
- **Monitor de CPU:** uso da CPU em tempo real por 10 segundos com média final
- **Data, hora e sincronização:** data, hora, fuso horário, offset UTC, horário de verão, status da sincronização automática e tentativa de sincronização NTP no Windows
- **Teste de velocidade:** download, upload e ping

## Instalação

```bash
pip install -r requirements.txt
```

O módulo de data e hora usa `tzlocal` para identificar o fuso horário local. No Windows, a sincronização é solicitada pelo comando `w32tm /resync`; o aplicativo não altera automaticamente a configuração do sistema.

## Uso

```bash
python main.py
```

## Gerar executável (.exe)

> **Importante:** o .exe deve ser gerado em uma máquina Windows, pois o PyInstaller não faz cross-compilação.

```bash
pyinstaller --onefile main.py
```

O executável estará em `dist/main.exe`.

## Dica de commit

```
fix: reescreve arquivos para garantir integridade
```
