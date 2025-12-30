import pyaudio
import wave

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
RECORD_SECONDS = 3

p = pyaudio.PyAudio()

print("Recording for 3 seconds...")
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=9,  # Your Turtle Beach
                frames_per_buffer=CHUNK)

frames = []
for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
    data = stream.read(CHUNK)
    frames.append(data)
    if i % 10 == 0:
        print(".", end="", flush=True)

print("\nRecording finished!")
stream.stop_stream()
stream.close()
p.terminate()