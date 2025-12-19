# 🚀 Quick Start Guide - VSub TTS Generator v2.0

## First Time Setup

1. **Start the application:**
   ```bash
   python vsub_tts.py
   ```

2. **Prepare your assets:**
   - Put meme images in `assets/memes/`
   - Put sound effects in `assets/sounds/`
   - Background videos go in `assets/background/`

## Basic Workflow

### 1️⃣ Create Script
1. Click **Script & Settings** tab
2. Type or paste your text
3. Click **Parse Text** button
4. Your text is split into sentences with individual words

### 2️⃣ Customize Voices
- **Global Settings**: Voice, Pitch, Rate apply to ALL words
- **Word Settings**: Click any word to customize it individually
- **Templates**: Use or create presets for quick voice changes

### 3️⃣ Add Images (Optional)
1. Go to **Library** tab → **🖼️ Images**
2. Click **➕ Add Images...** or place files in `assets/memes/`
3. Click **🔄 Refresh** if needed
4. Select a word, select an image, click **🖼️ Set Image**
5. Use **⚙️ Config Image** for timing/position/scale

### 4️⃣ Add Sound Effects (Optional) 🆕
1. Go to **Library** tab → **🔊 Sound Effects**
2. Click **➕ Add Audio...** or place files in `assets/sounds/`
3. Click **🔄 Refresh** if needed
4. Select audio and click **▶️ Play** to preview
5. Select a word, select audio, click **🔊 Set Audio**
6. Use **⚙️ Config Audio** for volume/timing/duration

### 5️⃣ Verify Timeline
- Check the **Timeline Properties** section
- 🔊 = Audio effects
- 📷 = Images
- 💬 = Words/Speech
- Scroll horizontally if needed

### 6️⃣ Generate
1. Enter a **Title** for your project
2. Click **Generate Audio (Async)**
3. Wait for completion
4. Files saved in `assets/audio/`:
   - `Title.mp3` - The TTS audio
   - `Title_config.json` - Video generation data
   - `Title.srt` - Subtitles

### 7️⃣ Save Project
- **Ctrl+S** or **File → Save Project**
- Saves all settings, words, images, audio
- Load later with **Ctrl+O** or **File → Open Project**

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | New Project |
| `Ctrl+O` | Open Project |
| `Ctrl+S` | Save Project |
| `Ctrl+Shift+S` | Save As |

## Word Color Guide

| Color | Meaning |
|-------|---------|
| ⚫ Black | Default (no changes) |
| 🔵 Blue | Voice customized (pitch/rate) |
| 🟣 Purple + 📷 | Has image attached |
| 🟢 Green + 🔊 | Has sound effect attached |
| 🟣 Dark Violet + 📷🔊 | Has BOTH image & audio! |

## Common Tasks

### Change Voice for One Word
1. Click the word
2. Select template OR enter Pitch/Rate manually
3. Click **✓ Apply**

### Copy Settings to Multiple Words
1. Save settings as Template (Edit → Manage Templates)
2. Click each word and select that template

### Remove All Media from Word
1. Click the word
2. Click **🗑️ Clear Media**
3. Confirm

### Preview Sound Before Using
1. Go to Library → Sound Effects tab
2. Select audio file
3. Click **▶️ Play** button

### Open Asset Folders Quickly
1. Go to Library tab
2. Click **📂 Open Folder** button
3. Windows Explorer opens that folder

## Tips & Tricks

### 🎯 For Emphasis
- High Pitch + Image + Sound Effect
- Example: "CRAZY!" → pitch +50Hz + shocked-face.png + wow.mp3

### 🎭 For Drama
- Slow Rate + Long Image Duration
- Example: "dramatic pause" → rate -25%, image 2000ms

### 💥 For Action Words
- Normal voice + short punchy sound
- Example: "BOOM" → boom.mp3, duration 800ms, volume 1.0

### 🎶 For Background Ambience
- Long audio + low volume + early start
- Example: sentence start → ambient.mp3, 5000ms, volume 0.3, offset -200ms

### 🎨 For Visual Jokes
- Image at word end for comedic timing
- Config Image → Start Offset: 200ms (appears after word spoken)

### 🔊 For Sound Crescendo
- Audio starts before word, peaks during word
- Config Audio → Start Offset: -500ms, full duration

## Troubleshooting

### "No Voices Available"
- Check internet connection (Edge TTS requires internet)
- Wait a few seconds for voices to load
- Restart application if needed

### "Audio Won't Generate"
- Ensure title is entered
- Check all words have valid settings
- Look at status bar for specific error
- Try parsing text again

### "Can't Find My Files"
- Click **🔄 Refresh** in Library tab
- Check files are in correct folder:
  - Images: `assets/memes/`
  - Audio: `assets/sounds/`
- Check file extensions are supported

### "Sound Won't Play in Preview"
- MP3 and WAV work best on Windows
- Convert other formats to MP3 if issues
- Check file isn't corrupted
- Try different audio file

### "Timeline is Blank"
- Select a sentence from the list on left
- Ensure sentence has words parsed
- Try clicking another sentence then back

## File Formats

### Supported Image Formats
- PNG (recommended for transparency)
- JPG/JPEG
- GIF
- WEBP

### Supported Audio Formats
- MP3 (recommended - best compatibility)
- WAV (uncompressed - larger files)
- OGG
- M4A
- FLAC

### Output Formats
- Audio: MP3
- Config: JSON
- Subtitles: SRT
- Timestamps: JSON, CSV, SRT, VTT (via Export menu)

## Need Help?

1. Check status bar at bottom for messages
2. Look for error dialogs
3. Try Help → About for version info
4. Save your project before experimenting
5. Use Ctrl+N to start fresh if stuck

---

**Remember:** 
- 💾 Save often (Ctrl+S)
- 🎧 Preview audio before generating
- 📊 Check timeline before export
- 🔄 Refresh libraries after adding files

Happy creating! 🎬✨
