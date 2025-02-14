from pydub import AudioSegment
from pydub.silence import split_on_silence

# Load the audio file
audio = AudioSegment.from_file("./Training.wav", format="wav")

# Split on silence
chunks = split_on_silence(audio, 
                           min_silence_len=1000,  # Minimum silence duration (milliseconds)
                           silence_thresh=-30,   # Silence threshold in dBFS
                           keep_silence=200)     # Keep some silence at the edges

# Export each chunk
for i, chunk in enumerate(chunks):
    chunk.export(f"chunk_{i}.wav", format="wav")

print(f"Split into {len(chunks)} chunks.")