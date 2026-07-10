#!/usr/bin/env python3
"""
B站音频流下载脚本
=================
从B站视频下载音频流并转换为WAV格式（16kHz mono）。

用法：
    python bili_audio_download.py <BV号> [--output <输出目录>]

示例：
    python bili_audio_download.py BV1zvMu6UEYC
    python bili_audio_download.py BV1zvMu6UEYC --output /tmp/audio_work

前置依赖：
    如未安装依赖，先运行: python env_setup.py --fix
    或手动安装: pip install imageio-ffmpeg
"""
import sys
import os
import json
import time
import argparse
import subprocess


def get_cid(bvid: str) -> int:
    """通过BV号获取视频的cid"""
    import urllib.request
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": f"https://www.bilibili.com/video/{bvid}"
    })
    resp = urllib.request.urlopen(req, timeout=30)
    data = json.loads(resp.read().decode("utf-8"))
    if data["code"] != 0:
        raise RuntimeError(f"API error: {data.get('message', 'unknown')}")
    return data["data"]["cid"]


def get_audio_url(bvid: str, cid: int) -> dict:
    """获取DASH格式音频流URL"""
    import urllib.request
    url = f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&fnval=16&fnver=0"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": f"https://www.bilibili.com/video/{bvid}"
    })
    resp = urllib.request.urlopen(req, timeout=30)
    data = json.loads(resp.read().decode("utf-8"))
    if data["code"] != 0:
        raise RuntimeError(f"API error: {data.get('message', 'unknown')}")

    dash = data["data"]["dash"]
    if not dash or "audio" not in dash or len(dash["audio"]) == 0:
        raise RuntimeError("No audio stream available")

    # 选码率最高的音频流
    audio_streams = sorted(dash["audio"], key=lambda x: x.get("bandwidth", 0), reverse=True)
    best = audio_streams[0]
    return {
        "url": best["baseUrl"],
        "bandwidth": best.get("bandwidth", 0),
        "codecs": best.get("codecs", "unknown"),
        "duration": data["data"].get("dash", {}).get("duration", 0),
    }


def download_audio(url: str, output_path: str, referer: str = ""):
    """下载音频流文件"""
    import urllib.request
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": referer or "https://www.bilibili.com/",
    })
    resp = urllib.request.urlopen(req, timeout=60)
    total = int(resp.headers.get("Content-Length", 0))
    print(f"Audio stream size: {total / 1024 / 1024:.1f} MB")

    downloaded = 0
    t0 = time.time()
    with open(output_path, "wb") as f:
        while True:
            chunk = resp.read(131072)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if downloaded % (5 * 1024 * 1024) < 131072:
                pct = downloaded / total * 100 if total else 0
                speed = downloaded / 1024 / 1024 / (time.time() - t0) if time.time() > t0 else 0
                print(f"  {downloaded / 1024 / 1024:.0f}/{total / 1024 / 1024:.0f} MB ({pct:.0f}%) [{speed:.1f} MB/s]")

    elapsed = time.time() - t0
    print(f"Downloaded in {elapsed:.1f}s")


def convert_to_wav(input_path: str, output_path: str):
    """使用imageio-ffmpeg将音频转换为WAV (16kHz mono)"""
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        # 尝试系统ffmpeg
        ffmpeg = "ffmpeg"

    cmd = [
        ffmpeg, "-y", "-i", input_path,
        "-ar", "16000", "-ac", "1", "-f", "wav",
        output_path
    ]
    print(f"Converting to WAV: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"FFmpeg stderr: {result.stderr[-500:]}")
        raise RuntimeError("FFmpeg conversion failed")

    size = os.path.getsize(output_path)
    print(f"WAV file: {output_path} ({size / 1024 / 1024:.1f} MB)")


def main():
    parser = argparse.ArgumentParser(description="Download audio from Bilibili")
    parser.add_argument("bvid", help="Bilibili BV ID (e.g., BV1zvMu6UEYC)")
    parser.add_argument("--output", default=None, help="Output directory (default: TEMP/bili_audio)")
    args = parser.parse_args()

    bvid = args.bvid
    work_dir = args.output or os.path.join(os.environ.get("TEMP", "/tmp"), "bili_audio")
    os.makedirs(work_dir, exist_ok=True)

    print(f"BV ID: {bvid}")
    print(f"Work dir: {work_dir}")

    # Step 1: Get CID
    print("\n[1/4] Getting CID...")
    cid = get_cid(bvid)
    print(f"  CID: {cid}")

    # Step 2: Get audio URL
    print("\n[2/4] Getting audio stream URL...")
    audio_info = get_audio_url(bvid, cid)
    print(f"  Bandwidth: {audio_info['bandwidth']}")
    print(f"  Codecs: {audio_info['codecs']}")
    print(f"  Duration: {audio_info['duration']}s")

    # Step 3: Download audio
    print("\n[3/4] Downloading audio stream...")
    m4s_path = os.path.join(work_dir, "audio.m4s")
    referer = f"https://www.bilibili.com/video/{bvid}"
    download_audio(audio_info["url"], m4s_path, referer)

    # Step 4: Convert to WAV
    print("\n[4/4] Converting to WAV (16kHz mono)...")
    wav_path = os.path.join(work_dir, "audio.wav")
    convert_to_wav(m4s_path, wav_path)

    print(f"\nDone!")
    print(f"  Audio stream: {m4s_path}")
    print(f"  WAV file:     {wav_path}")
    print(f"  Duration:     {audio_info['duration']}s ({audio_info['duration'] // 60}m {audio_info['duration'] % 60}s)")


if __name__ == "__main__":
    main()
