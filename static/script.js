// Global state to track current file and transcription
let currentFileInfo = null;
let currentTranscriptionData = null;  // Store transcription and words data

// Function to format milliseconds to MM:SS
function formatTime(milliseconds) {
    const totalSeconds = Math.floor(milliseconds / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

// Function to display timestamped transcription with word-level timing
function displayTimestampedTranscription(wordsData) {
    const container = document.getElementById('timestamps-container');
    const section = document.getElementById('timestamped-transcription');
    
    if (!wordsData || wordsData.length === 0) {
        section.style.display = 'none';
        return;
    }
    
    // Group words into chunks by time (e.g., every 5-10 words or by sentence)
    let chunks = [];
    let currentChunk = {
        text: [],
        start: null,
        end: null
    };
    
    const wordsPerChunk = 8; // Group approximately 8 words per timestamp
    
    for (let i = 0; i < wordsData.length; i++) {
        const wordData = wordsData[i];
        
        if (!wordData.text) continue;
        
        // Initialize chunk start time
        if (currentChunk.start === null && wordData.start !== null) {
            currentChunk.start = wordData.start;
        }
        
        currentChunk.text.push(wordData.text);
        currentChunk.end = wordData.end;
        
        // Check if we should end this chunk
        const isLastWord = i === wordsData.length - 1;
        const chunkFull = currentChunk.text.length >= wordsPerChunk;
        const isPunctuation = wordData.text.match(/[.!?]$/);
        
        if (chunkFull || isPunctuation || isLastWord) {
            if (currentChunk.text.length > 0) {
                chunks.push({
                    text: currentChunk.text.join(' '),
                    start: currentChunk.start,
                    end: currentChunk.end
                });
            }
            currentChunk = {
                text: [],
                start: null,
                end: null
            };
        }
    }
    
    // Build HTML for timestamped transcription
    let html = '';
    chunks.forEach((chunk, index) => {
        const startTime = formatTime(chunk.start || 0);
        const endTime = formatTime(chunk.end || 0);
        html += `<div style="margin-bottom: 12px; padding: 8px; background: white; border-radius: 4px;">
                    <span style="color: #007bff; font-weight: bold; margin-right: 12px;">[${startTime}]</span>
                    <span>${chunk.text}</span>
                </div>`;
    });
    
    container.innerHTML = html;
    section.style.display = 'block';
    
    console.log(`Displayed ${chunks.length} timestamped chunks`);
}

// Check for existing file and transcription when page loads
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const response = await fetch('/current-file', {
            credentials: 'include'  // Include cookies/session
        });
        const data = await response.json();
        
        if (data.has_transcription) {
            currentFileInfo = data;
            document.getElementById('file-status').textContent = `Current file: ${data.original_file}`;
            document.getElementById('language-select').value = data.current_language;
            document.getElementById('transcribe-container').style.display = 'none';
            document.getElementById('translate-container').style.display = 'block';
            document.getElementById('download-section').style.display = 'block';
            document.getElementById('clear-button').style.display = 'inline-block';
            
            // Fetch and display the current transcription
            await fetchCurrentTranscription();
        }
    } catch (error) {
        console.error('Error checking for existing file:', error);
    }
});

// Fetch the current transcription for display
async function fetchCurrentTranscription() {
    try {
        const response = await fetch('/current-file', { credentials: 'include' });
        const data = await response.json();

        if (data.has_transcription && data.transcription) {
            document.getElementById('transcription-output').innerHTML =
                `<p>${data.transcription}</p>`;

            // Restore words/timestamped data if available
            if (data.words_data && data.words_data.length > 0) {
                currentTranscriptionData = {
                    transcription: data.transcription,
                    words_data: data.words_data,
                    filename: data.original_file || 'captions'
                };
                displayTimestampedTranscription(data.words_data);
            } else {
                // Store transcription even if no words data
                currentTranscriptionData = {
                    transcription: data.transcription,
                    words_data: [],
                    filename: data.original_file || 'captions'
                };
                document.getElementById('transcription-output').innerHTML =
                    `<p>${data.transcription}</p>`;
            }
        } else {
            document.getElementById('transcription-output').innerHTML =
                '<p>Previous transcription available. Use the translate button to switch languages or clear to start over.</p>';
        }
    } catch (error) {
        console.error('Error fetching transcription:', error);
        document.getElementById('transcription-output').innerHTML =
            '<p>Could not load previous transcription.</p>';
    }
}

