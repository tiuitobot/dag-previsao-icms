#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROXY = 'http://proxyservidores.lbintra.fazenda.sp.gov.br:8080'
DEFAULT_NO_PROXY = 'fazenda.sp.gov.br,localhost'
DEFAULT_MODEL = 'gpt-5-mini'
DEFAULT_TIMEOUT = 600
DEFAULT_REASONING_EFFORT = 'low'
DEFAULT_MAX_AUTOPILOT_CONTINUES = 3
LEGACY_MODEL_ALIASES = {
    'gpt-4': DEFAULT_MODEL,
}


def load_step(graph: dict, step_id: str) -> dict:
    for step in graph.get('steps', []):
        if step.get('id') == step_id:
            return step
    raise KeyError(f'Step não encontrado: {step_id}')


def resolve_copilot_command() -> list[str] | None:
    appdata = os.environ.get('APPDATA')
    if appdata:
        npm_loader = Path(appdata) / 'npm' / 'node_modules' / '@github' / 'copilot' / 'npm-loader.js'
        if npm_loader.exists():
            node_path = shutil.which('node')
            if node_path:
                return [node_path, str(npm_loader)]

    copilot_path = shutil.which('copilot')
    if copilot_path:
        return [copilot_path]
    return None


def build_copilot_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop('GITHUB_TOKEN', None)

    proxy = env.get('HTTPS_PROXY') or env.get('https_proxy') or env.get('HTTP_PROXY') or env.get('http_proxy') or DEFAULT_PROXY
    no_proxy = env.get('NO_PROXY') or env.get('no_proxy') or DEFAULT_NO_PROXY

    env['HTTP_PROXY'] = proxy
    env['HTTPS_PROXY'] = proxy
    env['FTP_PROXY'] = env.get('FTP_PROXY') or env.get('ftp_proxy') or proxy
    env['NO_PROXY'] = no_proxy
    return env


def resolve_model(cli_model: str | None, step: dict) -> tuple[str | None, str | None]:
    requested_model = cli_model or step.get('model') or os.environ.get('COPILOT_MODEL') or DEFAULT_MODEL
    if not requested_model:
        return None, None
    normalized_model = LEGACY_MODEL_ALIASES.get(requested_model, requested_model)
    if normalized_model != requested_model:
        return normalized_model, requested_model
    return normalized_model, None


def resolve_reasoning_effort(cli_reasoning_effort: str | None) -> str:
    return cli_reasoning_effort or os.environ.get('COPILOT_REASONING_EFFORT') or DEFAULT_REASONING_EFFORT


def build_step_prompt(step: dict, contract_path: Path, artifacts_dir: Path, output_path: Path) -> str:
    return (
        f"Você está executando o step {step['id']} do pipeline dag-previsao-icms.\n\n"
        f"Leia o contrato em: {contract_path}\n"
        f"Leia os artefatos em: {artifacts_dir}\n"
        f"Escreva a saída esperada em: {output_path}\n\n"
        f"Respeite o contrato e gere apenas o artefato solicitado."
    )


def build_smoke_prompt(output_dir: Path) -> str:
    smoke_output = output_dir / 'copilot_smoke_test.json'
    return (
        'Você está executando um smoke test do Copilot CLI para o projeto dag-previsao-icms.\n\n'
        f'Escreva um arquivo JSON válido em: {smoke_output}\n'
        'O JSON deve conter exatamente as chaves "status", "model", "reasoning_effort" e "message".\n'
        'Use valores simples e responda com um texto curto em português em "message".\n'
        'Não altere outros arquivos.'
    )


