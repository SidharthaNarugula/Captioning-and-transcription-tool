from flask import Flask, request, jsonify, send_file, render_template, session
import os
import uuid
import requests
import time
import json
import traceback
from google.cloud import translate_v2 as translate
import pysrt
import assemblyai as aai
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
aai.settings.api_key = ASSEMBLYAI_API_KEY

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or os.urandom(24)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour session timeout

# Store transcription data in memory as backup (in case session fails)
transcription_store = {}

# Ensure upload and transcription directories exist
UPLOAD_FOLDER = 'uploads'
TRANSCRIPTION_FOLDER = 'transcriptions'
CAPTIONS_FOLDER = 'captions'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(TRANSCRIPTION_FOLDER):
    os.makedirs(TRANSCRIPTION_FOLDER)
if not os.path.exists(CAPTIONS_FOLDER):
    os.makedirs(CAPTIONS_FOLDER)

ALLOWED_EXTENSIONS = {'mp3', 'wav', 'mp4', 'm4a', 'flac'}

ASSEMBLYAI_UPLOAD_URL = "https://api.assemblyai.com/v2/upload"
ASSEMBLYAI_TRANSCRIPT_URL = "https://api.assemblyai.com/v2/transcript"

# Google Cloud Translation config - path loaded from .env
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
if GOOGLE_APPLICATION_CREDENTIALS:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        # Check if a file was uploaded
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        
        if not allowed_file(file.filename):
            return jsonify({"error": f"Invalid file format. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}"}), 400
        
        # Generate a unique filename to avoid overwriting
        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        print(f"Saving file to: {file_path}")
        file.save(file_path)
        
        # Store file info in session
        session['uploaded_file'] = {
            'original_name': file.filename,
            'path': file_path,
            'unique_filename': unique_filename
        }
        session['is_file_uploaded'] = True
        session['uploaded_filename'] = unique_filename
        
        # Check if the file exists
        if not os.path.exists(file_path):
            return jsonify({"error": f"File not found at path: {file_path}"}), 500
        
        # Get the target language from the form data
        target_language = request.form.get('language', 'en')
        valid_languages = ['en', 'es', 'fr', 'de', 'hi', 'te', 'kn', 'ta']
        
        if target_language not in valid_languages:
            return jsonify({"error": f"Unsupported target language: {target_language}"}), 400
        
        print(f"Selected target language: {target_language}")
        
        # Upload file to AssemblyAI and get transcription
        transcription_data = transcribe_audio_with_assemblyai(file_path)
        
        # Extract text and words data
        transcription = transcription_data['text']
        words_data = transcription_data.get('words', [])
        
        # Save original transcription before translation
        session['original_transcription'] = transcription
        session['words_data'] = words_data  # Store word timing data
        
        # Also store in backup dictionary with session ID as key
        session_id = str(uuid.uuid4())
        session['session_id'] = session_id
        transcription_store[session_id] = {
            'transcription': transcription,
            'words_data': words_data,
            'uploaded_filename': unique_filename
        }
        print(f"Original transcription saved in session: {transcription[:50]}...")
        print(f"Session ID: {session_id}")
        
        # Translate if the target language is not English
        if target_language != 'en':
            print(f"Translating to: {target_language}")
            transcription = translate_text(transcription, target_language)
        
        # Save the transcription to a text file
        output_file = os.path.join(TRANSCRIPTION_FOLDER, f"{os.path.splitext(unique_filename)[0]}.txt")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(transcription)
        print(f"Transcription saved to file: {output_file}")
        
        # Store the output file path in session
        session['output_file'] = output_file
        session['current_language'] = target_language
        session.modified = True  # Ensure session is saved
        
        return jsonify({
            "message": "Transcription complete",
            "transcription": transcription,
            "file": os.path.basename(output_file),
            "original_file": file.filename,
            "current_language": target_language,
            "words_data": words_data,  # Send words data to client
            "session_id": session.get('session_id', '')  # Send session ID
        })
    
    except Exception as e:
        print(f"Error during transcription: {e}")
        traceback.print_exc()
        return jsonify({"error": f"Error during transcription: {str(e)}"}), 500

