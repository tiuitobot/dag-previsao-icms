#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from common import parse_common_args, dump_json, load_json, output_file, input_file, ensure_dir
from forecast_core import fit_validation_models


def main() -> int:
    args = parse_common_args('Step 03 - modelagem', needs_input=True)
    output_dir = ensure_dir(Path(args.output))
    input_dir = Path(args.input_dir)
    prepared = load_json(input_file(input_dir, 'base_preparada.json'))
    df_full = pd.DataFrame(prepared['base_completa']['records'])
    df_full['data'] = pd.to_datetime(df_full['data'])
    for col in [c for c in df_full.columns if c != 'data']:
        df_full[col] = pd.to_numeric(df_full[col], errors='coerce')
    results = fit_validation_models(df_full)
    payload = {'step': '03-modelagem', 'status': 'ok', **results}
    dump_json(output_file(output_dir, 'modelagem.json'), payload)
    print('OK modelagem.json gerado')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