def summarize_step_inputs(step_id: str, output_dir: Path) -> dict[str, Any]:
    previsoes = json.loads((output_dir / 'previsoes.json').read_text(encoding='utf-8'))
    monthly_records = previsoes.get('monthly_forecast', {}).get('records', [])
    context_records = previsoes.get('historical_context', {}).get('records', [])
    annual_totals = previsoes.get('annual_totals', {})
    mean_2025 = annual_totals.get('2025', {}).get('mean')
    mean_2026 = annual_totals.get('2026', {}).get('mean')
    low_2026 = annual_totals.get('2026', {}).get('low95')
    high_2026 = annual_totals.get('2026', {}).get('high95')
    yoy_2026_vs_2025 = None
    if mean_2025 and mean_2026:
        yoy_2026_vs_2025 = (mean_2026 / mean_2025) - 1
    interval_width_2026 = None
    if low_2026 is not None and high_2026 is not None and mean_2026:
        interval_width_2026 = (high_2026 - low_2026) / mean_2026

    validation_mapes = {
        model_name: model_info.get('mape')
        for model_name, model_info in previsoes.get('modelagem', {}).get('models', {}).items()
        if isinstance(model_info, dict) and model_info.get('status') == 'ok'
    }
    validation_rank = [
        {'model': model_name, 'mape': validation_mapes[model_name]}
        for model_name in sorted(validation_mapes, key=validation_mapes.get)
    ]
    base_summary = {
        'step': step_id,
        'annual_totals': annual_totals,
        'yoy_2026_vs_2025': yoy_2026_vs_2025,
        'interval_width_2026': interval_width_2026,
        'best_model_by_aic': previsoes.get('modelagem', {}).get('best_model_by_aic'),
        'validation_rank': validation_rank,
        'monthly_forecast_head': [
            {
                'data': row.get('data'),
                'icms_previsto_medio': row.get('icms_previsto_medio'),
                'icms_lower_95': row.get('icms_lower_95'),
                'icms_upper_95': row.get('icms_upper_95'),
            }
            for row in monthly_records[:3]
        ],
        'historical_context_tail': context_records[-3:],
    }
    if step_id == '05-analise-qualitativa':
        return base_summary
    if step_id == '06-cenarios':
        analise_path = output_dir / 'analise_qualitativa.md'
        if not analise_path.exists():
            raise FileNotFoundError(analise_path)
        return {
            **base_summary,
            'analise_qualitativa_markdown': analise_path.read_text(encoding='utf-8'),
        }
    if step_id == '08-relatorio-narrativa':
        cenarios_path = output_dir / 'cenarios.json'
        visualizacoes_path = output_dir / 'visualizacoes.json'
        if not cenarios_path.exists():
            raise FileNotFoundError(cenarios_path)
        if not visualizacoes_path.exists():
            raise FileNotFoundError(visualizacoes_path)
        cenarios = json.loads(cenarios_path.read_text(encoding='utf-8'))
        visualizacoes = json.loads(visualizacoes_path.read_text(encoding='utf-8'))
        return {
            **base_summary,
            'cenarios': cenarios.get('cenarios', {}),
            'cenarios_input_hint': cenarios.get('input_hint'),
            'charts': visualizacoes.get('charts', []),
            'visual_annual_totals': visualizacoes.get('annual_totals', {}),
        }
    raise ValueError(f'Modo programatico ainda nao suportado para o step {step_id}.')


