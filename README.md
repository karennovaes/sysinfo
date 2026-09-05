# Diagnóstico do Sistema — Anota AI

Aplicativo para diagnóstico do computador e da conexão de internet, com interface gráfica em Tkinter e uma versão de terminal como fallback. A ferramenta reúne verificações úteis para o atendimento da Anota AI em um único lugar.

## Funcionalidades

- **Interface gráfica:** execução dos diagnósticos em uma janela responsiva, com resultados coloridos e barra de rolagem.
- **Compatibilidade com a Anota AI:** verifica processador, memória RAM, armazenamento SSD e sistema operacional.
- **Informações do sistema:** exibe processador, placa-mãe, núcleos, RAM, Windows, discos, hostname e IP local.
- **Monitor de CPU:** acompanha o uso da CPU por aproximadamente 10 segundos e apresenta a média.
- **Data, hora e NTP:** informa data, hora, fuso horário, offset UTC e estado da sincronização automática; no Windows, também tenta sincronizar pelo serviço Windows Time.
- **Teste de velocidade:** mede ping, download e upload.
- **Limpeza de temporários e cache:** remove arquivos temporários do usuário e do sistema e o cache local da Anota AI, ignorando arquivos em uso.
- **Comandos de suporte:** acesso às impressoras, download do instalador universal de drivers e download do Anota AI Desktop.
- **Versão de terminal:** permite executar os diagnósticos sem a interface gráfica.

## Estrutura do projeto

```text
.
├── .github/
│   └── workflows/
│       └── build-exe.yml
├── .gitignore
├── README.md
├── gui.py
├── main.py
├── modules/
│   ├── __init__.py
│   ├── compatibility_check.py
│   ├── system_info.py
│   ├── cpu_monitor.py
│   ├── datetime_sync.py
│   ├── speedtest.py
│   └── temp_cleaner.py
└── requirements.txt
```

## Como rodar localmente

Recomenda-se Python 3.11 ou superior compatível com as dependências do projeto. Na pasta do repositório, instale os pacotes:

```bash
python -m pip install -r requirements.txt
```

Para abrir a interface gráfica:

```bash
python gui.py
```

Para usar a versão de terminal:

```bash
python main.py
```

A verificação de compatibilidade considera como referência processadores Intel Core i5/i7/i9 ou AMD Ryzen 5/7/9, pelo menos 8 GB de RAM (12 GB ideal), SSD de pelo menos 120 GB e Windows 10/11 de 64 bits. Quando uma informação não pode ser identificada, o resultado é mostrado como não verificado.

## Gerar o executável manualmente

O PyInstaller precisa ser executado no Windows para gerar um `.exe` Windows. Com as dependências instaladas, execute:

```bash
pyinstaller --onefile --windowed gui.py
```

O arquivo será criado como `dist/gui.exe`. Para usar o mesmo nome amigável do build automático:

```bash
python -m PyInstaller --onefile --windowed --name "DiagnosticoSistema-AnotaAI" gui.py
```

Nesse caso, o arquivo será `dist/DiagnosticoSistema-AnotaAI.exe`.

## GitHub Actions e Releases

O workflow `.github/workflows/build-exe.yml` é executado automaticamente em:

- push para `main` ou `master`;
- pull request para `main` ou `master`;
- execução manual pelo botão **Run workflow** na aba **Actions**.

A automação usa `windows-latest` e Python 3.11, instala `requirements.txt` e compila `gui.py` como `DiagnosticoSistema-AnotaAI.exe`. O executável fica disponível como artifact da execução. Em pushes para `main` ou `master`, o workflow também cria uma Release com a tag `v< número da execução >` e anexa o `.exe` na aba **Releases**.

Para publicar uma nova versão, faça commit e push na branch principal:

```bash
git add .
git commit -m "descrição da alteração"
git push origin main
```

Pull requests executam o build para validação, mas a Release automática só é criada quando o push ocorre diretamente em `main` ou `master`.

## Observação sobre permissões (UAC)

No Windows, o aplicativo solicita automaticamente elevação pelo UAC quando necessário. Confirme a janela de administrador para permitir os diagnósticos que dependem de permissões elevadas, como sincronização de horário e limpeza de pastas do sistema. Em outros sistemas operacionais, a solicitação de UAC não se aplica.

