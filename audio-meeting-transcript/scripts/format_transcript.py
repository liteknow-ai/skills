#!/usr/bin/env python3
"""
Format Vosk JSON output as readable meeting transcript.

Usage:
    python format_transcript.py <transcript.json> [output.md]

Output: Markdown-formatted meeting transcript with speaker labels and timestamps.
"""
import sys
import os
import json


def format_timestamp(seconds):
    """Format seconds as HH:MM:SS."""
    s = int(seconds or 0)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:02d}"


def format_transcript(data):
    """Convert JSON transcript data to Markdown."""
    segments = data.get("segments", [])
    speakers = data.get("speakers", [])
    mode = data.get("mode", "lite")
    mode_label = "语音声纹识别" if mode == "full" else "静音分割（精简模式）"

    lines = []
    lines.append("# 录音稿\n")

    # Metadata
    lines.append(f"| 项目 | 内容 |")
    lines.append(f"|------|------|")
    lines.append(f"| 参与人 | {', '.join(speakers) if speakers else '未知'} |")
    lines.append(f"| 说话人数量 | {len(speakers)} |")
    lines.append(f"| 识别模式 | {mode_label} |")
    if segments:
        lines.append(f"| 时间范围 | {segments[0].get('start_str', 'N/A')} — {segments[-1].get('end_str', 'N/A')} |")
    lines.append("")

    # Speaker reference
    if speakers:
        lines.append("### 说话人对照\n")
        for i, spk in enumerate(speakers):
            lines.append(f"- {spk} = 第{i + 1}位发言者")
        lines.append("")

    lines.append("---\n")

    # Transcript body
    lines.append("### 对话内容\n")
    current_speaker = None
    for seg in segments:
        speaker = f"说话人{seg.get('speaker_label', 'A')}"
        timestamp = seg.get("start_str", format_timestamp(seg.get("start", 0)))

        if speaker != current_speaker:
            lines.append(f"\n**[{timestamp}] {speaker}:**\n")
            current_speaker = speaker

        text = seg.get("text", "").strip()
        if text:
            lines.append(text)
            lines.append("")

    lines.append("\n---\n")
    lines.append("> *本录音稿由 AI 自动生成，说话人识别基于声纹特征或语音停顿推断，"
                 "可能存在误差。关键内容请以原始录音为准。*")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python format_transcript.py <transcript.json> [output.md]")
        sys.exit(1)

    json_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    if not os.path.isfile(json_path):
        print(f"Error: File not found: {json_path}")
        sys.exit(1)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if data.get("status") != "success":
        print(f"Error: Transcript status is '{data.get('status')}'")
        sys.exit(1)

    content = format_transcript(data)

    if output_path is None:
        output_path = json_path.replace(".json", "_录音稿.md")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(json.dumps({
        "status": "success",
        "output": os.path.abspath(output_path),
        "chars": len(content),
        "lines": content.count("\n"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
