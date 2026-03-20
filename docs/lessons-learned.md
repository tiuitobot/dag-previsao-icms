# Lessons Learned — DAG Previsão ICMS

Este arquivo preserva e evolui os aprendizados do repositório original.

## Preservado do repo fonte
- Máscara booleana é obrigatória para modelos com exógenas laggadas (`X.notna().all(axis=1) & y.notna()`).
- Monte Carlo path-a-path é superior a banda ingênua por desvio-padrão entre modelos.
- APIs externas são instáveis; a base local em Excel continua sendo fallback operacional obrigatório.
- PDF com fonte core exige cuidado com encoding e layout.

## Evolução nesta versão DAG
- Separação entre cálculo e narrativa: os steps 01-04/07/09 mantêm o núcleo determinístico; steps 05/06/08 são opcionais e desacoplados.
- Estado observável do pipeline: `pipeline-state.json` facilita rerun seletivo e debug.
- Serialização em JSON impõe refit no step 04, mas evita coupling com objetos pickled difíceis de versionar.
- O wrapper Copilot CLI já nasce com a prática operacional correta: `unset GITHUB_TOKEN` antes de executar, para não conflitar com auth do Copilot.

## Backlog imediato
- Implementar retries/exponential backoff para BCB/IPEA.
- Substituir proxies hardcoded do Focus por coleta real mensal.
- Adicionar testes automatizados por step.
- Adicionar branch do DAG para backtesting rolling-window (epic E01 do repo anterior).
