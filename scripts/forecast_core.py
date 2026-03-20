#!/usr/bin/env python3
from __future__ import annotations

from calendar import monthrange
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import openpyxl
import pandas as pd
import requests
from jinja2 import Environment, FileSystemLoader
from statsmodels.tsa.statespace.sarimax import SARIMAX

SEED = 42
N_SIMULACOES = 1000
HORIZONTE_VALIDACAO = 12
DATA_CORTE_HISTORICO = '2025-08-01'
HORIZONTE_PREVISAO = 16
ARQUIVO_EXCEL = 'Variaveis_para_Previsão_260105.xlsx'

np.random.seed(SEED)

MODEL_DEFS = [
    {'nome': 'M1', 'ordem': (1, 1, 1), 'saz': (0, 0, 0, 12), 'exog_cols': ['dias_uteis', 'LS2008NOV', 'TC2020APR04', 'TC2022OUT05']},
    {'nome': 'M2', 'ordem': (3, 1, 0), 'saz': (2, 0, 0, 12), 'exog_cols': ['igp_di_lag1', 'ibc_br_lag1', 'dias_uteis', 'LS2008NOV', 'TC2020APR04', 'TC2022OUT05']},
    {'nome': 'M3', 'ordem': (0, 1, 1), 'saz': (0, 1, 1, 12), 'exog_cols': ['igp_di', 'ibc_br', 'ibc_br_lag1', 'dias_uteis', 'LS2008NOV', 'TC2020APR04', 'TC2022OUT05']},
    {'nome': 'M4', 'ordem': (0, 1, 1), 'saz': (0, 1, 2, 12), 'exog_cols': ['ibc_br', 'ibc_br_lag1', 'dias_uteis', 'LS2008NOV', 'TC2020APR04', 'TC2022OUT05']},
    {'nome': 'M5', 'ordem': (0, 1, 1), 'saz': (0, 1, 2, 12), 'exog_cols': ['igp_di', 'ibc_br', 'ibc_br_lag1', 'LS2008NOV', 'TC2020APR04', 'TC2022OUT05']},
]


def dias_uteis_ano_mes(ano: int, mes: int) -> int:
    dias_total = monthrange(ano, mes)[1]
    return sum(1 for dia in range(1, dias_total + 1) if datetime(ano, mes, dia).weekday() < 5)


def fetch_bcb_series(code: int, timeout: int = 10) -> pd.DataFrame:
    url = f'https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados?formato=json'
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    df = pd.DataFrame(data)
    if df.empty:
        return pd.DataFrame(columns=['data', 'valor'])
    df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
    df['valor'] = df['valor'].astype(float)
    return df


def try_external_sources(timeout: int = 10) -> dict[str, Any]:
    sources: dict[str, Any] = {'ibc_br': {'status': 'not_run'}, 'igp_di': {'status': 'not_run'}}
    for name, code in [('ibc_br', 24363), ('igp_di', 190)]:
        try:
            df = fetch_bcb_series(code, timeout=timeout)
            sources[name] = {
                'status': 'ok',
                'code': code,
                'rows': int(len(df)),
                'latest_date': df['data'].max().strftime('%Y-%m-%d') if not df.empty else None,
                'latest_value': float(df['valor'].iloc[-1]) if not df.empty else None,
            }
        except Exception as exc:
            sources[name] = {'status': 'error', 'code': code, 'error': str(exc)}
    return sources


def ler_dados_excel(data_dir: Path, excel_name: str = ARQUIVO_EXCEL, cutoff: str = DATA_CORTE_HISTORICO) -> pd.DataFrame:
    excel_path = data_dir / excel_name
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    df = pd.DataFrame(rows[1:], columns=rows[0])
    col_map = {
        'date': 'data',
        'icms_sp': 'icms_sp',
        'ibc_br': 'ibc_br',
        'igp_di': 'igp_di',
        'dolar': 'dolar',
        'dias_uteis': 'dias_uteis',
    }
    cols_existentes = {c: col_map[c] for c in df.columns if c in col_map}
    df = df.rename(columns=cols_existentes)
    df = df[list(cols_existentes.values())]
    df['data'] = pd.to_datetime(df['data'])
    df = df[df['data'] <= pd.to_datetime(cutoff)].copy()
    numeric_cols = [c for c in df.columns if c != 'data']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    return df.sort_values('data').reset_index(drop=True)


