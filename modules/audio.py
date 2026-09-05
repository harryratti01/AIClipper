import ffmpeg
import imageio_ffmpeg


def extract_audio(video_path, audio_path):
    """
    Extract audio from a video file.
    """

    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

    (
        ffmpeg
        .input(str(video_path))
        .output(str(audio_path))
        .run(
            cmd=ffmpeg_path,
            overwrite_output=True
        )
    )