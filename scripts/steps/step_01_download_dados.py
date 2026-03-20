#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from common import parse_common_args, dump_json, output_file, ensure_dir
from forecast_core import ler_dados_excel, try_external_sources, ARQUIVO_EXCEL, DATA_CORTE_HISTORICO


def main() -> int:
    args = parse_common_args('Step 01 - download/ingestão de dados')
    output_dir = ensure_dir(Path(args.output))
    data_dir = Path(args.data_dir)
    df_hist = ler_dados_excel(data_dir)
    payload = {
        'step': '01-download-dados',
        'status': 'ok',
        'cutoff_historico': DATA_CORTE_HISTORICO,
        'excel_principal': str(data_dir / ARQUIVO_EXCEL),
        'outras_fontes_locais': [str(data_dir / 'dados_sefaz.xlsx'), str(data_dir / 'Trajetória PIB e Inflação_260105.xlsx')],
        'fontes_externas': try_external_sources(),
        'historico': {
            'columns': list(df_hist.columns),
            'records': [
                {k: (v.strftime('%Y-%m-%d') if hasattr(v, 'strftime') else (None if v != v else float(v) if isinstance(v, (int, float)) else v)) for k, v in row.items()}
                for row in df_hist.to_dict(orient='records')
            ],
        },
        'resumo': {
            'linhas': int(len(df_hist)),
            'inicio': df_hist['data'].min().strftime('%Y-%m-%d'),
            'fim': df_hist['data'].max().strftime('%Y-%m-%d'),
            'colunas': list(df_hist.columns),
        },
    }
    dump_json(output_file(output_dir, 'dados_brutos.json'), payload)
    print('OK dados_brutos.json gerado')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