def projetar_exogenas(df_hist: pd.DataFrame, horizonte: int = HORIZONTE_PREVISAO) -> pd.DataFrame:
    df_hist = df_hist.copy()
    last_date = df_hist['data'].max()
    future_dates = pd.date_range(start=last_date + pd.DateOffset(months=1), periods=horizonte, freq='MS')
    df_fut = pd.DataFrame({'data': future_dates})

    focus_pib = {2025: 2.00, 2026: 2.00}
    focus_igpm = {2025: 4.00, 2026: 3.80}

    df_hist['mes'] = df_hist['data'].dt.month
    df_hist['ano'] = df_hist['data'].dt.year
    anos_sazonal = range(last_date.year - 5, last_date.year)
    fatores = []
    for ano in anos_sazonal:
        df_ano = df_hist[df_hist['ano'] == ano]
        if len(df_ano) == 12:
            media_ano = df_ano['ibc_br'].mean()
            fatores.append(df_ano['ibc_br'].values / media_ano)
    perfil_sazonal = np.mean(fatores, axis=0) if fatores else np.ones(12)

    ibc_proj = []
    igp_proj = []
    val_ibc = float(df_hist.iloc[-1]['ibc_br'])
    val_igp = float(df_hist.iloc[-1]['igp_di'])

    for dt in future_dates:
        m = dt.month - 1
        taxa_tendencia = (1 + focus_pib.get(dt.year, 0.0) / 100) ** (1 / 12) - 1 if dt.year in focus_pib else 0.0
        fator_atual = perfil_sazonal[m]
        fator_anterior = perfil_sazonal[m - 1] if m > 0 else perfil_sazonal[11]
        var_sazonal = (fator_atual / fator_anterior) - 1
        val_ibc = val_ibc * (1 + taxa_tendencia + var_sazonal)
        ibc_proj.append(val_ibc)

        taxa_igp = (1 + focus_igpm.get(dt.year, 3.80) / 100) ** (1 / 12) - 1
        val_igp = val_igp * (1 + taxa_igp)
        igp_proj.append(val_igp)

    df_fut['ibc_br'] = ibc_proj
    df_fut['igp_di'] = igp_proj
    df_fut['ano'] = df_fut['data'].dt.year
    df_fut['mes'] = df_fut['data'].dt.month
    df_fut['dias_uteis'] = df_fut.apply(lambda x: dias_uteis_ano_mes(int(x['ano']), int(x['mes'])), axis=1)

    df_full = pd.concat([df_hist, df_fut], ignore_index=True)
    if 'ano' not in df_full.columns:
        df_full['ano'] = df_full['data'].dt.year
    if 'mes' not in df_full.columns:
        df_full['mes'] = df_full['data'].dt.month
    df_full['LS2008NOV'] = (((df_full['ano'] == 2008) & (df_full['mes'] >= 11)) | (df_full['ano'] > 2008)).astype(int)
    df_full['TC2020APR04'] = ((df_full['ano'] == 2020) & (df_full['mes'] >= 4) & (df_full['mes'] <= 7)).astype(int)
    df_full['TC2022OUT05'] = (((df_full['ano'] == 2022) & (df_full['mes'] >= 10)) | ((df_full['ano'] == 2023) & (df_full['mes'] <= 5))).astype(int)
    for col in ['ibc_br', 'igp_di', 'dias_uteis']:
        for lag in range(1, 5):
            df_full[f'{col}_lag{lag}'] = df_full[col].shift(lag)
    return df_full.reset_index(drop=True)


def split_train_test(df_full: pd.DataFrame, cutoff_hist: str = DATA_CORTE_HISTORICO, horizon_validacao: int = HORIZONTE_VALIDACAO):
    data_corte_treino = pd.to_datetime(cutoff_hist) - pd.DateOffset(months=horizon_validacao)
    mask_treino = df_full['data'] <= data_corte_treino
    mask_teste = (df_full['data'] > data_corte_treino) & (df_full['data'] <= pd.to_datetime(cutoff_hist))
    train = df_full[mask_treino].copy()
    test = df_full[mask_teste].copy()
    return train, test, data_corte_treino


def ajustar_modelo(y: pd.Series, X: pd.DataFrame, ordem, sazonal, nome: str):
    model = SARIMAX(y, exog=X, order=ordem, seasonal_order=sazonal, enforce_stationarity=False, enforce_invertibility=False)
    return model.fit(disp=False)


def fit_validation_models(df_full: pd.DataFrame) -> dict[str, Any]:
    train, test, data_corte_treino = split_train_test(df_full)
    y_train = np.log(train['icms_sp'])
    y_test_real = test['icms_sp'].values
    resultados = {}
    metricas = {}
    for m in MODEL_DEFS:
        X_train = train[m['exog_cols']]
        X_test = test[m['exog_cols']]
        mask_nan = X_train.notna().all(axis=1) & y_train.notna()
        if mask_nan.sum() < 24:
            resultados[m['nome']] = {'status': 'insufficient_data'}
            continue
        try:
            modelo = ajustar_modelo(y_train[mask_nan], X_train[mask_nan], m['ordem'], m['saz'], m['nome'])
            pred = modelo.get_forecast(steps=len(test), exog=X_test)
            pred_inv = np.exp(pred.predicted_mean)
            mape = float(np.mean(np.abs((y_test_real - pred_inv) / y_test_real)) * 100)
            resultados[m['nome']] = {
                'status': 'ok',
                'mape': mape,
                'aic': float(modelo.aic),
                'bic': float(modelo.bic),
                'loglik': float(modelo.llf),
                'nobs': int(modelo.nobs),
                'ordem': list(m['ordem']),
                'sazonal': list(m['saz']),
                'exog_cols': m['exog_cols'],
            }
            metricas[m['nome']] = resultados[m['nome']]
        except Exception as exc:
            resultados[m['nome']] = {'status': 'error', 'error': str(exc), 'exog_cols': m['exog_cols']}
    return {
        'train_end': data_corte_treino.strftime('%Y-%m-%d'),
        'validation_rows': int(len(test)),
        'models': resultados,
        'best_model_by_aic': min(metricas, key=lambda k: metricas[k]['aic']) if metricas else None,
    }


