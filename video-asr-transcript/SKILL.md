---
name: video-asr-transcript
description: "视频音频离线转录技能。当抖音/B站/快手等平台视频没有字幕或CC字幕不可用时，通过下载音频流并使用 Vosk 离线语音识别引擎进行中文转录，再自动清理 ASR 错误并格式化输出。适用于：视频无字幕需要提取口播文案、需要完整逐字转录而非简介摘要、视频时长较长且无法使用在线API的场景。触发词：视频转录、音频转文字、提取口播文案、无字幕视频转录、ASR转录、语音识别转文字。"
version: 2.0.0
author: WorkBuddy
agent_created: true
trigger:
  - 视频转录
  - 音频转文字
  - 提取口播文案
  - 无字幕视频转录
  - ASR转录
  - 语音识别转文字
  - 视频文案提取
trigger_keywords:
  - 视频转录
  - 音频转文字
  - 口播文案提取
  - 无字幕转录
  - ASR
  - 语音识别
  - vosk
  - whisper
allowed_intents:
  - content_extract
  - text_optimize
  - text_analysis
parameters:
  - name: video_url_or_info
    type: string
    description: 视频链接或视频描述信息（抖音分享文本、B站BV号等）
    required: true
supported_tools: []
---
# 视频音频离线转录技能

## 概述

当视频平台（抖音、B站、快手等）的视频没有可用字幕/CC时，通过下载音频流并使用 Vosk 离线语音识别引擎进行中文转录，再自动清理 ASR 错误并格式化输出。

**全程离线运行，无需 API Key，无需 GPU。** 跨平台支持 Windows / macOS / Linux。

## 适用 / 不适用场景

| 适用 | 不适用 |
|------|--------|
| 抖音/快手/视频号无字幕视频 | 已有可用字幕（直接提取更准） |
| B站视频无CC字幕 | 纯外语视频（仅支持中文模型） |
| 需要完整逐字口播文案 | 需要极高准确率（离线模型有 5-15% 错误率） |
| 视频 1-120 分钟 | 实时/流式转录 |

## 快速开始

### 零、环境初始化（首次使用，30 秒完成）

```bash
python scripts/env_setup.py --fix
```

此命令自动完成：
- 检测 Python 版本（需 3.8+）
- 安装缺失的 Python 包（vosk, requests, imageio-ffmpeg）
- 确保 ffmpeg 可用
- 下载 Vosk 中文语音模型（~42 MB）

> **国内用户加速**: 加 `--mirror` 使用清华 pip 镜像。

### 完整工作流

```
env_setup --fix  →  下载音频  →  转录  →  清理  →  格式化输出
```

---

## 工作流程

### 第一步：确定视频源

#### 抖音
抖音分享文本中的短链接（如 `d@n.dn ZmQ:/`）通常无法直接解析：
1. 提取视频标题和作者名
2. 搜索引擎搜索 `视频标题 douyin.com` 找到 `https://www.douyin.com/video/{video_id}`
3. 从链接中提取视频ID（纯数字，如 `7657058079216848178`）
4. 如搜索引擎找不到，尝试B站搜索同名视频

#### B站
直接使用 BV号 或 av号

#### 其他平台
需手动获取音频下载链接

### 第二步：下载音频流

#### 抖音

```bash
python scripts/douyin_audio_download.py <video_id> [--output-dir <目录>]
```

输出：`video.mp4` + `audio.wav`（16kHz mono）

脚本会自动检测视频是否已有字幕（`caption` 字段），如有则直接保存。

#### B站

```bash
python scripts/bili_audio_download.py <BV号> [--output <目录>]
```

输出：`audio.m4s`（原始流）+ `audio.wav`（16kHz mono）

### 第三步：运行转录

```bash
python scripts/vosk_transcribe.py \
  --audio audio.wav \
  --model vosk-model-small-cn-0.22 \
  --output transcript.txt \
  --srt transcript.srt
```

参数说明：
- `--audio`: WAV 音频（16kHz mono）
- `--model`: Vosk 模型目录
- `--download-model`: 模型不存在时自动下载
- `--output`: 文本输出路径
- `--srt`: SRT 字幕输出路径（可选）

转录速度约 **10x 实时**（30 分钟音频约需 3 分钟）。

### 第四步：清理 ASR 输出

