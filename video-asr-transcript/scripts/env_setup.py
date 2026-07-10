#!/usr/bin/env python3
"""
通用环境检测与依赖自动安装脚本
=================================
跨平台（Windows / macOS / Linux）自动检测运行环境并安装缺失依赖。

功能：
  1. 检测 Python 版本（需要 3.8+）
  2. 检测 pip 是否可用
  3. 检测并安装 Python 包（vosk, requests, imageio-ffmpeg）
  4. 检测 ffmpeg（系统安装或 imageio-ffmpeg 内置）
  5. 检测并下载 Vosk 中文语音模型

用法：
  # 仅检查环境
  python env_setup.py --check

  # 检查并自动修复（安装缺失依赖、下载模型）
  python env_setup.py --fix

  # 指定模型目录和工作目录
  python env_setup.py --fix --model-dir ./models --work-dir ./temp

  # 使用国内镜像加速
  python env_setup.py --fix --mirror
"""

import argparse
import os
import subprocess
import sys
import shutil
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
MIN_PYTHON = (3, 8)

VOSK_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip"
VOSK_MODEL_NAME = "vosk-model-small-cn-0.22"

PIP_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"
HF_MIRROR = "https://hf-mirror.com"

REQUIRED_PACKAGES = [
    ("vosk", None),            # 离线语音识别
    ("requests", None),        # HTTP 请求
    ("imageio-ffmpeg", None),  # ffmpeg 二进制
]


# ---------------------------------------------------------------------------
# 日志输出
# ---------------------------------------------------------------------------
class Color:
    """跨平台 ANSI 颜色（Windows CMD 可能不显示，但无害）"""
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    CYAN   = "\033[96m"
    RESET  = "\033[0m"
    BOLD   = "\033[1m"


def ok(msg: str) -> None:
    print(f"  {Color.GREEN}[OK]{Color.RESET} {msg}")


def warn(msg: str) -> None:
    print(f"  {Color.YELLOW}[WARN]{Color.RESET} {msg}")


def err(msg: str) -> None:
    print(f"  {Color.RED}[ERR]{Color.RESET} {msg}")


def info(msg: str) -> None:
    print(f"  {Color.CYAN}[...]{Color.RESET} {msg}")


def heading(msg: str) -> None:
    print(f"\n{Color.BOLD}{'=' * 60}{Color.RESET}")
    print(f"{Color.BOLD}{msg}{Color.RESET}")
    print(f"{Color.BOLD}{'=' * 60}{Color.RESET}")


# ---------------------------------------------------------------------------
# 核心检测 / 修复函数
# ---------------------------------------------------------------------------

def check_python_version() -> bool:
    """检测 Python 版本是否满足要求"""
    cur = sys.version_info[:2]
    ok_msg = f"Python {cur[0]}.{cur[1]}"
    if cur >= MIN_PYTHON:
        ok(ok_msg)
        return True
    err(f"Python 版本过低: {cur[0]}.{cur[1]}，需要 {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+")
    return False


def get_pip_cmd() -> str | None:
    """返回可用的 pip 命令（绝对路径），优先使用当前解释器的 pip"""
    # 尝试当前 Python 的 pip 模块
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True, timeout=10,
        )
        return [sys.executable, "-m", "pip"]
    except Exception:
        pass
    # 尝试系统 pip
    for cmd in ["pip3", "pip"]:
        if shutil.which(cmd):
            return [cmd]
    return None


def check_pip() -> bool:
    pip = get_pip_cmd()
    if pip:
        ok(f"pip 可用 ({' '.join(pip)})")
        return True
    err("pip 不可用，请先安装 pip: https://pip.pypa.io/en/stable/installation/")
    return False


def check_package(name: str) -> bool:
    """检测某个 Python 包是否已安装"""
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def install_packages(pip_cmd: list, mirror: bool = False) -> bool:
    """安装所有必要 Python 包"""
    packages = [name for name, _ in REQUIRED_PACKAGES]
    cmd = list(pip_cmd) + ["install"] + packages
    if mirror:
        cmd += ["-i", PIP_MIRROR]
    info(f"安装包: {' '.join(packages)}")
    result = subprocess.run(cmd, capture_output=False, timeout=300)
    if result.returncode != 0:
        err("包安装失败")
        return False
    ok("包安装完成")
    return True


def check_all_packages(mirror: bool = False) -> bool:
    """检测所有必要包，缺失则安装"""
    missing = [name for name, _ in REQUIRED_PACKAGES if not check_package(name)]

    if not missing:
        ok("所有 Python 包已就绪")
        return True

    warn(f"缺失包: {', '.join(missing)}")
    pip_cmd = get_pip_cmd()
    if not pip_cmd:
        err("pip 不可用，无法安装包")
        return False

    return install_packages(pip_cmd, mirror)


def check_ffmpeg() -> bool:
    """检测 ffmpeg 是否可用（系统 ffmpeg 或 imageio-ffmpeg 内置）"""
    # 先检查系统 ffmpeg
    if shutil.which("ffmpeg"):
        ok("系统 ffmpeg 可用")
        return True
    # 再检查 imageio-ffmpeg
    if check_package("imageio_ffmpeg"):
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            if exe and os.path.isfile(exe):
                ok("imageio-ffmpeg 内建 ffmpeg 可用")
                return True
        except Exception:
            pass
    warn("ffmpeg 未检测到，将尝试通过 imageio-ffmpeg 安装")
    return False  # 让后续步骤处理


def get_model_dir(work_dir: str) -> str:
    """返回 Vosk 模型的存储目录"""
    # 优先放在工作目录下
    return os.path.join(work_dir or ".", VOSK_MODEL_NAME)


