"""
End-to-end graph generation tests.
Each script is what the LLM SHOULD generate. We run it through script_runner
and verify the output is a valid PNG via JARVIS_IMAGE:.
"""
import sys, os, asyncio, base64, struct, zlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)

from script_runner import run_code

G="\033[92m"; R="\033[91m"; Y="\033[93m"; B="\033[94m"; E="\033[0m"
results = []

def is_valid_png(data: bytes) -> bool:
    return data[:8] == b'\x89PNG\r\n\x1a\n' and len(data) > 100

def check(name, ok, detail=""):
    results.append((name, ok, detail))
    status = f"{G}✅ PASS{E}" if ok else f"{R}❌ FAIL{E}"
    print(f"  {status}  {name}" + (f"\n         {Y}{detail}{E}" if detail else ""))

GRAPH_TEMPLATE = '''
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import io, base64
from datetime import datetime, timedelta

{body}

plt.tight_layout()
buf = io.BytesIO()
fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
buf.seek(0)
print("JARVIS_IMAGE:" + base64.b64encode(buf.read()).decode())
plt.close(fig)
'''

TESTS = {
    "Sonnenstand Berlin 24h": GRAPH_TEMPLATE.format(body="""
import math
now = datetime.now()
hours = [(now - timedelta(hours=23-i)) for i in range(24)]
# Solar elevation angle (simplified – Berlin lat 52.5°)
lat = math.radians(52.5)
def solar_elevation(dt):
    doy = dt.timetuple().tm_yday
    hour = dt.hour + dt.minute/60
    decl = math.radians(23.45 * math.sin(math.radians(360/365*(doy-81))))
    ha = math.radians(15*(hour-12))
    alt = math.degrees(math.asin(math.sin(lat)*math.sin(decl)+math.cos(lat)*math.cos(decl)*math.cos(ha)))
    return max(alt, -90)
elevations = [solar_elevation(h) for h in hours]
labels = [h.strftime('%H:%M') for h in hours]
fig, ax = plt.subplots(figsize=(12,5))
ax.fill_between(range(24), elevations, alpha=0.3, color='orange')
ax.plot(range(24), elevations, color='orange', linewidth=2, marker='o', markersize=4)
ax.axhline(0, color='gray', linestyle='--', alpha=0.5, label='Horizont')
ax.fill_between(range(24), elevations, 0, where=[e>0 for e in elevations], alpha=0.2, color='yellow', label='Über Horizont')
ax.set_xticks(range(24))
ax.set_xticklabels(labels, rotation=45, fontsize=8)
ax.set_title('☀️ Sonnenstand Berlin – letzte 24h', fontsize=14, fontweight='bold')
ax.set_xlabel('Uhrzeit'); ax.set_ylabel('Elevation (°)')
ax.legend(); ax.grid(True, alpha=0.3)
"""),

    "Meeresspiegel Nordsee 24h": GRAPH_TEMPLATE.format(body="""
now = datetime.now()
hours = [(now - timedelta(hours=23-i)) for i in range(24)]
import math
# Simulated tidal curve (semidiurnal tide, M2 period ~12.4h)
t = [i * (2*math.pi/12.4) for i in range(24)]
sea_levels = [1.5 * math.sin(ti) + 0.3*math.sin(2*ti) + 0.1*(i%3-1)*0.05 for i, ti in enumerate(t)]
labels = [h.strftime('%H:%M') for h in hours]
fig, ax = plt.subplots(figsize=(12,5))
ax.fill_between(range(24), sea_levels, alpha=0.4, color='steelblue')
ax.plot(range(24), sea_levels, color='steelblue', linewidth=2)
ax.axhline(0, color='gray', linestyle='--', alpha=0.5)
high_times = [i for i in range(1, 23) if sea_levels[i] > sea_levels[i-1] and sea_levels[i] > sea_levels[i+1]]
for ht in high_times:
    ax.annotate(f'HW {sea_levels[ht]:.1f}m', xy=(ht, sea_levels[ht]), xytext=(ht, sea_levels[ht]+0.2),
                ha='center', fontsize=9, color='navy', fontweight='bold')
ax.set_xticks(range(24)); ax.set_xticklabels(labels, rotation=45, fontsize=8)
ax.set_title('🌊 Gezeitenverlauf Nordsee – letzte 24h', fontsize=14, fontweight='bold')
ax.set_xlabel('Uhrzeit'); ax.set_ylabel('Wasserstand (m über NN)')
ax.grid(True, alpha=0.3)
"""),

    "Temperaturverlauf München 7 Tage": GRAPH_TEMPLATE.format(body="""
import random; random.seed(42)
days = [(datetime.now() - timedelta(days=6-i)).strftime('%a %d.%m') for i in range(7)]
temps_max = [random.uniform(8, 18) for _ in range(7)]
temps_min = [t - random.uniform(4, 8) for t in temps_max]
fig, ax = plt.subplots(figsize=(10,5))
x = range(7)
ax.fill_between(x, temps_min, temps_max, alpha=0.3, color='tomato', label='Temperaturbereich')
ax.plot(x, temps_max, 'ro-', linewidth=2, markersize=8, label='Max')
ax.plot(x, temps_min, 'bo-', linewidth=2, markersize=8, label='Min')
for i, (mx, mn) in enumerate(zip(temps_max, temps_min)):
    ax.annotate(f'{mx:.1f}°', (i, mx), textcoords='offset points', xytext=(0,8), ha='center', fontsize=9, color='red')
    ax.annotate(f'{mn:.1f}°', (i, mn), textcoords='offset points', xytext=(0,-14), ha='center', fontsize=9, color='blue')
ax.set_xticks(x); ax.set_xticklabels(days)
ax.set_title('🌡️ Temperaturverlauf München – 7 Tage', fontsize=14, fontweight='bold')
ax.set_ylabel('Temperatur (°C)'); ax.legend(); ax.grid(True, alpha=0.3)
"""),

    "Normalverteilung Histogram": GRAPH_TEMPLATE.format(body="""
import random; random.seed(42)
data = [sum(random.random() for _ in range(12)) - 6 for _ in range(1000)]
fig, ax = plt.subplots(figsize=(10,5))
n, bins, patches = ax.hist(data, bins=40, color='steelblue', edgecolor='white', alpha=0.8, density=True)
import math
x = [bins[0] + i*(bins[-1]-bins[0])/200 for i in range(201)]
gauss = [math.exp(-xi**2/2)/math.sqrt(2*math.pi) for xi in x]
ax.plot(x, gauss, 'r-', linewidth=2, label='Normalverteilung N(0,1)')
ax.set_title('📊 Histogram – Normalverteilung (n=1000)', fontsize=14, fontweight='bold')
ax.set_xlabel('Wert'); ax.set_ylabel('Dichte')
ax.legend(); ax.grid(True, alpha=0.3)
"""),

    "Fibonacci Plot": GRAPH_TEMPLATE.format(body="""
def fib(n):
    a, b = 0, 1
    result = []
    for _ in range(n):
        result.append(a); a, b = b, a+b
    return result
fibs = fib(15)
fig, axes = plt.subplots(1, 2, figsize=(12,5))
axes[0].bar(range(15), fibs, color=['steelblue' if i%2==0 else 'orange' for i in range(15)])
axes[0].set_title('Fibonacci-Zahlen (linear)', fontweight='bold')
axes[0].set_xlabel('Index'); axes[0].set_ylabel('Wert')
axes[0].grid(True, alpha=0.3, axis='y')
axes[1].semilogy(range(15), [max(f,1) for f in fibs], 'go-', linewidth=2, markersize=8)
axes[1].set_title('Fibonacci-Zahlen (log)', fontweight='bold')
axes[1].set_xlabel('Index'); axes[1].set_ylabel('Wert (log)')
axes[1].grid(True, alpha=0.3)
"""),

    "Sinus Cosinus Graph": GRAPH_TEMPLATE.format(body="""
import math
x = [i*0.1 for i in range(63)]  # 0 to 2pi
sin_v = [math.sin(xi) for xi in x]
cos_v = [math.cos(xi) for xi in x]
tan_v = [max(-3, min(3, math.tan(xi))) for xi in x]
fig, ax = plt.subplots(figsize=(12,5))
ax.plot(x, sin_v, 'b-', linewidth=2.5, label='sin(x)')
ax.plot(x, cos_v, 'r-', linewidth=2.5, label='cos(x)')
ax.plot(x, tan_v, 'g--', linewidth=1.5, alpha=0.7, label='tan(x) (geclippt)')
ax.axhline(0, color='black', linewidth=0.8)
ax.set_xlim(0, 2*math.pi)
ax.set_ylim(-3.2, 3.2)
pi = math.pi
ax.set_xticks([0, pi/2, pi, 3*pi/2, 2*pi])
ax.set_xticklabels(['0', 'π/2', 'π', '3π/2', '2π'])
ax.set_title('📈 Trigonometrische Funktionen', fontsize=14, fontweight='bold')
ax.legend(fontsize=11); ax.grid(True, alpha=0.3)
"""),

    "Programmiersprachen Kreisdiagramm": GRAPH_TEMPLATE.format(body="""
langs = ['Python', 'JavaScript', 'TypeScript', 'Java', 'C++', 'Rust', 'Go', 'Andere']
sizes = [28, 22, 14, 12, 8, 5, 4, 7]
colors = ['#3776ab','#f7df1e','#3178c6','#b07219','#00599c','#ce422b','#00add8','#999']
explode = (0.05,)*len(langs)
fig, ax = plt.subplots(figsize=(10,7))
wedges, texts, autotexts = ax.pie(sizes, explode=explode, labels=langs, colors=colors,
    autopct='%1.1f%%', startangle=140, pctdistance=0.85)
for at in autotexts: at.set_fontsize(9)
ax.set_title('💻 Beliebteste Programmiersprachen 2024', fontsize=14, fontweight='bold', pad=20)
"""),

    "Deutsche Städte Einwohner": GRAPH_TEMPLATE.format(body="""
cities = ['Berlin','Hamburg','München','Köln','Frankfurt','Stuttgart','Düsseldorf','Leipzig']
pop = [3.7, 1.85, 1.55, 1.08, 0.76, 0.63, 0.62, 0.62]
colors = ['steelblue' if p > 1 else 'lightsteelblue' for p in pop]
fig, ax = plt.subplots(figsize=(11,6))
bars = ax.barh(cities, pop, color=colors, edgecolor='white', height=0.6)
for bar, val in zip(bars, pop):
    ax.text(val+0.03, bar.get_y()+bar.get_height()/2, f'{val:.2f}M', va='center', fontsize=10, fontweight='bold')
ax.set_xlabel('Einwohner (Millionen)')
ax.set_title('🏙️ Einwohnerzahl größter deutscher Städte', fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3, axis='x')
ax.set_xlim(0, 4.3)
ax.invert_yaxis()
"""),

    "Primzahlverteilung bis 100": GRAPH_TEMPLATE.format(body="""
def is_prime(n):
    if n < 2: return False
    for i in range(2, int(n**0.5)+1):
        if n%i==0: return False
    return True
primes = [n for n in range(2, 101) if is_prime(n)]
non_primes = [n for n in range(2, 101) if not is_prime(n)]
gaps = [primes[i+1]-primes[i] for i in range(len(primes)-1)]
fig, axes = plt.subplots(1, 2, figsize=(13,5))
axes[0].scatter(primes, [1]*len(primes), s=80, color='green', alpha=0.8, label=f'Primzahlen ({len(primes)})', zorder=3)
axes[0].scatter(non_primes, [0]*len(non_primes), s=20, color='lightgray', alpha=0.5, label='Zusammengesetzt', zorder=2)
axes[0].set_yticks([0,1]); axes[0].set_yticklabels(['Zusammengesetzt','Prim'])
axes[0].set_title('Primzahlen bis 100', fontweight='bold')
axes[0].grid(True, alpha=0.2); axes[0].legend()
axes[1].bar(range(len(gaps)), gaps, color='orange', alpha=0.8)
axes[1].set_title('Primzahllücken', fontweight='bold')
axes[1].set_xlabel('Primzahl-Index'); axes[1].set_ylabel('Lücke zur nächsten Primzahl')
axes[1].grid(True, alpha=0.3, axis='y')
"""),

    "Zufällige Kursentwicklung 30 Tage": GRAPH_TEMPLATE.format(body="""
import math, random; random.seed(99)
days = [(datetime.now() - timedelta(days=29-i)) for i in range(30)]
price = 100.0
prices = [price]
for _ in range(29):
    price *= (1 + random.gauss(0.002, 0.025))
    prices.append(max(price, 1))
dates = [d.strftime('%d.%m') for d in days]
fig, ax = plt.subplots(figsize=(12,5))
color = 'green' if prices[-1] >= prices[0] else 'red'
ax.fill_between(range(30), prices, prices[0], alpha=0.2, color=color)
ax.plot(range(30), prices, color=color, linewidth=2)
ax.axhline(prices[0], color='gray', linestyle='--', alpha=0.5, label=f'Start: {prices[0]:.2f}')
change = (prices[-1]/prices[0]-1)*100
ax.set_title(f'📈 Simulierter Kurs – 30 Tage | Veränderung: {change:+.1f}%', fontsize=13, fontweight='bold')
ax.set_xticks(range(0, 30, 3)); ax.set_xticklabels(dates[::3], rotation=45, fontsize=8)
ax.set_ylabel('Preis'); ax.legend(); ax.grid(True, alpha=0.3)
"""),
}

