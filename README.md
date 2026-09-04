# Diagnóstico do Sistema

Aplicativo de terminal para coletar informações básicas do computador, acompanhar o uso da CPU e testar a velocidade da internet.

> O programa foi escrito para Python 3 e pode ser empacotado como um executável Windows com o PyInstaller.

## Estrutura

- `main.py`: ponto de entrada e orquestração das etapas.
- `modules/system_info.py`: informações do sistema, processador, memória, Windows, rede e disco.
- `modules/cpu_monitor.py`: monitoramento do uso da CPU.
- `modules/speedtest.py`: teste de ping, download e upload.

## Uso durante o desenvolvimento

1. Instale o Python 3.
2. Instale as dependências:

   ```bash
   python -m pip install -r requirements.txt
   ```

3. Execute:

   ```bash
   python main.py
   ```

## Gerar o executável `.exe`

A geração de um `.exe` Windows deve ser feita em uma máquina Windows (o PyInstaller não faz cross-compilação entre sistemas operacionais):

```bash
python -m pip install -r requirements.txt
pyinstaller --onefile main.py
```

O arquivo será criado em `dist/main.exe`. Ele poderá ser executado em um computador Windows sem Python instalado.

## Observações

- O teste de velocidade depende de acesso à internet e pode falhar em redes com proxy, firewall ou sem conectividade. Nesse caso, o diagnóstico continua e informa o erro.
- O monitor de CPU dura aproximadamente 10 segundos, com uma leitura por segundo.
- Ao terminar, o programa aguarda `Enter`, o que permite usá-lo em uma sessão remota.

## Saída do diagnóstico

A tela apresenta processador, placa-mãe (quando disponível), quantidade de núcleos físicos e lógicos, memória RAM total e disponível, nome/versão/build do sistema, hostname, IP local e capacidade do disco. Em seguida, exibe dez leituras de CPU e a média do período, e tenta medir ping, download e upload.
