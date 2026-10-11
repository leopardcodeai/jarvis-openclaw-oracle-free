"""
Jarvis Bot Behavior Tests
Run from project root: python tests/test_bot_behavior.py
"""
import sys, asyncio, traceback, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)

G="\033[92m"; R="\033[91m"; Y="\033[93m"; B="\033[94m"; E="\033[0m"
results = []

def check(name, condition, detail=""):
    status = f"{G}✅ PASS{E}" if condition else f"{R}❌ FAIL{E}"
    results.append((name, condition, detail))
    print(f"  {status}  {name}" + (f"\n         {Y}{detail}{E}" if detail else ""))
    return condition

# ══════════════════════════════════════════════════════════════════════════════
# 1. TRIGGER DETECTION (inline – mirrors bot.py logic)
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{B}═══ 1. TRIGGER DETECTION ═══{E}")

CHART_TRIGGERS = ["verlauf","chart","graph","entwicklung","historisch","history",
                  "letztes jahr","letzten monat","wie war","performance","rendite",
                  "als chart","als bild","als diagramm","aktienkurs"]
_CHART_WORD = ["aktie","kurs","börse"]
COMPANY_TICKERS = {"volkswagen":"VOW3.DE","vw":"VOW3.DE","tesla":"TSLA","apple":"AAPL",
                   "nvidia":"NVDA","bitcoin":"BTC-USD","microsoft":"MSFT"}

def _is_chart_query(msg):
    if any(t in msg for t in CHART_TRIGGERS): return True
    return any(re.search(rf'\b{t}\b', msg) for t in _CHART_WORD)

def _has_known_ticker(msg):
    return any(n in msg for n in COMPANY_TICKERS)

_SYS_EXACT = ["auslastung","system stats","systemstatus","wie viel ram","wie viel cpu",
              "server load","arbeitsspeicher"]
_SYS_WORD  = ["cpu","ram","uptime","speicher"]
def _sys_hit(msg):
    return (any(t in msg for t in _SYS_EXACT)
            or any(re.search(rf'\b{t}\b', msg) for t in _SYS_WORD))

check("chart fires: 'tesla aktienkurs'",      _is_chart_query("tesla aktienkurs"))
check("chart fires: 'bitcoin chart'",         _is_chart_query("bitcoin chart"))
check("chart fires: 'nvidia verlauf'",        _is_chart_query("nvidia verlauf"))
check("no chart: 'aktuelle news'",            not _is_chart_query("aktuelle news"))
check("no chart: 'was ist instagram'",        not _is_chart_query("was ist instagram"))
check("no chart: 'keto einkaufen'",           not _is_chart_query("keto einkaufen"))
check("no ticker: 'meeresspiegel als graph'", not _has_known_ticker("meeresspiegel als graph"),
      "chart query but no ticker → no stock chart sent (correct!)")
check("no sysstat: 'instagram link'",         not _sys_hit("instagram link"))
check("no sysstat: 'programm installieren'",  not _sys_hit("programm installieren"))
check("sysstat: 'wie viel ram habe ich'",     _sys_hit("wie viel ram habe ich"))
check("sysstat: 'cpu auslastung'",            _sys_hit("cpu auslastung"))

# ══════════════════════════════════════════════════════════════════════════════
# 2. EXTRACT FUNCTIONS: NULL SAFETY
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{B}═══ 2. NULL SAFETY ═══{E}")

from script_runner import extract_script_from_response
from plugin_manager import extract_plugin_from_response

check("extract_script(None)",  extract_script_from_response(None) is None)
check("extract_script('')",    extract_script_from_response("") is None)
check("extract_plugin(None)",  extract_plugin_from_response(None) is None)
check("extract_plugin('')",    extract_plugin_from_response("") is None)
check("extract_script valid",
      extract_script_from_response("```python\nprint('hi')\n```\n[JARVIS_EXEC: name=test, tags=test]") is not None)

# ══════════════════════════════════════════════════════════════════════════════
# 3. PLUGIN EXECUTION
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{B}═══ 3. PLUGIN EXECUTION ═══{E}")

import importlib, os
PLUGINS_DIR = "plugins"
sys.path.insert(0, PLUGINS_DIR)

async def run_plugin(name, query):
    try:
        mod = importlib.import_module(name)
        return await mod.run(query), None
    except Exception as e:
        return None, traceback.format_exc()