def transcribe_audio_with_assemblyai(file_path):
    """Transcribe audio using AssemblyAI API"""
    if not ASSEMBLYAI_API_KEY:
        raise ValueError("AssemblyAI API key is not set. Please set the ASSEMBLYAI_API_KEY environment variable.")
    
    headers = {
        "authorization": ASSEMBLYAI_API_KEY
    }
    
    # Step 1: Upload the file to AssemblyAI
    print(f"Uploading file to AssemblyAI: {file_path}")
    with open(file_path, "rb") as f:
        response = requests.post(
            ASSEMBLYAI_UPLOAD_URL,
            headers=headers,
            data=f
        )
    
    if response.status_code != 200:
        raise Exception(f"Error uploading file: {response.text}")
    
    upload_url = response.json()["upload_url"]
    print(f"File uploaded successfully. URL: {upload_url}")
    
    # Step 2: Submit the transcription request with word timing enabled
    transcript_request = {
        "audio_url": upload_url
    }
    
    response = requests.post(
        ASSEMBLYAI_TRANSCRIPT_URL,
        json=transcript_request,
        headers=headers
    )
    
    if response.status_code != 200:
        raise Exception(f"Error submitting transcription request: {response.text}")
    
    transcript_id = response.json()["id"]
    print(f"Transcription job submitted. ID: {transcript_id}")
    
    # Step 3: Poll for the transcription result
    polling_endpoint = f"{ASSEMBLYAI_TRANSCRIPT_URL}/{transcript_id}"
    while True:
        response = requests.get(polling_endpoint, headers=headers)
        transcript = response.json()
        
        if transcript["status"] == "completed":
            print("Transcription completed successfully")
            print(f"Transcript keys: {list(transcript.keys())}")
            
            words = transcript.get("words", [])
            if words:
                print(f"Found {len(words)} words with timing data")
            else:
                print("No words data in transcript response")
            
            return {
                "text": transcript.get("text", ""),
                "words": words
            }
        elif transcript["status"] == "error":
            raise Exception(f"Transcription error: {transcript.get('error', 'Unknown error')}")
        else:
            print(f"Transcription in progress... Status: {transcript['status']}")
            time.sleep(5)  # Wait for 5 seconds before polling again

def generate_srt_captions(words_data, max_chars_per_line=42):
    """Generate SRT format captions from word timing data"""
    if not words_data:
        return None
    
    subtitles = pysrt.SubRipFile()
    current_line = ""
    current_start = None
    current_end = None
    index = 1
    
    for word_info in words_data:
        word = word_info.get('text', '')
        start_ms = word_info.get('start')
        end_ms = word_info.get('end')
        
        if start_ms is None or end_ms is None:
            continue
        
        # Convert milliseconds to timedelta
        start_time = timedelta(milliseconds=start_ms)
        end_time = timedelta(milliseconds=end_ms)
        
        # Initialize start time for the first word in a subtitle block
        if current_start is None:
            current_start = start_time
        
        # Add word to current line
        if current_line:
            test_line = f"{current_line} {word}"
        else:
            test_line = word
        
        # If adding the word exceeds max chars, create a new subtitle
        if len(test_line) > max_chars_per_line and current_line:
            subtitle = pysrt.SubRipItem()
            subtitle.index = index
            subtitle.start = current_start
            subtitle.end = current_end
            subtitle.text = current_line
            subtitles.append(subtitle)
            
            # Start new subtitle block
            current_line = word
            current_start = start_time
            index += 1
        else:
            current_line = test_line
        
        current_end = end_time
    
    # Add the last subtitle block
    if current_line:
        subtitle = pysrt.SubRipItem()
        subtitle.index = index
        subtitle.start = current_start
        subtitle.end = current_end
        subtitle.text = current_line
        subtitles.append(subtitle)
    
    return subtitles

