# dag-previsao-icms

Pipeline DAG para previsão de arrecadação do ICMS-SP, reorganizando o SARIMAX monolítico do repo `previsao-icms-sp` em etapas independentes, versionáveis e prontas para convivência entre cálculo determinístico e steps assistidos por Copilot CLI.

## O que faz
- lê a base histórica consolidada em Excel;
- prepara exógenas e features (lags, dummies, dias úteis);
- ajusta 5 modelos SARIMAX preservando a especificação do projeto original;
- executa validação out-of-sample;
- gera previsões futuras com ensemble + Monte Carlo;
- produz gráficos, HTML e PDF final;
- reserva 3 steps opcionais para análise qualitativa, cenários e narrativa com `copilot_cli`.

## Arquitetura do DAG

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

## Estrutura

```text
dag-previsao-icms/
├── README.md
├── requirements.txt
├── .gitignore
├── .env.example
├── plans/pipeline-graph.json
├── contracts/
├── scripts/
│   ├── run_pipeline.py
│   ├── copilot_cli_runner.py
│   ├── common.py
│   ├── forecast_core.py
│   └── steps/
├── data/raw/
├── workspace/outputs/active/
├── docs/
└── templates/relatorio.html.j2
```

## Modelos SARIMAX documentados

| Modelo | Especificação | Exógenas |
|---|---|---|
| M1 | SARIMA(1,1,1)(0,0,0,12) | dias úteis + dummies |
| M2 | SARIMAX(3,1,0)(2,0,0,12) | igp_di_lag1, ibc_br_lag1, dias úteis + dummies |
| M3 | SARIMAX(0,1,1)(0,1,1,12) | igp_di, ibc_br, ibc_br_lag1, dias úteis + dummies |
| M4 | SARIMAX(0,1,1)(0,1,2,12) | ibc_br, ibc_br_lag1, dias úteis + dummies |
| M5 | SARIMAX(0,1,1)(0,1,2,12) | igp_di, ibc_br, ibc_br_lag1 + dummies |

## Instalação

```bash
cd ~/repos/dag-previsao-icms
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Como rodar

### 1) Listar o DAG
```bash
python scripts/run_pipeline.py --list
```

### 2) Rodar sem Copilot
```bash
python scripts/run_pipeline.py
```

### 3) Rodar com Copilot CLI
```bash
unset GITHUB_TOKEN
python scripts/run_pipeline.py --with-copilot
```

### 4) Rodar step isolado
```bash
python scripts/steps/step_01_download_dados.py --output workspace/outputs/active
python scripts/steps/step_02_preparacao_base.py --input-dir workspace/outputs/active --output workspace/outputs/active
python scripts/steps/step_03_modelagem.py --input-dir workspace/outputs/active --output workspace/outputs/active
python scripts/steps/step_04_previsoes.py --input-dir workspace/outputs/active --output workspace/outputs/active --n-simulacoes 1000
python scripts/steps/step_07_visualizacao.py --input-dir workspace/outputs/active --output workspace/outputs/active
python scripts/steps/step_09_pdf_output.py --input-dir workspace/outputs/active --output workspace/outputs/active
```

## Copilot CLI wrapper

O wrapper em `scripts/copilot_cli_runner.py` segue o padrão do repo de revisão técnica:
- usa `--yolo`;
- usa `--autopilot`;
- usa `--no-ask-user`;
- usa `--add-dir .`;
- remove `GITHUB_TOKEN` do ambiente do subprocess.

> Importante: em ambientes com PAT carregado, rode `unset GITHUB_TOKEN` antes do Copilot CLI. O PAT costuma conflitar com a autenticação própria do Copilot.

## Visualização do DAG (resumo de executores)

| Step | Executor | Saída principal |
|---|---|---|
| 01-download-dados | deterministic | dados_brutos.json |
| 02-preparacao-base | deterministic | base_preparada.json |
| 03-modelagem | deterministic | modelagem.json |
| 04-previsoes | deterministic | previsoes.json |
| 05-analise-qualitativa | copilot_cli | analise_qualitativa.json |
| 06-cenarios | copilot_cli | cenarios.json |
| 07-visualizacao | deterministic | visualizacoes.json |
| 08-relatorio-narrativa | copilot_cli | relatorio_narrativa.json |
| 09-pdf-output | deterministic | relatorio_final.json |

## Fontes de dados
- `data/raw/Variaveis_para_Previsão_260105.xlsx` — base principal usada no pipeline fonte.
- `data/raw/dados_sefaz.xlsx` — referência adicional preservada.
- `data/raw/Trajetória PIB e Inflação_260105.xlsx` — apoio para premissas macro.
- BCB SGS 24363 (IBC-BR) e SGS 190 (proxy inflação) — consultados como evidência externa/fallback operacional.

## Notas metodológicas
- O núcleo matemático foi preservado em `scripts/forecast_core.py`.
- O step 03 faz validação; o step 04 refaz o fit final para manter I/O somente em JSON.
- Steps AI são opcionais e não contaminam o cálculo determinístico.

## Próximos passos óbvios
- plugar coleta real do Focus mensal;
- adicionar testes de regressão por step;
- criar branch DAG específica para rolling backtest;
- melhorar renderização do PDF com narrativa e cenários quando os steps AI estiverem ativos.
