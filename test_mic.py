import sounddevice as sd
import numpy as np

print("Starting mic test...")
print(f"Using device 9: Stealth 600X Gen 2 MAX")

duration = 3  # seconds
sample_rate = 16000

try:
    print("Recording NOW - speak into your mic...")
    audio = sd.rec(int(duration * sample_rate), 
                   samplerate=sample_rate, 
                   channels=1, 
                   device=9,
                   dtype=np.int16)
    print("Waiting for recording to finish...")
    sd.wait()
    print("Recording complete!")
    print(f"Recorded {len(audio)} samples")
    print(f"Max amplitude: {np.max(np.abs(audio))}")
except Exception as e:
    print(f"Error: {e}")