#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from common import parse_common_args, dump_json, load_json, input_file, output_file, ensure_dir


def main() -> int:
    args = parse_common_args('Step 06 - construção de cenários alternativos', needs_input=True)
    output_dir = ensure_dir(Path(args.output))
    input_dir = Path(args.input_dir)
    previsoes = load_json(input_file(input_dir, 'previsoes.json'))
    payload = {
        'step': '06-cenarios',
        'status': 'stub',
        'executor': 'copilot_cli',
        'summary': 'Stub criado para integração futura com Copilot CLI.',
        'instructions': 'Execute este step via scripts/copilot_cli_runner.py usando o contrato correspondente.',
        'input_hint': {'annual_totals': previsoes.get('annual_totals', {})},
    }
    dump_json(output_file(output_dir, 'cenarios.json'), payload)
    print('OK cenarios.json gerado (stub)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
