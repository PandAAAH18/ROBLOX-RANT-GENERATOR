import json
import re
import os
import tempfile
import asyncio
import threading
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple, Optional
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox, simpledialog
import edge_tts
import pandas as pd
from datetime import timedelta
import sys
from PIL import Image, ImageTk

# Import video generation function
try:
    from generate_video import generate_video
    VIDEO_GENERATION_AVAILABLE = True
except ImportError:
    VIDEO_GENERATION_AVAILABLE = False
    print("Warning: generate_video.py not found. Video generation will be disabled.")

@dataclass
class WordSettings:
    """Individual word settings for pitch and rate"""
    text: str
    pitch: str = "+0Hz"
    rate: str = "+0%"
    # Image/Visual settings
    image_path: Optional[str] = None
    image_start_ms: Optional[int] = None
    image_duration_ms: int = 1000
    image_position: str = "center"
    image_scale: float = 1.0
    # Audio/Sound Effect settings
    audio_path: Optional[str] = None
    audio_start_ms: Optional[int] = None
    audio_duration_ms: Optional[int] = None  # None = full audio
    audio_volume: float = 1.0  # 0.0 to 1.0

@dataclass
class SentenceSettings:
    """Sentence-level settings"""
    text: str
    words: List[WordSettings]
    voice: str = "en-US-ChristopherNeural"
    pitch: str = "+0Hz"
    rate: str = "+0%"
    # Visual settings
    background_video: Optional[str] = "assets/background/gameplay.mp4"
    caption_style: str = "default"

class ImageLibrary:
    """Manages collection of meme images"""
    def __init__(self, base_path: str = "assets/memes"):
        self.base_path = base_path
        self.images: List[str] = []
        self._ensure_path()
        self.refresh()
        
    def _ensure_path(self):
        if not os.path.exists(self.base_path):
            try:
                os.makedirs(self.base_path)
            except:
                pass
                
    def refresh(self):
        """Scan directory for images"""
        self.images = []
        if os.path.exists(self.base_path):
            for f in os.listdir(self.base_path):
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                    self.images.append(os.path.join(self.base_path, f))
                    
    def get_images(self) -> List[str]:
        return self.images

class AudioLibrary:
    """Manages collection of sound effect audio files"""
    def __init__(self, base_path: str = "assets/sounds"):
        self.base_path = base_path
        self.audio_files: List[str] = []
        self._ensure_path()
        self.refresh()
        
    def _ensure_path(self):
        if not os.path.exists(self.base_path):
            try:
                os.makedirs(self.base_path)
            except:
                pass
                
    def refresh(self):
        """Scan directory for audio files"""
        self.audio_files = []
        if os.path.exists(self.base_path):
            for f in os.listdir(self.base_path):
                if f.lower().endswith(('.mp3', '.wav', '.ogg', '.m4a', '.flac')):
                    self.audio_files.append(os.path.join(self.base_path, f))
                    
    def get_audio_files(self) -> List[str]:
        return self.audio_files

