# VSub TTS Generator - Enhanced Edition v2.0

## 🎉 What's New in v2.0

### Major UI/UX Improvements

#### 1. **Professional Menu Bar**
- **File Menu**: New Project, Open, Save, Save As, Export Timestamps, Exit
- **Edit Menu**: Quick access to Template Manager
- **View Menu**: Refresh libraries with one click
- **Help Menu**: About dialog with feature overview
- **Keyboard Shortcuts**: 
  - `Ctrl+N` - New Project
  - `Ctrl+O` - Open Project
  - `Ctrl+S` - Save Project
  - `Ctrl+Shift+S` - Save As

#### 2. **Enhanced Library System**
The Library tab now features **organized sub-tabs**:

**🖼️ Images Tab:**
- Visual image preview (200x200 thumbnail)
- Quick action buttons with icons
- "Open Folder" button for easy file management
- Drag-and-drop support for adding images

**🔊 Sound Effects Tab:**
- Audio file browser
- Built-in audio preview/playback with "▶️ Play" button
- File information display (name, size)
- Support for multiple formats: MP3, WAV, OGG, M4A, FLAC
- "Open Folder" for quick access to sound library

#### 3. **Improved Word Settings Panel**
Reorganized into logical sections:

**Voice Settings Row:**
- Word name display
- Template dropdown
- Pitch and Rate controls
- Apply button

**Media Controls Row:**
- 🖼️ Set Image - Apply image from library
- ⚙️ Config Image - Advanced image settings
- 🔊 Set Audio - Apply sound effect from library
- ⚙️ Config Audio - Advanced audio settings
- 🗑️ Clear Media - Remove all media from word

#### 4. **Enhanced Timeline Visualization**
Now displays **3 lanes**:
- **🔊 Audio Lane** - Sound effects timeline (blue blocks)
- **📷 Image Lane** - Image overlays timeline (green blocks)
- **💬 Word Lane** - Text/speech timeline (gray blocks)

Visual improvements:
- Better colors and contrast
- Lane labels with emojis
- Compact file names in timeline
- Scroll support for long content

#### 5. **Visual Word Indicators**
Words now show their status with intuitive colors:
- **Black** - Default word (no customization)
- **Blue** - Voice customized (pitch/rate changed)
- **Purple + 📷** - Has image attached
- **Green + 🔊** - Has audio attached
- **Dark Violet + 📷🔊** - Has both image AND audio!

### 🔊 Sound Effects Audio Feature

Just like images, you can now **pair sound effects with words**!

#### How to Use Sound Effects:

1. **Add Audio Files to Library**
   - Go to Library tab → Sound Effects sub-tab
   - Click "➕ Add Audio..." button
   - Select MP3, WAV, OGG, M4A, or FLAC files
   - Files are copied to `assets/sounds/` folder

2. **Apply Audio to Word**
   - Select a word in the sentence editor
   - Select an audio file from the library
   - Click "🔊 Set Audio" button
   - Audio is now paired with that word!

3. **Customize Audio Settings**
   - Click "⚙️ Config Audio" button
   - **Audio Path**: Browse or select from library
   - **▶️ Play**: Preview the audio file
   - **Duration**: Set how long audio plays (0 = full duration)
   - **Volume**: 0.0 to 1.0 (0% to 100%)
   - **Start Offset**: When audio starts relative to word (-1000ms to +2000ms)

4. **View in Timeline**
   - Audio appears in the 🔊 Audio lane
   - Blue blocks show timing and filename
   - Synced with word timing

#### Audio Configuration Options:

```python
WordSettings:
  audio_path: str              # Path to audio file
  audio_start_ms: int          # Offset from word start (can be negative)
  audio_duration_ms: int       # How long to play (None = full audio)
  audio_volume: float          # Volume 0.0-1.0
```

#### Export Data Structure:

When you generate audio, the JSON config includes audio data:

```json
{
  "sentences": [
    {
      "words": [
        {
          "text": "boom",
          "audio": {
            "path": "assets/sounds/explosion.mp3",
            "start_ms": 0,
            "duration_ms": null,
            "volume": 0.8,
            "absolute_start_ms": 1234
          }
        }
      ]
    }
  ]
}
```

### 🎨 UI/UX Enhancements

#### Better Organization:
- Larger window (1400x850) for comfortable work
- Clear visual hierarchy with labeled sections
- Emoji icons for quick recognition
- Consistent spacing and padding

#### Improved Workflow:
1. **Input** → Parse text into sentences
2. **Edit** → Click words to customize
3. **Media** → Add images/audio from library
4. **Timeline** → Visualize timing
5. **Export** → Generate with File menu

#### Helpful Features:
- Status bar shows current operation
- Clear error messages
- Confirmation dialogs for destructive actions
- Auto-refresh after adding files to library
- Tooltip-like status updates

