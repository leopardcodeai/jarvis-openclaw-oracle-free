"""
QM Coding Test Suite – 10 real coding challenges
LLM generates → script runs → output verified
Run: python tests/test_qm_coding.py
"""
import sys, os, asyncio, types, re, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
_p = types.ModuleType("src"); _p.__path__ = [os.path.join(ROOT, "src")]; sys.modules["src"] = _p

from src.llm_router import LLMRouter
from src.script_runner import run_code, extract_script_from_response, _fix_llm_code

G="\033[92m"; R="\033[91m"; Y="\033[93m"; B="\033[94m"; C="\033[96m"; E="\033[0m"
router = LLMRouter()
results = []

with open(os.path.join(ROOT, "src/conversation.py")) as f: _c = f.read()
_m = re.search(r'_default_system_prompt\s*=\s*"""(.*?)"""', _c, re.DOTALL)
SYSTEM = _m.group(1).strip() if _m else ""

def log(name, ok, detail="", timing=None):
    results.append((name, ok, detail))
    t = f"  {Y}{timing:.1f}s{E}" if timing else ""
    color = G if ok else R
    sym = "✅" if ok else "❌"
    print(f"  {color}{sym}{E} {name}{t}" + (f"\n     {Y}→ {detail}{E}" if detail and not ok else
          (f"\n     {G}→ {detail}{E}" if detail else "")))

_CODE_BLOCK = re.compile(r'```(?:python)?\s*\n(.*?)```', re.DOTALL)

def _extract_any_code(resp: str) -> dict | None:
    """Try JARVIS_EXEC marker first, then any fenced code block as fallback."""
    info = extract_script_from_response(resp)
    if info:
        return info
    m = _CODE_BLOCK.search(resp)
    if m:
        return {"code": m.group(1).strip(), "name": "script", "tags": "", "clean_text": ""}
    return None

async def run_coding_challenge(prompt: str) -> dict:
    t0 = time.time()
    r = await router.chat([{"role": "user", "content": prompt}], SYSTEM)
    elapsed = time.time() - t0
    resp = r.content or ""
    info = _extract_any_code(resp)
    if not info:
        return {"has_script": False, "elapsed": elapsed, "raw": resp[:200]}
    info["code"] = _fix_llm_code(info["code"])
    result = await run_code(info["code"])
    return {
        "has_script": True,
        "name": info.get("name", "?"),
        "elapsed": elapsed,
        "success": result.get("success", False),
        "stdout": (result.get("stdout") or "").strip(),
        "stderr": ((result.get("stderr") or "") + (result.get("error") or "")).strip(),
    }

# ══════════════════════════════════════════════════════════════════════════════

CHALLENGES = [
    # ── 1. Algorithmen ──────────────────────────────────────────────────────────
    (
        "Implementiere QuickSort mit einem JARVIS_EXEC Script. "
        "Sortiere diese Liste: [64, 34, 25, 12, 22, 11, 90, 1, 55, 42]. "
        "Gib das Ergebnis als eine einzige Zeile aus.",
        lambda out: all(x in out for x in ["1", "11", "90", "55"]) and
                    list(re.findall(r'\d+', out)) == sorted(re.findall(r'\d+', out), key=int),
        "QuickSort-Ergebnis korrekt (aufsteigend sortiert)",
    ),
    (
        "Implementiere Binary Search mit JARVIS_EXEC. "
        "Suche den Wert 73 in: [1, 5, 11, 22, 35, 47, 60, 73, 88, 99]. "
        "Gib nur den gefundenen Index aus (0-basiert).",
        lambda out: "7" in out.split(),
        "Binary Search Index = 7",
    ),
    # ── 2. String-Algorithmen ───────────────────────────────────────────────────
    (
        "Schreibe ein JARVIS_EXEC Script das prüft ob ein String ein Palindrom ist. "
        "Teste: 'racecar', 'hello', 'madam', 'python'. "
        "Ausgabe pro Wort: 'racecar: True' usw.",
        lambda out: "racecar: True" in out and "hello: False" in out and "madam: True" in out,
        "Palindrom-Erkennung korrekt",
    ),
    (
        "Implementiere Caesar-Cipher mit JARVIS_EXEC (ROT13). "
        "Verschlüssele: 'Hello World' → dann entschlüssele das Ergebnis zurück. "
        "Letzte Zeile der Ausgabe: das entschlüsselte Wort.",
        lambda out: "hello world" in out.lower() or "Hello World" in out,
        "ROT13 encode→decode ergibt Original",
    ),
    # ── 3. Datenstrukturen ──────────────────────────────────────────────────────
    (
        "Implementiere einen Stack (LIFO) mit JARVIS_EXEC als Python class. "
        "push(1), push(2), push(3), pop() → 3, peek() → 2, size() → 2. "
        "Gib pop-Ergebnis, peek-Ergebnis und size jeweils auf separaten Zeilen aus.",
        lambda out: "3" in out and "2" in out,
        "Stack push/pop/peek korrekt",
    ),
    (
        "Implementiere eine einfache HashMap Klasse (dict-Nachbau) mit JARVIS_EXEC. "
        "Methoden: set(key, value) und get(key). "
        "Test: set('name','Jarvis'), set('version','2.0'), print(get('name')), print(get('missing')). "
        "Ausgabe: 'Jarvis' dann 'None' (oder -1 falls key fehlt).",
        lambda out: "Jarvis" in out and ("None" in out or "-1" in out or "not found" in out.lower()),
        "HashMap: Jarvis gefunden, missing=None",
    ),
    # ── 4. Mathematik / Zahlentheorie ───────────────────────────────────────────
    (
        "Schreibe JARVIS_EXEC Script: berechne den GCD (ggT) von 252 und 105 mit dem Euklidischen Algorithmus. "
        "Dann das LCM (kgV). Ausgabe exakt:\n'GCD: 21'\n'LCM: 1260'",
        lambda out: "GCD: 21" in out and "LCM: 1260" in out,
        "GCD=21, LCM=1260",
    ),
    (
        "Implementiere das Sieb des Eratosthenes mit JARVIS_EXEC um alle Primzahlen bis 100 zu finden. "
        "Letzte Zeile der Ausgabe genau: 'Count: 25'",
        lambda out: "25" in out,
        "25 Primzahlen bis 100",
    ),
    # ── 5. Komplexere Algorithmen ───────────────────────────────────────────────
    (
        "Implementiere Dijkstra's Algorithmus mit JARVIS_EXEC. "
        "Graph: A→B(4), A→C(2), C→B(1), B→D(5), C→D(8). "
        "Kürzester Weg von A nach D. Ausgabe: 'Shortest: X' und 'Path: A→...→D'.",
        lambda out: "8" in out and ("A" in out and "D" in out),
        "Dijkstra: Shortest=8, Pfad enthält A und D",
    ),
    (
        "Implementiere einen LRU-Cache (Least Recently Used) mit JARVIS_EXEC, capacity=3. "
        "put(1,'a'), put(2,'b'), put(3,'c'), get(1) → 'a', put(4,'d') evicts key 2, "
        "get(2) → None oder -1. Gib get(1) und get(2) Ergebnis aus.",
        lambda out: ("a" in out.lower() or "1" in out) and ("none" in out.lower() or "-1" in out or "not found" in out.lower() or "None" in out),
        "LRU: get(1)='a', get(2)=None nach eviction",
    ),
]