def generate_forecasts(df_full: pd.DataFrame, n_simulacoes: int = N_SIMULACOES, cutoff_hist: str = DATA_CORTE_HISTORICO) -> dict[str, Any]:
    full_mask = df_full['data'] <= pd.to_datetime(cutoff_hist)
    full_train = df_full[full_mask].copy()
    future_df = df_full[df_full['data'] > pd.to_datetime(cutoff_hist)].copy()
    y_full = np.log(full_train['icms_sp'])
    steps_future = len(future_df)

    lista_simulacoes = []
    model_summaries = {}
    monthly_per_model = {'data': future_df['data']}
    for m in MODEL_DEFS:
        X_full = full_train[m['exog_cols']]
        X_future = future_df[m['exog_cols']]
        mask_nan = X_full.notna().all(axis=1) & y_full.notna()
        if mask_nan.sum() < 12:
            model_summaries[m['nome']] = {'status': 'insufficient_data'}
            continue
        try:
            mod = ajustar_modelo(y_full[mask_nan], X_full[mask_nan], m['ordem'], m['saz'], m['nome'])
            sims_log = np.zeros((n_simulacoes, steps_future))
            for s in range(n_simulacoes):
                sim = mod.simulate(nsimulations=steps_future, anchor='end', exog=X_future)
                sims_log[s, :] = np.asarray(sim)
            sims_real = np.exp(sims_log)
            lista_simulacoes.append(sims_real)
            monthly_per_model[m['nome']] = sims_real.mean(axis=0)
            model_summaries[m['nome']] = {
                'status': 'ok',
                'aic': float(mod.aic),
                'bic': float(mod.bic),
                'loglik': float(mod.llf),
                'nobs': int(mod.nobs),
            }
        except Exception as exc:
            model_summaries[m['nome']] = {'status': 'error', 'error': str(exc)}
    if not lista_simulacoes:
        raise RuntimeError('Nenhum modelo pôde ser simulado com sucesso.')

    simulacoes_ensemble = np.stack(lista_simulacoes, axis=0)
    ensemble_paths = np.mean(simulacoes_ensemble, axis=0)
    perc_low95 = np.percentile(ensemble_paths, 2.5, axis=0)
    perc_high95 = np.percentile(ensemble_paths, 97.5, axis=0)
    perc_mean = np.mean(ensemble_paths, axis=0)

    future_dates = future_df['data'].values
    years_future = pd.to_datetime(future_dates).year
    realizado_anual = {}
    df_hist_real = full_train[['data', 'icms_sp']].copy()
    df_hist_real['ano'] = df_hist_real['data'].dt.year
    for ano in df_hist_real['ano'].unique():
        realizado_anual[int(ano)] = float(df_hist_real[df_hist_real['ano'] == ano]['icms_sp'].sum())

    totais_anuais = {}
    years_to_report = np.unique(np.concatenate([years_future, list(realizado_anual.keys())]))
    years_to_report = [int(y) for y in years_to_report if int(y) >= 2024]
    for ano in sorted(years_to_report):
        realizado = realizado_anual.get(ano, 0.0)
        indices_ano = np.where(years_future == ano)[0]
        if len(indices_ano) > 0:
            somas_paths = np.sum(ensemble_paths[:, indices_ano], axis=1)
            total_paths = somas_paths + realizado
            totais_anuais[str(ano)] = {
                'mean': float(np.mean(total_paths)),
                'low95': float(np.percentile(total_paths, 2.5)),
                'high95': float(np.percentile(total_paths, 97.5)),
                'realizado_parcial': bool(realizado > 0),
            }
        else:
            totais_anuais[str(ano)] = {
                'mean': float(realizado), 'low95': float(realizado), 'high95': float(realizado), 'realizado_parcial': False
            }

    monthly_df = pd.DataFrame({'data': future_df['data'], 'icms_previsto_medio': perc_mean, 'icms_lower_95': perc_low95, 'icms_upper_95': perc_high95})
    for key, value in monthly_per_model.items():
        if key == 'data':
            continue
        monthly_df[key] = value
    contexto = full_train[['data', 'icms_sp']].tail(24).rename(columns={'icms_sp': 'icms_realizado'})
    return {
        'n_simulacoes': int(n_simulacoes),
        'future_steps': int(steps_future),
        'model_summaries': model_summaries,
        'monthly_forecast': monthly_df,
        'historical_context': contexto,
        'annual_totals': totais_anuais,
    }


def render_html_report(template_dir: Path, template_name: str, context: dict[str, Any]) -> str:
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template(template_name)
    return template.render(**context)
