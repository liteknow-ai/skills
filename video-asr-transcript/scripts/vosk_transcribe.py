#!/usr/bin/env python
"""
Vosk 离线语音识别转录脚本
使用 Vosk + vosk-model-small-cn 对中文音频进行离线转录

用法：
    python vosk_transcribe.py --audio <wav文件> --model <模型目录> [--output <输出文件>]

示例：
    python vosk_transcribe.py --audio audio.wav --model vosk-model-small-cn-0.22 --output transcript.txt

要求：
    - 音频格式：WAV, 16kHz, mono
    - 依赖：vosk, wave (Python标准库)
    - 模型：vosk-model-small-cn-0.22 (https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip)
"""
import argparse
import json
import os
import sys
import time
import wave


def download_model(model_dir: str, work_dir: str):
    """下载并解压 Vosk 中文小模型"""
    import urllib.request
    import zipfile

    url = "https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip"
    zip_path = os.path.join(work_dir, "vosk-model-small-cn.zip")

    if os.path.isdir(model_dir):
        print(f"Model already exists: {model_dir}")
        return

    print(f"Downloading Vosk model from {url}...")
    t0 = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=120)
    total = int(resp.headers.get("Content-Length", 0))
    print(f"  File size: {total / 1024 / 1024:.1f} MB")

    downloaded = 0
    with open(zip_path, "wb") as f:
        while True:
            chunk = resp.read(131072)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if downloaded % (5 * 1024 * 1024) < 131072:
                print(f"  {downloaded / 1024 / 1024:.0f}/{total / 1024 / 1024:.0f} MB ({downloaded / total * 100:.0f}%)")

    elapsed = time.time() - t0
    print(f"  Downloaded in {elapsed:.1f}s")

    print("Extracting...")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(work_dir)
    print(f"  Extracted to {model_dir}")


def transcribe(wav_path: str, model_dir: str, out_txt: str, out_srt: str = None):
    """使用Vosk转录音频"""
    from vosk import Model, KaldiRecognizer

    # Load model
    print(f"Loading Vosk model: {model_dir}")
    t0 = time.time()
    model = Model(model_dir)
    print(f"  Model loaded in {time.time() - t0:.1f}s")

    # Open WAV
    wf = wave.open(wav_path, "rb")
    channels = wf.getnchannels()
    rate = wf.getframerate()
    frames = wf.getnframes()
    duration = frames / rate

    print(f"Audio: {wav_path}")
    print(f"  Channels: {channels}, Rate: {rate}Hz")
    print(f"  Duration: {duration:.1f}s ({duration // 60:.0f}m {duration % 60:.0f}s)")

    if channels != 1:
        print("WARNING: Audio is not mono. Consider converting with ffmpeg: -ac 1")
    if rate != 16000:
        print("WARNING: Audio rate is not 16000Hz. Consider converting with ffmpeg: -ar 16000")

    # Recognizer
    rec = KaldiRecognizer(model, rate)
    rec.SetWords(True)

    # Transcribe
    print(f"\nTranscribing...")
    t0 = time.time()

    results = []
    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            if result.get("text"):
                results.append(result)

    # Final
    final = json.loads(rec.FinalResult())
    if final.get("text"):
        results.append(final)

    elapsed = time.time() - t0
    print(f"Transcription completed in {elapsed:.1f}s ({duration / elapsed:.1f}x realtime)")
    print(f"Got {len(results)} segments")

    # Build full text
    full_text = "".join(r.get("text", "").strip() for r in results)
    print(f"Full text: {len(full_text)} chars")

    # Save txt
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(full_text)
    print(f"Saved text: {out_txt}")

    # Save SRT
    if out_srt:
        def fmt_ts(seconds):
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            ms = int((seconds - int(seconds)) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        with open(out_srt, "w", encoding="utf-8") as f:
            idx = 1
            for r in results:
                words = r.get("result", [])
                if not words:
                    continue
                start = words[0]["start"]
                end = words[-1]["end"]
                text = r.get("text", "").strip()
                if not text:
                    continue
                f.write(f"{idx}\n")
                f.write(f"{fmt_ts(start)} --> {fmt_ts(end)}\n")
                f.write(f"{text}\n\n")
                idx += 1
        print(f"Saved SRT: {out_srt}")

    # Preview
    print("\n" + "=" * 60)
    print("PREVIEW (first 500 chars):")
    print("=" * 60)
    print(full_text[:500])
    print("=" * 60)

    return full_text


def main():
    parser = argparse.ArgumentParser(description="Vosk offline transcription")
    parser.add_argument("--audio", required=True, help="Path to WAV audio file (16kHz mono)")
    parser.add_argument("--model", required=True, help="Path to Vosk model directory")
    parser.add_argument("--output", default="transcript.txt", help="Output text file path")
    parser.add_argument("--srt", default=None, help="Output SRT file path (optional)")
    parser.add_argument("--download-model", action="store_true", help="Download model if not found")
    args = parser.parse_args()

    wav_path = os.path.abspath(args.audio)
    model_dir = os.path.abspath(args.model)
    out_txt = os.path.abspath(args.output)
    out_srt = os.path.abspath(args.srt) if args.srt else None

    # Verify audio
    if not os.path.isfile(wav_path):
        print(f"ERROR: Audio file not found: {wav_path}")
        sys.exit(1)

    # Download model if needed
    if not os.path.isdir(model_dir) and args.download_model:
        work_dir = os.path.dirname(model_dir)
        download_model(model_dir, work_dir)

    if not os.path.isdir(model_dir):
        print(f"ERROR: Model directory not found: {model_dir}")
        print(f"  Use --download-model to auto-download, or download manually from:")
        print(f"  https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip")
        sys.exit(1)

    transcribe(wav_path, model_dir, out_txt, out_srt)


if __name__ == "__main__":
    main()