// Handle file selection
document.getElementById('file-upload').addEventListener('change', (event) => {
    if (event.target.files.length) {
        const fileName = event.target.files[0].name;
        document.getElementById('file-status').textContent = `Selected file: ${fileName}`;
        document.getElementById('transcribe-button').disabled = false;
    } else {
        document.getElementById('file-status').textContent = 'No file selected';
        document.getElementById('transcribe-button').disabled = true;
    }
});

// Handle transcription
document.getElementById('transcribe-button').addEventListener('click', async () => {
    const fileInput = document.getElementById('file-upload');
    const languageSelect = document.getElementById('language-select');
    const transcriptionOutput = document.getElementById('transcription-output');
    const statusElement = document.getElementById('status-message');

    // Check if a file is selected
    if (!fileInput.files.length) {
        alert('Please select a file to upload.');
        return;
    }

    const file = fileInput.files[0];
    const language = languageSelect.value;

    // Create FormData to send the file and language
    const formData = new FormData();
    formData.append('file', file);
    formData.append('language', language);

    // Update UI to show processing state
    statusElement.textContent = 'Processing... This may take a moment.';
    statusElement.style.display = 'block';
    document.getElementById('transcribe-button').disabled = true;

    // Send the file to the backend
    try {
        // First, clear any existing session data to ensure fresh start
        await fetch('/clear', { method: 'POST' });
        
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData,
            credentials: 'include'  // Include cookies/session
        });

        if (!response.ok) {
            throw new Error('Failed to upload file');
        }

        const data = await response.json();
        
        // Update UI with transcription result
        transcriptionOutput.innerHTML = `<p>${data.transcription}</p>`;
        statusElement.textContent = 'Transcription complete!';
        statusElement.style.color = 'green';
        
        // Store transcription data for caption generation
        currentTranscriptionData = {
            transcription: data.transcription,
            words_data: data.words_data || [],
            filename: file.name
        };
        console.log('Stored transcription data:', currentTranscriptionData);
        
        // Display timestamped transcription if word data is available
        if (data.words_data && data.words_data.length > 0) {
            displayTimestampedTranscription(data.words_data);
        }
        
        // Update global state
        currentFileInfo = {
            original_file: data.original_file,
            current_language: data.current_language,
            has_transcription: true
        };
        
        // Show translate controls instead of transcribe controls
        document.getElementById('transcribe-container').style.display = 'none';
        document.getElementById('translate-container').style.display = 'block';
        document.getElementById('download-section').style.display = 'block';
        document.getElementById('clear-button').style.display = 'inline-block';
        
        // Don't reset the file input - we want to keep the reference
    } catch (error) {
        console.error('Error:', error);
        statusElement.textContent = 'Error occurred during transcription.';
        statusElement.style.color = 'red';
        transcriptionOutput.innerHTML = '<p>Error occurred during transcription.</p>';
        document.getElementById('transcribe-button').disabled = false;
    }
});

// Handle translation to different language
document.getElementById('translate-button').addEventListener('click', async () => {
    const languageSelect = document.getElementById('language-select');
    const transcriptionOutput = document.getElementById('transcription-output');
    const statusElement = document.getElementById('status-message');
    
    const language = languageSelect.value;
    
    // Update UI to show processing state
    statusElement.textContent = 'Translating...';
    statusElement.style.display = 'block';
    document.getElementById('translate-button').disabled = true;
    
    // Create FormData with just the language
    const formData = new FormData();
    formData.append('language', language);
    
    try {
        const response = await fetch('/translate', {
            method: 'POST',
            body: formData,
            credentials: 'include'  // Include cookies/session
        });
        
        if (!response.ok) {
            throw new Error('Failed to translate');
        }
        
        const data = await response.json();
        
        // Update UI with translated result
        transcriptionOutput.innerHTML = `<p>${data.transcription}</p>`;
        statusElement.textContent = 'Translation complete!';
        statusElement.style.color = 'green';
        
        // Update current language in global state
        currentFileInfo.current_language = data.current_language;
        
        document.getElementById('translate-button').disabled = false;
    } catch (error) {
        console.error('Error:', error);
        statusElement.textContent = 'Error occurred during translation.';
        statusElement.style.color = 'red';
        document.getElementById('translate-button').disabled = false;
    }
});