def build_stdout_json_prompt(step: dict, summarized_inputs: dict[str, Any]) -> str:
    if step['id'] == '08-relatorio-narrativa':
        annual_totals = summarized_inputs.get('annual_totals', {})
        totals_2025 = annual_totals.get('2025', {})
        totals_2026 = annual_totals.get('2026', {})
        return (
            f'Voce esta executando o step {step["id"]} do pipeline dag-previsao-icms.\n\n'
            'Responda somente com um JSON valido, sem markdown, sem explicacoes extras e sem bloco de codigo.\n'
            'Nao leia arquivos e nao grave arquivos.\n'
            'O JSON deve ter exatamente estas chaves no nivel raiz: '
            'step, status, resumo_executivo, mensagens_chave, limitacoes, recomendacoes, input_hint.\n'
            'status deve ser "ok".\n'
            'resumo_executivo deve ser uma string curta em portugues.\n'
            'mensagens_chave, limitacoes e recomendacoes devem ser listas de strings.\n\n'
            'Dados-chave para a narrativa:\n'
            f'- media 2025: {totals_2025.get("mean")}\n'
            f'- media 2026: {totals_2026.get("mean")}\n'
            f'- intervalo 2026: {totals_2026.get("low95")} a {totals_2026.get("high95")}\n'
            f'- variacao 2026 vs 2025: {summarized_inputs.get("yoy_2026_vs_2025")}\n'
            f'- melhor modelo por AIC: {summarized_inputs.get("best_model_by_aic")}\n'
            f'- melhores modelos por MAPE: {json.dumps(summarized_inputs.get("validation_rank", [])[:2], ensure_ascii=False)}\n'
            f'- cenarios: {json.dumps(summarized_inputs.get("cenarios", {}), ensure_ascii=False)}\n'
            f'- charts: {json.dumps(summarized_inputs.get("charts", []), ensure_ascii=False)}\n'
            f'- totais anuais para visualizacao: {json.dumps(summarized_inputs.get("visual_annual_totals", {}), ensure_ascii=False)}\n'
            f'- hint dos cenarios: {json.dumps(summarized_inputs.get("cenarios_input_hint"), ensure_ascii=False)}'
        )
    if step['id'] == '06-cenarios':
        annual_totals = summarized_inputs.get('annual_totals', {})
        totals_2025 = annual_totals.get('2025', {})
        totals_2026 = annual_totals.get('2026', {})
        return (
            f'Voce esta executando o step {step["id"]} do pipeline dag-previsao-icms.\n\n'
            'Responda somente com um JSON valido, sem markdown, sem explicacoes extras e sem bloco de codigo.\n'
            'Nao leia arquivos e nao grave arquivos.\n'
            'O JSON deve ter exatamente estas chaves no nivel raiz: step, status, cenarios, input_hint.\n'
            'cenarios deve ser um objeto com exatamente tres chaves: base, otimista, pessimista.\n'
            'Cada cenario deve ter exatamente estas chaves: resumo, atividade, inflacao, arrecadacao, implicacao_icms.\n'
            'Todas as chaves de cada cenario devem ser strings curtas em portugues.\n'
            'status deve ser "ok".\n\n'
            'Dados-chave para construir os cenarios:\n'
            f'- media 2025: {totals_2025.get("mean")}\n'
            f'- media 2026: {totals_2026.get("mean")}\n'
            f'- intervalo 2026: {totals_2026.get("low95")} a {totals_2026.get("high95")}\n'
            f'- variacao 2026 vs 2025: {summarized_inputs.get("yoy_2026_vs_2025")}\n'
            f'- largura relativa do intervalo 2026: {summarized_inputs.get("interval_width_2026")}\n'
            f'- melhor modelo por AIC: {summarized_inputs.get("best_model_by_aic")}\n'
            f'- melhor MAPE de validacao: {json.dumps(summarized_inputs.get("validation_rank", [])[:2], ensure_ascii=False)}\n\n'
            'Analise qualitativa de referencia:\n'
            f'{summarized_inputs.get("analise_qualitativa_markdown", "")}'
        )
    annual_totals = summarized_inputs.get('annual_totals', {})
    totals_2025 = annual_totals.get('2025', {})
    totals_2026 = annual_totals.get('2026', {})
    validation_rank = summarized_inputs.get('validation_rank', [])
    best_validation = validation_rank[0] if validation_rank else {}
    return (
        f'Voce esta executando o step {step["id"]} do pipeline dag-previsao-icms.\n\n'
        'Responda somente com um JSON valido, sem markdown, sem explicacoes extras e sem bloco de codigo.\n'
        'Nao leia arquivos e nao grave arquivos.\n'
        'O JSON deve ter exatamente estas chaves no nivel raiz: '
        'step, status, summary, riscos, drivers_macro, ressalvas_metodologicas, input_hint.\n'
        'Regras:\n'
        '- status deve ser "ok"\n'
        '- summary deve ser uma string curta em portugues\n'
        '- riscos deve ser lista de strings\n'
        '- drivers_macro deve ser lista de strings\n'
        '- ressalvas_metodologicas deve ser lista de strings\n'
        '- input_hint deve ser um objeto resumindo os numeros-chave usados\n\n'
        'Dados-chave para a analise:\n'
        f'- media 2025: {totals_2025.get("mean")}\n'
        f'- media 2026: {totals_2026.get("mean")}\n'
        f'- intervalo 2026: {totals_2026.get("low95")} a {totals_2026.get("high95")}\n'
        f'- variacao 2026 vs 2025: {summarized_inputs.get("yoy_2026_vs_2025")}\n'
        f'- largura relativa do intervalo 2026: {summarized_inputs.get("interval_width_2026")}\n'
        f'- melhor modelo por AIC: {summarized_inputs.get("best_model_by_aic")}\n'
        f'- melhor MAPE de validacao: {best_validation.get("model")} ({best_validation.get("mape")})\n'
        f'- primeiros meses previstos: {json.dumps(summarized_inputs.get("monthly_forecast_head", []), ensure_ascii=False)}\n'
        f'- contexto historico recente: {json.dumps(summarized_inputs.get("historical_context_tail", []), ensure_ascii=False)}'
    )


