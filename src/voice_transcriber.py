import asyncio
import logging
import os
import tempfile

logger = logging.getLogger(__name__)

_model = None
_model_name = "base"  # tiny=39MB fast, base=74MB accurate, small=244MB best quality


def _load_model():
    global _model
    if _model is None:
        import whisper
        logger.info(f"Loading Whisper model '{_model_name}'...")
        _model = whisper.load_model(_model_name)
        logger.info("Whisper model loaded.")
    return _model


async def transcribe_voice(ogg_bytes: bytes) -> tuple[str, str]:
    """Transcribe voice bytes (OGG Opus) to text.
    Returns (transcribed_text, detected_language).
    Runs in a thread pool to avoid blocking the event loop.
    """
    def _run():
        model = _load_model()
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            f.write(ogg_bytes)
            tmp_path = f.name
        try:
            result = model.transcribe(
                tmp_path,
                language=None,       # auto-detect: de / en / etc.
                task="transcribe",
                fp16=False,          # CPU-safe
            )
            text = result.get("text", "").strip()
            lang = result.get("language", "unknown")
            return text, lang
        finally:
            os.unlink(tmp_path)

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _run)
