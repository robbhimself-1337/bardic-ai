#!/usr/bin/env python3
"""
Voice Sample Recording Script for Bardic AI

Records a 30-second voice sample for use with Coqui TTS XTTS v2 voice cloning.
The recording is saved to voice_samples/dm_narrator.wav
"""

import subprocess
import os

print("=" * 60)
print("Bardic AI - Voice Sample Recording")
print("=" * 60)
print("Duration: 30 seconds")
print("Output: voice_samples/dm_narrator.wav")
print()
print("INSTRUCTIONS:")
print("- Speak naturally and clearly")
print("- Vary your tone and intonation")
print("- Read a passage from a book or describe an adventure")
print()
print("Recording will start in:")
for i in [3, 2, 1]:
    print(f"  {i}...")
    import time
    time.sleep(1)

print("\n🔴 RECORDING NOW - Speak naturally!\n")

# Create directory
os.makedirs('voice_samples', exist_ok=True)

# Record using arecord
try:
    subprocess.run([
        'arecord',
        '-D', 'hw:3,0',  # Your Turtle Beach
        '-f', 'S16_LE',
        '-r', '48000',
        '-c', '1',
        '-d', '30',
        'voice_samples/dm_narrator.wav'
    ], check=True)
    
    print("\n✅ Recording saved to voice_samples/dm_narrator.wav")
    print("\nYou can now use this voice for the DM!")
    
except subprocess.CalledProcessError as e:
    print(f"\n❌ Recording failed: {e}")
except FileNotFoundError:
    print("\n❌ arecord not found. Install with: sudo apt install alsa-utils")


