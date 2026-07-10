#!/usr/bin/env python3
"""
抖音视频音频下载脚本
=====================
通过 iesdouyin 移动端页面提取视频流地址，下载无水印 MP4 并转换为 WAV 音频。

原理：
1. 访问 https://www.iesdouyin.com/share/video/{video_id}（移动端 User-Agent）
2. 从页面 HTML 中提取 window._ROUTER_DATA JSON 数据
3. 从 JSON 中获取 play_addr.url_list[0]
4. 将 URL 中的 playwm 改为 play 获取无水印版本
5. 下载 MP4 → ffmpeg 转换为 WAV（16kHz mono）

无需登录/Cookie，仅需移动端 User-Agent。

用法：
    python douyin_audio_download.py <video_id> [--output-dir <dir>]

示例：
    python douyin_audio_download.py 7657058079216848178
    python douyin_audio_download.py 7657058079216848178 --output-dir /tmp/douyin_work

前置依赖：
    如未安装依赖，先运行: python env_setup.py --fix
    或手动安装: pip install requests imageio-ffmpeg
"""

import argparse
import json
import os
import re
import subprocess
import sys
from urllib.parse import unquote

try:
    import requests
except ImportError:
    sys.exit(
        "错误: requests 未安装。\n"
        "请运行: python scripts/env_setup.py --fix\n"
        "或手动: pip install requests"
    )

try:
    import imageio_ffmpeg
except ImportError:
    sys.exit(
        "错误: imageio-ffmpeg 未安装。\n"
        "请运行: python scripts/env_setup.py --fix\n"
        "或手动: pip install imageio-ffmpeg"
    )


def get_video_data(video_id: str) -> dict:
    """从 iesdouyin 移动端页面提取视频数据"""
    url = f"https://www.iesdouyin.com/share/video/{video_id}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/16.6 Mobile/15E148 Safari/604.1"
        ),
        "Referer": "https://www.douyin.com/",
        "Accept": "text/html,application/xhtml+xml",
    }

    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()

    # 提取 window._ROUTER_DATA
    match = re.search(
        r"window\._ROUTER_DATA\s*=\s*(.*?)(?:</script>|\Z)",
        resp.text,
        re.DOTALL,
    )
    if not match:
        raise RuntimeError("未找到 _ROUTER_DATA，页面结构可能已变化")

    raw = match.group(1)
    # 修复 Unicode 转义
    raw = raw.replace("\\u002F", "/")
    data = json.loads(raw)

    # 导航到视频信息
    loader = data.get("loaderData", {})
    for key, val in loader.items():
        if isinstance(val, dict) and "videoInfoRes" in val:
            item_list = val["videoInfoRes"].get("item_list", [])
            if item_list:
                return item_list[0]

    raise RuntimeError("未找到视频信息，可能视频已被删除或设为私密")


def get_play_url(video_data: dict) -> str:
    """从视频数据中提取无水印播放地址"""
    video = video_data.get("video", {})
    play_addr = video.get("play_addr", {})
    urls = play_addr.get("url_list", [])
    if not urls:
        raise RuntimeError("未找到播放地址")

    # playwm → play 获取无水印版本
    play_url = urls[0].replace("playwm", "play")
    return play_url


def download_video(url: str, output_path: str) -> int:
    """下载视频文件"""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/16.6 Mobile/15E148 Safari/604.1"
        ),
        "Referer": "https://www.iesdouyin.com/",
    }

    resp = requests.get(url, headers=headers, timeout=120, stream=True)
    resp.raise_for_status()

    total = int(resp.headers.get("content-length", 0))
    print(f"视频大小: {total / 1024 / 1024:.1f} MB")

    downloaded = 0
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if downloaded % (1024 * 1024) < 65536:
                    print(f"  下载进度: {downloaded / 1024 / 1024:.1f} MB")

    print(f"下载完成: {downloaded} bytes ({downloaded / 1024 / 1024:.1f} MB)")
    return downloaded


def convert_to_wav(video_path: str, wav_path: str) -> None:
    """将 MP4 转换为 WAV（16kHz mono 16-bit）"""
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg, "-y",
        "-i", video_path,
        "-vn",               # 不要视频流
        "-acodec", "pcm_s16le",
        "-ar", "16000",      # 16kHz
        "-ac", "1",          # 单声道
        wav_path,
    ]
    print(f"转换音频: {video_path} → {wav_path}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"ffmpeg stderr: {result.stderr[-500:]}", file=sys.stderr)
        raise RuntimeError("ffmpeg 转换失败")

    size = os.path.getsize(wav_path)
    print(f"WAV 文件: {wav_path} ({size / 1024 / 1024:.1f} MB)")


def main():
    parser = argparse.ArgumentParser(description="抖音视频音频下载工具")
    parser.add_argument("video_id", help="抖音视频ID（纯数字，如 7657058079216848178）")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="输出目录（默认: 系统临时目录/douyin_work）",
    )
    args = parser.parse_args()

    # 设置输出目录
    output_dir = args.output_dir or os.path.join(
        os.environ.get("TEMP", "/tmp"), "douyin_work"
    )
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: 获取视频数据
    print(f"=== 获取视频数据: {args.video_id} ===")
    video_data = get_video_data(args.video_id)
    print(f"标题: {video_data.get('desc', '(无)')}")
    duration = video_data.get("duration", 0)
    print(f"时长: {duration / 1000:.0f} 秒")

    # 检查是否有字幕
    caption = video_data.get("caption", "")
    if caption:
        print(f"\n⚠️  视频已有字幕（caption），可直接使用:\n{caption[:500]}")
        # 保存字幕
        caption_path = os.path.join(output_dir, "caption.txt")
        with open(caption_path, "w", encoding="utf-8") as f:
            f.write(caption)
        print(f"字幕已保存到: {caption_path}")

    # Step 2: 获取播放地址
    print(f"\n=== 获取播放地址 ===")
    play_url = get_play_url(video_data)
    print(f"播放地址: {play_url[:100]}...")

    # Step 3: 下载视频
    print(f"\n=== 下载视频 ===")
    video_path = os.path.join(output_dir, "video.mp4")
    download_video(play_url, video_path)

    # Step 4: 转换为 WAV
    print(f"\n=== 转换音频 ===")
    wav_path = os.path.join(output_dir, "audio.wav")
    convert_to_wav(video_path, wav_path)

    print(f"\n=== 完成 ===")
    print(f"视频: {video_path}")
    print(f"音频: {wav_path}")
    print(f"\n下一步: 使用 vosk_transcribe.py 进行转录")


if __name__ == "__main__":
    main()
