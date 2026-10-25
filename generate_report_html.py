import html
import re

with open('PROJECT_REPORT.md', 'r', encoding='utf-8') as f:
    text = f.read()

lines = text.split('\n')
html_out = [
    '<!DOCTYPE html>',
    '<html lang="en">',
    '<head>',
    '<meta charset="UTF-8">',
    '<title>Conversational RAG Project Report</title>',
    '<style>',
    'body { font-family: "Calibri", "Segoe UI", Arial, sans-serif; line-height: 1.6; color: #111; max-width: 860px; margin: 30px auto; padding: 24px; background: #ffffff; }',
    'h1 { font-size: 22px; text-align: center; text-transform: uppercase; margin-top: 36px; margin-bottom: 16px; color: #000; border-bottom: 2px solid #222; padding-bottom: 6px; }',
    'h2 { font-size: 18px; margin-top: 28px; margin-bottom: 12px; color: #1a202c; border-bottom: 1px solid #cbd5e0; padding-bottom: 4px; }',
    'h3 { font-size: 15px; margin-top: 20px; margin-bottom: 8px; color: #2d3748; }',
    'h4 { font-size: 14px; margin-top: 16px; margin-bottom: 6px; color: #4a5568; }',
    'p { margin: 8px 0; text-align: justify; }',
    'table { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 13.5px; }',
    'th, td { border: 1px solid #cbd5e0; padding: 8px 10px; text-align: left; }',
    'th { background-color: #f1f5f9; font-weight: 600; color: #1e293b; }',
    'tr:nth-child(even) { background-color: #f8fafc; }',
    'code { background: #f1f5f9; padding: 2px 5px; border-radius: 4px; font-family: Consolas, monospace; font-size: 12.5px; }',
    'pre { background: #f8fafc; border: 1px solid #e2e8f0; padding: 12px; border-radius: 6px; overflow-x: auto; font-family: Consolas, monospace; font-size: 12px; line-height: 1.45; }',
    'pre code { background: none; padding: 0; }',
    'hr { border: 0; height: 1px; background: #cbd5e0; margin: 28px 0; }',
    'ul { margin: 8px 0 12px 20px; padding: 0; }',
    'li { margin-bottom: 4px; }',
    '@media print {',
    '  body { max-width: 100%; margin: 0; padding: 15mm; background: #fff; }',
    '  h1, h2 { page-break-after: avoid; }',
    '  table, pre { page-break-inside: avoid; }',
    '  .no-print { display: none; }',
    '}',
    '.btn-print { position: fixed; top: 18px; right: 24px; padding: 10px 18px; background: #2563eb; color: #fff; border: none; border-radius: 6px; font-size: 14px; font-weight: 600; cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,0.15); }',
    '.btn-print:hover { background: #1d4ed8; }',
    '</style>',
    '</head>',
    '<body>',
    '<button class="btn-print no-print" onclick="window.print()">🖨️ Print / Save as PDF</button>'
]

in_code = False
code_buf = []

for line in lines:
    if line.startswith('```'):
        if in_code:
            html_out.append('<pre><code>' + html.escape('\n'.join(code_buf)) + '</code></pre>')
            code_buf = []
            in_code = False
        else:
            in_code = True
        continue
    if in_code:
        code_buf.append(line)
        continue
    
    clean_line = line.strip()
    if line.startswith('# '):
        html_out.append(f'<h1>{html.escape(line[2:])}</h1>')
    elif line.startswith('## '):
        html_out.append(f'<h2>{html.escape(line[3:])}</h2>')
    elif line.startswith('### '):
        html_out.append(f'<h3>{html.escape(line[4:])}</h3>')
    elif line.startswith('#### '):
        html_out.append(f'<h4>{html.escape(line[5:])}</h4>')
    elif clean_line == '---':
        html_out.append('<hr>')
    elif clean_line.startswith('|') and clean_line.endswith('|'):
        cells = [c.strip() for c in clean_line.strip('|').split('|')]
        if all(re.match(r'^:?-+:?$', c) for c in cells):
            continue
        html_out.append('<tr>' + ''.join(f'<td>{html.escape(c)}</td>' for c in cells) + '</tr>')
    elif clean_line.startswith('- '):
        html_out.append(f'<li>{html.escape(clean_line[2:])}</li>')
    elif clean_line:
        html_out.append(f'<p>{html.escape(clean_line)}</p>')

html_out.append('</body></html>')

raw_html = '\n'.join(html_out)
raw_html = re.sub(r'(<tr>.*?</tr>(\s*<tr>.*?</tr>)*)', r'<table>\1</table>', raw_html, flags=re.DOTALL)
raw_html = re.sub(r'(<li>.*?</li>(\s*<li>.*?</li>)*)', r'<ul>\1</ul>', raw_html, flags=re.DOTALL)

with open('PROJECT_REPORT.html', 'w', encoding='utf-8') as f:
    f.write(raw_html)

print("SUCCESS")