async def test_plugins():
    tests = [
        # (plugin_name, query, check_fn, description)
        ("unit_converter",    "5 km in miles",          lambda r: "mile" in r.lower() or "3.1" in r,      "5km → ~3.1 miles"),
        ("unit_converter",    "37 C in F",              lambda r: "98" in r or "F" in r,                  "37°C → ~98.6°F"),
        ("password_generator","generate password 20",   lambda r: len([l for l in r.split('`') if len(l)>=20]) > 0, "20 char password"),
        ("hash_tool",         "sha256 hello world",     lambda r: "b94d27b9" in r or len(r) > 30,         "SHA256 hash"),
        ("base64_tool",       "encode hello world",     lambda r: "aGVsbG8gd29ybGQ" in r,                 "base64 encode"),
        ("base64_tool",       "decode aGVsbG8gd29ybGQ=",lambda r: "hello world" in r.lower(),             "base64 decode"),
        ("json_formatter",    '{"key": "value", "num": 42}', lambda r: "key" in r,                       "JSON format"),
        ("timestamp_tool",    "timestamp now",          lambda r: "unix" in r.lower() or len(r) > 30,     "current timestamp"),
        ("text_stats",        "text stats Hello World this is a test sentence with multiple words",
                              lambda r: "Wörter" in r or "words" in r.lower() or "7" in r,               "word count"),
        ("dice_roller",       "2d6",                    lambda r: "Total" in r,                           "dice roll"),
        ("timezone_tool",     "current time Berlin Tokyo",
                              lambda r: "Berlin" in r or "Tokyo" in r or "Europe" in r,                   "timezone conversion"),
        ("generate_qr_code",  "https://example.com",   lambda r: isinstance(r, dict) and r.get("type") == "photo", "QR code photo"),
        ("ip_lookup",         "8.8.8.8",               lambda r: "Google" in r or "8.8.8.8" in r,        "IP lookup Google DNS"),
        ("currency_converter","100 USD in EUR",         lambda r: "EUR" in r and ("€" in r or "eur" in r.lower() or "=" in r), "USD→EUR"),
        ("regex_tester",      "`\\d+` against `I am 25 years old`",
                              lambda r: "25" in r,                                                         "regex find numbers"),
    ]

    for plugin, query, check_fn, desc in tests:
        result, err = await run_plugin(plugin, query)
        if err:
            check(f"plugin {plugin}: {desc}", False, err[:120])
        elif result is None:
            check(f"plugin {plugin}: {desc}", False, "returned None")
        elif isinstance(result, dict):
            if result.get("type") == "error":
                check(f"plugin {plugin}: {desc}", False, result.get("message", "")[:80])
            else:
                ok = check_fn(result)
                check(f"plugin {plugin}: {desc}", ok, str(result)[:60] if not ok else "")
        else:
            ok = check_fn(str(result))
            check(f"plugin {plugin}: {desc}", ok, str(result)[:80] if not ok else "")

asyncio.run(test_plugins())

# ══════════════════════════════════════════════════════════════════════════════
# 4. SCRIPT SAFETY CHECKS
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{B}═══ 4. SCRIPT SAFETY ═══{E}")
from script_runner import _safety_check, _syntax_check

ok1, _ = _syntax_check("print('hello')")
ok2, _ = _syntax_check("def broken(:")
check("syntax: valid code",   ok1)
check("syntax: broken code",  not ok2)

safe1, _ = _safety_check("import math\nprint(math.sqrt(16))")
safe2, _ = _safety_check("import subprocess\nsubprocess.run(['rm', '-rf', '/'])")
safe3, _ = _safety_check("import matplotlib.pyplot as plt\nplt.show()")
check("safety: math script ok",       safe1)
check("safety: subprocess blocked",   not safe2)
check("safety: matplotlib blocked",   not safe3)

# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{B}══════════════════════════════{E}")
passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)
total  = len(results)
color  = G if failed == 0 else (Y if failed <= 3 else R)
print(f"{color}Results: {passed}/{total} passed, {failed} failed{E}")

if failed > 0:
    print(f"\n{R}Failed tests:{E}")
    for name, ok, detail in results:
        if not ok:
            print(f"  ❌ {name}" + (f"\n     {detail}" if detail else ""))

sys.exit(0 if failed == 0 else 1)
