---
name: audio-meeting-transcript
version: 1.1.0
description: 录音转写技能——将音频转为带说话人识别和时间戳的录音稿，并生成会议纪要。类似飞书"妙记"。
trigger_words:
  - 录音转写
  - 会议纪要
  - 录音稿
  - 转写录音
  - 音频转文字
  - 会议记录
  - 妙记
  - transcribe meeting
  - meeting minutes
---

# 录音转写技能 (Audio Meeting Transcript)

> 将上传的音频文件转为**带说话人识别和时间戳的录音稿**，再由 AI 生成**结构化会议纪要**。

## 能力概览

| 能力 | 说明 |
|------|------|
| 音频预处理 | 自动将 mp3/m4a/flac/ogg 等转为 16kHz 单声道 WAV |
| 语音转文字 | 基于 Vosk 离线 ASR，支持中英文，无需联网 |
| 说话人识别 | 声纹聚类（Full 模式）或静音分割（Lite 模式） |
| 时间戳标注 | 每段发言精确到秒级时间戳 |
| 会议纪要 | AI 自动生成摘要、议题、决策、待办事项 |

## 两种模式

### Full 模式（推荐）— 声纹识别
- 使用 `vosk-model-spk-0.4` 提取声纹特征
- 通过层次聚类区分不同说话人
- 准确率高，支持自动估算说话人数量
- 需下载说话人模型（约 1.2GB，一次性）

### Lite 模式 — 静音分割
- 无需额外模型，开箱即用
- 基于语音停顿推断说话人切换
- 准确率较低，适合快速预览

## 工作流程

```
用户上传音频 → ① 预处理 → ② 转写+分离 → ③ 格式化录音稿 → ④ AI 生成会议纪要
```

### Step 1: 音频预处理
将任意格式音频转为 Vosk 所需的 16kHz 单声道 WAV。

```bash
python3 scripts/audio_preprocess.py <input_audio> [output.wav]
```
- 自动检测 ffmpeg（优先系统 ffmpeg，其次 imageio-ffmpeg）
- 输出 JSON：`{ wav_path, duration, duration_str }`
- **必须先运行此步骤**，Vosk 要求 16kHz mono WAV

### Step 2: 转写 + 说话人分离
运行 Vosk ASR，提取声纹，聚类说话人。

```bash
python3 scripts/transcribe_diarize.py \
    --audio <wav_path> \
    [--num-speakers N] \
    [--output transcript.json]
```
- 自动检测 ASR 模型和说话人模型（搜索顺序见下方"模型查找"）
- `--num-speakers` 可指定说话人数量（不指定则自动估算）
- `--no-spk` 强制使用 Lite 模式
- `--model <path>` 手动指定 ASR 模型路径
- `--spk-model <path>` 手动指定说话人模型路径
- 输出 JSON：segments 数组，每个含 text/start/end/speaker_label

### Step 3: 格式化录音稿
将 JSON 转为可读的 Markdown 录音稿。

```bash
python3 scripts/format_transcript.py <transcript.json> [output.md]
```
- 输出带说话人标签和时间戳的对话格式
- 包含元信息表格（参与人、时长、模式等）

### Step 4: AI 生成会议纪要
**由 AI Agent 直接完成**，无需脚本。读取录音稿后按以下模板生成：

```markdown
# 会议纪要

## 会议信息
- 日期：YYYY-MM-DD
- 时长：XX 分钟
- 参与人：说话人A、说话人B、...

## 会议摘要
（2-3 句话概述会议主旨和核心结论）

## 主要议题
1. **议题一标题**
   - 要点 1
   - 要点 2
   - 说话人A 提出：...
   - 说话人B 补充：...

2. **议题二标题**
   - ...

## 关键决策
- 决策 1：...
- 决策 2：...

## 待办事项
| 事项 | 负责人 | 截止日期 |
|------|--------|----------|
| ... | ... | ... |

## 讨论细节（可选）
（按时间线记录重要讨论片段）
```

## 环境配置

### Python 依赖

```bash
pip install -r requirements.txt
```

依赖列表：
- `vosk` — 离线语音识别
- `numpy` — 数值计算
- `scikit-learn` — 声纹聚类
- `soundfile` — 音频信息读取
- `imageio-ffmpeg` — ffmpeg 二进制（系统未装 ffmpeg 时的备选）

### ffmpeg 要求

脚本优先使用系统安装的 ffmpeg。若系统未安装，会自动回退到 `imageio-ffmpeg` 包内置的 ffmpeg。

系统 ffmpeg 安装方式：
- **macOS**: `brew install ffmpeg`
- **Ubuntu/Debian**: `sudo apt install ffmpeg`
- **Windows**: 从 https://ffmpeg.org 下载或 `choco install ffmpeg`

### 模型查找

脚本按以下顺序自动查找 Vosk 模型：

1. **环境变量** `VOSK_MODEL_PATH` — 指定的目录
2. **技能本地目录** `./models/` — 与脚本同级
3. **用户目录** `~/.vosk/models/` — 标准用户级位置
4. **系统目录** `/usr/share/vosk/models/` — Linux 系统级
5. **命令行参数** `--model` / `--spk-model` — 手动指定（最高优先级）

### Vosk 模型

| 模型 | 大小 | 用途 | 必需 |
|------|------|------|------|
| vosk-model-small-cn-0.22 | ~42MB | 中文 ASR（小模型） | ✅ |
| vosk-model-cn-0.22 | ~1.3GB | 中文 ASR（大模型，精度更高） | ⬜ 可选 |
| vosk-model-spk-0.4 | ~1.2GB | 说话人声纹识别 | ⬜ 可选 |
| vosk-model-small-en-us-0.15 | ~40MB | 英文 ASR | ⬜ 可选 |

下载地址：https://alphacephei.com/vosk/models

快速安装说话人模型：
```bash
python3 scripts/download_speaker_model.py
```

## 关键注意事项

1. **音频时长** — 超过 30 分钟的录音，处理时间约为音频时长的 0.3-0.5 倍
2. **说话人数量** — Full 模式下自动估算，但手动指定 `--num-speakers` 效果更佳
3. **识别精度** — Vosk small 模型对专业术语和方言识别率有限，可换用大模型 `vosk-model-cn-0.22`
4. **输出文件** — 录音稿和会议纪要均保存为 `.md` 文件，便于阅读和分享
5. **隐私安全** — 全程离线处理，音频不上传任何服务器

## 输出示例

详见 `references/output_examples.md`

## 安装指南

详见 `references/setup_guide.md`