Vosk 中文输出有两个特征性问题：
1. **逐词空格** — 每个词之间都有空格（如 `我们 每天 一 睁眼`）
2. **同音错字** — 对同音字、专有名词、金融术语识别有误

```bash
python scripts/cleanup_transcript.py \
  --input transcript.txt \
  --output transcript_clean.txt
```

清理流程：
1. 去除中文字符间的空格（保留英文/数字周围空格）
2. 应用 200+ 条常见 ASR 错误修正
3. 按内容逻辑插入段落分隔

**重要**：自动清理无法修复所有错误。必须人工通读，重点检查专有名词、数字、专业术语。

### 第五步：格式化输出

```
【标题】
(视频标题)

【口播文案 · 原版提取】
(清理后的完整转录文本，按内容分段)

【文案时长参考】
总字数：XXX 字
建议口播时长：约 XX 分钟
```

---

## 模型选择

| 模型 | 大小 | 准确率 | 速度 | 适用 |
|------|------|--------|------|------|
| vosk-model-small-cn-0.22 | 42MB | 中等 | 快 | 默认选择，快速转录 |
| vosk-model-cn-0.22 | 1.3GB | 较高 | 中等 | 需要更好准确率 |
| SenseVoiceSmall (ModelScope) | 940MB | 高 | 需 PyTorch | 追求最佳效果 |

**推荐**: 先用 small 模型，不满意再换大模型。

---

## 备选引擎

如果 Vosk 效果不理想：

1. **faster-whisper**（CTranslate2 加速版 Whisper）
   ```bash
   pip install faster-whisper
   ```
   国内用户设置 `HF_ENDPOINT=https://hf-mirror.com`

2. **SenseVoiceSmall**（阿里达摩院）
   ```bash
   pip install modelscope funasr torch
   ```
   ModelScope 国内 CDN 高速下载

3. **在线 API**（如有网络）
   - 阿里云 / 腾讯云语音识别
   - OpenAI Whisper API

---

## 脚本清单

| 脚本 | 用途 |
|------|------|
| `scripts/env_setup.py` | 🆕 环境检测与依赖自动安装 |
| `scripts/douyin_audio_download.py` | 从抖音下载无水印视频并转 WAV |
| `scripts/bili_audio_download.py` | 从B站下载音频流并转 WAV |
| `scripts/vosk_transcribe.py` | Vosk 离线转录，输出 txt + srt |
| `scripts/cleanup_transcript.py` | 清理 ASR 输出：去空格、修正错误、分段 |

---

## 网络加速（国内用户）

| 资源 | 镜像 |
|------|------|
| pip 包 | `pip install -i https://pypi.tuna.tsinghua.edu.cn/simple` |
| HuggingFace 模型 | `HF_ENDPOINT=https://hf-mirror.com` |
| Vosk 模型 | 直连 `alphacephei.com`（通常可访问） |
| SenseVoice | ModelScope: `iic/SenseVoiceSmall`（阿里 CDN） |

> `env_setup.py --fix --mirror` 自动使用清华 pip 镜像。

---

## 常见问题

**Q: 提示 vosk / requests 未安装？**
A: 运行 `python scripts/env_setup.py --fix` 自动安装所有依赖。

**Q: ffmpeg 找不到？**
A: `env_setup.py --fix` 会安装 `imageio-ffmpeg`，提供内建 ffmpeg，无需系统安装。

**Q: 模型下载慢或失败？**
A: 手动从 https://alphacephei.com/vosk/models 下载 `vosk-model-small-cn-0.22.zip`，解压到工作目录即可。

**Q: 转录准确率不满意？**
A: 1) 换大模型 vosk-model-cn-0.22 (1.3GB)；2) 试试 faster-whisper；3) 人工校对关键部分。

**Q: macOS / Linux 能用吗？**
A: 完全支持。所有脚本使用 `pathlib` / `os.path` 跨平台路径，`env_setup.py` 自动适配。

**Q: 多语言或英语视频？**
A: Vosk small-cn 仅支持中文。多语言请使用 faster-whisper 或在线 API。

---

## 参考

- Vosk 模型列表: https://alphacephei.com/vosk/models
- faster-whisper: https://github.com/SYSTRAN/faster-whisper
- ASR 错误模式参考: `references/asr_error_patterns.md`
