# 环境配置指南

## 1. Python 环境

技能需要 Python 3.8+，建议使用虚拟环境：

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 验证
python --version  # 应输出 Python 3.8+
```

## 2. 安装依赖

```bash
pip install -r requirements.txt
```

验证安装：
```bash
python -c "
import vosk
import numpy
import sklearn
import soundfile
import imageio_ffmpeg
print('All dependencies OK')
print('ffmpeg:', imageio_ffmpeg.get_ffmpeg_exe())
"
```

## 3. ffmpeg（可选但推荐）

脚本优先使用系统 ffmpeg，未安装时自动回退到 `imageio-ffmpeg` 内置版本。

系统 ffmpeg 安装：
- **macOS**: `brew install ffmpeg`
- **Ubuntu/Debian**: `sudo apt install ffmpeg`
- **Windows**: `choco install ffmpeg` 或从 https://ffmpeg.org 下载

## 4. 下载 Vosk 模型

### ASR 模型（必需）

**中文小模型（~42MB，推荐起步）：**
```bash
# 下载
curl -L -o /tmp/vosk-cn.zip https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip
# 解压到模型目录
mkdir -p ~/.vosk/models
unzip /tmp/vosk-cn.zip -d ~/.vosk/models/
```

**中文大模型（~1.3GB，精度更高，可选）：**
```bash
curl -L -o /tmp/vosk-cn-large.zip https://alphacephei.com/vosk/models/vosk-model-cn-0.22.zip
unzip /tmp/vosk-cn-large.zip -d ~/.vosk/models/
```

**英文模型（~40MB，可选）：**
```bash
curl -L -o /tmp/vosk-en.zip https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip /tmp/vosk-en.zip -d ~/.vosk/models/
```

### 说话人模型（可选，推荐）

**声纹识别模型（~1.2GB）：**
```bash
# 方式一：使用内置下载脚本（推荐）
python scripts/download_speaker_model.py

# 方式二：手动下载
curl -L -o /tmp/vosk-spk.zip https://alphacephei.com/vosk/models/vosk-model-spk-0.4.zip
unzip /tmp/vosk-spk.zip -d ~/.vosk/models/
```

安装后，`transcribe_diarize.py` 会自动检测并启用 Full 模式。

## 5. 模型目录结构

默认模型目录为 `~/.vosk/models/`（可通过 `VOSK_MODEL_PATH` 环境变量自定义）：

```
~/.vosk/models/
├── vosk-model-small-cn-0.22/    # ASR 小模型（必需）
│   ├── am/
│   ├── conf/
│   ├── graph/
│   └── ivector/
├── vosk-model-cn-0.22/          # ASR 大模型（可选）
├── vosk-model-spk-0.4/          # 说话人模型（可选）
└── vosk-model-small-en-us-0.15/ # 英文 ASR（可选）
```

### 自定义模型路径

通过环境变量指定模型目录：
```bash
export VOSK_MODEL_PATH=/path/to/your/models
```

或通过命令行参数指定：
```bash
python scripts/transcribe_diarize.py --audio input.wav --model /path/to/vosk-model-small-cn-0.22
```

## 6. 模型查找顺序

脚本按以下优先级查找模型：

1. **命令行参数** `--model` / `--spk-model`（最高优先级）
2. **环境变量** `VOSK_MODEL_PATH` 指定的目录
3. **技能本地目录** `scripts/../models/`
4. **用户目录** `~/.vosk/models/`
5. **系统目录** `/usr/share/vosk/models/`（Linux）
6. **当前工作目录** `.`

## 7. 常见问题

### Q: ffmpeg 报错？
A: 脚本会先尝试系统 ffmpeg，找不到时自动使用 `imageio-ffmpeg` 包内置的 ffmpeg。确保已安装 `imageio-ffmpeg`：`pip install imageio-ffmpeg`。

### Q: 模型找不到？
A: 检查模型是否解压到正确目录。可通过 `VOSK_MODEL_PATH` 环境变量或 `--model` 参数指定路径。

### Q: 说话人识别不准？
A:
- 确认已安装 `vosk-model-spk-0.4`
- 尝试 `--num-speakers N` 手动指定说话人数量
- 短音频（<1分钟）声纹特征不足，效果较差
- 噪音环境会影响识别精度

### Q: 处理速度慢？
A:
- 小模型处理速度约为实时速度的 2-3 倍
- 大模型处理速度约为实时速度的 0.5-1 倍
- 超长音频可先剪辑再处理

### Q: 如何支持其他语言？
A: 下载对应语言的 Vosk 模型，使用 `--lang` 参数指定：
```bash
python scripts/transcribe_diarize.py --audio input.wav --lang en
```
