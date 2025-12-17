import asyncio
import edge_tts

async def test():
    text = "."
    voice = "en-US-GuyNeural"
    pitch = "+100Hz"
    rate = "+50%"
    
    print(f"Testing TTS with: '{text}', {voice}, {pitch}, {rate}")
    
    try:
        communicate = edge_tts.Communicate(text, voice, pitch=pitch, rate=rate)
        await communicate.save("test_dot.mp3")
        print("Success")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
