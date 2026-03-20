#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAPH_DEFAULT = ROOT / 'plans' / 'pipeline-graph.json'
STATE_DEFAULT = ROOT / 'workspace' / 'outputs' / 'active' / 'pipeline-state.json'
OUTDIR = ROOT / 'workspace' / 'outputs' / 'active'


def load_graph(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def topo_sort(steps: list[dict]) -> list[dict]:
    by_id = {step['id']: step for step in steps}
    indeg = {step['id']: len(step.get('dependencies', [])) for step in steps}
    outgoing = {step['id']: [] for step in steps}
    for step in steps:
        for dep in step.get('dependencies', []):
            outgoing[dep].append(step['id'])
    q = deque([by_id[sid] for sid, deg in indeg.items() if deg == 0])
    ordered = []
    while q:
        step = q.popleft()
        ordered.append(step)
        for nxt in outgoing[step['id']]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                q.append(by_id[nxt])
    if len(ordered) != len(steps):
        raise RuntimeError('DAG inválido: ciclo detectado.')
    return ordered


def write_state(path: Path, graph: dict, ordered: list[dict], step_status: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'pipeline': graph.get('pipeline'),
        'version': graph.get('version'),
        'steps': [
            {
                'id': step['id'],
                'executor': step['executor'],
                'status': step_status.get(step['id'], 'pending'),
                'outputs': step.get('outputs', []),
            }
            for step in ordered
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description='Orquestrador simplificado do DAG dag-previsao-icms')
    parser.add_argument('--graph', default=str(GRAPH_DEFAULT))
    parser.add_argument('--state', default=str(STATE_DEFAULT))
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--with-copilot', action='store_true')
    parser.add_argument('--from-step', default=None)
    parser.add_argument('--to-step', default=None)
    args = parser.parse_args()

    graph = load_graph(Path(args.graph))
    ordered = topo_sort(graph['steps'])
    if args.list:
        for step in ordered:
            print(f"{step['id']} [{step['executor']}] deps={step.get('dependencies', [])}")
        return 0

    step_status = {}
    started = args.from_step is None
    for step in ordered:
        if not started and step['id'] == args.from_step:
            started = True
        if not started:
            step_status[step['id']] = 'skipped_before_from_step'
            continue

        if step['executor'] == 'deterministic':
            cmd = [sys.executable, str(ROOT / step['script']), '--output', str(OUTDIR)]
            if step['id'] != '01-download-dados':
                cmd += ['--input-dir', str(OUTDIR)]
            print('▶', step['id'])
            rc = subprocess.call(cmd, cwd=ROOT)
            step_status[step['id']] = 'done' if rc == 0 else f'failed({rc})'
            write_state(Path(args.state), graph, ordered, step_status)
            if rc != 0:
                return rc
        elif step['executor'] == 'copilot_cli':
            if not args.with_copilot or shutil.which('copilot') is None:
                step_status[step['id']] = 'skipped_optional' if step.get('optional', False) else 'copilot_unavailable'
                write_state(Path(args.state), graph, ordered, step_status)
                if not step.get('optional', False) and args.with_copilot:
                    return 2
            else:
                cmd = [sys.executable, str(ROOT / 'scripts' / 'copilot_cli_runner.py'), '--step-id', step['id'], '--graph', str(ROOT / 'plans' / 'pipeline-graph.json'), '--output-dir', str(OUTDIR)]
                print('▶', step['id'])
                rc = subprocess.call(cmd, cwd=ROOT)
                step_status[step['id']] = 'done' if rc == 0 else f'failed({rc})'
                write_state(Path(args.state), graph, ordered, step_status)
                if rc != 0 and not step.get('optional', False):
                    return rc

        if args.to_step and step['id'] == args.to_step:
            break

    write_state(Path(args.state), graph, ordered, step_status)
    print('✓ pipeline-state.json atualizado')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
