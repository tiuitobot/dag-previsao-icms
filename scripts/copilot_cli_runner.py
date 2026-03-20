#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_step(graph: dict, step_id: str) -> dict:
    for step in graph.get('steps', []):
        if step.get('id') == step_id:
            return step
    raise KeyError(f'Step não encontrado: {step_id}')


def main() -> int:
    parser = argparse.ArgumentParser(description='Wrapper mínimo para executar steps copilot_cli do DAG')
    parser.add_argument('--step-id', required=True)
    parser.add_argument('--graph', default=str(ROOT / 'plans' / 'pipeline-graph.json'))
    parser.add_argument('--output-dir', default=str(ROOT / 'workspace' / 'outputs' / 'active'))
    parser.add_argument('--model', default='gpt-4')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    graph = json.loads(Path(args.graph).read_text(encoding='utf-8'))
    step = load_step(graph, args.step_id)
    contract_path = ROOT / step['contract']
    if not contract_path.exists():
        raise FileNotFoundError(contract_path)
    if shutil.which('copilot') is None:
        print('Copilot CLI não encontrado no PATH. Step opcional será pulado pelo orquestrador.')
        return 2

    output_path = ROOT / step['outputs'][0]
    prompt = (
        f"Você está executando o step {step['id']} do pipeline dag-previsao-icms.\n\n"
        f"Leia o contrato em: {contract_path}\n"
        f"Leia os artefatos em: {Path(args.output_dir)}\n"
        f"Escreva a saída esperada em: {output_path}\n\n"
        f"Respeite o contrato e gere apenas o artefato solicitado."
    )
    cmd = [
        'copilot', '-p', prompt,
        '--model', args.model,
        '--yolo',
        '--autopilot',
        '--no-ask-user',
        '--add-dir', str(ROOT),
    ]
    env = dict(os.environ)
    env.pop('GITHUB_TOKEN', None)

    print('⚠️  Dica: faça `unset GITHUB_TOKEN` antes de usar o Copilot CLI se houver PAT carregado.')
    print('Comando:', ' '.join(cmd[:2] + ['<PROMPT>'] + cmd[3:]))
    if args.dry_run:
        return 0
    return subprocess.call(cmd, cwd=ROOT, env=env)


if __name__ == '__main__':
    raise SystemExit(main())
