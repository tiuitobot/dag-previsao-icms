#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
from fpdf import FPDF

sys.path.append(str(Path(__file__).resolve().parents[1]))

from common import parse_common_args, dump_json, load_json, output_file, input_file, ensure_dir
from forecast_core import render_html_report


class PDFRelatorio(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 12)
        self.cell(0, 8, 'DAG Previsão ICMS-SP', 0, 1, 'C')
        self.ln(2)

    def footer(self):
        self.set_y(-12)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 8, f'Página {self.page_no()}', 0, 0, 'C')


def main() -> int:
    args = parse_common_args('Step 09 - HTML/PDF output', needs_input=True)
    output_dir = ensure_dir(Path(args.output))
    input_dir = Path(args.input_dir)
    previsoes = load_json(input_file(input_dir, 'previsoes.json'))
    visual = load_json(input_file(input_dir, 'visualizacoes.json'))
    narrativa_path = input_file(input_dir, 'relatorio_narrativa.json')
    narrativa = load_json(narrativa_path) if narrativa_path.exists() else {'summary': 'Narrativa AI não executada nesta run.'}

    monthly = pd.DataFrame(previsoes['monthly_forecast']['records'])
    monthly['data'] = pd.to_datetime(monthly['data'])
    annual_totals = previsoes['annual_totals']
    html = render_html_report(
        Path(__file__).resolve().parents[2] / 'templates',
        'relatorio.html.j2',
        {
            'annual_totals': annual_totals,
            'monthly_rows': monthly.to_dict(orient='records'),
            'charts': visual['charts'],
            'narrativa': narrativa,
            'modelagem': previsoes.get('modelagem', {}),
        }
    )
    html_path = output_dir / 'relatorio_previsao_icms.html'
    html_path.write_text(html, encoding='utf-8')

    pdf = PDFRelatorio()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, 'Resumo Executivo', 0, 1)
    pdf.set_font('Helvetica', '', 11)
    for ano, dados in sorted(annual_totals.items()):
        pdf.cell(0, 7, f"{ano}: R$ {dados['mean']/1e9:.2f} bi (IC95%: {dados['low95']/1e9:.2f} - {dados['high95']/1e9:.2f})", 0, 1)
    pdf.ln(4)
    pdf.multi_cell(0, 6, str(narrativa.get('summary') or narrativa.get('instructions') or 'Narrativa indisponível.'))
    for chart in visual['charts']:
        chart_path = Path(chart)
        if chart_path.exists():
            pdf.add_page()
            pdf.set_font('Helvetica', 'B', 12)
            pdf.cell(0, 8, chart_path.name, 0, 1)
            pdf.image(str(chart_path), w=185)
    pdf_path = output_dir / 'relatorio_previsao_icms.pdf'
    pdf.output(str(pdf_path))

    payload = {
        'step': '09-pdf-output',
        'status': 'ok',
        'html': str(html_path),
        'pdf': str(pdf_path),
        'charts': visual['charts'],
    }
    dump_json(output_file(output_dir, 'relatorio_final.json'), payload)
    print('✓ relatorio_final.json gerado')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
