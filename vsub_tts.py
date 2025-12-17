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
        self.root.title("VSub TTS Generator")
        self.root.geometry("1200x800")
        
        self.generator = VSubTTSGenerator()
        self.current_sentence_index = 0
        
        # Variables
        self.voice_var = tk.StringVar(value="en-US-ChristopherNeural")
        self.pitch_var = tk.StringVar(value="+0Hz")
        self.rate_var = tk.StringVar(value="+0%")
        
        self.setup_ui()
        self.load_voices()
        self.load_templates()
        
        # Initialize Image Library
        self.image_library = ImageLibrary()
        self.clipboard_img = None
    
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
        
        lib_ctrl = ttk.Frame(self.tab_library)
        lib_ctrl.pack(fill=tk.X, pady=5)
        
        def refresh_lib():
            self.image_library.refresh()
            update_lib_list()
            
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

        ttk.Button(lib_ctrl, text="Refresh", command=refresh_lib).pack(side=tk.LEFT, padx=5)
        ttk.Button(lib_ctrl, text="Add Images...", command=add_to_lib).pack(side=tk.LEFT, padx=5)
        
        self.lib_list = tk.Listbox(self.tab_library)
        self.lib_list.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Preview
        self.preview_lbl = ttk.Label(self.tab_library, text="No Preview", relief=tk.SUNKEN, anchor=tk.CENTER)
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
        
        # Initial populate (use after instead to ensure library init)
        self.root.after(100, update_lib_list)
        
        # --- Right Panel: Editor & Generation ---
        right_panel = ttk.Frame(main_paned)
        main_paned.add(right_panel, weight=3)
        
        # Editor Area
        self.editor_frame = ttk.LabelFrame(right_panel, text="Sentence Editor", padding=10)
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
        for i in range(12):
             p_grid.columnconfigure(i, weight=1)
        
        ttk.Label(p_grid, text="Word:").grid(row=0, column=0, sticky=tk.W)
        self.lbl_selected_word = ttk.Label(p_grid, text="[None]", font=('Helvetica', 10, 'bold'))
        self.lbl_selected_word.grid(row=0, column=1, sticky=tk.W, padx=10)
        
        ttk.Label(p_grid, text="Template:").grid(row=0, column=2, sticky=tk.W, padx=(20, 5))
        self.var_word_template = tk.StringVar(value="Select Template")
        self.combo_word_template = ttk.Combobox(p_grid, textvariable=self.var_word_template, state='disabled')
        self.combo_word_template.grid(row=0, column=3, sticky=tk.W)
        
        ttk.Label(p_grid, text="Pitch:").grid(row=0, column=4, sticky=tk.W, padx=(20, 5))
        self.entry_word_pitch = ttk.Entry(p_grid, width=10, state='disabled')
        self.entry_word_pitch.grid(row=0, column=5, sticky=tk.W)
        
        ttk.Label(p_grid, text="Rate:").grid(row=0, column=6, sticky=tk.W, padx=(20, 5))
        self.entry_word_rate = ttk.Entry(p_grid, width=10, state='disabled')
        self.entry_word_rate.grid(row=0, column=7, sticky=tk.W)
        
        ttk.Button(p_grid, text="Apply", command=self.apply_word_settings).grid(row=0, column=8, padx=20)
        
        ttk.Button(p_grid, text="Apply", command=self.apply_word_settings).grid(row=0, column=8, padx=20)
        
        self.btn_apply_lib_img = ttk.Button(p_grid, text="Set Lib Img", command=self.apply_lib_image, state='disabled')
        self.btn_apply_lib_img.grid(row=0, column=9, padx=5)
        
        self.btn_customize_img = ttk.Button(p_grid, text="Customize", command=self.open_image_config, state='disabled')
        self.btn_customize_img.grid(row=0, column=10, padx=5)

        # Timeline Visualization
        self.timeline_frame = ttk.LabelFrame(self.editor_frame, text="Timeline Properties", padding=10)
        self.timeline_frame.pack(fill=tk.X, pady=10)
        
        self.timeline_canvas = tk.Canvas(self.timeline_frame, height=100, bg='white')
        self.timeline_canvas.pack(side=tk.TOP, fill=tk.X, expand=True)
        
        timeline_scroll = ttk.Scrollbar(self.timeline_frame, orient="horizontal", command=self.timeline_canvas.xview)
        timeline_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.timeline_canvas.configure(xscrollcommand=timeline_scroll.set)

        # Generation Controls
        gen_frame = ttk.LabelFrame(right_panel, text="Export", padding=10)
        gen_frame.pack(fill=tk.X)
        
        ttk.Label(gen_frame, text="Title:").pack(side=tk.LEFT)
        self.title_entry = ttk.Entry(gen_frame)
        self.title_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        
        self.generate_btn = ttk.Button(gen_frame, text="Generate Audio (Async)", command=self.start_generation, style="Action.TButton")
        self.generate_btn.pack(side=tk.RIGHT)
        
        self.progress = ttk.Progressbar(gen_frame, mode='indeterminate')
        self.progress.pack(side=tk.RIGHT, padx=10)
        
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(right_panel, textvariable=self.status_var, relief=tk.SUNKEN).pack(fill=tk.X, pady=5)
        
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
            
            # Style button based on if it has custom settings or image
            has_settings = word.pitch != "+0Hz" or word.rate != "+0%"
            has_image = word.image_path is not None
            
            if has_image:
                btn.config(fg='purple', font=('Segoe UI', 9, 'bold', 'underline'))
                btn.config(bg='#f0e6ff') # Light purple
            elif has_settings:
                btn.config(fg='blue', font=('Segoe UI', 9, 'bold'))
                btn.config(bg='#e6f3ff')
            else:
                btn.config(fg='black', font=('Segoe UI', 9), bg='#f0f0f0')
            
            btn.pack(side=tk.TOP, fill=tk.X)
            
            if has_image:
                img_indicator = tk.Label(container, text="📷", bg='#ffffff', font=('Segoe UI', 8))
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
        y_words = 60
        y_images = 20
        height_block = 30
        
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
                start_x + (current_time/1000)*PX_PER_SECOND + 5, y_words + 15,
                text=word.text, anchor="w", font=('Segoe UI', 8)
            )
            
            # Draw Image Block if exists
            if word.image_path:
                img_start = word.image_start_ms if word.image_start_ms is not None else current_time
                img_duration = word.image_duration_ms
                
                # Check for overlap/replacement based on simple logic
                # For visualization, we just draw them. Real conflict resolution happens in export.
                
                self.timeline_canvas.create_rectangle(
                    start_x + (img_start/1000)*PX_PER_SECOND, y_images,
                    start_x + ((img_start + img_duration)/1000)*PX_PER_SECOND, y_images + height_block,
                    fill="#d0f0c0", outline="#80c080"
                )
                
                # Truncate filename
                fname = os.path.basename(word.image_path)
                if len(fname) > 15: fname = fname[:12] + "..."
                
                self.timeline_canvas.create_text(
                    start_x + (img_start/1000)*PX_PER_SECOND + 5, y_images + 15,
                    text=f"📷 {fname}", anchor="w", font=('Segoe UI', 8)
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

    def insert_sample_text(self):
        """Insert sample text into input area"""
        sample = """Old Roblox was SO much better and I'm tired of pretending it's not. Like, we had GUESTS. Those yellow dudes just hanging out in every game. Roblox deleted them for "being confusing." Bruh what? And remember TIX? Free currency just for logging in? You could earn Robux without paying. Now? Everything costs money."""
        self.text_input.delete("1.0", tk.END)
        self.text_input.insert("1.0", sample)

    def update_status(self, message):
        """Update status bar"""
        self.status_var.set(message)

def main():
    root = tk.Tk()
    app = VSubApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()