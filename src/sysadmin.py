import asyncio
import subprocess
import shlex
import logging
import platform
import time

import psutil

logger = logging.getLogger(__name__)


def get_system_stats() -> dict:
    """Collect real-time system resource stats via psutil."""
    cpu = psutil.cpu_percent(interval=0.5)
    cpu_count = psutil.cpu_count()
    freq = psutil.cpu_freq()

    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()

    disk = psutil.disk_usage("/")

    uptime_secs = int(time.time() - psutil.boot_time())
    h, rem = divmod(uptime_secs, 3600)
    m, s = divmod(rem, 60)
    uptime_str = f"{h}h {m}m"

    # GPU via nvidia-smi if available
    gpu_info = None
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            parts = [p.strip() for p in result.stdout.strip().split(",")]
            if len(parts) >= 5:
                gpu_info = {
                    "name": parts[0],
                    "util_pct": parts[1],
                    "mem_used_mb": parts[2],
                    "mem_total_mb": parts[3],
                    "temp_c": parts[4],
                }
    except Exception:
        pass

    # macOS often returns bogus low MHz values – only show if plausible (> 100 MHz)
    freq_mhz = None
    if freq and freq.current > 100:
        freq_mhz = round(freq.current)

    return {
        "cpu_pct": cpu,
        "cpu_cores": cpu_count,
        "cpu_freq_mhz": freq_mhz,
        "ram_used_gb": round(mem.used / 1e9, 1),
        "ram_total_gb": round(mem.total / 1e9, 1),
        "ram_pct": mem.percent,
        "swap_used_gb": round(swap.used / 1e9, 1),
        "swap_total_gb": round(swap.total / 1e9, 1),
        "disk_used_gb": round(disk.used / 1e9, 1),
        "disk_total_gb": round(disk.total / 1e9, 1),
        "disk_pct": disk.percent,
        "uptime": uptime_str,
        "os": platform.system(),
        "node": platform.node(),
        "gpu": gpu_info,
    }


def format_system_stats(s: dict) -> str:
    """Format system stats as a Telegram-ready Markdown string."""
    gpu_line = ""
    if s.get("gpu"):
        g = s["gpu"]
        gpu_line = (
            f"\n\n🎮 *GPU:* {g['name']}\n"
            f"  ⚡ Auslastung: `{g['util_pct']}%` | 🌡 Temp: `{g['temp_c']}°C`\n"
            f"  💾 VRAM: `{g['mem_used_mb']} / {g['mem_total_mb']} MB`"
        )

    if s.get("cpu_freq_mhz"):
        mhz = s["cpu_freq_mhz"]
        if mhz >= 1000:
            cpu_freq = f" @ {mhz/1000:.1f} GHz"
        else:
            cpu_freq = f" @ {mhz} MHz"
    else:
        cpu_freq = ""

    return (
        f"🖥 *System-Auslastung* | `{s['node']}` ({s['os']})\n"
        f"⏱ Uptime: `{s['uptime']}`\n\n"
        f"🔲 *CPU:* `{s['cpu_pct']}%` ({s['cpu_cores']} Kerne{cpu_freq})\n"
        f"🧠 *RAM:* `{s['ram_used_gb']} / {s['ram_total_gb']} GB` ({s['ram_pct']}%)\n"
        f"💾 *Swap:* `{s['swap_used_gb']} / {s['swap_total_gb']} GB`\n"
        f"📀 *Disk:* `{s['disk_used_gb']} / {s['disk_total_gb']} GB` ({s['disk_pct']}%)"
        f"{gpu_line}"
    )

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