# ══════════════════════════════════════════════════════════════════════════════

async def main():
    print(f"\n{B}{'═'*58}{E}")
    print(f"{B}  QM CODING TEST – 10 Herausforderungen (als QM Engineer){E}")
    print(f"{B}{'═'*58}{E}")

    categories = [
        "1. QuickSort",
        "2. Binary Search",
        "3. Palindrom-Check",
        "4. Caesar Cipher (ROT13)",
        "5. Stack (LIFO)",
        "6. HashMap",
        "7. GCD & LCM (Euklid)",
        "8. Sieb des Eratosthenes",
        "9. Dijkstra Shortest Path",
        "10. LRU-Cache",
    ]

    for i, ((prompt, check_fn, check_desc), cat) in enumerate(zip(CHALLENGES, categories)):
        print(f"\n  {C}[{i+1}/10] {cat}{E}")
        r = await run_coding_challenge(prompt)

        if not r["has_script"]:
            log(f"{cat}: Script generiert", False,
                f"LLM schrieb kein Script. Response: {r['raw'][:100]}", r["elapsed"])
            continue

        log(f"{cat}: Script generiert", True, f"name={r['name']}", r["elapsed"])

        if not r["success"]:
            log(f"{cat}: Ausgeführt", False, r["stderr"][:150])
            continue

        log(f"{cat}: Ausgeführt", True)

        ok = check_fn(r["stdout"])
        log(f"{cat}: Ergebnis korrekt ({check_desc})", ok,
            f"stdout: {r['stdout'][:120]}" if not ok else r["stdout"][:80])

    # ── Summary ────────────────────────────────────────────────────────────────
    print(f"\n{B}{'═'*58}{E}")
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    failed = total - passed
    # Count actual coding challenges passed (only "Ergebnis korrekt" checks)
    task_results = [(n, ok, d) for n, ok, d in results if "Ergebnis korrekt" in n or "Script generiert" in n]
    tasks_done = sum(1 for _, ok, _ in task_results if ok and "Ergebnis korrekt" in _)

    pct = int(passed / total * 100) if total else 0
    color = G if pct >= 85 else (Y if pct >= 65 else R)
    verdict = "BESTANDEN ✅" if pct >= 75 else "NACHARBEIT NÖTIG ❌"
    print(f"{color}QM Coding: {passed}/{total} Checks ({pct}%) – {verdict}{E}")
    print(f"{B}Coding Challenges gelöst: {tasks_done}/10{E}")

    if failed:
        print(f"\n{R}Fehlgeschlagene Checks:{E}")
        for n, ok, d in results:
            if not ok:
                print(f"  ❌ {n}" + (f"\n     {d}" if d else ""))

asyncio.run(main())
