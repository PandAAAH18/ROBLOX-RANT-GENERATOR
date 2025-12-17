import asyncio
import edge_tts
from pydub import AudioSegment
import os

def trim_silence(audio_segment, silence_thresh=-30):
    start_trim = 0
    end_trim = len(audio_segment)
    
    # Detect start
    for i, chunk in enumerate(audio_segment[::10]): 
        if chunk.dBFS > silence_thresh:
            start_trim = i * 10
            break
    
    # Detect end
    for i, chunk in enumerate(audio_segment[::-1][::10]):
        if chunk.dBFS > silence_thresh:
            end_trim = len(audio_segment) - (i * 10)
            break
    
    print(f"Trim Start: {start_trim}ms, End: {end_trim}ms")
    
    if start_trim >= end_trim:
        return audio_segment 
        
    return audio_segment[start_trim:end_trim]

async def test():
    text = "GUESTS"
    voice = "en-US-GuyNeural"
    pitch = "-50Hz"
    rate = "-50%"
    filename = "debug_slow_word.mp3"
    
    print(f"Generating '{text}' with {pitch}, {rate}...")
    communicate = edge_tts.Communicate(text, voice, pitch=pitch, rate=rate)
    await communicate.save(filename)
    
    audio = AudioSegment.from_file(filename)
    print(f"Original Duration: {len(audio)}ms")
    print(f"Average dBFS: {audio.dBFS}")
    print(f"Start 500ms dBFS: {audio[:500].dBFS}")
    print(f"End 500ms dBFS: {audio[-500:].dBFS}")
    
    trimmed = trim_silence(audio, silence_thresh=-30)
    print(f"Trimmed Duration (-30dB): {len(trimmed)}ms")
    
    trimmed_aggr = trim_silence(audio, silence_thresh=-20)
    print(f"Trimmed Duration (-20dB): {len(trimmed_aggr)}ms")

if __name__ == "__main__":
    asyncio.run(test())
