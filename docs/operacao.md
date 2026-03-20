# Operação

## Instalação
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Listar DAG
```bash
python scripts/run_pipeline.py --list
```

## Rodar só os steps determinísticos
```bash
python scripts/run_pipeline.py
```

## Rodar com Copilot CLI
```bash
unset GITHUB_TOKEN
python scripts/run_pipeline.py --with-copilot
```

## Rodar um step isolado
```bash
python scripts/steps/step_01_download_dados.py --output workspace/outputs/active
python scripts/steps/step_02_preparacao_base.py --input-dir workspace/outputs/active --output workspace/outputs/active
python scripts/steps/step_03_modelagem.py --input-dir workspace/outputs/active --output workspace/outputs/active
python scripts/steps/step_04_previsoes.py --input-dir workspace/outputs/active --output workspace/outputs/active --n-simulacoes 1000
python scripts/steps/step_07_visualizacao.py --input-dir workspace/outputs/active --output workspace/outputs/active
python scripts/steps/step_09_pdf_output.py --input-dir workspace/outputs/active --output workspace/outputs/active
```
