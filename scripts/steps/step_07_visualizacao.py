#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

sys.path.append(str(Path(__file__).resolve().parents[1]))

from common import parse_common_args, dump_json, load_json, output_file, input_file, ensure_dir

sns.set_theme(style='whitegrid', palette='deep', font_scale=1.0)


def main() -> int:
    args = parse_common_args('Step 07 - visualização', needs_input=True)
    output_dir = ensure_dir(Path(args.output))
    input_dir = Path(args.input_dir)
    prepared = load_json(input_file(input_dir, 'base_preparada.json'))
    previsoes = load_json(input_file(input_dir, 'previsoes.json'))

    df_full = pd.DataFrame(prepared['base_completa']['records'])
    df_full['data'] = pd.to_datetime(df_full['data'])
    for col in [c for c in df_full.columns if c != 'data']:
        df_full[col] = pd.to_numeric(df_full[col], errors='coerce')

    monthly = pd.DataFrame(previsoes['monthly_forecast']['records'])
    monthly['data'] = pd.to_datetime(monthly['data'])
    for col in [c for c in monthly.columns if c != 'data']:
        monthly[col] = pd.to_numeric(monthly[col], errors='coerce')

    hist = df_full[df_full['icms_sp'].notna()].copy()
    future = monthly.copy()
    outputs = []

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(hist['data'], hist['icms_sp'] / 1e9, label='ICMS realizado', linewidth=2)
    ax.plot(future['data'], future['icms_previsto_medio'] / 1e9, label='Previsão média', linestyle='--', linewidth=2)
    ax.fill_between(future['data'], future['icms_lower_95'] / 1e9, future['icms_upper_95'] / 1e9, alpha=0.2, label='IC 95%')
    ax.set_title('ICMS-SP: histórico e previsão')
    ax.set_ylabel('R$ bilhões')
    ax.legend()
    path = output_dir / 'grafico_serie_historica.png'
    fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)
    outputs.append(str(path))

    fig, ax = plt.subplots(figsize=(14, 7))
    for model in [c for c in future.columns if c.startswith('M')]:
        ax.plot(future['data'], future[model] / 1e9, label=model, alpha=0.85)
    ax.plot(future['data'], future['icms_previsto_medio'] / 1e9, label='Ensemble', color='black', linewidth=2.5)
    ax.set_title('Comparação dos 5 modelos SARIMAX')
    ax.set_ylabel('R$ bilhões')
    ax.legend(ncol=3)
    path = output_dir / 'grafico_comparacao_modelos.png'
    fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)
    outputs.append(str(path))

    annual = []
    for model in [c for c in future.columns if c.startswith('M')] + ['icms_previsto_medio']:
        for ano, grupo in future.groupby(future['data'].dt.year):
            annual.append({'ano': int(ano), 'modelo': model, 'valor_bi': float(grupo[model].sum() / 1e9)})
    annual_df = pd.DataFrame(annual)
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.barplot(data=annual_df, x='ano', y='valor_bi', hue='modelo', ax=ax)
    ax.set_title('Totais anuais por modelo')
    ax.set_ylabel('R$ bilhões')
    path = output_dir / 'grafico_performance_anual.png'
    fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)
    outputs.append(str(path))

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes[0,0].plot(df_full['data'], df_full['ibc_br']); axes[0,0].set_title('IBC-BR')
    axes[0,1].plot(df_full['data'], df_full['igp_di']); axes[0,1].set_title('IGP-DI')
    axes[1,0].bar(df_full['data'], df_full['dias_uteis']); axes[1,0].set_title('Dias úteis')
    axes[1,1].plot(df_full['data'], df_full['LS2008NOV'], label='LS2008NOV')
    axes[1,1].plot(df_full['data'], df_full['TC2020APR04'], label='TC2020APR04')
    axes[1,1].plot(df_full['data'], df_full['TC2022OUT05'], label='TC2022OUT05')
    axes[1,1].legend(); axes[1,1].set_title('Dummies estruturais')
    path = output_dir / 'grafico_variaveis_exogenas.png'
    fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)
    outputs.append(str(path))

    annual_totals = previsoes['annual_totals']
    anos = sorted([int(a) for a in annual_totals.keys()])
    medias = [annual_totals[str(a)]['mean'] / 1e9 for a in anos]
    lows = [annual_totals[str(a)]['low95'] / 1e9 for a in anos]
    highs = [annual_totals[str(a)]['high95'] / 1e9 for a in anos]
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.bar([str(a) for a in anos], medias, color='#3498db')
    ax.errorbar([str(a) for a in anos], medias, yerr=[[m-l for m, l in zip(medias, lows)], [h-m for h, m in zip(highs, medias)]], fmt='none', ecolor='black', capsize=6)
    ax.set_title('Totais anuais com IC 95%')
    ax.set_ylabel('R$ bilhões')
    path = output_dir / 'grafico_totais_anuais_ic.png'
    fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)
    outputs.append(str(path))

    payload = {
        'step': '07-visualizacao',
        'status': 'ok',
        'charts': outputs,
        'annual_totals': annual_totals,
    }
    dump_json(output_file(output_dir, 'visualizacoes.json'), payload)
    print('OK visualizacoes.json gerado')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
