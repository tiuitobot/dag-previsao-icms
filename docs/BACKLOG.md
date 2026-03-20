# Backlog — DAG Previsão ICMS

## Herdado do projeto anterior

### E01: Framework de validação dinâmica
- rolling window / time-series cross-validation
- matriz de erros por horizonte (3, 6, 12, 24 meses)
- ranking dinâmico e combinação ótima de modelos

### E02: Reimplementação crítica / paridade com Excel-R
- refinar distribuição mensal do Focus
- consolidar Monte Carlo agregado anual
- revisar pontos de paridade residual com o modelo original

## Novos itens desta versão DAG
- [ ] criar testes automatizados por step
- [ ] registrar schemas JSON explícitos para artefatos principais
- [ ] suportar rerun incremental por hash de inputs
- [ ] adicionar executor alternativo para outros wrappers AI além do Copilot CLI
- [ ] publicar GitHub Action mensal para rerodar pipeline e anexar PDF
