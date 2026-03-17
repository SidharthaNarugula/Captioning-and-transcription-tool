# AI Captioning and Transcription Tool

A Flask web application that transcribes audio and video files using the AssemblyAI API, supports translation into multiple languages via Google Cloud Translation, and generates downloadable SRT caption files with word-level timing.

---

## Key Features

- **Audio/Video Transcription** — Uploads files to AssemblyAI and polls for the completed transcript. Returns full text and word-level timing data.
- **Word-Level Timestamped Display** — Groups transcribed words into timed chunks and renders them in the browser with timestamps.
- **Multi-Language Translation** — Translates the original English transcription into Spanish, French, German, Hindi, Telugu, Kannada, or Tamil using Google Cloud Translation API v2.
- **SRT Caption Generation** — Builds `.srt` subtitle files from word-level timing data when available, with a text-based fallback when timing data is absent.
- **Caption and Transcription Download** — Users can download the plain transcription (`.txt`), timestamped transcription (`.txt`), or caption file (`.srt`) directly from the browser.
- **Session Persistence** — Uploaded file metadata and transcription are stored in the Flask session, with an in-memory dictionary as a fallback for session loss within the same server process.
- **Session Reset** — A clear button wipes session state and resets the UI for a fresh upload.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask 3.1 |
| Transcription | AssemblyAI REST API (v2) |
| Translation | Google Cloud Translation API v2 (`google-cloud-translate`) |
| Caption Parsing | pysrt |
| Frontend | Vanilla HTML, CSS, JavaScript (no framework) |
| Environment Config | python-dotenv |
| Session Storage | Flask cookie-based session (filesystem session type configured but requires `flask-session`) |

---

## Project Structure

```
DesignThinkProject/
├── app.py                  # Flask application: routes, transcription, translation, caption logic
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (not committed)
├── templates/
│   └── index.html          # Single-page UI template
├── static/
│   ├── script.js           # All client-side logic (upload, translate, download, captions)
│   └── styles.css          # Application styles
├── uploads/                # Temporarily stores uploaded audio/video files
├── transcriptions/         # Stores transcription output as .txt files
└── captions/               # Stores generated .srt caption files
```

---

## How It Works

1. **Upload** — The user selects an audio or video file (`.mp3`, `.wav`, `.mp4`, `.m4a`, `.flac`) and a target language, then clicks "Start Transcription".
2. **Transcription** — The file is uploaded to AssemblyAI's API. The server polls the transcript endpoint every 5 seconds until the status is `completed`. The response includes full text and per-word start/end timestamps in milliseconds.
3. **Translation** — If the selected language is not English, the full transcript text is passed to Google Cloud Translation API and the translated result is returned to the client.
4. **Display** — The transcription text is shown in the UI. If word-level timing data is available, a second panel renders the transcript grouped into 8-word chunks with timestamps.
5. **Caption Generation** — Clicking "Generate Captions (SRT)" sends the transcription text and word timing data to `/generate-captions`. The server builds an `.srt` file using word timing (falling back to estimated timing if unavailable) and saves it to the `captions/` folder.
6. **Download** — The user can download the transcription as plain text, timestamped text, or the generated `.srt` file.
7. **Re-translate** — After transcription, the user can switch language and click "Change Language" to re-translate the original English transcript without re-uploading the file.

---

## Setup Instructions

### Prerequisites

- Python 3.9 or later
- A valid [AssemblyAI API key](https://www.assemblyai.com/)
- A Google Cloud project with the Translation API enabled and a service account JSON key file

### Installation

```bash
# Clone the repository
git clone https://github.com/SidharthaNarugula/Captioning-and-transcription-tool.git
cd Captioning-and-transcription-tool

# Create and activate a virtual environment
python -m venv env
# Windows
env\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Environment Configuration

Create a `.env` file in the project root with the following:

```ini
ASSEMBLYAI_API_KEY=your_assemblyai_api_key_here
GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\your\google-credentials.json
```

### Run the Application

```bash
python app.py
```

The server starts on `http://localhost:5001`.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ASSEMBLYAI_API_KEY` | Yes | API key for AssemblyAI transcription service |
| `GOOGLE_APPLICATION_CREDENTIALS` | Yes (for translation) | Absolute path to the Google Cloud service account JSON key file |
| `SECRET_KEY` | No | Flask session secret key. Falls back to a random value per process if not set |

---

## Usage

1. Open `http://localhost:5001` in a browser.
2. Click the file input and select an audio or video file.
3. Choose a target language from the dropdown (default: English).
4. Click **Start Transcription** and wait for the result.
5. The transcription appears in the main panel. If word timing data is available, a timestamped view appears below it.
6. To translate to a different language, select it from the dropdown and click **Change Language**.
7. Click **Download Transcription (.txt)** to save plain text.
8. Click **Download Timestamped Transcription (.txt)** for the timed version.
9. Click **Generate Captions (SRT)** to create an `.srt` file, then **Download Captions** to save it.
10. Click **Clear** to reset everything and start over.

---

## Limitations

- **No persistent storage** — Transcription data is held in the Flask session (cookie-based). Restarting the server clears all session data. The in-memory fallback (`transcription_store`) is also lost on restart.
- **Single user per session** — The application is not designed for concurrent multi-user use. Each session is independent but there is no user authentication or account system.
- **English-only transcription** — AssemblyAI is called without a `language_code` parameter, so transcription defaults to English. Translation is applied as a post-processing step.
- **No video file handling** — Video files (`.mp4`) are uploaded and sent directly to AssemblyAI, which extracts audio server-side. No local video processing is done.
- **Session size risk** — Word-level timing data for long recordings stored in the Flask cookie session may exceed the 4KB cookie limit, causing silent data loss. `flask-session` is listed as a dependency but filesystem session storage is not fully initialized in `app.py`.
- **Polling-based transcription** — The `/upload` route blocks until transcription completes (polling every 5 seconds). For long files this can cause request timeouts on some hosting environments.
- **Translation only on full text** — When the language is changed, word-level timing data is not re-translated. The timestamped display is not updated after a language change.

---

## Potential Improvements

- Replace blocking transcription polling with a webhook or background task (e.g., Celery) to avoid request timeouts on long files.
- Fully configure `flask-session` with filesystem or Redis backend to handle large word-timing payloads safely.
- Add `language_code` to the AssemblyAI request to support non-English source audio.
- Persist uploaded file references and transcription results to a database rather than session cookies.
- Re-apply word-level timing offsets after translation so the timestamped view stays accurate when the language is changed.
- Add input validation and file size limits on the upload endpoint.
