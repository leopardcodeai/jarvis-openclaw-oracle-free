"""
Plugin Manager – allows Jarvis to install packages and write persistent plugins at runtime.

Plugins are Python files in the plugins/ directory.
Each plugin exposes:
  PLUGIN_NAME: str
  PLUGIN_DESCRIPTION: str
  async def run(query: str) -> str   (optional)

The LLM can write a plugin via the marker:
  [JARVIS_PLUGIN: name=<name>, description=<desc>, packages=<pkg1,pkg2>]
  ```python
  <code>
  ```
"""

import asyncio
import importlib.util
import json
import logging
import re
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

PLUGINS_DIR = Path("plugins")
PLUGINS_DIR.mkdir(exist_ok=True)
INSTALL_LOG = Path("installed_packages.json")


# ── Package installation ───────────────────────────────────────────────────────

def _load_install_log() -> dict:
    if INSTALL_LOG.exists():
        try:
            return json.loads(INSTALL_LOG.read_text())
        except Exception:
            pass
    return {}


def _save_install_log(log: dict):
    INSTALL_LOG.write_text(json.dumps(log, indent=2))


async def pip_install(package: str) -> tuple[bool, str]:
    """Install a pip package at runtime. Returns (success, output)."""
    log = _load_install_log()
    loop = asyncio.get_event_loop()

    def _run():
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package, "--quiet"],
            capture_output=True, text=True, timeout=120
        )
        return result

    result = await loop.run_in_executor(None, _run)

    if result.returncode == 0:
        log[package] = {"installed": True, "output": result.stdout.strip()}
        _save_install_log(log)
        logger.info(f"Installed package: {package}")
        return True, f"✅ `{package}` installiert."
    else:
        logger.error(f"pip install {package} failed: {result.stderr}")
        return False, f"❌ Installation fehlgeschlagen:\n```\n{result.stderr[:500]}\n```"


def list_installed() -> list[str]:
    return list(_load_install_log().keys())


# ── Plugin loading ─────────────────────────────────────────────────────────────

_loaded_plugins: dict[str, object] = {}


def load_plugins() -> list[str]:
    """Load all .py files from plugins/ directory."""
    loaded = []
    for path in sorted(PLUGINS_DIR.glob("*.py")):
        name = path.stem
        try:
            spec = importlib.util.spec_from_file_location(f"plugins.{name}", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            _loaded_plugins[name] = module
            loaded.append(name)
            logger.info(f"Plugin loaded: {name}")
        except Exception as e:
            logger.error(f"Failed to load plugin {name}: {e}")
    return loaded


def list_plugins() -> list[dict]:
    out = []
    for name, mod in _loaded_plugins.items():
        out.append({
            "name": name,
            "description": getattr(mod, "PLUGIN_DESCRIPTION", "Keine Beschreibung"),
        })
    # Also list unloaded plugin files
    for path in PLUGINS_DIR.glob("*.py"):
        if path.stem not in _loaded_plugins:
            out.append({"name": path.stem, "description": "(nicht geladen)"})
    return out


async def run_plugin(name: str, query: str) -> str | None:
    """Run a loaded plugin's run() function if it exists."""
    mod = _loaded_plugins.get(name)
    if not mod:
        return None
    run_fn = getattr(mod, "run", None)
    if not run_fn:
        return f"Plugin `{name}` hat keine run()-Funktion."
    if asyncio.iscoroutinefunction(run_fn):
        return await run_fn(query)
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, run_fn, query)


# ── Plugin file writing ────────────────────────────────────────────────────────

PLUGIN_MARKER = r"\[JARVIS_PLUGIN:\s*name=([^,\]]+)(?:,\s*description=([^\],]+))?(?:,\s*packages=([^\]]+))?\]"


def extract_plugin_from_response(response: str) -> dict | None:
    """Extract plugin definition from LLM response."""
    marker = re.search(PLUGIN_MARKER, response, re.IGNORECASE)
    if not marker:
        return None
    code_match = re.search(r"```python\s*([\s\S]+?)```", response)
    if not code_match:
        return None
    return {
        "name": marker.group(1).strip().replace(" ", "_"),
        "description": (marker.group(2) or "").strip(),
        "packages": [p.strip() for p in (marker.group(3) or "").split(",") if p.strip()],
        "code": code_match.group(1).strip(),
    }


async def save_and_load_plugin(plugin: dict) -> tuple[bool, str]:
    """Write plugin to disk, install required packages, and load it."""
    name = plugin["name"]
    code = plugin["code"]
    packages = plugin.get("packages", [])

    # Install required packages
    for pkg in packages:
        ok, msg = await pip_install(pkg)
        if not ok:
            return False, f"Package-Installation fehlgeschlagen: {msg}"

    # Write plugin file
    path = PLUGINS_DIR / f"{name}.py"
    path.write_text(code)
    logger.info(f"Plugin written: {path}")

    # Load it
    try:
        spec = importlib.util.spec_from_file_location(f"plugins.{name}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _loaded_plugins[name] = module
        return True, f"✅ Plugin `{name}` gespeichert und geladen."
    except Exception as e:
        return False, f"❌ Plugin-Ladefehler: {e}"


# Load plugins on import
load_plugins()
