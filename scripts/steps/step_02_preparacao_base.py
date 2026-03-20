#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from common import parse_common_args, dump_json, load_json, output_file, input_file, ensure_dir
from forecast_core import projetar_exogenas, MODEL_DEFS, DATA_CORTE_HISTORICO, HORIZONTE_PREVISAO


def main() -> int:
    args = parse_common_args('Step 02 - preparação da base', needs_input=True)
    output_dir = ensure_dir(Path(args.output))
    input_dir = Path(args.input_dir)
    raw = load_json(input_file(input_dir, 'dados_brutos.json'))
    df_hist = pd.DataFrame(raw['historico']['records'])
    df_hist['data'] = pd.to_datetime(df_hist['data'])
    for col in [c for c in df_hist.columns if c != 'data']:
        df_hist[col] = pd.to_numeric(df_hist[col], errors='coerce')
    df_full = projetar_exogenas(df_hist, horizonte=HORIZONTE_PREVISAO)
    payload = {
        'step': '02-preparacao-base',
        'status': 'ok',
        'cutoff_historico': DATA_CORTE_HISTORICO,
        'horizonte_previsao_meses': HORIZONTE_PREVISAO,
        'model_defs': MODEL_DEFS,
        'base_completa': {
            'columns': list(df_full.columns),
            'records': [
                {k: (v.strftime('%Y-%m-%d') if hasattr(v, 'strftime') else (None if v != v else float(v) if isinstance(v, (int, float)) else v)) for k, v in row.items()}
                for row in df_full.to_dict(orient='records')
            ],
        },
        'resumo': {
            'linhas_total': int(len(df_full)),
            'linhas_historicas': int(df_full['icms_sp'].notna().sum()),
            'linhas_futuras': int(df_full['icms_sp'].isna().sum()),
            'inicio': df_full['data'].min().strftime('%Y-%m-%d'),
            'fim': df_full['data'].max().strftime('%Y-%m-%d'),
        },
    }
    dump_json(output_file(output_dir, 'base_preparada.json'), payload)
    print('✓ base_preparada.json gerado')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
