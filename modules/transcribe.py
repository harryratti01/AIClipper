from faster_whisper import WhisperModel
from config import WHISPER_MODEL
model = WhisperModel(WHISPER_MODEL, device="cuda", compute_type="float16") 
def transcribe_audio(audio_path):
    segments, info = model.transcribe(audio_path, word_timestamps=True)

    results = []

    for segment in segments:
        print(f"{segment.start:.2f} --> {segment.end:.2f} : {segment.text}")

        words = []

        for word in segment.words:
            print(
                f"WORD: {word.start:.2f} --> " 
                f"{word.end:.2f} : {word.word}"
            )
            words.append({
                "start": word.start,
                "end": word.end,
                "word": word.word
            })

        results.append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text,
            "words": words
        })

    return results

