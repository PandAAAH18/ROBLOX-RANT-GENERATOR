import inspect
import moviepy
try:
    from moviepy import TextClip
except ImportError:
    from moviepy.editor import TextClip

print(f"MoviePy Version: {moviepy.__version__}")
print("TextClip signature:")
try:
    print(inspect.signature(TextClip.__init__))
except:
    print("Could not get signature")
    print(TextClip.__init__.__doc__)