async def run_all():
    print(f"\n{B}═══ GRAPH GENERATION TESTS (end-to-end) ═══{E}\n")
    for name, code in TESTS.items():
        result = await run_code(code)
        stdout = (result.get("stdout") or "").strip()
        stderr = (result.get("stderr") or "").strip()

        if not result["success"]:
            check(name, False, f"Script error: {stderr[:120]}")
            continue

        if not stdout.startswith("JARVIS_IMAGE:"):
            check(name, False, f"No JARVIS_IMAGE in output: {stdout[:80]}")
            continue

        raw = stdout[len("JARVIS_IMAGE:"):].strip()
        raw += "=" * (-len(raw) % 4)
        try:
            img_bytes = base64.b64decode(raw)
        except Exception as e:
            check(name, False, f"base64 decode failed: {e}")
            continue

        if not is_valid_png(img_bytes):
            check(name, False, f"Not a valid PNG (len={len(img_bytes)}, magic={img_bytes[:8].hex()})")
            continue

        check(name, True, f"PNG OK – {len(img_bytes)//1024}KB")

asyncio.run(run_all())

print(f"\n{B}══════════════════════════════{E}")
passed = sum(1 for _, ok, _ in results if ok)
failed = len(results) - passed
color = G if failed == 0 else (Y if failed <= 2 else R)
print(f"{color}Results: {passed}/{len(results)} graph tests passed{E}")

if failed:
    print(f"\n{R}Failed:{E}")
    for n, ok, d in results:
        if not ok:
            print(f"  ❌ {n}: {d}")

import sys; sys.exit(0 if failed == 0 else 1)
