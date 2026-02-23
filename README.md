# video2slides

Extracts unique slides from YouTube videos and bundles them into a PDF. Also pulls subtitles and groups them by slide so you get captions for each one.

We built this because we wanted to make reviewing our online lecture easier and more efficient. Instead of taking screenshots now we can automate it via this app.
## How it works

1. Downloads the video from YouTube using `yt-dlp`
2. Extracts frames at a set interval using `ffmpeg`
3. Compares consecutive frames using SSIM (structural similarity) to detect slide changes
4. Saves only the unique frames — skips duplicates
5. Stitches the frames into a PDF with `img2pdf`
6. Fetches subtitles via `youtube-transcript-api` and groups them by slide timestamp

The result is a folder under `static/<video_id>/` containing:
- Individual frame PNGs (`frame_1.png`, `frame_2.png`, ...)
- `output.pdf` — all slides in one PDF
- `subtitle_groups.json` — captions mapped to each slide

## Setup

You'll need Python 3.10+ and a couple of external tools installed on your system:

- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [ffmpeg](https://ffmpeg.org/) (includes ffprobe)

Then:

```bash
python -m venv env
source env/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root with:

```
X_COMPLETION_HEADER=your_completion_auth_token
X_COMPILE_REQUEST_HEADER=your_compile_auth_token
GEMINI_API_KEY=your_google_genai_key
```

The `X_COMPILE_REQUEST_HEADER` is used to gate the `/compile` endpoint. The `X_COMPLETION_HEADER` is sent when notifying an external service that processing is done.

## Running

```bash
python app.py
```

Starts the Flask + SocketIO server on port 5000.

## API

### REST

**POST `/compile`**

Kicks off slide extraction in the background. Requires the `X-Compile-Request-Header` header to match what's in your `.env`.

Request body (JSON):

```json
{
  "video_path": "https://www.youtube.com/watch?v=...",
  "interval": 10,
  "threshold": 0.95,
  "video_id": "optional-server-side-id"
}
```

- `video_path` — YouTube URL (required)
- `interval` — seconds between frame captures (default: 5)
- `threshold` — SSIM similarity threshold, higher means stricter duplicate detection (default: 0.95)
- `video_id` — optional identifier; if provided, the server sends a POST to the completion endpoint when done

Returns immediately with `{"message": "process begun"}`.

### WebSocket

Connect via Socket.IO and emit a `compute_task` event:

```json
{
  "video_path": "https://www.youtube.com/watch?v=...",
  "interval": 10,
  "threshold": 0.95
}
```

You'll get real-time events back:
- `status` — processing started
- `processing_complete` — includes `video_id`, `pdf_path`, `frames_count`
- `processing_error` — something went wrong

## Testing

There's a basic test client in `test_app.py`. Make sure the server is running first, then:

```bash
python test_app.py
```

It hits the `/compile` endpoint with a sample video. There's also a websocket test you can uncomment if you want to try that path.

## Project structure

```
app.py              — main Flask app, all the processing logic
test_app.py         — simple test client
requirements.txt    — pip dependencies
static/             — output directory (frames, PDFs, subtitle JSON)
archive/main.py     — older standalone version (no server, just CLI-ish)
```

## Notes

- Long videos take a while since it has to download the whole thing and process every Nth frame. A 1-hour lecture with `interval=10` means ~360 frames to compare.
- The threshold parameter matters a lot. 0.95 works well for clean slide transitions. If the video has animations or webcam overlays, you might want to lower it to ~0.85.
- Downloaded videos are cached in `static/videos/` so re-processing the same video is faster.
- The subtitle grouping isn't perfect — it depends on YouTube having captions available for that video.
