#!/usr/bin/env python3
"""
Download Vosk speaker model for Full diarization mode.

Usage:
    python download_speaker_model.py [--target <dir>]

Downloads vosk-model-spk-0.4 (~1.2GB).
Default target: ~/.vosk/models/ (or $VOSK_MODEL_PATH if set)
"""
import sys
import os
import urllib.request
import zipfile
import shutil

MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-spk-0.4.zip"
MODEL_NAME = "vosk-model-spk-0.4"


def get_default_target_dir():
    """Determine default model directory."""
    env_path = os.environ.get("VOSK_MODEL_PATH")
    if env_path:
        return os.path.expanduser(env_path)
    return os.path.expanduser("~/.vosk/models")


def download_with_progress(url, filepath):
    """Download file with progress indication."""
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as response:
        total = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 1024 * 1024  # 1MB

        with open(filepath, "wb") as f:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = downloaded * 100 // total
                    mb_done = downloaded // (1024 * 1024)
                    mb_total = total // (1024 * 1024)
                    print(f"\r  Downloaded: {mb_done}MB / {mb_total}MB ({pct}%)",
                          end="", flush=True)
        print()


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Download Vosk speaker model"
    )
    parser.add_argument("--target", default=None,
                        help="Target directory (default: $VOSK_MODEL_PATH or ~/.vosk/models)")
    args = parser.parse_args()

    target_dir = args.target or get_default_target_dir()
    target_model_dir = os.path.join(target_dir, MODEL_NAME)

    if os.path.isdir(target_model_dir):
        print(f"Speaker model already exists at: {target_model_dir}")
        overwrite = input("Overwrite? (y/N): ").strip().lower()
        if overwrite != "y":
            print("Aborted.")
            return
        shutil.rmtree(target_model_dir)

    os.makedirs(target_dir, exist_ok=True)

    zip_path = os.path.join(target_dir, f"{MODEL_NAME}.zip")

    print(f"Downloading {MODEL_NAME}...")
    print(f"  URL: {MODEL_URL}")
    print(f"  Target: {target_model_dir}")
    print(f"  Size: ~1.2GB (this may take a few minutes)")
    print()

    try:
        download_with_progress(MODEL_URL, zip_path)
    except Exception as e:
        print(f"\nDownload failed: {e}")
        print("You can manually download from:")
        print(f"  {MODEL_URL}")
        print(f"  Extract to: {target_dir}")
        sys.exit(1)

    print("\nExtracting...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(target_dir)

    # Clean up zip
    os.remove(zip_path)

    # Verify
    if os.path.isdir(target_model_dir):
        files = os.listdir(target_model_dir)
        print(f"\nDone! Speaker model installed at: {target_model_dir}")
        print(f"  Contents: {', '.join(files[:5])}")
        print(f"\nFull diarization mode is now available.")
        print(f"Run transcribe_diarize.py without --no-spk to use it.")
    else:
        print(f"\nError: Model directory not found after extraction.")
        sys.exit(1)


if __name__ == "__main__":
    main()
