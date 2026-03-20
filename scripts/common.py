#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = ROOT / 'workspace' / 'outputs' / 'active'
DEFAULT_DATA_DIR = ROOT / 'data' / 'raw'


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def parse_common_args(description: str, needs_input: bool = False) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--output', default=str(DEFAULT_OUTPUT_DIR), help='Diretório de saída JSON/artefatos')
    if needs_input:
        parser.add_argument('--input-dir', default=str(DEFAULT_OUTPUT_DIR), help='Diretório com artefatos de entrada')
    parser.add_argument('--data-dir', default=str(DEFAULT_DATA_DIR), help='Diretório com arquivos brutos')
    parser.add_argument('--verbose', action='store_true')
    return parser.parse_args()


def json_default(obj: Any):
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if hasattr(obj, 'item'):
        try:
            return obj.item()
        except Exception:
            pass
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f'Objeto não serializável: {type(obj)!r}')


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + '\n', encoding='utf-8')


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def output_file(output_dir: Path, name: str) -> Path:
    ensure_dir(output_dir)
    return output_dir / name


def input_file(input_dir: Path, name: str) -> Path:
    return input_dir / name


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default
