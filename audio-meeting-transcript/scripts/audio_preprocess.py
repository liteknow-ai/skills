#!/usr/bin/env python3
"""
Audio Preprocessing - Convert any audio file to 16kHz mono WAV for Vosk.
Supports: mp3, wav, m4a, flac, ogg, aac, wma, etc.

Usage:
    python audio_preprocess.py <input_audio> [output_wav]

Output: JSON with wav_path and duration info.
"""
import sys
import os
import json
import subprocess


def get_ffmpeg():
    """Get ffmpeg binary path. Tries system ffmpeg first, then imageio-ffmpeg."""
    # Try system ffmpeg first
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True
        )
        if result.returncode == 0:
            return "ffmpeg"
    except (FileNotFoundError, OSError):
        pass

    # Fall back to imageio-ffmpeg bundled binary
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        raise RuntimeError(
            "ffmpeg not found. Either install ffmpeg on your system, "
            "or run: pip install imageio-ffmpeg"
        )


def get_audio_duration(wav_path):
    """Get audio duration in seconds using wave module."""
    import wave
    try:
        with wave.open(wav_path, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / float(rate) if rate > 0 else 0
    except Exception:
        return 0


def convert_audio(input_path, output_path=None):
    """
    Convert audio to 16kHz mono 16-bit PCM WAV.
    Returns (output_path, duration_seconds).
    """
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Audio file not found: {input_path}")

    if output_path is None:
        base = os.path.splitext(input_path)[0]
        output_path = os.path.join(
            os.path.dirname(base),
            os.path.basename(base) + "_16k_mono.wav"
        )

    ffmpeg = get_ffmpeg()

    # Convert: 16kHz, mono, 16-bit PCM
    cmd = [
        ffmpeg, "-y",
        "-i", input_path,
        "-ar", "16000",
        "-ac", "1",
        "-acodec", "pcm_s16le",
        "-vn",  # Strip video if any
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg conversion failed:\n{result.stderr[-500:]}"
        )

    duration = get_audio_duration(output_path)

    return output_path, duration


def format_duration(seconds):
    """Format seconds as HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python audio_preprocess.py <input_audio> [output_wav]")
        sys.exit(1)

    input_audio = sys.argv[1]
    output_wav = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        wav_path, duration = convert_audio(input_audio, output_wav)
        result = {
            "status": "success",
            "input": os.path.abspath(input_audio),
            "wav_path": os.path.abspath(wav_path),
            "duration": round(duration, 2),
            "duration_str": format_duration(duration),
            "sample_rate": 16000,
            "channels": 1,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({
            "status": "error",
            "error": str(e)
        }, ensure_ascii=False))
        sys.exit(1)
