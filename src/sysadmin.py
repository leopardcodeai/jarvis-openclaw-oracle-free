import asyncio
import subprocess
import shlex
import logging

logger = logging.getLogger(__name__)

# Whitelist of allowed command prefixes (safe, read-only operations)
ALLOWED_COMMANDS = {
    "free": "free -h",
    "ram": "free -h",
    "disk": "df -h",
    "df": "df -h",
    "uptime": "uptime",
    "top": "top -bn1 | head -20",
    "ps": "ps aux --sort=-%cpu | head -20",
    "ping": None,   # handled separately
    "status ollama": "systemctl status ollama --no-pager -l",
    "status openclaw": "systemctl status openclaw --no-pager -l",
    "status tailscale": "systemctl status tailscaled --no-pager -l",
    "tailscale": "tailscale status",
    "ip": "ip addr show | grep inet",
    "whoami": "whoami",
    "uname": "uname -a",
    "logs ollama": "journalctl -u ollama -n 30 --no-pager",
    "logs openclaw": "journalctl -u openclaw -n 30 --no-pager",
    "restart ollama": "sudo systemctl restart ollama",
    "restart openclaw": "sudo systemctl restart openclaw",
}

ALLOWED_COMMAND_KEYS = list(ALLOWED_COMMANDS.keys())


def _run_sync(cmd: str, timeout: int = 15) -> dict:
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        output = result.stdout.strip() or result.stderr.strip() or "(keine Ausgabe)"
        return {"success": True, "output": output[:2000], "returncode": result.returncode}
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "⏱️ Timeout – Befehl zu langsam"}
    except Exception as e:
        return {"success": False, "output": str(e)}


async def run_command(user_input: str) -> dict:
    """Run a whitelisted system command safely."""
    user_input = user_input.strip().lower()

    # Check ping specially
    if user_input.startswith("ping "):
        host = shlex.split(user_input)[1] if len(shlex.split(user_input)) > 1 else None
        if host and all(c.isalnum() or c in "-._" for c in host):
            cmd = f"ping -c 3 -W 2 {host}"
            return await asyncio.get_event_loop().run_in_executor(None, _run_sync, cmd)
        return {"success": False, "output": "❌ Ungültiger Hostname"}

    # Match against whitelist
    for key, cmd in ALLOWED_COMMANDS.items():
        if user_input == key or user_input.startswith(key + " "):
            if cmd is None:
                return {"success": False, "output": "❌ Befehl nicht verfügbar"}
            return await asyncio.get_event_loop().run_in_executor(None, _run_sync, cmd)

    available = "\n".join(f"• `{k}`" for k in ALLOWED_COMMAND_KEYS)
    return {
        "success": False,
        "output": f"❌ Befehl nicht erlaubt. Verfügbare Befehle:\n{available}"
    }


def format_result(data: dict, command: str) -> str:
    if not data["success"]:
        return data["output"]
    code = data["returncode"]
    status = "✅" if code == 0 else "⚠️"
    return f"{status} *`{command}`*\n```\n{data['output']}\n```"