def build_programmatic_text_prompt(step: dict, summarized_inputs: dict[str, Any]) -> str:
    annual_totals = summarized_inputs.get('annual_totals', {})
    totals_2025 = annual_totals.get('2025', {})
    totals_2026 = annual_totals.get('2026', {})
    validation_rank = summarized_inputs.get('validation_rank', [])
    best_validation = validation_rank[0] if validation_rank else {}
    return (
        f'Voce esta executando o step {step["id"]} do pipeline dag-previsao-icms.\n\n'
        'Escreva apenas o conteudo final do arquivo em markdown, sem cercas de codigo e sem comentarios extras.\n'
        'Estruture em 4 secoes com estes titulos: Resumo executivo, Riscos, Drivers macro, Ressalvas metodologicas.\n'
        'Use portugues claro, tom tecnico e objetivo.\n'
        'Nao leia arquivos e nao grave arquivos.\n\n'
        'Dados-chave para a analise:\n'
        f'- media 2025: {totals_2025.get("mean")}\n'
        f'- media 2026: {totals_2026.get("mean")}\n'
        f'- intervalo 2026: {totals_2026.get("low95")} a {totals_2026.get("high95")}\n'
        f'- variacao 2026 vs 2025: {summarized_inputs.get("yoy_2026_vs_2025")}\n'
        f'- largura relativa do intervalo 2026: {summarized_inputs.get("interval_width_2026")}\n'
        f'- melhor modelo por AIC: {summarized_inputs.get("best_model_by_aic")}\n'
        f'- melhor MAPE de validacao: {best_validation.get("model")} ({best_validation.get("mape")})\n'
        f'- primeiros meses previstos: {json.dumps(summarized_inputs.get("monthly_forecast_head", []), ensure_ascii=False)}\n'
        f'- contexto historico recente: {json.dumps(summarized_inputs.get("historical_context_tail", []), ensure_ascii=False)}'
    )


def output_is_textual(output_path: Path) -> bool:
    return output_path.suffix.lower() in {'.md', '.txt'}


def step_requires_programmatic_mode(step_id: str) -> bool:
    return step_id in {'06-cenarios', '08-relatorio-narrativa'}


def extract_assistant_content(raw_text: str) -> str:
    stripped = raw_text.strip()
    if not stripped:
        raise ValueError('Saida vazia do Copilot CLI.')
    for line in stripped.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        try:
            event = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get('type') != 'assistant.message':
            continue
        content = event.get('data', {}).get('content')
        if isinstance(content, str):
            return content
    return stripped


