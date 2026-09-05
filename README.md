# Diagnóstico do Sistema

Aplicativo de diagnóstico do computador e da conexão de internet. O projeto possui uma interface gráfica em Tkinter, com o visual da Anota AI/iFood, e mantém a versão de terminal como fallback.

## Funcionalidades

- **Verificação de compatibilidade Anota AI:** processador, RAM, armazenamento SSD e sistema operacional, com mensagens coloridas para cada requisito
- **Informações do sistema:** processador, placa-mãe, núcleos, RAM, versão do Windows, disco, hostname e IP local
- **Monitor de CPU:** uso da CPU em tempo real por 10 segundos com média final
- **Data, hora e sincronização:** data, hora, fuso horário, offset UTC, horário de verão, status da sincronização automática e tentativa de sincronização NTP no Windows
- **Teste de velocidade:** download, upload e ping

## Interface gráfica

A GUI é aberta pelo arquivo `gui.py` e tem o título **Diagnóstico do Sistema — Anota AI**. Ela oferece os botões:

- **Verificar Compatibilidade**
- **Informações do Sistema**
- **Monitor de CPU**
- **Data, Hora e Sincronização**
- **Teste de Velocidade**
- **Executar Tudo**
- **Limpar** e **Sair**

Os diagnósticos são executados em uma thread separada para que a janela continue responsiva. Enquanto uma operação está em execução, os botões ficam desabilitados e o status mostra **Executando...**. Os resultados impressos pelos módulos são capturados e exibidos na área de texto com rolagem. A GUI traduz os destaques ANSI existentes para as cores de resultado positivo e negativo.

A interface usa apenas Tkinter, biblioteca nativa do Python. O cabeçalho e os botões usam o vermelho `#EA1D2F`, com fundo branco, texto de resultado cinza escuro `#3F3E3E`, destaque positivo `#2E7D32` e destaque negativo `#C62828`.

## Instalação

```bash
pip install -r requirements.txt
```

A primeira seção verifica se o computador atende aos requisitos mínimos do Anota AI: Intel Core i5/i7/i9 ou AMD Ryzen 5/7/9, pelo menos 8 GB de RAM (12 GB ideal), SSD de pelo menos 120 GB e Windows 10/11 de 64 bits. A identificação do tipo de armazenamento usa WMIC ou PowerShell no Windows; quando não é possível identificar o tipo, o resultado é exibido como não verificado.

O módulo de data e hora usa `tzlocal` para identificar o fuso horário local. No Windows, a sincronização é solicitada pelo comando `w32tm /resync`; o aplicativo não altera automaticamente a configuração do sistema além da tentativa de sincronização solicitada pela funcionalidade.

## Uso

### Interface gráfica

```bash
python gui.py
```

### Terminal (fallback)

```bash
python main.py
```

A função `_ensure_admin()` solicita elevação UAC no Windows antes da execução, tanto na GUI quanto no fallback de terminal.

## Gerar executável (.exe)

> **Importante:** o `.exe` deve ser gerado em uma máquina Windows, pois o PyInstaller não faz cross-compilação.

Para gerar a versão gráfica como um único executável, execute na pasta do projeto:

```bash
python -m PyInstaller --onefile --windowed gui.py
```

A opção `--windowed` esconde a janela do console ao iniciar a aplicação gráfica. O executável estará em `dist/gui.exe`.

Para gerar opcionalmente a versão de terminal:

```bash
python -m PyInstaller --onefile main.py
```
