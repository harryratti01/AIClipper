print("=" * 40)
print("        AIClipper v2.0")
print("=" * 40)
print()

from pathlib import Path

from modules.audio import extract_audio
from modules.transcribe import transcribe_audio
from modules.highlights import find_highlights
from modules.video_renderer import render_clip


VIDEO_PATH = Path("input/bill gates test3.mp4")
AUDIO_PATH = Path("temp/audio.wav")
OUTPUT_PATH = Path("output") / f"{VIDEO_PATH.stem}-result.mp4"


def main():

    print("📂 Loading video...")

    print("🎤 Extracting audio...")
    extract_audio(VIDEO_PATH, AUDIO_PATH)
    print("✅ Audio extracted.\n")

    print("🧠 Transcribing audio...")
    transcript = transcribe_audio(AUDIO_PATH)
    print(f"✅ {len(transcript)} transcript segments generated.\n")

    print("🎬 Finding best highlight...")
    best_highlight = find_highlights(transcript)
    print("✅ Best highlight selected.\n")

    print("✂️ Creating highlight clip...")
    render_clip(
        VIDEO_PATH,
        OUTPUT_PATH,
        best_highlight["start"],
        best_highlight["end"],
    )

    print("✅ Highlight saved!")
    print("\n🎉 AIClipper finished successfully!")


if __name__ == "__main__":
    main()