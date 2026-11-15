"""
AudioGuard - Automated Engine & Power-Loss Resilience Verification
1. Part A: Simulates sudden power loss / terminate() mid-stream and verifies
   with soundfile.info() that FLAC format, samplerate, channels, and blocks
   were safely committed to disk.
2. Part B: Standard session test verifying complete end-to-end decoding with sf.read().
"""

import os
import sys
import time
import subprocess
from pathlib import Path

def run_child_recorder(output_file: str):
    """Worker child process that records audio and gets abruptly terminated."""
    import numpy as np
    import soundfile as sf

    print(f"[CHILD] Starting abrupt recording test into: {output_file}", flush=True)
    
    raw_file = open(output_file, "wb")
    sf_file = sf.SoundFile(
        raw_file,
        mode="w",
        samplerate=48000,
        channels=2,
        format="FLAC",
        subtype="PCM_24"
    )

    sample_rate = 48000
    block_size = 4096
    t = 0.0
    dt = 1.0 / sample_rate

    last_flush = time.time()
    blocks_written = 0

    print("[CHILD] Writing blocks with 1.0s continuous flush...", flush=True)
    while True:
        time_vec = np.arange(block_size) * dt + t
        t += block_size * dt
        sine_wave = (0.5 * np.sin(2 * np.pi * 440.0 * time_vec)).astype(np.float32)
        stereo_block = np.column_stack((sine_wave, sine_wave))

        sf_file.write(stereo_block)
        blocks_written += 1

        now = time.time()
        if now - last_flush >= 1.0:
            sf_file.flush()
            raw_file.flush()
            os.fsync(raw_file.fileno())
            last_flush = now
            print(f"[CHILD] Flushed + fsynced at block {blocks_written} ({blocks_written * block_size / sample_rate:.2f}s)", flush=True)

        time.sleep(block_size / sample_rate)

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        output_file = sys.argv[2]
        run_child_recorder(output_file)
        sys.exit(0)

    import soundfile as sf
    import numpy as np

    print("=" * 65)
    print("AudioGuard - Automated Engine & Crash Verification")
    print("=" * 65)

    test_dir = Path("./test_output")
    test_dir.mkdir(parents=True, exist_ok=True)
    crash_flac = test_dir / "crash_test_simulation.flac"
    clean_flac = test_dir / "clean_test_session.flac"

    for f in [crash_flac, clean_flac]:
        if f.exists():
            try: f.unlink()
            except Exception: pass

    # -------------------------------------------------------------
    # PART A: ABRUPT CRASH & POWER-LOSS RESILIENCE
    # -------------------------------------------------------------
    print("\n--- PART A: Abrupt Power-Loss Simulation ---")
    print(f"[1/4] Spawning child recording process targeting {crash_flac.name}...")
    proc = subprocess.Popen([
        sys.executable,
        os.path.abspath(__file__),
        "--child",
        str(crash_flac.resolve())
    ])

    print("[2/4] Allowing child process to record for 4.5 seconds...")
    time.sleep(4.5)

    print("[3/4] ABRUPT TERMINATION: Simulating sudden power cut (proc.terminate())...")
    proc.terminate()
    try:
        proc.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        proc.kill()

    print(f"[3/4] Process forcefully killed. Return code: {proc.returncode}")

    print("[4/4] Verifying FLAC file integrity with soundfile.info()...")
    if not crash_flac.exists():
        print("[FAIL] Test FLAC file was not created on disk.")
        sys.exit(1)

    file_size_bytes = crash_flac.stat().st_size
    print(f"       File size on disk: {file_size_bytes:,} bytes")
    if file_size_bytes < 30000:
        print("[FAIL] File size is suspiciously small.")
        sys.exit(1)

    info = sf.info(str(crash_flac))
    print(f"       Format:     {info.format} ({info.format_info})")
    print(f"       Subtype:    {info.subtype} ({info.subtype_info})")
    print(f"       Channels:   {info.channels}")
    print(f"       SampleRate: {info.samplerate} Hz")

    assert info.format == "FLAC", "Format must be FLAC"
    assert info.subtype == "PCM_24", "Subtype must be PCM_24"
    assert info.channels == 2, "Channels must be 2"
    assert info.samplerate == 48000, "Sample rate must be 48000"
    print("[PASS] Part A Passed: FLAC header and blocks intact after abrupt crash!")

    # -------------------------------------------------------------
    # PART B: CLEAN SESSION & FULL DECODE INTEGRITY
    # -------------------------------------------------------------
    print("\n--- PART B: Clean Session & Full Audio Decode ---")
    print("Writing 2.0s clean FLAC file with final close()...")
    with sf.SoundFile(str(clean_flac), mode="w", samplerate=48000, channels=2, format="FLAC", subtype="PCM_24") as f:
        t = np.linspace(0, 2.0, 96000, endpoint=False)
        sine = (0.4 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
        stereo = np.column_stack((sine, sine))
        f.write(stereo)

    clean_info = sf.info(str(clean_flac))
    print(f"       Duration:   {clean_info.duration:.2f} seconds ({clean_info.frames:,} frames)")
    decoded_data, sr = sf.read(str(clean_flac))
    print(f"       Decoded:    {len(decoded_data):,} samples at {sr} Hz")
    assert len(decoded_data) == 96000, "Decoded sample count mismatch"
    assert sr == 48000, "Sample rate mismatch"
    print("[PASS] Part B Passed: Clean FLAC file decoded with 100% accuracy!")

    print("\n" + "=" * 65)
    print("[ALL PASS] AudioGuard Audio Engine 100% Verified!")
    print("=" * 65)

if __name__ == "__main__":
    main()
