import re
with open('F:\\Kyle\\Coding\\ESG_HRMS\\index.html', 'r', encoding='utf-8') as f:
    html = f.read()
opens = html.count('<div')
closes = html.count('</div>')
print(f'<div>: {opens}, </div>: {closes}, diff: {opens - closes}')
sections = re.findall(r'<div[^>]*id="section-([^"]*)"', html)
print(f'Sections found: {len(sections)}')
for s in sections:
    print(f'  - {s}')