// Handle Download Button
document.getElementById('download-button').addEventListener('click', () => {
    const transcriptionOutput = document.getElementById('transcription-output').innerText;
    
    // Create a Blob with the transcription text
    const blob = new Blob([transcriptionOutput], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    
    // Create a temporary anchor element to trigger the download
    const a = document.createElement('a');
    a.href = url;
    a.download = 'transcription.txt';
    document.body.appendChild(a);
    a.click();
    
    // Clean up
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
});

// Handle Download Timestamped Transcription
document.getElementById('download-timestamped-button').addEventListener('click', () => {
    if (!currentTranscriptionData || !currentTranscriptionData.words_data) {
        alert('No timestamped data available.');
        return;
    }
    
    const wordsData = currentTranscriptionData.words_data;
    let content = 'TIMESTAMPED TRANSCRIPTION\n';
    content += '========================\n\n';
    
    // Group words into chunks same as display
    let chunks = [];
    let currentChunk = {
        text: [],
        start: null,
        end: null
    };
    
    const wordsPerChunk = 8;
    
    for (let i = 0; i < wordsData.length; i++) {
        const wordData = wordsData[i];
        
        if (!wordData.text) continue;
        
        if (currentChunk.start === null && wordData.start !== null) {
            currentChunk.start = wordData.start;
        }
        
        currentChunk.text.push(wordData.text);
        currentChunk.end = wordData.end;
        
        const isLastWord = i === wordsData.length - 1;
        const chunkFull = currentChunk.text.length >= wordsPerChunk;
        const isPunctuation = wordData.text.match(/[.!?]$/);
        
        if (chunkFull || isPunctuation || isLastWord) {
            if (currentChunk.text.length > 0) {
                chunks.push({
                    text: currentChunk.text.join(' '),
                    start: currentChunk.start,
                    end: currentChunk.end
                });
            }
            currentChunk = {
                text: [],
                start: null,
                end: null
            };
        }
    }
    
    // Add chunks to content
    chunks.forEach((chunk) => {
        const startTime = formatTime(chunk.start || 0);
        content += `[${startTime}] ${chunk.text}\n`;
    });
    
    // Create and download
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'transcription_timestamped.txt';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
});

// Clear current transcription and reset UI
document.getElementById('clear-button').addEventListener('click', async () => {
    try {
        // Clear the session data on the server
        await fetch('/clear', { method: 'POST', credentials: 'include' });
        
        // Reset UI state
        document.getElementById('transcription-output').innerHTML = '<p>Transcription will appear here...</p>';
        document.getElementById('file-upload').value = '';
        document.getElementById('file-status').textContent = 'No file selected';
        document.getElementById('status-message').style.display = 'none';
        
        // Reset controls
        document.getElementById('transcribe-container').style.display = 'block';
        document.getElementById('translate-container').style.display = 'none';
        document.getElementById('download-section').style.display = 'none';
        document.getElementById('clear-button').style.display = 'none';
        document.getElementById('transcribe-button').disabled = true;
        
        // Reset global state
        currentFileInfo = null;
    } catch (error) {
        console.error('Error clearing session:', error);
        alert('Failed to clear session. Please try again.');
    }
});

// Handle Caption Generation
document.getElementById('generate-captions-button').addEventListener('click', async () => {
    const statusElement = document.getElementById('status-message');
    const downloadCaptionsButton = document.getElementById('download-captions-button');
    
    // Check if we have transcription data
    if (!currentTranscriptionData || !currentTranscriptionData.transcription) {
        statusElement.textContent = 'Error: No transcription data. Please transcribe a file first.';
        statusElement.style.display = 'block';
        statusElement.style.color = 'red';
        return;
    }
    
    // Update UI to show processing state
    statusElement.textContent = 'Generating captions...';
    statusElement.style.display = 'block';
    statusElement.style.color = 'black';
    document.getElementById('generate-captions-button').disabled = true;
    
    try {
        const response = await fetch('/generate-captions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(currentTranscriptionData),
            credentials: 'include'  // Include cookies/session
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to generate captions');
        }
        
        statusElement.textContent = 'Captions generated successfully!';
        statusElement.style.color = 'green';
        downloadCaptionsButton.style.display = 'inline-block';
        
        document.getElementById('generate-captions-button').disabled = false;
    } catch (error) {
        console.error('Error:', error);
        statusElement.textContent = `Error: ${error.message}`;
        statusElement.style.color = 'red';
        document.getElementById('generate-captions-button').disabled = false;
    }
});

// Handle Caption Download
document.getElementById('download-captions-button').addEventListener('click', async () => {
    try {
        const response = await fetch('/download-captions');
        
        if (!response.ok) {
            throw new Error('Failed to download captions');
        }
        
        // Get filename from response headers if available
        const contentDisposition = response.headers.get('content-disposition');
        let filename = 'captions.srt';
        
        if (contentDisposition) {
            const match = contentDisposition.match(/filename="?([^"]+)"?/);
            if (match) filename = match[1];
        }
        
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        
        // Create a temporary anchor element to trigger the download
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        
        // Clean up
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (error) {
        console.error('Error downloading captions:', error);
        alert('Failed to download captions. Please try again.');
    }
});