def generate_srt_from_text(text, duration_ms=None):
    """Generate basic SRT captions from text by splitting into lines"""
    if not text or not isinstance(text, str):
        print(f"Warning: Invalid text for caption generation: {type(text)}")
        return None
    
    subtitles = pysrt.SubRipFile()
    words = text.split()
    
    if not words:
        print("Warning: No words found in text")
        return subtitles
    
    # Estimate word duration if total duration is provided
    if duration_ms and len(words) > 0:
        word_duration_ms = duration_ms / len(words)
    else:
        word_duration_ms = 2000  # Default 2 seconds per subtitle block
    
    current_line = ""
    current_start_ms = 0
    index = 1
    max_chars_per_line = 42
    
    for i, word in enumerate(words):
        if current_line:
            test_line = f"{current_line} {word}"
        else:
            test_line = word
        
        # Check if we need to start a new subtitle block
        if len(test_line) > max_chars_per_line and current_line:
            # Calculate subtitle duration based on number of words in the block
            word_count = len(current_line.split())
            duration_for_block = word_count * (word_duration_ms / max(1, len(words)))
            
            # Create subtitle
            subtitle = pysrt.SubRipItem()
            subtitle.index = index
            subtitle.start = timedelta(milliseconds=current_start_ms)
            subtitle.end = timedelta(milliseconds=current_start_ms + max(duration_for_block, 1000))
            subtitle.text = current_line
            subtitles.append(subtitle)
            
            current_start_ms = current_start_ms + max(duration_for_block, 1000)
            current_line = word
            index += 1
        else:
            current_line = test_line
    
    # Add last subtitle
    if current_line:
        word_count = len(current_line.split())
        duration_for_block = word_count * (word_duration_ms / max(1, len(words)))
        
        subtitle = pysrt.SubRipItem()
        subtitle.index = index
        subtitle.start = timedelta(milliseconds=current_start_ms)
        subtitle.end = timedelta(milliseconds=current_start_ms + max(duration_for_block, 1000))
        subtitle.text = current_line
        subtitles.append(subtitle)
    
    print(f"Generated {len(subtitles)} subtitle items from text")
    return subtitles

@app.route('/generate-captions', methods=['POST'])
def generate_captions():
    """Generate SRT caption file from transcription"""
    try:
        # Get data from POST request body
        data = request.get_json()
        
        transcription = data.get('transcription') if data else None
        words_data = data.get('words_data', []) if data else []
        filename = data.get('filename', 'captions') if data else 'captions'
        
        print(f"Caption generation requested.")
        print(f"Transcription received: {len(transcription) if transcription else 0} chars")
        print(f"Words data: {len(words_data)} items")
        print(f"Filename: {filename}")
        
        if not transcription:
            print("Error: No transcription data received")
            return jsonify({"error": "No transcription available. Please transcribe a file first."}), 400
        
        subtitles = None
        
        # Try to use word-level timing data first
        if words_data and len(words_data) > 0:
            print(f"Attempting caption generation with {len(words_data)} words")
            subtitles = generate_srt_captions(words_data)
            if subtitles and len(subtitles) > 0:
                print(f"Successfully generated captions from word-level data: {len(subtitles)} items")
        
        # Fallback to text-based caption generation
        if not subtitles or len(subtitles) == 0:
            print("Using fallback text-based caption generation")
            print(f"Generating captions from text ({len(transcription)} characters)")
            subtitles = generate_srt_from_text(transcription)
            
            if subtitles and len(subtitles) > 0:
                print(f"Successfully generated captions from text: {len(subtitles)} items")
        
        if not subtitles or len(subtitles) == 0:
            print("Error: Failed to generate any captions")
            return jsonify({"error": "Failed to generate captions - no valid subtitle data"}), 500
        
        # Save the SRT file
        srt_filename = f"{os.path.splitext(filename)[0]}.srt"
        srt_path = os.path.join(CAPTIONS_FOLDER, srt_filename)
        print(f"Saving captions to: {srt_path}")
        subtitles.save(srt_path, encoding='utf-8')
        
        # Store caption file path in session so /download-captions can serve it
        session['caption_file'] = srt_path
        session.modified = True
        
        # Convert subtitles to JSON for display
        captions_json = []
        for subtitle in subtitles:
            captions_json.append({
                "index": subtitle.index,
                "start": str(subtitle.start),
                "end": str(subtitle.end),
                "text": subtitle.text
            })
        
        print(f"Generated {len(captions_json)} caption blocks successfully")
        
        return jsonify({
            "message": "Captions generated successfully",
            "file": srt_filename,
            "count": len(captions_json),
            "captions": captions_json
        })
        
    except Exception as e:
        print(f"Error generating captions: {e}")
        traceback.print_exc()
        return jsonify({"error": f"Error generating captions: {str(e)}"}), 500

