import json
import os
import sys
import math
from moviepy import *

def pop_bounce(t):
    """Subtle pop/bounce animation for text start"""
    # 0.0 -> 0.1s: Scale 0.1 -> 1.1
    # 0.1 -> 0.2s: Scale 1.1 -> 1.0
    if t < 0.1:
        return 0.1 + 10 * t
    elif t < 0.2:
        return 1.1 - (t - 0.1)
    else:
        return 1.0

def generate_video(config_path):
    """
    Generate video from config file using MoviePy v2.
    """
    if not os.path.exists(config_path):
        print(f"Error: Config file {config_path} not found.")
        return

    print(f"Loading config: {config_path}")
    with open(config_path, 'r') as f:
        data = json.load(f)

    metadata = data.get('metadata', {})
    sentences = data.get('sentences', [])
    
    # Paths
    base_dir = os.path.dirname(config_path)
    audio_file = os.path.join(base_dir, metadata.get('audio_file'))
    bg_video_path = metadata.get('background_video')
    
    if not os.path.exists(audio_file):
        print(f"Error: Audio file {audio_file} not found.")
        return

    # 1. Load Audio
    print("Loading audio...")
    audio = AudioFileClip(audio_file)
    duration = audio.duration
    
    # 2. Load Background
    if bg_video_path and os.path.exists(bg_video_path):
        print(f"Loading background: {bg_video_path}")
        video_clip = VideoFileClip(bg_video_path)
        # Loop background if shorter than audio
        if video_clip.duration < duration:
            video_clip = video_clip.loop(duration=duration)
        else:
            video_clip = video_clip.subclipped(0, duration)
    else:
        print("No background video found, using solid color.")
        video_clip = ColorClip(size=(1920, 1080), color=(0, 0, 0), duration=duration)
    
    # 3. Create Overlays (Images)
    clips = [video_clip]
    
    print("Processing events...")
    for sent in sentences:
        words = sent.get('words', [])
        for word in words:
            if 'image' in word:
                img_data = word['image']
                img_path = img_data.get('path')
                
                if img_path and os.path.exists(img_path):
                    start_t = img_data.get('absolute_start_ms', 0) / 1000.0
                    dur_t = img_data.get('duration_ms', 1000) / 1000.0
                    
                    # Create Image Clip
                    img_clip = ImageClip(img_path).with_start(start_t).with_duration(dur_t)
                    
                    # Handle Scaling
                    scale = img_data.get('scale', 1.0)
                    if scale != 1.0:
                        img_clip = img_clip.resized(scale)
                    
                    # Handle Positioning
                    pos = img_data.get('position', 'center')
                    if pos == 'center':
                        img_clip = img_clip.with_position('center')
                    elif pos == 'top-left':
                        img_clip = img_clip.with_position(('left', 'top'))
                    elif pos == 'top-right':
                        img_clip = img_clip.with_position(('right', 'top'))
                    elif pos == 'bottom-left':
                        img_clip = img_clip.with_position(('left', 'bottom'))
                    elif pos == 'bottom-right':
                        img_clip = img_clip.with_position(('right', 'bottom'))
                    
                    clips.append(img_clip)

    print("Generating captions...")
    # Get caption settings
    style = metadata.get('caption_style', 'default')
    
    # Use absolute font path for Windows compatibility (Arial Bold)
    font = 'C:/Windows/Fonts/arialbd.ttf'
    if not os.path.exists(font):
        font = 'C:/Windows/Fonts/arial.ttf'
        if not os.path.exists(font):
             font = 'Arial' # Fallback
        
    fontsize = 90
    color = 'white'
    stroke_color = 'black'
    stroke_width = 4
    
    for sent in sentences:
        words = sent.get('words', [])
        for word in words:
            text = word.get('text', '').strip()
            if not text:
                continue
                
            start_t = word.get('start_ms', 0) / 1000.0
            end_t = word.get('end_ms', 0) / 1000.0
            dur_t = end_t - start_t
            
            if dur_t <= 0:
                continue
            
            try:
                # Create Text Clip
                # MoviePy 2.1.2 signature: (font=None, text=None, ...)
                txt_clip = TextClip(
                    text=text, 
                    font=font, 
                    font_size=fontsize, 
                    color=color, 
                    stroke_color=stroke_color, 
                    stroke_width=stroke_width,
                    method='label',
                    margin=(20, 20) # Add padding to prevent cropping of stroke/descenders
                ).with_start(start_t).with_duration(dur_t)
                
                # Apply Bounce/Pop Animation and Position
                # Position: Center horizontally, 20% down vertically (Top area but not edge)
                txt_clip = txt_clip.with_position(('center', 0.2), relative=True)
                
                # Apply bounce efffect
                try:
                     txt_clip = txt_clip.resized(pop_bounce)
                except:
                     # Fallback if resized with func fails
                     pass

                clips.append(txt_clip)
            except Exception as e:
                print(f"Warning: Could not create caption for '{text}': {e}")
                # Likely ImageMagick missing or font issue

    print("Compositing video...")
    final_video = CompositeVideoClip(clips).with_audio(audio)
    
    # 5. Export
    output_filename = os.path.splitext(config_path)[0] + ".mp4"
    print(f"Exporting to {output_filename}...")
    
    # Try using NVENC for GPU acceleration
    # Added error handling to fallback to CPU if GPU fails
    try:
        print("Attempting GPU acceleration (h264_nvenc)...")
        final_video.write_videofile(
            output_filename, 
            fps=30, 
            codec='h264_nvenc', 
            audio_codec='aac',
            temp_audiofile='temp-audio.m4a',
            remove_temp=True,
            ffmpeg_params=['-preset', 'fast'] # 'p1'-'p7' for newer cards, 'fast' for compatibility
        )
    except Exception as e:
        print(f"GPU export failed: {e}")
        print("Falling back to CPU encoding (libx264)...")
        final_video.write_videofile(
            output_filename, 
            fps=30, 
            codec='libx264', 
            audio_codec='aac',
            temp_audiofile='temp-audio.m4a',
            remove_temp=True,
            preset='ultrafast' # maximize CPU speed
        )
    print("Done!")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        generate_video(sys.argv[1])
    else:
        print("Usage: python generate_video.py <path_to_config.json>")
