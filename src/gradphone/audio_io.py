"""Shared ffmpeg-based audio conversion helpers.

These were duplicated near-verbatim in voice_chat.py and translate.py; keeping
one copy means a fix (like the subprocess timeout below) lands in one place.

All conversions go through ffmpeg over pipes — small clips, no temp files. The
``timeout`` guards against a wedged ffmpeg hanging the worker thread forever
(these run under ``asyncio.to_thread``, which cannot cancel a blocked syscall).
"""

from __future__ import annotations

import io
import struct
import subprocess

# A clip-sized conversion should finish in well under a second; 30s is a
# generous ceiling that only trips on a genuinely stuck ffmpeg.
_FFMPEG_TIMEOUT = 30


def ffmpeg(args: list[str], stdin: bytes) -> bytes:
    """Run ffmpeg with bytes in/out via pipes; raise on non-zero exit."""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", *args],
        input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=_FFMPEG_TIMEOUT,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr.decode('utf-8', 'replace')[:300]}")
    return proc.stdout


def ogg_to_pcm16(audio: bytes, sample_rate: int) -> bytes:
    """Any Telegram audio (OGG/Opus, mp3, m4a, wav) → PCM16 mono @ sample_rate."""
    return ffmpeg(
        ["-i", "pipe:0", "-f", "s16le", "-acodec", "pcm_s16le",
         "-ac", "1", "-ar", str(sample_rate), "pipe:1"],
        audio,
    )


def wav_to_ogg_opus(wav: bytes) -> bytes:
    """WAV → OGG/Opus for Telegram's reply_voice."""
    return ffmpeg(
        ["-i", "pipe:0", "-c:a", "libopus", "-b:a", "32k", "-f", "ogg", "pipe:1"],
        wav,
    )


def pcm16_to_wav(pcm: bytes, sample_rate: int) -> bytes:
    """Wrap raw little-endian PCM16 mono in a minimal WAV container."""
    buf = io.BytesIO()
    data_len = len(pcm)
    byte_rate = sample_rate * 2  # mono, 16-bit
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_len))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, byte_rate, 2, 16))
    buf.write(b"data")
    buf.write(struct.pack("<I", data_len))
    buf.write(pcm)
    return buf.getvalue()