def extract_json_object(raw_text: str) -> dict[str, Any]:
    stripped = extract_assistant_content(raw_text)
    if stripped.startswith('```'):
        stripped = re.sub(r'^```(?:json)?\s*', '', stripped)
        stripped = re.sub(r'\s*```$', '', stripped)
    start = stripped.find('{')
    end = stripped.rfind('}')
    if start == -1 or end == -1 or end <= start:
        raise ValueError('Nao foi encontrado um objeto JSON valido na saida do Copilot CLI.')
    return json.loads(stripped[start:end + 1])


def append_log(log_path: Path, title: str, content: str) -> None:
    with log_path.open('a', encoding='utf-8') as handle:
        handle.write(f'\n## {title}\n')
        handle.write(content)
        if not content.endswith('\n'):
            handle.write('\n')


def sanitize_for_console(content: str) -> str:
    encoding = getattr(sys.stdout, 'encoding', None) or 'utf-8'
    return content.encode(encoding, errors='replace').decode(encoding, errors='replace')


def emit_stream(name: str, content: str) -> None:
    if content.strip():
        print(f'----- {name} -----')
        print(sanitize_for_console(content.rstrip()))


def main() -> int:
    parser = argparse.ArgumentParser(description='Wrapper mínimo para executar steps copilot_cli do DAG')
    parser.add_argument('--step-id', default=None)
    parser.add_argument('--graph', default=str(ROOT / 'plans' / 'pipeline-graph.json'))
    parser.add_argument('--output-dir', default=str(ROOT / 'workspace' / 'outputs' / 'active'))
    parser.add_argument('--model', default=None)
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument('--reasoning-effort', choices=['low', 'medium', 'high', 'xhigh'], default=None)
    parser.add_argument('--max-autopilot-continues', type=int, default=DEFAULT_MAX_AUTOPILOT_CONTINUES)
    parser.add_argument('--stdout-json', action='store_true')
    parser.add_argument('--smoke-test', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if not args.step_id and not args.smoke_test:
        parser.error('Informe --step-id ou use --smoke-test.')

    copilot_cmd = resolve_copilot_command()
    if copilot_cmd is None:
        print('Copilot CLI não encontrado no PATH. Step opcional será pulado pelo orquestrador.')
        return 2

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    step = {'id': 'smoke-test', 'outputs': [str(output_dir / 'copilot_smoke_test.json')], 'model': DEFAULT_MODEL} if args.smoke_test else None
    if not args.smoke_test:
        graph = json.loads(Path(args.graph).read_text(encoding='utf-8'))
        step = load_step(graph, args.step_id)
        contract_path = ROOT / step['contract']
        if not contract_path.exists():
            raise FileNotFoundError(contract_path)
    else:
        contract_path = ROOT / 'contracts' / '_smoke_test.md'

    model, remapped_from = resolve_model(args.model, step)
    reasoning_effort = resolve_reasoning_effort(args.reasoning_effort)

    output_path = ROOT / step['outputs'][0] if not args.smoke_test else output_dir / 'copilot_smoke_test.json'
    programmatic_mode = args.stdout_json or output_is_textual(output_path) or step_requires_programmatic_mode(step['id'])
    if programmatic_mode:
        summarized_inputs = summarize_step_inputs(step['id'], output_dir)
        prompt = build_programmatic_text_prompt(step, summarized_inputs) if output_is_textual(output_path) else build_stdout_json_prompt(step, summarized_inputs)
        cmd = [
            *copilot_cmd, '-p', prompt,
            '--model', model,
            '--output-format', 'json',
            '--reasoning-effort', reasoning_effort,
            '--no-alt-screen',
            '--stream', 'off',
            '--no-ask-user',
            '--allow-tool', 'github',
            '--no-custom-instructions',
            '-s',
        ]
    else:
        prompt = build_smoke_prompt(output_dir) if args.smoke_test else build_step_prompt(step, contract_path, output_dir, output_path)
        cmd = [
            *copilot_cmd, '-p', prompt,
            '--reasoning-effort', reasoning_effort,
            '--yolo',
            '--autopilot',
            '--max-autopilot-continues', str(args.max_autopilot_continues),
            '--no-ask-user',
            '--no-alt-screen',
            '--stream', 'off',
            '--add-dir', str(ROOT),
        ]
    if model and '--model' not in cmd:
        prompt_index = cmd.index(prompt)
        cmd[prompt_index + 1:prompt_index + 1] = ['--model', model]
    env = build_copilot_env()

    print('Proxy HTTP:', env['HTTP_PROXY'])
    print('NO_PROXY:', env['NO_PROXY'])
    print('GITHUB_TOKEN removido do subprocesso:', 'GITHUB_TOKEN' not in env)
    print('Timeout (s):', args.timeout)
    print('Reasoning effort:', reasoning_effort)
    print('Max autopilot continues:', args.max_autopilot_continues)
    print('Programmatic mode:', programmatic_mode)
    if remapped_from is not None:
        print(f'Modelo solicitado "{remapped_from}" remapeado para "{model}" por compatibilidade com o Copilot CLI local.')
    preview = [cmd[0], cmd[1], '<PROMPT>'] + cmd[3:]
    print('Comando:', sanitize_for_console(' '.join(preview)))
    log_path = output_dir / f'copilot_cli_{step["id"].replace("/", "_")}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    append_log(log_path, 'metadata', json.dumps({
        'step_id': step['id'],
        'model': model,
        'reasoning_effort': reasoning_effort,
        'timeout_seconds': args.timeout,
        'max_autopilot_continues': args.max_autopilot_continues,
        'stdout_json': args.stdout_json,
        'programmatic_mode': programmatic_mode,
        'output_path': str(output_path),
    }, ensure_ascii=False, indent=2))
    if args.dry_run:
        print('Log file:', log_path)
        return 0
    process = subprocess.Popen(
        cmd,
        cwd=ROOT,
        env=env,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        stdout, stderr = process.communicate(timeout=args.timeout)
        completed_returncode = process.returncode
    except subprocess.TimeoutExpired:
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], check=False, capture_output=True)
        stdout, stderr = process.communicate()
        append_log(log_path, 'stdout', stdout)
        append_log(log_path, 'stderr', stderr)
        append_log(log_path, 'timeout', f'Copilot CLI excedeu o timeout de {args.timeout}s.\noutput_exists={output_path.exists()}\n')
        emit_stream('stdout', stdout)
        emit_stream('stderr', stderr)
        print(f'Copilot CLI excedeu o timeout de {args.timeout}s.')
        print('Log file:', log_path)
        print('Output file exists:', output_path.exists())
        return 124
    append_log(log_path, 'stdout', stdout or '')
    append_log(log_path, 'stderr', stderr or '')
    if programmatic_mode and completed_returncode == 0:
        try:
            if output_is_textual(output_path):
                assistant_content = extract_assistant_content(stdout or '')
                output_path.write_text(assistant_content.rstrip() + '\n', encoding='utf-8')
            else:
                parsed_payload = extract_json_object(stdout or '')
                output_path.write_text(json.dumps(parsed_payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        except Exception as exc:
            append_log(log_path, 'parse_error', f'{type(exc).__name__}: {exc}\n')
            print(f'Falha ao interpretar saida do Copilot CLI: {exc}')
            print('Log file:', log_path)
            return 3
    append_log(log_path, 'result', f'returncode={completed_returncode}\noutput_exists={output_path.exists()}\n')
    emit_stream('stdout', stdout or '')
    emit_stream('stderr', stderr or '')
    print('Log file:', log_path)
    print('Output file exists:', output_path.exists())
    return completed_returncode


if __name__ == '__main__':
    raise SystemExit(main())