def check_vosk_model(model_dir: str) -> bool:
    """检测 Vosk 中文模型是否已下载"""
    if os.path.isdir(model_dir):
        # 验证目录完整性: 检查关键文件
        required_files = ["am/final.mdl", "conf/model.conf"]
        for f in required_files:
            if os.path.isfile(os.path.join(model_dir, f)):
                ok(f"Vosk 中文模型已就绪: {model_dir}")
                return True
    return False


def download_vosk_model(work_dir: str, model_dir: str) -> bool:
    """下载并解压 Vosk 中文模型"""
    if check_vosk_model(model_dir):
        return True

    import urllib.request
    import zipfile

    os.makedirs(work_dir, exist_ok=True)

    zip_path = os.path.join(work_dir, "vosk-model-small-cn.zip")

    info(f"下载 Vosk 中文模型 (~42 MB)")
    info(f"  来源: {VOSK_MODEL_URL}")

    try:
        req = urllib.request.Request(
            VOSK_MODEL_URL,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        resp = urllib.request.urlopen(req, timeout=300)
        total = int(resp.headers.get("Content-Length", 0))
        print(f"  文件大小: {total / 1024 / 1024:.1f} MB")

        t0 = time.time()
        downloaded = 0
        with open(zip_path, "wb") as f:
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if downloaded % (3 * 1024 * 1024) < 256 * 1024:
                    pct = downloaded / total * 100 if total else 0
                    print(f"  进度: {downloaded / 1024 / 1024:.0f}/{total / 1024 / 1024:.0f} MB ({pct:.0f}%)")

        elapsed = time.time() - t0
        ok(f"下载完成 ({elapsed:.1f}s)")

        info("解压中...")
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(work_dir)

        # 清理 zip
        os.remove(zip_path)
        ok(f"模型已就绪: {model_dir}")

    except Exception as e:
        err(f"模型下载失败: {e}")
        return False

    return True


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def run_check_only() -> bool:
    """仅检测环境，不修复"""
    all_ok = True
    all_ok &= check_python_version()
    all_ok &= check_pip()
    all_ok &= check_ffmpeg()

    heading("Python 包")
    for name, _ in REQUIRED_PACKAGES:
        if check_package(name):
            ok(f"{name}")
        else:
            warn(f"{name} (未安装)")
            all_ok = False

    heading("Vosk 模型")
    default_model = get_model_dir(os.getcwd())
    if check_vosk_model(default_model):
        pass
    else:
        warn(f"Vosk 中文模型未找到 ({default_model})")
        all_ok = False

    return all_ok


def run_fix(work_dir: str, model_dir: str, mirror: bool = False) -> bool:
    """检测并自动修复环境"""
    heading("1. Python 版本")
    if not check_python_version():
        return False

    heading("2. pip")
    if not check_pip():
        return False

    heading("3. Python 包")
    if not check_all_packages(mirror):
        return False

    heading("4. ffmpeg")
    if not check_ffmpeg():
        # imageio-ffmpeg 如果已安装会自动解决
        if check_package("imageio_ffmpeg"):
            ok("imageio-ffmpeg 已安装，提供内建 ffmpeg")
        else:
            warn("ffmpeg 不可用，请确保 imageio-ffmpeg 已安装")

    heading("5. Vosk 中文模型")
    if not check_vosk_model(model_dir):
        info("模型未下载，正在自动下载...")
        if not download_vosk_model(os.path.dirname(model_dir) or work_dir, model_dir):
            return False

    heading("环境就绪！")
    print(f"\n  工作目录: {work_dir}")
    print(f"  模型目录: {model_dir}")
    print(f"  Python:   {sys.executable}")
    print(f"\n下一步: 使用音频下载脚本获取音频，然后运行转录")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="视频音频转录环境检测与自动安装",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python env_setup.py --check          # 仅检测
  python env_setup.py --fix            # 检测并自动修复
  python env_setup.py --fix --mirror   # 使用清华镜像加速
  python env_setup.py --fix --work-dir ./my_work --model-dir ./my_models/vosk
        """,
    )
    parser.add_argument(
        "--check", action="store_true",
        help="仅检测环境，不修复"
    )
    parser.add_argument(
        "--fix", action="store_true",
        help="检测并自动安装缺失的依赖"
    )
    parser.add_argument(
        "--work-dir", default=None,
        help="工作目录（临时文件存放），默认: 系统临时目录下的 video_asr"
    )
    parser.add_argument(
        "--model-dir", default=None,
        help="Vosk 模型目录，默认: 当前目录下的 vosk-model-small-cn-0.22"
    )
    parser.add_argument(
        "--mirror", action="store_true",
        help="使用清华 pip 镜像加速安装"
    )

    args = parser.parse_args()

    # 确定工作目录
    if args.work_dir:
        work_dir = os.path.abspath(args.work_dir)
    else:
        # 使用系统临时目录
        import tempfile
        work_dir = os.path.join(tempfile.gettempdir(), "video_asr")

    os.makedirs(work_dir, exist_ok=True)

    # 确定模型目录
    if args.model_dir:
        model_dir = os.path.abspath(args.model_dir)
    else:
        model_dir = os.path.join(work_dir, VOSK_MODEL_NAME)

    if args.check and not args.fix:
        heading("环境检测")
        if run_check_only():
            print(f"\n{Color.GREEN}所有检查通过！{Color.RESET}")
            sys.exit(0)
        else:
            print(f"\n{Color.YELLOW}存在问题，运行 --fix 来自动修复{Color.RESET}")
            sys.exit(1)

    elif args.fix:
        if run_fix(work_dir, model_dir, args.mirror):
            sys.exit(0)
        else:
            print(f"\n{Color.RED}环境修复失败，请检查上述错误{Color.RESET}")
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
