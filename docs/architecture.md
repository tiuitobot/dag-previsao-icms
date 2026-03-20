# Arquitetura

## Visão geral

```text
01-download-dados
        ↓
02-preparacao-base
        ↓
03-modelagem
        ↓
04-previsoes ──→ 05-analise-qualitativa (copilot_cli, opcional) ──→ 06-cenarios (copilot_cli, opcional)
        ↓                                                           ↘
07-visualizacao ----------------------------------------------------→ 08-relatorio-narrativa (copilot_cli, opcional)
                                                                        ↓
                                                                  09-pdf-output
```

## Padrão de execução
- Steps determinísticos: scripts Python independentes, I/O por JSON em `workspace/outputs/active/`.
- Steps AI: contratos explícitos + wrapper `copilot_cli_runner.py`.
- Estado do pipeline: `workspace/outputs/active/pipeline-state.json`.

## Observações de design
- A matemática SARIMAX foi preservada do repo fonte e encapsulada em `scripts/forecast_core.py`.
- O step 03 valida os modelos; o step 04 refaz o fit final para manter serialização simples em JSON sem depender de pickle.
- O DAG foi desenhado para aceitar camadas de inteligência sem misturar texto gerado com cálculos determinísticos.
