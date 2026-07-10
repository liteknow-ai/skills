#!/usr/bin/env python3
"""
Vosk ASR + Speaker Diarization

Transcribes audio and identifies speakers using:
- Full mode: Vosk speaker model (x-vector embeddings + clustering)
- Lite mode: Pause-based speaker change detection (no extra model needed)

Usage:
    python transcribe_diarize.py --audio <wav_path> [options]

Options:
    --model         Path to Vosk ASR model (auto-detected if omitted)
    --spk-model     Path to Vosk speaker model (auto-detected if omitted)
    --num-speakers  Number of speakers (auto-estimated if omitted)
    --output        Output JSON path (default: <audio>_transcript.json)
    --lang          Language hint: cn (default) or en

Output: JSON file with speaker-attributed segments.
"""
import sys
import os
import json
import wave
import numpy as np


# ── Model Discovery ──────────────────────────────────────────────

def get_model_search_paths():
    """Build model search path list. Order = priority."""
    paths = []

    # 1. Environment variable
    env_path = os.environ.get("VOSK_MODEL_PATH")
    if env_path:
        paths.append(os.path.expanduser(env_path))

    # 2. Skill-local models directory (relative to this script)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    paths.append(os.path.join(script_dir, "..", "models"))

    # 3. User-level standard location
    paths.append(os.path.expanduser("~/.vosk/models"))

    # 4. System-level (Linux)
    paths.append("/usr/share/vosk/models")
    paths.append("/usr/local/share/vosk/models")

    # 5. Current working directory
    paths.append(".")

    return paths


def find_model(model_name, custom_path=None):
    """Find a Vosk model directory by name."""
    # Custom path (from CLI arg) has highest priority
    if custom_path and os.path.isdir(custom_path):
        return os.path.abspath(custom_path)

    for search_path in get_model_search_paths():
        candidate = os.path.join(search_path, model_name)
        if os.path.isdir(candidate):
            return os.path.abspath(candidate)

    return None


def find_asr_model(custom_path=None, lang="cn"):
    """Find Vosk ASR model. Tries larger models first for better accuracy."""
    if lang == "en":
        candidates = ["vosk-model-small-en-us-0.15", "vosk-model-en-us-0.22"]
    else:
        # Prefer larger models for meeting transcription accuracy
        candidates = [
            "vosk-model-cn-0.22",        # Large (~1.3GB, best accuracy)
            "vosk-model-small-cn-0.22",   # Small (~42MB, good enough)
        ]

    for name in candidates:
        path = find_model(name, custom_path)
        if path:
            return path

    return None


def find_spk_model(custom_path=None):
    """Find Vosk speaker model."""
    candidates = ["vosk-model-spk-0.4"]
    for name in candidates:
        path = find_model(name, custom_path)
        if path:
            return path
    return None


# ── Transcription ────────────────────────────────────────────────

def transcribe_audio(wav_path, asr_model, spk_model=None):
    """
    Run Vosk ASR on audio file.
    If spk_model is provided, also extract speaker embeddings.

    Returns list of segments with: text, start, end, spk (embedding).
    """
    from vosk import KaldiRecognizer

    wf = wave.open(wav_path, "rb")
    if wf.getframerate() != 16000:
        print(f"Warning: sample rate is {wf.getframerate()}, expected 16000. "
              f"Run audio_preprocess.py first.", file=sys.stderr)

    recognizer = KaldiRecognizer(asr_model, wf.getframerate())
    recognizer.SetWords(True)
    if spk_model is not None:
        recognizer.SetSpkModel(spk_model)

    segments = []
    chunk_size = 4000  # ~0.25s at 16kHz 16-bit mono

    while True:
        data = wf.readframes(chunk_size)
        if len(data) == 0:
            break
        if recognizer.AcceptWaveform(data):
            result = json.loads(recognizer.Result())
            seg = parse_result(result)
            if seg:
                segments.append(seg)

    # Final segment
    final = json.loads(recognizer.FinalResult())
    seg = parse_result(final)
    if seg:
        segments.append(seg)

    wf.close()
    return segments


def parse_result(result):
    """Parse a Vosk result dict into a segment dict."""
    text = result.get("text", "").strip()
    if not text:
        return None

    seg = {
        "text": text,
        "start": None,
        "end": None,
        "spk": None,
    }

    words = result.get("result", [])
    if words:
        seg["start"] = words[0].get("start", 0)
        seg["end"] = words[-1].get("end", 0)

    if "spk" in result and result["spk"]:
        seg["spk"] = list(result["spk"])

    return seg