class VSubTTSGenerator:
    def __init__(self):
        self.sentences: List[SentenceSettings] = []
        self.available_voices: List[str] = []
        self.current_project_path: Optional[str] = None
        
    def parse_text(self, text: str) -> List[str]:
        """Parse text into sentences"""
        # Split by common sentence endings, preserving the punctuation
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        # Remove empty sentences
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences
    
    def parse_sentence(self, sentence: str) -> List[str]:
        """Parse sentence into words"""
        # Split by word boundaries, preserving punctuation
        words = re.findall(r'\b\w+\b|[^\w\s]', sentence)
        return [w for w in words if w.strip()]
    
    async def get_available_voices(self):
        """Get available voices from Edge TTS"""
        voices = await edge_tts.list_voices()
        self.available_voices = [v['ShortName'] for v in voices]
        return self.available_voices
    
    async def generate_audio(self, sentences: List[SentenceSettings], output_path: str = "output.mp3") -> Tuple[str, Dict]:
        """Generate audio with timestamps"""
        timestamp_data = []
        temp_files = []
        
        try:
            async def _process_sentence(idx, sentence):
                temp_chunk_files = []
                try:
                    # Group words by pitch and rate
                    chunks = []
                    if not sentence.words:
                        return idx, None, None

                    current_chunk = {'words': [], 'pitch': sentence.words[0].pitch, 'rate': sentence.words[0].rate}
                    
                    for word in sentence.words:
                        if word.pitch == current_chunk['pitch'] and word.rate == current_chunk['rate']:
                            current_chunk['words'].append(word.text)
                        else:
                            chunks.append(current_chunk)
                            current_chunk = {'words': [word.text], 'pitch': word.pitch, 'rate': word.rate}
                    chunks.append(current_chunk)

                    # Generate temporary audio file for this sentence
                    temp_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
                    current_temp_file = temp_file.name
                    temp_file.close()

                    # Helper to validate/clamp parameters
                    def _validate_param(val_str, param_type):
                        try:
                            # Extract number
                            num_str = val_str.replace('%', '').replace('Hz', '').replace('+', '')
                            val = int(num_str)
                            
                            if param_type == 'rate':
                                # Clamp rate between -50% and +100%
                                val = max(-50, min(100, val))
                                return f"{val:+d}%"
                            elif param_type == 'pitch':
                                # Clamp pitch between -100Hz and +100Hz
                                val = max(-100, min(100, val))
                                return f"{val:+d}Hz"
                            return val_str
                        except:
                            return val_str

                    # Optimize: If only one chunk, generate directly
                    if len(chunks) == 1:
                        plain_text = ' '.join(chunks[0]['words'])
                        safe_pitch = _validate_param(chunks[0]['pitch'], 'pitch')
                        safe_rate = _validate_param(chunks[0]['rate'], 'rate')
                        
                        communicate = edge_tts.Communicate(
                            plain_text,
                            sentence.voice,
                            pitch=safe_pitch,
                            rate=safe_rate
                        )
                        await communicate.save(current_temp_file)
                    else:
                        # Generate audio for each chunk
                        chunk_tasks = []
                        for i, chunk in enumerate(chunks):
                            chunk_text = ' '.join(chunk['words'])
                            safe_pitch = _validate_param(chunk['pitch'], 'pitch')
                            safe_rate = _validate_param(chunk['rate'], 'rate')
                            
                            # Skip if chunk has no alphanumeric characters (punctuation only)
                            if not re.search('[a-zA-Z0-9]', chunk_text):
                                print(f"Skipping punctuation-only chunk: '{chunk_text}'")
                                continue
                                
                            print(f"Generating chunk {i}: Text='{chunk_text}', Pitch={safe_pitch} (was {chunk['pitch']}), Rate={safe_rate} (was {chunk['rate']}), Voice={sentence.voice}")
                            
                            chunk_temp = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
                            chunk_path = chunk_temp.name
                            chunk_temp.close()
                            temp_chunk_files.append(chunk_path)
                            
                            communicate = edge_tts.Communicate(
                                chunk_text,
                                sentence.voice,
                                pitch=safe_pitch,
                                rate=safe_rate
                            )
                            chunk_tasks.append(communicate.save(chunk_path))
                        
                        # Wait for all chunks
                        await asyncio.gather(*chunk_tasks)
                        
                        # Combine chunks
                        self._combine_audio_files(temp_chunk_files, current_temp_file)

                    # Create sentence timestamp data
                    sentence_timestamps = {
                        'sentence_index': idx,
                        'text': sentence.text,
                        'start_ms': idx * 2000, 
                        'end_ms': (idx + 1) * 2000,
                        'words': []
                    }
                    
                    # Add initial word data (timestamps will be refined later)
                    for word in sentence.words:
                        word_data = {
                            'text': word.text,
                            'start_ms': 0,
                            'end_ms': 0
                        }
                        if word.image_path:
                            word_data['image'] = {
                                'path': word.image_path,
                                'start_ms': word.image_start_ms if word.image_start_ms is not None else 0, # Relative to word start
                                'duration_ms': word.image_duration_ms,
                                'position': word.image_position,
                                'scale': word.image_scale
                            }
                        if word.audio_path:
                            word_data['audio'] = {
                                'path': word.audio_path,
                                'start_ms': word.audio_start_ms if word.audio_start_ms is not None else 0, # Relative to word start
                                'duration_ms': word.audio_duration_ms,
                                'volume': word.audio_volume
                            }
                        sentence_timestamps['words'].append(word_data)
                    
                    return idx, current_temp_file, sentence_timestamps
                except Exception as e:
                    return idx, None, e
                finally:
                    # Cleanup chunk files
                    for f in temp_chunk_files:
                        try:
                            if os.path.exists(f):
                                os.unlink(f)
                        except:
                            pass

            # Create tasks for all sentences
            tasks = [_process_sentence(idx, sentence) for idx, sentence in enumerate(sentences)]
            
            # Run all tasks in parallel
            results = await asyncio.gather(*tasks)
            
            # Sort results by index to ensure correct order
            results.sort(key=lambda x: x[0])
            
            # Process results
            for idx, temp_file_path, result in results:
                if isinstance(result, Exception):
                    raise result
                
                if temp_file_path:
                    temp_files.append(temp_file_path)
                    timestamp_data.append(result)
            
            # Combine all temporary audio files
            self._combine_audio_files(temp_files, output_path)
            
            # Generate more accurate timestamps from the combined audio
            # This is a simplified approach - in production you'd want to analyze the audio
            actual_sentences = self._estimate_timestamps(temp_files, timestamp_data)
            
            # Construct final project data
            project_data = {
                "metadata": {
                    "title": "Generated Video", # content for title would be passed in ideally
                    "background_video": sentences[0].background_video if sentences and sentences[0].background_video else None,
                    "caption_style": sentences[0].caption_style if sentences and sentences[0].caption_style else "default",
                    "audio_file": os.path.basename(output_path)
                },
                "sentences": actual_sentences
            }
            
            # Clean up temporary files
            for temp_file in temp_files:
                try:
                    os.unlink(temp_file)
                except:
                    pass
            
            return output_path, project_data
            
        except Exception as e:
            # Clean up on error
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    try:
                        os.unlink(temp_file)
                    except:
                        pass
            raise e
    
    def _estimate_timestamps(self, audio_files: List[str], initial_timestamps: List[Dict]) -> List[Dict]:
        """Estimate timestamps based on audio file durations"""
        import wave
        import contextlib
        
        timestamps = []
        current_time = 0
        
        for i, audio_file in enumerate(audio_files):
            try:
                # Try to get duration from WAV/MP3 file
                duration_ms = 0
                
                # Method 1: Use ffprobe (most accurate)
                try:
                    import subprocess
                    cmd = [
                        'ffprobe', 
                        '-v', 'error', 
                        '-show_entries', 'format=duration', 
                        '-of', 'default=noprint_wrappers=1:nokey=1', 
                        audio_file
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        duration_ms = float(result.stdout.strip()) * 1000
                    else:
                        raise Exception("ffprobe failed")
                except:
                    # Method 2: Fallback to file size (inaccurate)
                    file_size = os.path.getsize(audio_file)
                    # Approximate: 16kbps = 2KB per second (very rough)
                    duration_ms = (file_size / 2000) * 1000 if file_size > 0 else 2000
                
                if i < len(initial_timestamps):
                    ts = initial_timestamps[i].copy()
                    start_ms = int(current_time)
                    end_ms = int(current_time + duration_ms)
                    
                    ts['start_ms'] = start_ms
                    ts['end_ms'] = end_ms
                    
                    # Estimate word timestamps proportionally
                    words = ts.get('words', [])
                    if words:
                        total_chars = sum(len(w['text']) for w in words)
                        current_word_start = start_ms
                        
                        for w in words:
                            # Fraction of time based on length (plus a bit of smoothing)
                            if total_chars > 0:
                                word_duration = (len(w['text']) / total_chars) * duration_ms
                            else:
                                word_duration = duration_ms / len(words)
                            
                            w['start_ms'] = int(current_word_start)
                            w['end_ms'] = int(current_word_start + word_duration)
                            
                            # Update image absolute start time if it was relative (currently we just store it)
                            # Logic: Image start is relative to word start unless specified otherwise?
                            # Prompt says: "Default Image Start: Auto-calculate to word start time, but allow manual offset"
                            # We'll calculate absolute time for export comfort
                            if 'image' in w:
                                # Start is word start + offset (stored in start_ms which is 0 by default)
                                offset = w['image'].get('start_ms', 0)
                                if offset is None: offset = 0
                                w['image']['absolute_start_ms'] = int(current_word_start + offset)
                            
                            # Same for audio effects
                            if 'audio' in w:
                                offset = w['audio'].get('start_ms', 0)
                                if offset is None: offset = 0
                                w['audio']['absolute_start_ms'] = int(current_word_start + offset)

                            current_word_start += word_duration

                    timestamps.append(ts)
                    
                    current_time += duration_ms
                
            except Exception as e:
                # Fallback to initial timestamps
                if i < len(initial_timestamps):
                    timestamps.append(initial_timestamps[i])
        
        return timestamps
    
    def _create_ssml(self, sentence: SentenceSettings) -> str:
        """Create SSML with word-level adjustments"""
        ssml_parts = [
            f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">',
            f'<voice name="{sentence.voice}">',
            f'<prosody pitch="{sentence.pitch}" rate="{sentence.rate}">'
        ]
        
        for i, word in enumerate(sentence.words):
            if word.pitch != "+0Hz" or word.rate != "+0%":
                ssml_parts.append(f'<prosody pitch="{word.pitch}" rate="{word.rate}">{word.text}</prosody>')
            else:
                ssml_parts.append(word.text)
            
            # Add space between words (but not after the last word)
            if i < len(sentence.words) - 1:
                ssml_parts.append(' ')
        
        ssml_parts.extend(['</prosody>', '</voice>', '</speak>'])
        return ''.join(ssml_parts)
    
    def _srt_time_to_ms(self, srt_time: str) -> int:
        """Convert SRT time format to milliseconds"""
        try:
            time_parts = srt_time.replace(',', ':').split(':')
            h, m, s, ms = map(int, time_parts)
            return (h * 3600 + m * 60 + s) * 1000 + ms
        except:
            return 0
    
    def _combine_audio_files(self, input_files: List[str], output_file: str):
        """Combine multiple MP3 files into one using FFmpeg with silence trimming"""
        import subprocess
        import shutil
        
        trimmed_files = []
        try:
            # 1. Trim silence from each file individually
            for i, file in enumerate(input_files):
                trimmed_path = file.replace('.mp3', f'_trimmed_{i}.mp3')
                
                # Filter to remove silence from start and end (via reverse)
                # silenceremove=start_periods=1:start_silence=0.1:start_threshold=-30dB
                filter_complex = "silenceremove=start_periods=1:start_silence=0.01:start_threshold=-30dB,areverse,silenceremove=start_periods=1:start_silence=0.01:start_threshold=-30dB,areverse"
                
                cmd = [
                    'ffmpeg', '-y', '-v', 'quiet',
                    '-i', file,
                    '-af', filter_complex,
                    trimmed_path
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    trimmed_files.append(trimmed_path)
                else:
                    print(f"FFmpeg trim failed for {file}: {result.stderr}")
                    # Fallback to original if trim fails
                    trimmed_files.append(file)

            # 2. Create list file for concatenation
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                for file in trimmed_files:
                    # FFmpeg concat requires forward slashes and escaped paths
                    safe_path = os.path.abspath(file).replace('\\', '/')
                    f.write(f"file '{safe_path}'\n")
                list_file = f.name
            
            # 3. Concatenate
            cmd_concat = [
                'ffmpeg', '-y', '-v', 'error',
                '-f', 'concat', '-safe', '0',
                '-i', list_file,
                '-c', 'copy',
                output_file
            ]
            
            result = subprocess.run(cmd_concat, capture_output=True, text=True)
            
            if result.returncode != 0:
                 print(f"FFmpeg concat failed: {result.stderr}")
                 raise Exception(result.stderr)
                 
            # Cleanup list file
            try:
                os.unlink(list_file)
            except:
                pass
                
        except Exception as e:
            print(f"Combine failed: {e}")
            # Absolute fallback: copy first file if exists
            if input_files:
                shutil.copy2(input_files[0], output_file)
                
        finally:
            # Overwrite the input temporary files with the trimmed versions 
            # This ensures that subsequent timestamp estimation uses the correct (trimmed) durations.
            for i, unique_trimmed in enumerate(trimmed_files):
                 if unique_trimmed != input_files[i] and os.path.exists(unique_trimmed):
                     try:
                         shutil.move(unique_trimmed, input_files[i])
                     except Exception as ex:
                         print(f"Failed to overwrite temp file {input_files[i]}: {ex}")
                         # If move fails, try copy
                         try:
                             shutil.copy2(unique_trimmed, input_files[i])
                             os.unlink(unique_trimmed)
                         except:
                             pass
    
    def export_timestamps(self, timestamps: List[Dict], format: str = 'json') -> str:
        """Export timestamps in various formats"""
        if format == 'json':
            return json.dumps(timestamps, indent=2)
        elif format == 'csv':
            df = pd.DataFrame(timestamps)
            return df.to_csv(index=False)
        elif format == 'srt':
            srt_content = []
            for i, ts in enumerate(timestamps):
                srt_content.append(str(i + 1))
                start = self._ms_to_srt_time(ts['start_ms'])
                end = self._ms_to_srt_time(ts['end_ms'])
                srt_content.append(f"{start} --> {end}")
                srt_content.append(ts['text'])
                srt_content.append('')
            return '\n'.join(srt_content)
        elif format == 'vtt':
            vtt_content = ["WEBVTT", ""]
            for i, ts in enumerate(timestamps):
                start = self._ms_to_vtt_time(ts['start_ms'])
                end = self._ms_to_vtt_time(ts['end_ms'])
                vtt_content.append(f"{start} --> {end}")
                vtt_content.append(ts['text'])
                vtt_content.append('')
            return '\n'.join(vtt_content)
        
        return ''
    
    def _ms_to_srt_time(self, ms: int) -> str:
        """Convert milliseconds to SRT time format"""
        hours = ms // 3600000
        ms %= 3600000
        minutes = ms // 60000
        ms %= 60000
        seconds = ms // 1000
        milliseconds = ms % 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
    
    def _ms_to_vtt_time(self, ms: int) -> str:
        """Convert milliseconds to WebVTT time format"""
        hours = ms // 3600000
        ms %= 3600000
        minutes = ms // 60000
        ms %= 60000
        seconds = ms // 1000
        milliseconds = ms % 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

class VSubApp:
    def __init__(self, root):
        self.root = root
        self.root.title("VSub TTS Generator - Enhanced Edition")
        self.root.geometry("1400x850")
        
        self.generator = VSubTTSGenerator()
        self.current_sentence_index = 0
        
        # Variables
        self.voice_var = tk.StringVar(value="en-US-ChristopherNeural")
        self.pitch_var = tk.StringVar(value="+0Hz")
        self.rate_var = tk.StringVar(value="+0%")
        
        # Create menu bar first
        self.create_menu_bar()
        
        self.setup_ui()
        self.load_voices()
        self.load_templates()
        
        # Initialize Libraries
        self.image_library = ImageLibrary()
        self.audio_library = AudioLibrary()
        self.clipboard_img = None
    
    def create_menu_bar(self):
        """Create menu bar with File and Help menus"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Project", command=self.new_project, accelerator="Ctrl+N")
        file_menu.add_command(label="Open Project...", command=self.load_project, accelerator="Ctrl+O")
        file_menu.add_command(label="Save Project", command=self.save_project, accelerator="Ctrl+S")
        file_menu.add_command(label="Save Project As...", command=self.save_project_as, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        file_menu.add_command(label="Export Timestamps...", command=self.export_timestamps)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Edit Menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Manage Templates", command=self.open_template_manager)
        
        # View Menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Refresh Image Library", command=self.refresh_image_library)
        view_menu.add_command(label="Refresh Audio Library", command=self.refresh_audio_library)
        
        # Help Menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)
        
        # Bind keyboard shortcuts
        self.root.bind('<Control-n>', lambda e: self.new_project())
        self.root.bind('<Control-o>', lambda e: self.load_project())
        self.root.bind('<Control-s>', lambda e: self.save_project())
        self.root.bind('<Control-Shift-S>', lambda e: self.save_project_as())
    
    def new_project(self):
        """Create a new project"""
        if self.generator.sentences:
            if not messagebox.askyesno("Confirm", "Discard current project and start new?"):
                return
        self.generator.sentences = []
        self.generator.current_project_path = None
        self.text_input.delete("1.0", tk.END)
        self.update_sentence_list()
        self.update_status("New project created")
    
    def save_project_as(self):
        """Save project with new filename"""
        old_path = self.generator.current_project_path
        self.generator.current_project_path = None
        self.save_project()
        if self.generator.current_project_path is None:
            self.generator.current_project_path = old_path
    
    def refresh_image_library(self):
        """Refresh image library"""
        self.image_library.refresh()
        self.update_status("Image library refreshed")
    
    def refresh_audio_library(self):
        """Refresh audio library"""
        self.audio_library.refresh()
        self.update_status("Audio library refreshed")
    
    def show_about(self):
        """Show about dialog"""
        messagebox.showinfo(
            "About VSub TTS Generator",
            "VSub TTS Generator - Enhanced Edition\\n\\n"
            "A powerful tool for creating TTS audio with\\n"
            "visual and audio effects synchronized to words.\\n\\n"
            "Features:\\n"
            "• Text-to-Speech with Edge TTS\\n"
            "• Word-level pitch & rate control\\n"
            "• Image overlays on words\\n"
            "• Sound effects on words\\n"
            "• Timeline visualization\\n"
            "• Project save/load\\n\\n"
            "Version 2.0"
        )

    def load_templates(self):
        """Load templates from file"""
        self.templates = {
            "Reset": {"pitch": "+0Hz", "rate": "+0%"},
            "High Pitch": {"pitch": "+50Hz", "rate": "+0%"},
            "Low Pitch": {"pitch": "-50Hz", "rate": "+0%"},
            "Fast": {"pitch": "+0Hz", "rate": "+50%"},
            "Slow": {"pitch": "+0Hz", "rate": "-50%"}
        }
        
        try:
            if os.path.exists("templates.json"):
                with open("templates.json", "r") as f:
                    saved = json.load(f)
                    self.templates.update(saved)
        except Exception as e:
            print(f"Error loading templates: {e}")
            
    def save_templates(self):
        """Save templates to file"""
        try:
            with open("templates.json", "w") as f:
                json.dump(self.templates, f, indent=2)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save templates: {str(e)}")

    def open_template_manager(self):
        """Open template manager dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Voice Template Manager")
        dialog.geometry("500x400")
        
        # List of templates
        list_frame = ttk.Frame(dialog, padding="10")
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        ttk.Label(list_frame, text="Templates:").pack(anchor=tk.W)
        
        listbox = tk.Listbox(list_frame, height=15)
        listbox.pack(fill=tk.BOTH, expand=True, pady=(5,0))
        
        for name in sorted(self.templates.keys()):
            listbox.insert(tk.END, name)
            
        # Edit area
        edit_frame = ttk.Frame(dialog, padding="10")
        edit_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        ttk.Label(edit_frame, text="Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        name_entry = ttk.Entry(edit_frame)
        name_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)
        
        ttk.Label(edit_frame, text="Pitch:").grid(row=1, column=0, sticky=tk.W, pady=5)
        pitch_entry = ttk.Entry(edit_frame)
        pitch_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)
        
        ttk.Label(edit_frame, text="Rate:").grid(row=2, column=0, sticky=tk.W, pady=5)
        rate_entry = ttk.Entry(edit_frame)
        rate_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)
        
        def on_select(event):
            selection = listbox.curselection()
            if selection:
                name = listbox.get(selection[0])
                data = self.templates[name]
                name_entry.delete(0, tk.END)
                name_entry.insert(0, name)
                pitch_entry.delete(0, tk.END)
                pitch_entry.insert(0, data['pitch'])
                rate_entry.delete(0, tk.END)
                rate_entry.insert(0, data['rate'])
                
        listbox.bind('<<ListboxSelect>>', on_select)
        
        def save_template():
            name = name_entry.get().strip()
            pitch = pitch_entry.get().strip()
            rate = rate_entry.get().strip()
            
            if not name:
                messagebox.showwarning("Error", "Name is required")
                return
                
            self.templates[name] = {"pitch": pitch, "rate": rate}
            self.save_templates()
            
            # Refresh list
            listbox.delete(0, tk.END)
            for name in sorted(self.templates.keys()):
                listbox.insert(tk.END, name)
                
            # Refresh word editors if open
            self.display_current_sentence()
                
        def delete_template():
            selection = listbox.curselection()
            if selection:
                name = listbox.get(selection[0])
                if messagebox.askyesno("Confirm", f"Delete template '{name}'?"):
                    del self.templates[name]
                    self.save_templates()
                    listbox.delete(selection[0])
                    self.display_current_sentence()
        
        ttk.Button(edit_frame, text="Save/Update", command=save_template).grid(row=3, column=0, columnspan=2, pady=10, sticky=tk.EW)
        ttk.Button(edit_frame, text="Delete", command=delete_template).grid(row=4, column=0, columnspan=2, pady=5, sticky=tk.EW)

    def setup_ui(self):
        # Configure styles
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Word.TButton", padding=5)
        style.configure("Action.TButton", font=('Helvetica', 10, 'bold'))
        
        # Main container with split view
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # --- Left Panel: Navigation & Global Settings ---
        left_panel = ttk.Frame(main_paned, width=300)
        main_paned.add(left_panel, weight=1)
        
        # Tabs
        self.left_tabs = ttk.Notebook(left_panel)
        self.left_tabs.pack(fill=tk.BOTH, expand=True)
        
        self.tab_script = ttk.Frame(self.left_tabs, padding=5)
        self.tab_library = ttk.Frame(self.left_tabs, padding=5)
        
        self.left_tabs.add(self.tab_script, text="Script & Settings")
        self.left_tabs.add(self.tab_library, text="Image Library")
        
        # === TAB 1: SCRIPT ===
        
        # Global Settings Group
        global_group = ttk.LabelFrame(self.tab_script, text="Global Settings", padding=10)
        global_group.pack(fill=tk.X, pady=(0, 10))
        
        # Voice Selection
        ttk.Label(global_group, text="Voice:").pack(anchor=tk.W)
        self.voice_combo = ttk.Combobox(global_group, textvariable=self.voice_var)
        self.voice_combo.pack(fill=tk.X, pady=2)
        
        # Global Pitch/Rate
        settings_grid = ttk.Frame(global_group)
        settings_grid.pack(fill=tk.X, pady=5)
        
        ttk.Label(settings_grid, text="Pitch:").grid(row=0, column=0, sticky=tk.W)
        self.pitch_combo = ttk.Combobox(settings_grid, textvariable=self.pitch_var, width=10)
        self.pitch_combo['values'] = ['-100Hz', '-50Hz', '-20Hz', '+0Hz', '+20Hz', '+50Hz', '+100Hz']
        self.pitch_combo.grid(row=0, column=1, padx=5)
        
        ttk.Label(settings_grid, text="Rate:").grid(row=0, column=2, sticky=tk.W)
        self.rate_combo = ttk.Combobox(settings_grid, textvariable=self.rate_var, width=10)
        self.rate_combo['values'] = ['-50%', '-25%', '+0%', '+25%', '+50%']
        self.rate_combo.grid(row=0, column=3, padx=5)
        
        ttk.Button(global_group, text="Manage Templates", command=self.open_template_manager).pack(fill=tk.X, pady=5)
        
        # Input Section
        input_group = ttk.LabelFrame(self.tab_script, text="Input Text", padding=10)
        input_group.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.text_input = scrolledtext.ScrolledText(input_group, height=10, wrap=tk.WORD)
        self.text_input.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        btn_frame = ttk.Frame(input_group)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Sample Text", command=self.insert_sample_text).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,2))
        ttk.Button(btn_frame, text="Parse Text", command=self.parse_text, style="Action.TButton").pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2,0))
        
        # Sentence List
        list_group = ttk.LabelFrame(self.tab_script, text="Sentences", padding=10)
        list_group.pack(fill=tk.BOTH, expand=True)
        
        self.sentence_list = tk.Listbox(list_group, selectmode=tk.SINGLE)
        self.sentence_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(list_group, orient="vertical", command=self.sentence_list.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.sentence_list.config(yscrollcommand=scroll.set)
        self.sentence_list.bind('<<ListboxSelect>>', self.on_sentence_select)
        
        # === TAB 2: LIBRARY ===
        
        # Sentence selector at the top of Library tab
        lib_sentence_frame = ttk.LabelFrame(self.tab_library, text="Current Sentence", padding=5)
        lib_sentence_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(lib_sentence_frame, text="Select Sentence:").pack(side=tk.LEFT, padx=5)
        self.lib_sentence_combo = ttk.Combobox(lib_sentence_frame, state='readonly')
        self.lib_sentence_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.lib_sentence_combo.bind('<<ComboboxSelected>>', self.on_lib_sentence_select)
        
        # Create sub-tabs for Image and Audio libraries
        library_notebook = ttk.Notebook(self.tab_library)
        library_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Image Library Sub-Tab
        image_lib_frame = ttk.Frame(library_notebook, padding=5)
        library_notebook.add(image_lib_frame, text="🖼️ Images")
        
        lib_ctrl = ttk.Frame(image_lib_frame)
        lib_ctrl.pack(fill=tk.X, pady=5)
        
        def refresh_lib():
            self.image_library.refresh()
            update_lib_list()
            self.update_status("Image library refreshed")
            
        def add_to_lib():
            files = filedialog.askopenfilenames(
                title="Select Images",
                filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.webp")]
            )
            if files:
                import shutil
                dest_dir = self.image_library.base_path
                count = 0
                for f in files:
                    try:
                        shutil.copy2(f, dest_dir)
                        count += 1
                    except Exception as e:
                        print(f"Error copying {f}: {e}")
                refresh_lib()
                messagebox.showinfo("Success", f"Added {count} images to library.")

        ttk.Button(lib_ctrl, text="🔄 Refresh", command=refresh_lib).pack(side=tk.LEFT, padx=2)
        ttk.Button(lib_ctrl, text="➕ Add Images...", command=add_to_lib).pack(side=tk.LEFT, padx=2)
        ttk.Button(lib_ctrl, text="📂 Open Folder", command=lambda: os.startfile(self.image_library.base_path) if os.path.exists(self.image_library.base_path) else None).pack(side=tk.LEFT, padx=2)
        
        # List with scrollbar
        list_frame = ttk.Frame(image_lib_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.lib_list = tk.Listbox(list_frame)
        self.lib_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        list_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.lib_list.yview)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.lib_list.config(yscrollcommand=list_scroll.set)
        
        # Preview
        self.preview_lbl = ttk.Label(image_lib_frame, text="Select an image to preview", relief=tk.SUNKEN, anchor=tk.CENTER)
        self.preview_lbl.pack(fill=tk.BOTH, expand=True, pady=5, ipady=20)
        
        def on_lib_select(event):
            sel = self.lib_list.curselection()
            if sel:
                path = self.lib_list.get(sel[0])
                try:
                    # Load and resize image
                    pil_img = Image.open(path)
                    # Resize to fit 200x200 max
                    pil_img.thumbnail((200, 200))
                    tk_img = ImageTk.PhotoImage(pil_img)
                    
                    self.preview_lbl.config(image=tk_img, text="")
                    self.preview_lbl.image = tk_img # Keep reference
                except Exception as e:
                    self.preview_lbl.config(text=f"Error loading preview: {str(e)}", image="")
        
        self.lib_list.bind('<<ListboxSelect>>', on_lib_select)
        
        def update_lib_list():
            self.lib_list.delete(0, tk.END)
            for img in self.image_library.get_images():
                self.lib_list.insert(tk.END, img)
        
        # Audio Library Sub-Tab
        audio_lib_frame = ttk.Frame(library_notebook, padding=5)
        library_notebook.add(audio_lib_frame, text="🔊 Sound Effects")
        
        audio_ctrl = ttk.Frame(audio_lib_frame)
        audio_ctrl.pack(fill=tk.X, pady=5)
        
        def refresh_audio_lib():
            self.audio_library.refresh()
            update_audio_list()
            self.update_status("Audio library refreshed")
            
        def add_to_audio_lib():
            files = filedialog.askopenfilenames(
                title="Select Audio Files",
                filetypes=[("Audio Files", "*.mp3 *.wav *.ogg *.m4a *.flac")]
            )
            if files:
                import shutil
                dest_dir = self.audio_library.base_path
                count = 0
                for f in files:
                    try:
                        shutil.copy2(f, dest_dir)
                        count += 1
                    except Exception as e:
                        print(f"Error copying {f}: {e}")
                refresh_audio_lib()
                messagebox.showinfo("Success", f"Added {count} audio files to library.")
        
        def play_selected_audio():
            sel = self.audio_list.curselection()
            if sel:
                path = self.audio_list.get(sel[0])
                try:
                    # Use pygame or winsound to play
                    import winsound
                    winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                    self.update_status(f"Playing: {os.path.basename(path)}")
                except Exception as e:
                    messagebox.showwarning("Playback Error", f"Could not play audio: {str(e)}\\nMake sure the file format is supported.")

        ttk.Button(audio_ctrl, text="🔄 Refresh", command=refresh_audio_lib).pack(side=tk.LEFT, padx=2)
        ttk.Button(audio_ctrl, text="➕ Add Audio...", command=add_to_audio_lib).pack(side=tk.LEFT, padx=2)
        ttk.Button(audio_ctrl, text="▶️ Play", command=play_selected_audio).pack(side=tk.LEFT, padx=2)
        ttk.Button(audio_ctrl, text="📂 Open Folder", command=lambda: os.startfile(self.audio_library.base_path) if os.path.exists(self.audio_library.base_path) else None).pack(side=tk.LEFT, padx=2)
        
        # Audio list with scrollbar
        audio_list_frame = ttk.Frame(audio_lib_frame)
        audio_list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.audio_list = tk.Listbox(audio_list_frame)
        self.audio_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        audio_scroll = ttk.Scrollbar(audio_list_frame, orient="vertical", command=self.audio_list.yview)
        audio_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.audio_list.config(yscrollcommand=audio_scroll.set)
        
        # Audio info label
        self.audio_info_lbl = ttk.Label(audio_lib_frame, text="Select an audio file to see details", relief=tk.SUNKEN, anchor=tk.W, padding=10)
        self.audio_info_lbl.pack(fill=tk.X, pady=5)
        
        def on_audio_select(event):
            sel = self.audio_list.curselection()
            if sel:
                path = self.audio_list.get(sel[0])
                try:
                    size_kb = os.path.getsize(path) / 1024
                    filename = os.path.basename(path)
                    self.audio_info_lbl.config(text=f"File: {filename} | Size: {size_kb:.1f} KB")
                except Exception as e:
                    self.audio_info_lbl.config(text=f"Error: {str(e)}")
        
        self.audio_list.bind('<<ListboxSelect>>', on_audio_select)
        
        def update_audio_list():
            self.audio_list.delete(0, tk.END)
            for audio in self.audio_library.get_audio_files():
                self.audio_list.insert(tk.END, audio)
        
        # Initial populate (use after instead to ensure library init)
        self.root.after(100, update_lib_list)
        self.root.after(100, update_audio_list)
        
        # --- Right Panel: Editor & Generation ---
        right_panel = ttk.Frame(main_paned)
        main_paned.add(right_panel, weight=3)
        
        # Create tabs for right panel
        self.right_tabs = ttk.Notebook(right_panel)
        self.right_tabs.pack(fill=tk.BOTH, expand=True)
        
        # Tab 1: Editor
        editor_tab = ttk.Frame(self.right_tabs)
        self.right_tabs.add(editor_tab, text="📝 Editor")
        
        # Editor Area
        self.editor_frame = ttk.LabelFrame(editor_tab, text="Sentence Editor", padding=10)
        self.editor_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Full text display of selected sentence
        self.sentence_text = tk.Text(self.editor_frame, height=3, wrap=tk.WORD, font=('Segoe UI', 11))
        self.sentence_text.pack(fill=tk.X, pady=(0, 15))
        self.sentence_text.config(state='disabled', bg='#f0f0f0')
        
        # Word Tags (Interactive Area)
        self.words_container = ttk.Frame(self.editor_frame)
        self.words_container.pack(fill=tk.BOTH, expand=True)
        
        # Selected Word Properties (Bottom of Editor)
        self.props_frame = ttk.LabelFrame(self.editor_frame, text="Selected Word Settings", padding=10)
        self.props_frame.pack(fill=tk.X, pady=10)
        
        # Props Controls
        p_grid = ttk.Frame(self.props_frame)
        p_grid.pack(fill=tk.X)
        for i in range(14):
             p_grid.columnconfigure(i, weight=1)
        
        # Row 0: Word name and Template
        ttk.Label(p_grid, text="Word:").grid(row=0, column=0, sticky=tk.W)
        self.lbl_selected_word = ttk.Label(p_grid, text="[None]", font=('Helvetica', 10, 'bold'))
        self.lbl_selected_word.grid(row=0, column=1, sticky=tk.W, padx=10)
        
        ttk.Label(p_grid, text="Template:").grid(row=0, column=2, sticky=tk.W, padx=(20, 5))
        self.var_word_template = tk.StringVar(value="Select Template")
        self.combo_word_template = ttk.Combobox(p_grid, textvariable=self.var_word_template, state='disabled', width=15)
        self.combo_word_template.grid(row=0, column=3, sticky=tk.W)
        
        ttk.Label(p_grid, text="Pitch:").grid(row=0, column=4, sticky=tk.W, padx=(20, 5))
        self.entry_word_pitch = ttk.Entry(p_grid, width=10, state='disabled')
        self.entry_word_pitch.grid(row=0, column=5, sticky=tk.W)
        
        ttk.Label(p_grid, text="Rate:").grid(row=0, column=6, sticky=tk.W, padx=(20, 5))
        self.entry_word_rate = ttk.Entry(p_grid, width=10, state='disabled')
        self.entry_word_rate.grid(row=0, column=7, sticky=tk.W)
        
        ttk.Button(p_grid, text="✓ Apply", command=self.apply_word_settings).grid(row=0, column=8, padx=10)
        
        # Row 1: Media controls (Image and Audio)
        ttk.Label(p_grid, text="Media:", font=('Helvetica', 9, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=(10, 5))
        
        self.btn_apply_lib_img = ttk.Button(p_grid, text="🖼️ Set Image", command=self.apply_lib_image, state='disabled', width=12)
        self.btn_apply_lib_img.grid(row=1, column=1, padx=5, pady=(10, 5))
        
        self.btn_customize_img = ttk.Button(p_grid, text="⚙️ Config Image", command=self.open_image_config, state='disabled', width=14)
        self.btn_customize_img.grid(row=1, column=2, columnspan=2, padx=5, pady=(10, 5))
        
        self.btn_apply_audio = ttk.Button(p_grid, text="🔊 Set Audio", command=self.apply_lib_audio, state='disabled', width=12)
        self.btn_apply_audio.grid(row=1, column=4, padx=5, pady=(10, 5))
        
        self.btn_customize_audio = ttk.Button(p_grid, text="⚙️ Config Audio", command=self.open_audio_config, state='disabled', width=14)
        self.btn_customize_audio.grid(row=1, column=5, columnspan=2, padx=5, pady=(10, 5))
        
        self.btn_clear_media = ttk.Button(p_grid, text="🗑️ Clear Media", command=self.clear_media, state='disabled', width=12)
        self.btn_clear_media.grid(row=1, column=7, padx=5, pady=(10, 5))

        # Timeline Visualization
        self.timeline_frame = ttk.LabelFrame(editor_tab, text="Timeline Properties", padding=10)
        self.timeline_frame.pack(fill=tk.X, pady=10)
        
        self.timeline_canvas = tk.Canvas(self.timeline_frame, height=100, bg='white')
        self.timeline_canvas.pack(side=tk.TOP, fill=tk.X, expand=True)
        
        timeline_scroll = ttk.Scrollbar(self.timeline_frame, orient="horizontal", command=self.timeline_canvas.xview)
        timeline_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.timeline_canvas.configure(xscrollcommand=timeline_scroll.set)

        # Tab 2: Generation
        generation_tab = ttk.Frame(self.right_tabs)
        self.right_tabs.add(generation_tab, text="🎬 Generation")
        
        # Audio Generation Section
        audio_gen_frame = ttk.LabelFrame(generation_tab, text="Audio Generation", padding=10)
        audio_gen_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(audio_gen_frame, text="Title:").pack(side=tk.LEFT)
        self.title_entry = ttk.Entry(audio_gen_frame)
        self.title_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        
        self.generate_btn = ttk.Button(audio_gen_frame, text="Generate Audio (Async)", command=self.start_generation, style="Action.TButton")
        self.generate_btn.pack(side=tk.RIGHT)
        
        self.progress = ttk.Progressbar(audio_gen_frame, mode='indeterminate')
        self.progress.pack(side=tk.RIGHT, padx=10)
        
        # Video Generation Section
        video_frame = ttk.LabelFrame(generation_tab, text="Video Generation", padding=10)
        video_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Help text
        ttk.Label(video_frame, text="Generate final video with TTS audio, captions, and media overlays", 
                 font=('Segoe UI', 8), foreground='gray').pack(anchor=tk.W, pady=(0, 5))
        
        ttk.Label(video_frame, text="Config File:").pack(side=tk.LEFT)
        self.config_entry = ttk.Entry(video_frame)
        self.config_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        def browse_config():
            filename = filedialog.askopenfilename(
                title="Select Config File",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialdir=os.path.join(os.getcwd(), "assets", "audio")
            )
            if filename:
                self.config_entry.delete(0, tk.END)
                self.config_entry.insert(0, filename)
        
        ttk.Button(video_frame, text="Browse", command=browse_config).pack(side=tk.LEFT, padx=5)
        self.generate_video_btn = ttk.Button(video_frame, text="Generate Video", command=self.start_video_generation, style="Action.TButton")
        self.generate_video_btn.pack(side=tk.RIGHT)
        
        self.video_progress = ttk.Progressbar(video_frame, mode='indeterminate')
        self.video_progress.pack(side=tk.RIGHT, padx=10)
        
        # Status bar at bottom
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(generation_tab, textvariable=self.status_var, relief=tk.SUNKEN).pack(fill=tk.X, pady=5)
        
        # Setup bindings for properties
        self.combo_word_template.bind('<<ComboboxSelected>>', self.on_template_selected)
        
        # Setup bindings for properties
        self.combo_word_template.bind('<<ComboboxSelected>>', self.on_template_selected)

    def on_template_selected(self, event):
        if not self.selected_word:
            return
            
        name = self.combo_word_template.get()
        if name in self.templates:
            data = self.templates[name]
            self.entry_word_pitch.delete(0, tk.END)
            self.entry_word_pitch.insert(0, data['pitch'])
            self.entry_word_rate.delete(0, tk.END)
            self.entry_word_rate.insert(0, data['rate'])
        
    def on_sentence_select(self, event):
        selection = self.sentence_list.curselection()
        if selection:
            index = selection[0]
            self.current_sentence_index = index
            self.display_current_sentence()
            # Update library combo
            if hasattr(self, 'lib_sentence_combo') and self.lib_sentence_combo['values']:
                self.lib_sentence_combo.current(index)
    
    def on_lib_sentence_select(self, event):
        """Handle sentence selection from library tab"""
        if self.lib_sentence_combo.current() >= 0:
            self.current_sentence_index = self.lib_sentence_combo.current()
            self.display_current_sentence()
            # Update main sentence list selection
            self.sentence_list.selection_clear(0, tk.END)
            self.sentence_list.selection_set(self.current_sentence_index)
            self.sentence_list.see(self.current_sentence_index)

    def display_current_sentence(self):
        if not self.generator.sentences:
            return
            
        sentence = self.generator.sentences[self.current_sentence_index]
        
        # Update text display
        self.sentence_text.config(state='normal')
        self.sentence_text.delete("1.0", tk.END)
        self.sentence_text.insert("1.0", sentence.text)
        self.sentence_text.config(state='disabled')
        
        # Clear words container
        for widget in self.words_container.winfo_children():
            widget.destroy()
            
        # Create flow layout for words
        flow_frame = tk.Text(self.words_container, wrap=tk.WORD, bg='#ffffff', relief=tk.FLAT)
        flow_frame.pack(fill=tk.BOTH, expand=True)
        
        self.current_word_widgets = []
        
        for i, word in enumerate(sentence.words):
            # Container for word + image indicator
            container = tk.Frame(flow_frame, bg='#ffffff')
            
            # Create a button for each word
            btn = tk.Button(container, text=word.text, 
                          command=lambda w=word, idx=i: self.on_word_click(w, idx))
            
            # Style button based on if it has custom settings, image, or audio
            has_settings = word.pitch != "+0Hz" or word.rate != "+0%"
            has_image = word.image_path is not None
            has_audio = word.audio_path is not None
            
            if has_image and has_audio:
                btn.config(fg='darkviolet', font=('Segoe UI', 9, 'bold', 'underline'))
                btn.config(bg='#ffe6f0') # Pink-purple
            elif has_image:
                btn.config(fg='purple', font=('Segoe UI', 9, 'bold', 'underline'))
                btn.config(bg='#f0e6ff') # Light purple
            elif has_audio:
                btn.config(fg='darkgreen', font=('Segoe UI', 9, 'bold', 'italic'))
                btn.config(bg='#e6ffe6') # Light green
            elif has_settings:
                btn.config(fg='blue', font=('Segoe UI', 9, 'bold'))
                btn.config(bg='#e6f3ff')
            else:
                btn.config(fg='black', font=('Segoe UI', 9), bg='#f0f0f0')
            
            btn.pack(side=tk.TOP, fill=tk.X)
            
            # Indicators
            indicators = []
            if has_image:
                indicators.append("📷")
            if has_audio:
                indicators.append("🔊")
            
            if indicators:
                img_indicator = tk.Label(container, text=" ".join(indicators), bg='#ffffff', font=('Segoe UI', 8))
                img_indicator.pack(side=tk.BOTTOM)
                
            flow_frame.window_create(tk.END, window=container, padx=2, pady=2)
            self.current_word_widgets.append(btn)
            
        flow_frame.config(state='disabled')
        
        # Reset properties panel
        self.selected_word = None
        self.lbl_selected_word.config(text="[None]")
        self.entry_word_pitch.delete(0, tk.END)
        self.entry_word_rate.delete(0, tk.END)
        self.config_props_state('disabled')
        
        # Disable image buttons
        if hasattr(self, 'btn_apply_lib_img'):
             self.btn_apply_lib_img.config(state='disabled')
        if hasattr(self, 'btn_customize_img'):
             self.btn_customize_img.config(state='disabled')

        self.draw_timeline()

    def draw_timeline(self):
        """Draw timeline visualization"""
        self.timeline_canvas.delete("all")
        
        if not self.generator.sentences:
            return
            
        sentence = self.generator.sentences[self.current_sentence_index]
        
        # Constants
        PX_PER_SECOND = 100
        start_x = 10
        y_words = 80
        y_images = 40
        y_audio = 10
        height_block = 25
        
        # Draw labels
        self.timeline_canvas.create_text(5, y_audio + 12, text="🔊", anchor="e", font=('Segoe UI', 10))
        self.timeline_canvas.create_text(5, y_images + 12, text="📷", anchor="e", font=('Segoe UI', 10))
        self.timeline_canvas.create_text(5, y_words + 12, text="💬", anchor="e", font=('Segoe UI', 10))
        
        current_time = 0
        
        for word in sentence.words:
            # Estimate word duration (approx 500ms per word + extra for punctuation)
            duration_ms = 500
            if any(p in word.text for p in ',.!?'):
                duration_ms += 300
                
            width = (duration_ms / 1000) * PX_PER_SECOND
            
            # Draw Word Block
            self.timeline_canvas.create_rectangle(
                start_x + (current_time/1000)*PX_PER_SECOND, y_words,
                start_x + ((current_time + duration_ms)/1000)*PX_PER_SECOND, y_words + height_block,
                fill="#e0e0e0", outline="#a0a0a0"
            )
            self.timeline_canvas.create_text(
                start_x + (current_time/1000)*PX_PER_SECOND + 5, y_words + 12,
                text=word.text, anchor="w", font=('Segoe UI', 8)
            )
            
            # Draw Image Block if exists
            if word.image_path:
                img_start = word.image_start_ms if word.image_start_ms is not None else current_time
                img_duration = word.image_duration_ms
                
                self.timeline_canvas.create_rectangle(
                    start_x + (img_start/1000)*PX_PER_SECOND, y_images,
                    start_x + ((img_start + img_duration)/1000)*PX_PER_SECOND, y_images + height_block,
                    fill="#d0f0c0", outline="#80c080"
                )
                
                # Truncate filename
                fname = os.path.basename(word.image_path)
                if len(fname) > 12: fname = fname[:9] + "..."
                
                self.timeline_canvas.create_text(
                    start_x + (img_start/1000)*PX_PER_SECOND + 5, y_images + 12,
                    text=f"📷 {fname}", anchor="w", font=('Segoe UI', 7)
                )
            
            # Draw Audio Block if exists
            if word.audio_path:
                audio_start = word.audio_start_ms if word.audio_start_ms is not None else current_time
                # Use audio_duration_ms if specified, otherwise estimate
                audio_duration = word.audio_duration_ms if word.audio_duration_ms else 1000
                
                self.timeline_canvas.create_rectangle(
                    start_x + (audio_start/1000)*PX_PER_SECOND, y_audio,
                    start_x + ((audio_start + audio_duration)/1000)*PX_PER_SECOND, y_audio + height_block,
                    fill="#c0d0f0", outline="#8080c0"
                )
                
                # Truncate filename
                fname = os.path.basename(word.audio_path)
                if len(fname) > 12: fname = fname[:9] + "..."
                
                self.timeline_canvas.create_text(
                    start_x + (audio_start/1000)*PX_PER_SECOND + 5, y_audio + 12,
                    text=f"🔊 {fname}", anchor="w", font=('Segoe UI', 7)
                )
                
            current_time += duration_ms

        self.timeline_canvas.configure(scrollregion=self.timeline_canvas.bbox("all"))

    def config_props_state(self, state):
        self.combo_word_template.config(state=state)
        self.entry_word_pitch.config(state=state)
        self.entry_word_rate.config(state=state)
        if hasattr(self, 'btn_apply_lib_img'):
             self.btn_apply_lib_img.config(state=state)
        if hasattr(self, 'btn_customize_img'):
             self.btn_customize_img.config(state=state)
        if hasattr(self, 'btn_apply_audio'):
             self.btn_apply_audio.config(state=state)
        if hasattr(self, 'btn_customize_audio'):
             self.btn_customize_audio.config(state=state)
        if hasattr(self, 'btn_clear_media'):
             self.btn_clear_media.config(state=state)

    def on_word_click(self, word, idx):
        self.selected_word = word
        self.lbl_selected_word.config(text=f"'{word.text}'")
        self.config_props_state('normal')
        
        self.entry_word_pitch.delete(0, tk.END)
        self.entry_word_pitch.insert(0, word.pitch)
        self.entry_word_rate.delete(0, tk.END)
        self.entry_word_rate.insert(0, word.rate)
        
        # Update template list
        self.combo_word_template['values'] = ["Select Template"] + sorted(list(self.templates.keys()))
        self.combo_word_template.set("Select Template")

    def open_image_config(self):
        """Open image configuration dialog for selected word"""
        if not self.selected_word:
            return
            
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Image Settings for '{self.selected_word.text}'")
        dialog.geometry("400x500")
        
        word = self.selected_word
        
        # Image Path
        ttk.Label(dialog, text="Image Path:").pack(anchor=tk.W, padx=10, pady=(10, 0))
        path_frame = ttk.Frame(dialog)
        path_frame.pack(fill=tk.X, padx=10, pady=5)
        
        path_var = tk.StringVar(value=word.image_path if word.image_path else "")
        path_entry = ttk.Entry(path_frame, textvariable=path_var)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        def browse_image():
            filename = filedialog.askopenfilename(
                title="Select Image",
                filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.webp")]
            )
            if filename:
                path_var.set(filename)
                
        ttk.Button(path_frame, text="Browse", command=browse_image).pack(side=tk.RIGHT, padx=(5, 0))
        
        # Preview Frame in Dialog
        preview_frame = ttk.LabelFrame(dialog, text="Preview", padding=5)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        preview_lbl = tk.Label(preview_frame, text="No Image", bg='#f0f0f0')
        preview_lbl.pack(fill=tk.BOTH, expand=True)

        def update_preview(*args):
             p = path_var.get()
             if p and os.path.exists(p):
                 try:
                     pil_img = Image.open(p)
                     pil_img.thumbnail((150, 150))
                     tk_img = ImageTk.PhotoImage(pil_img)
                     preview_lbl.config(image=tk_img, text="")
                     preview_lbl.image = tk_img
                 except:
                     preview_lbl.config(text="Invalid Image", image="")
             else:
                 preview_lbl.config(text="No Image", image="")

        path_var.trace_add('write', update_preview)
        # Trigger initial update
        update_preview()

        # Duration
        ttk.Label(dialog, text="Duration (ms):").pack(anchor=tk.W, padx=10, pady=(10, 0))
        duration_var = tk.IntVar(value=word.image_duration_ms)
        duration_scale = ttk.Scale(dialog, from_=100, to=5000, variable=duration_var, orient=tk.HORIZONTAL)
        duration_scale.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(dialog, textvariable=duration_var).pack()
        
        # Position
        ttk.Label(dialog, text="Position:").pack(anchor=tk.W, padx=10, pady=(10, 0))
        pos_var = tk.StringVar(value=word.image_position)
        pos_combo = ttk.Combobox(dialog, textvariable=pos_var, 
                               values=["center", "top-left", "top-right", "bottom-left", "bottom-right"])
        pos_combo.pack(fill=tk.X, padx=10, pady=5)
        
        # Scale
        ttk.Label(dialog, text="Scale:").pack(anchor=tk.W, padx=10, pady=(10, 0))
        scale_var = tk.DoubleVar(value=word.image_scale)
        scale_scale = ttk.Scale(dialog, from_=0.5, to=2.0, variable=scale_var, orient=tk.HORIZONTAL)
        scale_scale.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(dialog, textvariable=scale_var).pack()
        
        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=20)
        
        def save():
            word.image_path = path_var.get() if path_var.get() else None
            word.image_duration_ms = int(duration_var.get())
            word.image_position = pos_var.get()
            word.image_scale = float(scale_var.get())
            if not word.image_path:
                word.image_start_ms = None
            
            self.display_current_sentence()
            dialog.destroy()
            
        def clear():
            path_var.set("")
            # Don't save yet, let user click save
            
        ttk.Button(btn_frame, text="Save", command=save).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Clear Image", command=clear).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def apply_word_settings(self):
        if self.selected_word:
            self.selected_word.pitch = self.entry_word_pitch.get()
            self.selected_word.rate = self.entry_word_rate.get()
            self.display_current_sentence() # Refresh to show visual indication
            
    def apply_lib_image(self):
        """Apply selected image from library to selected word"""
        if not self.selected_word:
            return
            
        # Get selected item from library
        sel = self.lib_list.curselection()
        if not sel:
            messagebox.showwarning("Selection", "Please select an image in the Library tab first.")
            self.left_tabs.select(self.tab_library)
            return
            
        path = self.lib_list.get(sel[0])
        self.selected_word.image_path = path
        # Set defaults if needed/not set
        self.selected_word.image_duration_ms = 1000
        self.selected_word.image_position = "center"
        self.selected_word.image_scale = 1.0
        self.selected_word.image_start_ms = None # auto
        
        self.display_current_sentence()
        self.update_status(f"Applied {os.path.basename(path)} to word")

    def update_sentence_list(self):
        self.sentence_list.delete(0, tk.END)
        for i, s in enumerate(self.generator.sentences):
            text_preview = (s.text[:30] + '..') if len(s.text) > 30 else s.text
            self.sentence_list.insert(tk.END, f"{i+1}: {text_preview}")
        
        # Also update the library tab sentence selector
        if hasattr(self, 'lib_sentence_combo'):
            sentence_options = []
            for i, s in enumerate(self.generator.sentences):
                text_preview = (s.text[:50] + '...') if len(s.text) > 50 else s.text
                sentence_options.append(f"{i+1}: {text_preview}")
            
            self.lib_sentence_combo['values'] = sentence_options
            if sentence_options and self.current_sentence_index < len(sentence_options):
                self.lib_sentence_combo.current(self.current_sentence_index)
    
    def on_frame_configure(self, event=None):
        """Update scroll region when frame size changes"""
        self.words_canvas.configure(scrollregion=self.words_canvas.bbox("all"))
    
    def load_voices(self):
        """Load available voices asynchronously"""
        def load_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                voices = loop.run_until_complete(self.generator.get_available_voices())
                self.root.after(0, self.update_voice_combo, voices)
            except Exception as e:
                print(f"Error loading voices: {e}")
                self.root.after(0, self.update_status, f"Error loading voices: {str(e)}")
        
        threading.Thread(target=load_async, daemon=True).start()
    
    def update_voice_combo(self, voices):
        """Update voice combobox with available voices"""
        self.voice_combo['values'] = voices
        if voices and "en-US-ChristopherNeural" in voices:
            self.voice_var.set("en-US-ChristopherNeural")
        elif voices:
            self.voice_var.set(voices[0])
    
    def parse_text(self):
        """Parse input text into sentences"""
        text = self.text_input.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("No Text", "Please enter some text to parse.")
            return
        
        sentences_text = self.generator.parse_text(text)
        self.generator.sentences = []
        
        for sent_text in sentences_text:
            words = self.generator.parse_sentence(sent_text)
            word_settings = [WordSettings(text=word) for word in words]
            sentence = SentenceSettings(
                text=sent_text,
                words=word_settings,
                voice=self.voice_var.get(),
                pitch=self.pitch_var.get(),
                rate=self.rate_var.get()
            )
            self.generator.sentences.append(sentence)
        
        self.update_sentence_list()
        self.update_status(f"Parsed {len(sentences_text)} sentences")
        
        # Select first sentence
        if self.generator.sentences:
            self.sentence_list.selection_set(0)
            self.on_sentence_select(None)

    def start_generation(self):
        self.generate_audio()
    
    def generate_audio(self):
        """Generate audio file with timestamps"""
        if not self.generator.sentences:
            messagebox.showwarning("No Sentences", "Please parse some text first.")
            return
        
        # Update global settings for ALL sentences
        global_voice = self.voice_var.get()
        global_pitch = self.pitch_var.get()
        global_rate = self.rate_var.get()
        
        for sentence in self.generator.sentences:
            sentence.voice = global_voice
            sentence.pitch = global_pitch
            sentence.rate = global_rate
            
            # Propagate global settings to words that are still default
            # This ensures "Global Settings" apply to the text unless specific words are customized
            for word in sentence.words:
                if word.pitch == "+0Hz":
                    word.pitch = global_pitch
                if word.rate == "+0%":
                    word.rate = global_rate
        
        # Get Title AND validate
        title = self.title_entry.get().strip()
        if not title:
            messagebox.showwarning("Missing Title", "Please enter a title for the audio file.")
            return

        # Prepare output directory
        base_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(base_dir, "assets", "audio")
        os.makedirs(output_dir, exist_ok=True)
        
        output_file = os.path.join(output_dir, f"{title}.mp3")
        
        def generate_async():
            try:
                self.root.after(0, self.update_status, "Generating audio...")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                output_path, project_data = loop.run_until_complete(
                    self.generator.generate_audio(self.generator.sentences, output_file)
                )
                
                if output_path:
                    # Save Project Config (JSON) for Video Makers
                    config_file = output_file.replace('.mp3', '_config.json')
                    with open(config_file, 'w') as f:
                        json.dump(project_data, f, indent=2)
                    
                    # Save SRT for subtitles
                    # Extract sentences list from project_data
                    sentences_data = project_data.get('sentences', [])
                    
                    timestamp_file_srt = output_file.replace('.mp3', '.srt')
                    with open(timestamp_file_srt, 'w', encoding='utf-8') as f:
                        f.write(self.generator.export_timestamps(sentences_data, 'srt'))
                    
                    # Auto-populate config file in video generation section
                    self.root.after(0, lambda: self.config_entry.delete(0, tk.END))
                    self.root.after(0, lambda: self.config_entry.insert(0, config_file))
                    
                    self.root.after(0, self.update_status, f"Saved to: {output_path}")
                    self.root.after(0, messagebox.showinfo, "Success", 
                                  f"Audio generated successfully!\n\n"
                                  f"Audio: {os.path.basename(output_path)}\n"
                                  f"Config: {os.path.basename(config_file)}\n"
                                  f"SRT: {os.path.basename(timestamp_file_srt)}")
                else:
                    self.root.after(0, self.update_status, "Generation failed.")
                    
            except Exception as e:
                self.root.after(0, messagebox.showerror, "Error", f"Failed to generate audio:\n{str(e)}")
                self.root.after(0, self.update_status, "Error occurred")
        
        threading.Thread(target=generate_async, daemon=True).start()

    def start_video_generation(self):
        """Start video generation from config file"""
        if not VIDEO_GENERATION_AVAILABLE:
            messagebox.showerror("Error", "Video generation is not available. Please ensure generate_video.py is in the same directory.")
            return
        
        config_path = self.config_entry.get().strip()
        if not config_path:
            messagebox.showwarning("No Config File", "Please select a config file first.")
            return
        
        if not os.path.exists(config_path):
            messagebox.showerror("File Not Found", f"Config file not found: {config_path}")
            return
        
        def generate_video_async():
            try:
                self.root.after(0, self.update_status, "Generating video...")
                self.root.after(0, lambda: self.video_progress.start())
                
                # Run video generation
                generate_video(config_path)
                
                self.root.after(0, lambda: self.video_progress.stop())
                self.root.after(0, self.update_status, "Video generation completed!")
                
                # Show success message
                output_video = os.path.splitext(config_path)[0] + ".mp4"
                if os.path.exists(output_video):
                    self.root.after(0, messagebox.showinfo, "Success", 
                                  f"Video generated successfully!\n\nVideo: {os.path.basename(output_video)}")
                else:
                    self.root.after(0, messagebox.showwarning, "Warning", 
                                  "Video generation completed but output file not found.")
                    
            except Exception as e:
                self.root.after(0, lambda: self.video_progress.stop())
                self.root.after(0, self.update_status, "Video generation failed")
                self.root.after(0, messagebox.showerror, "Error", f"Failed to generate video:\n{str(e)}")
        
        threading.Thread(target=generate_video_async, daemon=True).start()

    def update_status(self, message):
        """Update status bar"""
        self.status_var.set(message)
        
    def export_timestamps(self):
        """Export timestamps in selected format"""
        if not self.generator.sentences:
            messagebox.showwarning("No Data", "No audio has been generated yet.")
            return
        
        # Create estimated timestamps
        dummy_timestamps = [
            {
                'sentence_index': i,
                'text': sent.text,
                'start_ms': i * 2000,
                'end_ms': (i + 1) * 2000
            }
            for i, sent in enumerate(self.generator.sentences)
        ]
        
        format_choice = simpledialog.askstring(
            "Export Format",
            "Enter format (json, csv, srt, vtt):",
            initialvalue="json"
        )
        
        if format_choice and format_choice.lower() in ['json', 'csv', 'srt', 'vtt']:
            content = self.generator.export_timestamps(dummy_timestamps, format_choice.lower())
            
            output_file = filedialog.asksaveasfilename(
                defaultextension=f".{format_choice.lower()}",
                filetypes=[(f"{format_choice.upper()} files", f"*.{format_choice.lower()}")]
            )
            
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("Success", f"Timestamps exported to {output_file}")

    def save_project(self):
        """Save current project to JSON file"""
        if not self.generator.sentences:
            messagebox.showwarning("No Data", "No project to save.")
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path:
            project_data = {
                'sentences': [asdict(sent) for sent in self.generator.sentences],
                'current_sentence_index': self.current_sentence_index,
                'global_voice': self.voice_var.get(),
                'global_pitch': self.pitch_var.get(),
                'global_rate': self.rate_var.get()
            }
            
            with open(file_path, 'w') as f:
                json.dump(project_data, f, indent=2)
            
            self.generator.current_project_path = file_path
            self.update_status(f"Project saved to {file_path}")
    
    def load_project(self):
        """Load project from JSON file"""
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    project_data = json.load(f)
                
                # Recreate sentences
                self.generator.sentences = []
                for sent_data in project_data['sentences']:
                    words = [WordSettings(**word_data) for word_data in sent_data['words']]
                    sentence = SentenceSettings(
                        text=sent_data['text'],
                        words=words,
                        voice=sent_data['voice'],
                        pitch=sent_data['pitch'],
                        rate=sent_data['rate']
                    )
                    self.generator.sentences.append(sentence)
                
                # Restore state
                self.current_sentence_index = project_data.get('current_sentence_index', 0)
                self.voice_var.set(project_data.get('global_voice', 'en-US-ChristopherNeural'))
                self.pitch_var.set(project_data.get('global_pitch', '+0Hz'))
                self.rate_var.set(project_data.get('global_rate', '+0%'))
                
                self.generator.current_project_path = file_path
                self.display_current_sentence()
                self.update_status(f"Project loaded from {file_path}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load project: {str(e)}")

    def apply_lib_audio(self):
        """Apply selected audio from library to selected word"""
        if not self.selected_word:
            return
            
        # Get selected item from library
        sel = self.audio_list.curselection()
        if not sel:
            messagebox.showwarning("Selection", "Please select an audio file in the Library > Sound Effects tab first.")
            self.left_tabs.select(self.tab_library)
            return
            
        path = self.audio_list.get(sel[0])
        self.selected_word.audio_path = path
        # Set defaults if needed/not set
        self.selected_word.audio_duration_ms = None  # Use full audio
        self.selected_word.audio_volume = 1.0
        self.selected_word.audio_start_ms = None # auto
        
        self.display_current_sentence()
        self.update_status(f"Applied {os.path.basename(path)} to word")
    
    def open_audio_config(self):
        """Open audio configuration dialog for selected word"""
        if not self.selected_word:
            return
            
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Audio Settings for '{self.selected_word.text}'")
        dialog.geometry("400x400")
        
        word = self.selected_word
        
        # Audio Path
        ttk.Label(dialog, text="Audio Path:").pack(anchor=tk.W, padx=10, pady=(10, 0))
        path_frame = ttk.Frame(dialog)
        path_frame.pack(fill=tk.X, padx=10, pady=5)
        
        path_var = tk.StringVar(value=word.audio_path if word.audio_path else "")
        path_entry = ttk.Entry(path_frame, textvariable=path_var)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        def browse_audio():
            filename = filedialog.askopenfilename(
                title="Select Audio",
                filetypes=[("Audio Files", "*.mp3 *.wav *.ogg *.m4a *.flac")]
            )
            if filename:
                path_var.set(filename)
        
        def play_audio():
            p = path_var.get()
            if p and os.path.exists(p):
                try:
                    import winsound
                    winsound.PlaySound(p, winsound.SND_FILENAME | winsound.SND_ASYNC)
                except Exception as e:
                    messagebox.showwarning("Playback Error", f"Could not play: {str(e)}")
                    
        ttk.Button(path_frame, text="Browse", command=browse_audio).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(path_frame, text="▶️ Play", command=play_audio).pack(side=tk.RIGHT, padx=(5, 0))
        
        # Audio info
        info_lbl = ttk.Label(dialog, text="", relief=tk.SUNKEN, padding=5)
        info_lbl.pack(fill=tk.X, padx=10, pady=5)

        def update_info(*args):
             p = path_var.get()
             if p and os.path.exists(p):
                 try:
                     size_kb = os.path.getsize(p) / 1024
                     filename = os.path.basename(p)
                     info_lbl.config(text=f"File: {filename} | Size: {size_kb:.1f} KB")
                 except:
                     info_lbl.config(text="")
             else:
                 info_lbl.config(text="No audio file selected")

        path_var.trace_add('write', update_info)
        update_info()

        # Duration (optional - None means use full audio)
        ttk.Label(dialog, text="Duration (ms): (Leave at 0 for full duration)").pack(anchor=tk.W, padx=10, pady=(10, 0))
        duration_var = tk.IntVar(value=word.audio_duration_ms if word.audio_duration_ms else 0)
        duration_scale = ttk.Scale(dialog, from_=0, to=5000, variable=duration_var, orient=tk.HORIZONTAL)
        duration_scale.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(dialog, textvariable=duration_var).pack()
        
        # Volume
        ttk.Label(dialog, text="Volume:").pack(anchor=tk.W, padx=10, pady=(10, 0))
        volume_var = tk.DoubleVar(value=word.audio_volume)
        volume_scale = ttk.Scale(dialog, from_=0.0, to=1.0, variable=volume_var, orient=tk.HORIZONTAL)
        volume_scale.pack(fill=tk.X, padx=10, pady=5)
        volume_lbl = ttk.Label(dialog, text="")
        volume_lbl.pack()
        
        def update_volume_label(*args):
            volume_lbl.config(text=f"{volume_var.get():.2f}")
        
        volume_var.trace_add('write', update_volume_label)
        update_volume_label()
        
        # Start offset (relative to word start)
        ttk.Label(dialog, text="Start Offset (ms): (Relative to word start)").pack(anchor=tk.W, padx=10, pady=(10, 0))
        offset_var = tk.IntVar(value=word.audio_start_ms if word.audio_start_ms is not None else 0)
        offset_scale = ttk.Scale(dialog, from_=-1000, to=2000, variable=offset_var, orient=tk.HORIZONTAL)
        offset_scale.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(dialog, textvariable=offset_var).pack()
        
        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=20)
        
        def save():
            word.audio_path = path_var.get() if path_var.get() else None
            dur = int(duration_var.get())
            word.audio_duration_ms = dur if dur > 0 else None
            word.audio_volume = float(volume_var.get())
            word.audio_start_ms = int(offset_var.get()) if word.audio_path else None
            
            self.display_current_sentence()
            dialog.destroy()
            
        def clear():
            path_var.set("")
            
        ttk.Button(btn_frame, text="Save", command=save).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Clear Audio", command=clear).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def clear_media(self):
        """Clear all media (image and audio) from selected word"""
        if not self.selected_word:
            return
        
        if self.selected_word.image_path or self.selected_word.audio_path:
            if messagebox.askyesno("Confirm", "Clear all media (image and audio) from this word?"):
                self.selected_word.image_path = None
                self.selected_word.image_start_ms = None
                self.selected_word.audio_path = None
                self.selected_word.audio_start_ms = None
                self.selected_word.audio_duration_ms = None
                self.display_current_sentence()
                self.update_status("Media cleared")
        else:
            messagebox.showinfo("Info", "No media attached to this word")

    def insert_sample_text(self):
        """Insert sample text into input area"""
        sample = """Old Roblox was SO much better and I'm tired of pretending it's not. Like, we had GUESTS. Those yellow dudes just hanging out in every game. Roblox deleted them for "being confusing." Bruh what? And remember TIX? Free currency just for logging in? You could earn Robux without paying. Now? Everything costs money."""
        self.text_input.delete("1.0", tk.END)
        self.text_input.insert("1.0", sample)

def main():
    root = tk.Tk()
    app = VSubApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()