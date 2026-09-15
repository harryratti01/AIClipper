# AIClipper 🎬

AIClipper is a Python-based AI video highlight extraction tool designed to automatically find engaging moments in long-form videos and turn them into short-form vertical clips.

> 🚧 **Work in Progress**
>
> AIClipper is currently under active development. The core V2 pipeline is functional, but the project is not yet production-ready.

## What It Does

AIClipper analyzes a video's audio and transcript to identify potentially engaging sections. It scores candidate segments using multiple signals and selects the strongest highlight before rendering it as a vertical video.

## Current Pipeline

Video → Audio Extraction → Whisper Transcription → Candidate Generation → Highlight Scoring → Top-10 Shortlist → Sentence Boundary Adjustment → Re-scoring → Best Highlight → 9:16 Rendering

## Current Features

- Audio extraction from video
- AI transcription using Whisper
- Timestamp-based transcript processing
- 30-second overlapping candidate windows
- Top-10 candidate shortlisting
- Sentence-boundary adjustment
- Post-adjustment re-scoring
- Hook scoring
- Question scoring
- Emotion scoring
- Curiosity scoring
- Engagement scoring
- Numbers scoring
- Automatic best-highlight selection
- 9:16 vertical video rendering
- 1080×1920 output
- H.264 video with AAC audio
- Local FFmpeg processing
- End-to-end automated pipeline

## Technology

- Python
- faster-whisper
- FFmpeg
- PyTorch
- CUDA
- NVIDIA GPU acceleration

## Project Structure

AIClipper/
├── modules/
│   ├── audio.py
│   ├── highlights.py
│   ├── subtitles.py
│   ├── transcribe.py
│   ├── utils.py
│   └── video_renderer.py
├── app.py
├── config.py
└── .gitignore

## Current Status

**Version: V2 — Work in Progress**

The core pipeline is functional and has been tested end-to-end.

Remaining V2 work:

- Improve final video rendering quality
- Test across different types of videos
- Final reliability and code cleanup

## Future Plans — V3

Planned improvements include:

- Better semantic curiosity detection
- Improved interaction between scoring signals
- Smart auto-cropping
- Face tracking
- Animated captions
- Dynamic zoom effects
- Better multiple-speaker handling
- Improved highlight ranking

## Important Note

AIClipper is currently a learning and development project. Its scoring system is still largely based on engineered signals and is being improved toward stronger semantic understanding.

The goal is not simply to detect keywords, but to progressively build a system that can identify moments that are genuinely worth turning into short-form content.

## Author

**Harry Sharma**

AIClipper is being developed as a personal AI/software project focused on AI video processing, speech analysis, content ranking, and automated video generation.
