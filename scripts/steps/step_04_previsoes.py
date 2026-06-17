#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from common import dump_json, load_json, output_file, input_file, ensure_dir, env_int
from forecast_core import generate_forecasts, N_SIMULACOES


def main() -> int:
    parser = argparse.ArgumentParser(description='Step 04 - previsões e Monte Carlo')
    parser.add_argument('--output', default='workspace/outputs/active')
    parser.add_argument('--input-dir', default='workspace/outputs/active')
    parser.add_argument('--n-simulacoes', type=int, default=env_int('ICMS_N_SIMULACOES', N_SIMULACOES))
    args = parser.parse_args()

    output_dir = ensure_dir(Path(args.output))
    input_dir = Path(args.input_dir)
    prepared = load_json(input_file(input_dir, 'base_preparada.json'))
    modeling = load_json(input_file(input_dir, 'modelagem.json'))

    df_full = pd.DataFrame(prepared['base_completa']['records'])
    df_full['data'] = pd.to_datetime(df_full['data'])
    for col in [c for c in df_full.columns if c != 'data']:
        df_full[col] = pd.to_numeric(df_full[col], errors='coerce')

    forecasts = generate_forecasts(df_full, n_simulacoes=args.n_simulacoes)
    monthly = forecasts['monthly_forecast'].copy()
    context = forecasts['historical_context'].copy()
    payload = {
        'step': '04-previsoes',
        'status': 'ok',
        'modelagem': modeling,
        'n_simulacoes': forecasts['n_simulacoes'],
        'future_steps': forecasts['future_steps'],
        'model_summaries': forecasts['model_summaries'],
        'monthly_forecast': {
            'columns': list(monthly.columns),
            'records': [
                {k: (v.strftime('%Y-%m-%d') if hasattr(v, 'strftime') else (None if v != v else float(v) if isinstance(v, (int, float)) else v)) for k, v in row.items()}
                for row in monthly.to_dict(orient='records')
            ],
        },
        'historical_context': {
            'columns': list(context.columns),
            'records': [
                {k: (v.strftime('%Y-%m-%d') if hasattr(v, 'strftime') else (None if v != v else float(v) if isinstance(v, (int, float)) else v)) for k, v in row.items()}
                for row in context.to_dict(orient='records')
            ],
        },
        'annual_totals': forecasts['annual_totals'],
    }
    dump_json(output_file(output_dir, 'previsoes.json'), payload)
    print('OK previsoes.json gerado')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