# ── Speaker Diarization ──────────────────────────────────────────

def cosine_similarity(a, b):
    """Cosine similarity between two vectors."""
    a, b = np.array(a), np.array(b)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def cluster_speakers_sklearn(embeddings, num_speakers=None):
    """Cluster speaker embeddings using agglomerative clustering."""
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics import silhouette_score

    embeddings = np.array(embeddings)

    if num_speakers is None:
        # Auto-estimate optimal number of speakers
        n_samples = len(embeddings)
        max_k = min(8, n_samples - 1)
        if max_k < 2:
            return [0] * n_samples

        best_k, best_score = 2, -1
        for k in range(2, max_k + 1):
            try:
                labels = AgglomerativeClustering(
                    n_clusters=k, metric="cosine", linkage="average"
                ).fit_predict(embeddings)
                if len(set(labels)) > 1:
                    score = silhouette_score(embeddings, labels, metric="cosine")
                    if score > best_score:
                        best_k, best_score = k, score
            except Exception:
                continue

        num_speakers = best_k

    labels = AgglomerativeClustering(
        n_clusters=num_speakers, metric="cosine", linkage="average"
    ).fit_predict(embeddings)

    return labels.tolist()


def cluster_speakers_greedy(embeddings, num_speakers=None, threshold=0.65):
    """Greedy clustering: assign to nearest existing cluster or create new."""
    if not embeddings:
        return []

    embeddings = [np.array(e) for e in embeddings]
    centers = [embeddings[0]]
    labels = [0]

    for emb in embeddings[1:]:
        best_sim, best_idx = -1, -1
        for i, center in enumerate(centers):
            sim = cosine_similarity(emb, center)
            if sim > best_sim:
                best_sim, best_idx = sim, i

        if best_sim > threshold and (num_speakers is None or len(centers) >= num_speakers):
            labels.append(best_idx)
            # Update center as running mean
            count = sum(1 for l in labels if l == best_idx)
            centers[best_idx] = (centers[best_idx] * (count - 1) + emb) / count
        else:
            if num_speakers is not None and len(centers) >= num_speakers:
                # Exceeded max speakers, assign to nearest
                labels.append(best_idx)
            else:
                centers.append(emb)
                labels.append(len(centers) - 1)

    return labels


def diarize_full(segments, num_speakers=None):
    """Full diarization using speaker embeddings."""
    # Collect embeddings
    has_emb = [(i, seg) for i, seg in enumerate(segments) if seg.get("spk")]
    no_emb = [i for i, seg in enumerate(segments) if not seg.get("spk")]

    if not has_emb:
        print("Warning: No speaker embeddings found. Falling back to lite mode.",
              file=sys.stderr)
        return diarize_lite(segments)

    embeddings = [seg["spk"] for _, seg in has_emb]

    # Cluster
    try:
        labels = cluster_speakers_sklearn(embeddings, num_speakers)
    except ImportError:
        print("sklearn not available, using greedy clustering.", file=sys.stderr)
        labels = cluster_speakers_greedy(embeddings, num_speakers)

    # Assign labels
    for (idx, seg), label in zip(has_emb, labels):
        seg["speaker"] = int(label)
        seg.pop("spk", None)

    # Fill in segments without embeddings (inherit from previous)
    last_speaker = 0
    for seg in segments:
        if "speaker" not in seg:
            seg["speaker"] = last_speaker
        else:
            last_speaker = seg["speaker"]

    return merge_consecutive(segments)


def diarize_lite(segments, gap_threshold=1.5):
    """
    Lite mode: estimate speaker changes from silence gaps.
    Alternates between speakers when a significant pause is detected.
    """
    if not segments:
        return segments

    current_speaker = 0
    for i, seg in enumerate(segments):
        seg["speaker"] = current_speaker
        if i < len(segments) - 1:
            end = seg.get("end") or 0
            next_start = segments[i + 1].get("start") or 0
            gap = next_start - end
            if gap > gap_threshold:
                current_speaker = (current_speaker + 1) % 2

    # Remove spk field if present
    for seg in segments:
        seg.pop("spk", None)

    return merge_consecutive(segments)


