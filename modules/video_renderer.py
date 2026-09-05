import ffmpeg
import imageio_ffmpeg


def render_clip(video_path, output_path, start, end):
    """
    Render a high-quality vertical (9:16) highlight clip.
    """

    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

    input_stream = ffmpeg.input(
        str(video_path),
        ss=start,
        to=end
    )

    # Process only the video stream
    video = (
        input_stream.video
        .filter(
            "crop",
            "ih*9/16",
            "ih",
            "(iw-ih*9/16)/2",
            0
        )
        .filter(
            "scale",
            1080,
            1920
        )
    )

    # Keep the original audio
    audio = input_stream.audio

    (
        ffmpeg
        .output(
            video,
            audio,
            str(output_path),
            vcodec="libx264",
            acodec="aac",
            audio_bitrate="192k",
            preset="slow",
            crf=18,
            movflags="+faststart"
        )
        .overwrite_output()
        .run(
            cmd=ffmpeg_path,
            overwrite_output=True
        )
    )