### 🛠️ Technical Improvements

#### Data Structure Updates:
- `WordSettings` dataclass extended with audio fields
- `AudioLibrary` class for managing sound effects
- Timeline calculation includes audio blocks
- Export includes audio metadata

#### Better Code Organization:
- Menu bar creation separated
- Library management modularized
- Clear function naming conventions
- Comprehensive error handling

### 📁 Project Structure

```
Roblox-Rants/
├── vsub_tts.py              # Main application
├── requirements.txt         # Python dependencies
├── templates.json           # Voice templates
├── assets/
│   ├── audio/              # Generated TTS audio output
│   ├── background/         # Background videos
│   ├── memes/              # Image library
│   └── sounds/             # Sound effects library (NEW!)
```

### 🎯 Usage Examples

#### Example 1: Add Sound Effect to Emphasized Word

1. Parse text: "That was CRAZY!"
2. Select word "CRAZY"
3. In Library → Sound Effects, select "wow.mp3"
4. Click "🔊 Set Audio"
5. The word now has a sound effect synchronized!

#### Example 2: Combine Image + Audio

1. Select word "explosion"
2. Set image: explosion.png (from Image library)
3. Set audio: boom.mp3 (from Sound Effects library)
4. Customize timing if needed
5. Timeline shows both 📷 and 🔊 overlays

#### Example 3: Background Ambient Sound

1. Select first word in sentence
2. Set audio with long duration (5000ms)
3. Set Start Offset to 0ms
4. Set volume to 0.3 (30% for background)
5. Audio plays throughout sentence

### 🔧 Configuration Tips

**For Short Punchy Effects:**
- Duration: 500-1000ms
- Volume: 0.8-1.0
- Start Offset: 0ms

**For Background Ambience:**
- Duration: 2000-5000ms  
- Volume: 0.2-0.4
- Start Offset: -500ms (start before word)

**For Timed Crescendo:**
- Duration: Full audio (0 = use file length)
- Volume: 1.0
- Start Offset: Adjust to sync peak with word

### 📊 Export Format

Generated project config includes:
- TTS audio file path
- Sentence timing data
- Word-level timestamps
- Image overlay data with absolute timing
- Audio effect data with absolute timing
- Volume and duration settings

Video generation tools can parse this JSON to:
1. Play TTS audio track
2. Show image overlays at specified times
3. Mix sound effects with timing and volume
4. Apply all simultaneously to video

### 🎓 Best Practices

1. **Organize Your Assets**
   - Name audio files descriptively (boom.mp3, applause.wav)
   - Keep file sizes reasonable (< 1MB for quick loading)
   - Use consistent format (MP3 recommended)

2. **Test Audio Before Applying**
   - Use "▶️ Play" button to preview
   - Check volume levels match
   - Ensure audio quality is good

3. **Use Timeline for Verification**
   - Check for overlapping audio
   - Verify timing looks correct
   - Adjust durations if needed

4. **Save Projects Frequently**
   - Use Ctrl+S to save
   - Save before generating audio
   - Keep backups of working projects

### 🐛 Troubleshooting

**Audio Won't Play in Preview:**
- Ensure file format is supported by Windows (MP3, WAV work best)
- Check file isn't corrupted
- Try converting to MP3 if having issues

**Audio Not Showing in Library:**
- Click "🔄 Refresh" button
- Check file is in `assets/sounds/` folder
- Ensure file extension is: .mp3, .wav, .ogg, .m4a, or .flac

**Timeline Looks Crowded:**
- Use horizontal scrollbar at bottom
- Shorten audio durations
- Adjust window size

**Lost Your Work:**
- Use File → Open Project to load saved .json
- Check for auto-saved project files
- Always Ctrl+S after major changes

### 🚀 What's Next?

Future improvements could include:
- Audio waveform visualization
- Batch apply audio to multiple words
- Audio fade in/out controls
- Audio playback in timeline preview
- Drag-and-drop audio from library to words
- Audio trimming tool
- Volume envelope editor

---

## Version History

### v2.0 (Current)
- ✨ Added sound effects audio support
- 🎨 Complete UI/UX redesign
- 📋 Professional menu bar with keyboard shortcuts
- 📚 Enhanced library with Image/Audio sub-tabs
- 🎬 3-lane timeline visualization
- 🎨 Color-coded word indicators
- 🖼️ Image preview in library
- 🔊 Audio playback in library
- ⚙️ Advanced configuration dialogs
- 🗑️ Clear media functionality
- 📂 "Open Folder" quick access buttons

### v1.0 (Previous)
- Text-to-Speech generation
- Word-level pitch/rate control
- Image overlay support
- Basic timeline visualization
- Template system
- Project save/load

---

**Made with ❤️ for content creators who want precise control over TTS videos!**