def merge_consecutive(segments):
    """Merge consecutive segments from the same speaker."""
    if not segments:
        return segments

    merged = [segments[0].copy()]
    for seg in segments[1:]:
        if merged[-1].get("speaker") == seg.get("speaker"):
            merged[-1]["text"] += seg["text"]
            if seg.get("end"):
                merged[-1]["end"] = seg["end"]
        else:
            merged.append(seg.copy())
    return merged


# ── Formatting ───────────────────────────────────────────────────

def format_timestamp(seconds):
    """Format seconds as HH:MM:SS."""
    s = int(seconds or 0)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:02d}"


def relabel_speakers(segments):
    """Relabel speakers as A, B, C, ... in order of first appearance."""
    speaker_order = []
    for seg in segments:
        spk = seg.get("speaker", 0)
        if spk not in speaker_order:
            speaker_order.append(spk)

    label_map = {}
    for i, spk in enumerate(speaker_order):
        label_map[spk] = chr(ord("A") + i)

    for seg in segments:
        seg["speaker_label"] = label_map[seg.get("speaker", 0)]
        seg["start_str"] = format_timestamp(seg.get("start", 0))
        seg["end_str"] = format_timestamp(seg.get("end", 0))

    return [f"说话人{label_map[s]}" for s in speaker_order]


# ── Main ─────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Vosk ASR + Speaker Diarization"
    )
    parser.add_argument("--audio", required=True, help="Path to 16kHz mono WAV")
    parser.add_argument("--model", default=None, help="Path to Vosk ASR model")
    parser.add_argument("--spk-model", default=None, help="Path to Vosk speaker model")
    parser.add_argument("--num-speakers", type=int, default=None,
                        help="Number of speakers (auto-estimated if omitted)")
    parser.add_argument("--output", default=None, help="Output JSON path")
    parser.add_argument("--lang", default="cn", choices=["cn", "en"],
                        help="Language hint (default: cn)")
    parser.add_argument("--no-spk", action="store_true",
                        help="Disable speaker model, use lite mode")

    args = parser.parse_args()

    # Load ASR model
    print("Loading ASR model...", file=sys.stderr)
    asr_path = find_asr_model(args.model, args.lang)
    if not asr_path:
        print(json.dumps({
            "status": "error",
            "error": "Vosk ASR model not found. Download from https://alphacephei.com/vosk/models"
        }, ensure_ascii=False))
        sys.exit(1)
    print(f"  ASR model: {asr_path}", file=sys.stderr)

    from vosk import Model
    asr_model = Model(asr_path)

    # Load speaker model (unless disabled)
    spk_model = None
    if not args.no_spk:
        spk_path = find_spk_model(args.spk_model)
        if spk_path:
            print(f"  Speaker model: {spk_path}", file=sys.stderr)
            from vosk import SpkModel
            spk_model = SpkModel(spk_path)
            print("  Mode: FULL (speaker embeddings)", file=sys.stderr)
        else:
            print("  Speaker model not found. Mode: LITE (pause-based)", file=sys.stderr)
    else:
        print("  Speaker model disabled. Mode: LITE", file=sys.stderr)

    # Transcribe
    print(f"Transcribing: {args.audio}", file=sys.stderr)
    segments = transcribe_audio(args.audio, asr_model, spk_model)
    print(f"  Raw segments: {len(segments)}", file=sys.stderr)

    if not segments:
        print(json.dumps({
            "status": "error",
            "error": "No speech detected in audio"
        }, ensure_ascii=False))
        sys.exit(1)

    # Diarize
    print("Diarizing speakers...", file=sys.stderr)
    if spk_model is not None:
        segments = diarize_full(segments, args.num_speakers)
    else:
        segments = diarize_lite(segments)

    # Relabel speakers
    speakers = relabel_speakers(segments)
    print(f"  Speakers detected: {len(speakers)} ({', '.join(speakers)})", file=sys.stderr)
    print(f"  Final segments: {len(segments)}", file=sys.stderr)

    # Build output
    result = {
        "status": "success",
        "audio": os.path.abspath(args.audio),
        "mode": "full" if spk_model else "lite",
        "num_speakers": len(speakers),
        "speakers": speakers,
        "duration_str": segments[-1]["end_str"] if segments else "00:00:00",
        "segments": segments,
    }

    output_path = args.output or args.audio.replace(".wav", "_transcript.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        "status": "success",
        "output": os.path.abspath(output_path),
        "mode": result["mode"],
        "num_speakers": result["num_speakers"],
        "speakers": result["speakers"],
        "num_segments": len(segments),
        "duration": result["duration_str"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
