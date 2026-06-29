"""Generate QR codes for Booth Game.

Two types:
  1. SHORT QR — "engineer,high,mid,low" — for photo upload + jsQR
  2. URL QR  — full URL with params — for native camera scan (iPad/iPhone)

Usage:
  python gen_qr.py                                    # short QR only
  python gen_qr.py http://192.168.1.50:8000           # short + URL QR
"""
import qrcode, os, base64, io, sys
from qrcode.constants import ERROR_CORRECT_H

BASE = sys.argv[1] if len(sys.argv) > 1 else None
out = os.path.join(os.path.dirname(__file__), "qr_codes")
os.makedirs(out, exist_ok=True)

for f in list(os.listdir(out)):
    os.remove(os.path.join(out, f))

categories = {"engineer": "工程師", "management": "管理職", "sales": "業務"}
levels = {"high": "高", "mid": "中", "low": "低"}
all_b64 = {}

BOX_SIZE = 16

# ── 1. Short content QR codes (for photo upload + jsQR) ──
for cat in categories:
    for ed in levels:
        for ex in levels:
            for sk in levels:
                content = f"{cat},{ed},{ex},{sk}"
                name = f"{cat}_{ed}_{ex}_{sk}"
                qr = qrcode.QRCode(box_size=BOX_SIZE, border=4, error_correction=ERROR_CORRECT_H)
                qr.add_data(content); qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                img.save(os.path.join(out, f"{name}.png"))
                buf = io.BytesIO(); img.save(buf, format="PNG")
                all_b64[name] = base64.b64encode(buf.getvalue()).decode()

print(f"[SHORT] {len([k for k in all_b64 if not k.startswith('url_')])} QR codes")

# ── 2. URL QR codes (for native camera scan) ──
if BASE:
    for cat in categories:
        for ed in levels:
            for ex in levels:
                for sk in levels:
                    url = f"{BASE}/booth/?category={cat}&edu={ed}&experience={ex}&skill={sk}"
                    name = f"url_{cat}_{ed}_{ex}_{sk}"
                    qr = qrcode.QRCode(box_size=BOX_SIZE, border=4, error_correction=ERROR_CORRECT_H)
                    qr.add_data(url); qr.make(fit=True)
                    img = qr.make_image(fill_color="black", back_color="white")
                    img.save(os.path.join(out, f"{name}.png"))
                    buf = io.BytesIO(); img.save(buf, format="PNG")
                    all_b64[name] = base64.b64encode(buf.getvalue()).decode()
    print(f"[URL]   {81} QR codes (base: {BASE})")

# ── Reference HTML ──
def b64(k):
    return f"data:image/png;base64,{all_b64[k]}"

have_url = BASE is not None

html = """<!DOCTYPE html><html lang="zh-TW">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Booth QR Menu</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,sans-serif;background:#f5f5f5;padding:12px;color:#1a1a2e}
h1{font-size:1.1rem;text-align:center;margin:6px 0}
.sub{text-align:center;font-size:.72rem;color:#666;margin-bottom:10px}
.tabs{display:flex;gap:6px;justify-content:center;margin-bottom:12px;flex-wrap:wrap}
.tab{padding:5px 12px;border-radius:16px;border:1.5px solid #ddd;background:#fff;cursor:pointer;font-size:.72rem;font-weight:600;transition:all .2s}
.tab:hover{border-color:#4f46e5;color:#4f46e5}
.tab.active{background:#4f46e5;color:#fff;border-color:#4f46e5}
.cat-title{font-size:.9rem;font-weight:700;margin:12px 0 4px;padding:4px 8px;background:#eef2ff;border-left:3px solid #4f46e5;border-radius:4px}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-bottom:4px}
@media(max-width:500px){.grid{grid-template-columns:1fr 1fr}}
.card{background:#fff;border:1px solid #e0e0e0;border-radius:5px;padding:4px;text-align:center;break-inside:avoid}
.card img{width:80px;height:80px;display:block;margin:0 auto}
.card .l{font-size:.55rem;font-weight:600;margin-top:1px}
.note{background:#fff8e1;border:1px solid #ffe082;border-radius:6px;padding:8px 10px;margin:10px 0;font-size:.72rem;line-height:1.4}
.note2{background:#e3f2fd;border:1px solid #90caf9;border-radius:6px;padding:8px 10px;margin:10px 0;font-size:.72rem;line-height:1.4}
.tag{display:inline-block;font-size:.5rem;padding:1px 5px;border-radius:3px;margin-top:1px;font-weight:600}
.tag-short{background:#e8eaf6;color:#4f46e5}
.tag-url{background:#e8f5e9;color:#2e7d32}
.fade{display:none}
@media print{.card{box-shadow:none;border:1px solid #ccc}.grid{break-inside:avoid}.tabs{display:none}}
</style></head>
<body>
<h1>Booth QR Menu</h1>
<p class="sub">""" + ("印出後剪下，手機相機掃描 URL QR 自動開啟，或拍照上傳 Short QR" if have_url else "印出後剪下，拍照上傳 Short QR 到 Booth Game 圖片模式") + """</p>"""

if have_url:
    html += """<div class="tabs">
  <button class="tab active" onclick="f('all',this)">全部</button>
  <button class="tab" onclick="f('engineer',this)">工程師</button>
  <button class="tab" onclick="f('management',this)">管理職</button>
  <button class="tab" onclick="f('sales',this)">業務</button>
</div>
<script>
function f(c,b){document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));b.classList.add('active');document.querySelectorAll('.card').forEach(d=>d.classList.toggle('fade',c!='all'&&!d.dataset.cat.includes(c)));}
</script>"""
    html += f"""<div class="note2"><strong>iPad/iPhone：用相機掃描 URL QR</strong> — 相機對準 QR → 點擊通知 → 自動開啟配對（不需上傳照片）</div>"""

html += f"""<div class="note"><strong>Short QR：</strong> 拍照上傳到 Booth Game → 圖片模式 → 掃描 QR 標籤，自動辨識配對</div>"""

for cat in categories:
    html += f'<div class="cat-title">{categories[cat]}</div><div class="grid">'
    for ed in levels:
        for ex in levels:
            for sk in levels:
                name = f"{cat}_{ed}_{ex}_{sk}"
                lbl = f"{levels[ed]}/{levels[ex]}/{levels[sk]}"
                html += f'<div class="card" data-cat="{cat}"><img src="{b64(name)}" alt="{lbl}"><div class="l">{lbl}</div><span class="tag tag-short">short</span>'
                if have_url:
                    uname = f"url_{cat}_{ed}_{ex}_{sk}"
                    html += f'<br><img src="{b64(uname)}" alt="url" style="width:80px;height:80px;margin-top:2px"><span class="tag tag-url">url</span>'
                html += '</div>'
    html += '</div>'

html += '</body></html>'

with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
    f.write(html)

print(f"Printable menu: {os.path.join(out, 'index.html')}")
