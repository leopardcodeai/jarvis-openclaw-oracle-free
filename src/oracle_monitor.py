import asyncio
import logging
import subprocess
import json
from datetime import datetime

logger = logging.getLogger(__name__)

COMPARTMENT_ID = "ocid1.tenancy.oc1..aaaaaaaaq7gax5mvmwhbfa76qc6g57iqcvi26ah524ys46coydwppokzxgma"


def _run_oci(args: list[str]) -> dict | None:
    """Run an OCI CLI command and return parsed JSON output."""
    try:
        result = subprocess.run(
            ["oci"] + args,
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except Exception as e:
        logger.error(f"OCI command failed: {e}")
    return None


def get_instance_status() -> dict:
    """Check Oracle Cloud for running instances."""
    data = _run_oci([
        "compute", "instance", "list",
        "--compartment-id", COMPARTMENT_ID,
        "--lifecycle-state", "RUNNING"
    ])

    if data and data.get("data"):
        instance = data["data"][0]
        instance_id = instance["id"]

        # Get public IP
        vnic_data = _run_oci([
            "compute", "instance", "list-vnics",
            "--instance-id", instance_id
        ])
        public_ip = None
        if vnic_data and vnic_data.get("data"):
            public_ip = vnic_data["data"][0].get("public-ip")

        return {
            "found": True,
            "name": instance.get("display-name", "openclaw-server"),
            "shape": instance.get("shape", ""),
            "ip": public_ip,
            "instance_id": instance_id,
            "region": "eu-frankfurt-1"
        }

    return {"found": False}


def check_retry_log() -> dict:
    """Check the retry log for recent activity."""
    try:
        with open("retry.log", "r") as f:
            lines = f.readlines()

        last_lines = lines[-10:] if len(lines) >= 10 else lines
        content = "".join(last_lines)

        attempt = 0
        last_time = None
        for line in reversed(lines):
            if "Versuch" in line and "Warte" in line:
                try:
                    attempt = int(line.split("Versuch")[1].strip().rstrip(")"))
                except:
                    pass
            if "Nächster Versuch" in line:
                try:
                    last_time = line.split(" - ")[0].strip()
                except:
                    pass
            if attempt and last_time:
                break

        still_running = attempt > 0

        return {
            "running": still_running,
            "attempt": attempt,
            "last_check": last_time,
            "snippet": content[-300:].strip()
        }
    except FileNotFoundError:
        return {"running": False, "attempt": 0, "last_check": None, "snippet": "Kein Log"}


class OracleMonitor:
    """Monitors Oracle Cloud instance creation and sends Telegram notifications."""

    def __init__(self, bot, chat_id: int):
        self.bot = bot
        self.chat_id = chat_id
        self._task: asyncio.Task | None = None
        self._instance_found = False
        self._check_interval = 60  # 1 Minute

    def start(self):
        """Start the background monitoring task."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._monitor_loop())
            logger.info("Oracle monitor started")

    def stop(self):
        """Stop the monitoring task."""
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("Oracle monitor stopped")

    async def _monitor_loop(self):
        """Main monitoring loop."""
        await asyncio.sleep(10)  # Initial delay
        while True:
            try:
                await self._check_and_notify()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor error: {e}")
            await asyncio.sleep(self._check_interval)

    async def _check_and_notify(self):
        """Check Oracle Cloud status and notify if instance found."""
        status = get_instance_status()

        if status["found"] and not self._instance_found:
            self._instance_found = True
            ip = status.get("ip", "unbekannt")
            msg = (
                f"🎉 *Captain Leopard! Mission erfüllt!*\n\n"
                f"Ihr Oracle Cloud Server ist online!\n\n"
                f"🖥 *Name:* `{status['name']}`\n"
                f"🌐 *IP:* `{ip}`\n"
                f"⚙️ *Shape:* `{status['shape']}`\n\n"
                f"*SSH-Verbindung:*\n"
                f"`ssh -i ~/.ssh/oracle_openclaw ubuntu@{ip}`\n\n"
                f"Bereit für die Installation, Captain!"
            )
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=msg,
                parse_mode="Markdown"
            )
            logger.info(f"Instance found! IP: {ip}")

    async def send_heartbeat(self, youtube_monitor=None) -> str:
        """Generate a heartbeat status message."""
        instance = get_instance_status()
        log = check_retry_log()
        now = datetime.now().strftime("%H:%M:%S")

        if instance["found"]:
            ip = instance.get("ip", "unbekannt")
            oracle_section = (
                f"✅ *Oracle Server:* Online\n"
                f"🌐 IP: `{ip}` | 🖥 `{instance['name']}`"
            )
        else:
            status = "🔄 Läuft" if log["running"] else "⚠️ Gestoppt"
            attempt = log["attempt"] or "?"
            last = log["last_check"] or "?"
            oracle_section = (
                f"⏳ *Oracle Instance:* Nicht verfügbar\n"
                f"🔁 Retry: {status} | Versuch #{attempt} | {last}"
            )

        yt_section = ""
        if youtube_monitor:
            yt = await youtube_monitor.get_status()
            latest = yt.get("latest")
            if latest:
                yt_section = (
                    f"\n\n🎥 *YouTube {yt['channel']}*\n"
                    f"📺 _{latest['title']}_\n"
                    f"📅 {latest['published']} | 🔗 {latest['url']}"
                )
            else:
                yt_section = f"\n\n🎥 *YouTube:* {yt['status']}"

        return (
            f"{'💚' if instance['found'] else '💛'} *Heartbeat – {now}*\n\n"
            f"{oracle_section}"
            f"{yt_section}\n\n"
            f"_Oracle: jede Minute | YouTube: stündlich_"
        )