@app.route('/download-captions', methods=['GET'])
def download_captions():
    """Download the generated caption file"""
    try:
        if 'caption_file' not in session:
            return jsonify({"error": "No caption file available"}), 400
        
        caption_path = session['caption_file']
        
        if not os.path.exists(caption_path):
            return jsonify({"error": "Caption file not found"}), 404
        
        return send_file(caption_path, as_attachment=True, download_name=os.path.basename(caption_path))
        
    except Exception as e:
        print(f"Error downloading captions: {e}")
        return jsonify({"error": f"Error downloading captions: {str(e)}"}), 500

@app.route('/translate', methods=['POST'])
def translate_transcription():
    try:
        # Try session first, then fall back to in-memory store
        if 'original_transcription' not in session:
            session_id = session.get('session_id')
            if session_id and session_id in transcription_store:
                store = transcription_store[session_id]
                session['original_transcription'] = store['transcription']
                session['words_data'] = store['words_data']
                print(f"Restored transcription from in-memory store for session: {session_id}")
            else:
                return jsonify({"error": "No transcription available to translate"}), 400
            
        # Get the target language from the form data
        target_language = request.form.get('language')
        if not target_language:
            return jsonify({"error": "No target language specified"}), 400
            
        valid_languages = ['en', 'es', 'fr', 'de', 'hi', 'te', 'kn', 'ta']
        if target_language not in valid_languages:
            return jsonify({"error": f"Unsupported target language: {target_language}"}), 400
            
        # Get the original transcription from session
        transcription = session['original_transcription']
        
        # Translate the text
        if target_language != 'en':
            translated_text = translate_text(transcription, target_language)
        else:
            translated_text = transcription
            
        # Update the output file with the new translation
        if 'output_file' in session:
            with open(session['output_file'], 'w', encoding='utf-8') as f:
                f.write(translated_text)
                
        # Update current language in session
        session['current_language'] = target_language
        
        return jsonify({
            "message": "Translation complete",
            "transcription": translated_text,
            "file": os.path.basename(session['output_file']),
            "original_file": session['uploaded_file']['original_name'],
            "current_language": target_language
        })
        
    except Exception as e:
        print(f"Error during translation: {e}")
        traceback.print_exc()
        return jsonify({"error": f"Error during translation: {str(e)}"}), 500

def translate_text(text, target_language):
    """Translate text using Google Cloud Translation API"""
    try:
        print(f"Translating text: {text[:50]}... to {target_language}")
        
        # Create a translation client
        translate_client = translate.Client()
        
        # Perform the translation
        result = translate_client.translate(
            text,
            target_language=target_language
        )
        
        print(f"Translation successful")
        return result['translatedText']
        
    except Exception as e:
        print(f"Translation failed: {e}")
        traceback.print_exc()
        return text  # Return original text if translation fails

@app.route('/current-file', methods=['GET'])
def get_current_file():
    """Return information about the currently uploaded file and its transcription"""
    if 'uploaded_file' in session and 'output_file' in session:
        # Read the current transcription file
        try:
            with open(session['output_file'], 'r', encoding='utf-8') as f:
                transcription = f.read()
                
            return jsonify({
                "original_file": session['uploaded_file']['original_name'],
                "current_language": session.get('current_language', 'en'),
                "has_transcription": True,
                "transcription": transcription
            })
        except Exception as e:
            print(f"Error reading transcription file: {e}")
            # If we can't read the file, return the basic info without transcription
            return jsonify({
                "original_file": session['uploaded_file']['original_name'],
                "current_language": session.get('current_language', 'en'),
                "has_transcription": True
            })
    return jsonify({"has_transcription": False})

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    path = os.path.join(TRANSCRIPTION_FOLDER, filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    else:
        return jsonify({"error": "File not found"}), 404

@app.route('/clear', methods=['POST'])
def clear_session():
    """Clear the session data to start fresh"""
    session.clear()
    return jsonify({"message": "Session cleared successfully"})

if __name__ == '__main__':
    app.run(debug=True, port=5001)