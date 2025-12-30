from flask import Flask, render_template, request, jsonify
from services.ollama_client import call_ollama
from services.voice_input import transcribe_audio

app = Flask(__name__)

@app.route('/')
def index():
    return """
    <html>
        <head><title>Bardic AI</title></head>
        <body>
            <h1>Bardic AI - Voice Powered DM</h1>
            <form method="POST" action="/action">
                <label>What do you do?</label><br>
                <input type="text" name="player_action" size="50"><br>
                <button type="submit">Take Action</button>
            </form>
            <br>
            <p><a href="/voice"><button type="button">Use Voice Input</button></a></p>
        </body>
    </html>
    """

@app.route('/voice')
def voice():
    return """
    <html>
        <head>
            <title>Bardic AI - Voice Input</title>
            <style>
                .recording {
                    background-color: #ff0000;
                    color: white;
                }
                #status {
                    margin: 10px 0;
                    font-weight: bold;
                }
                #transcription {
                    margin: 20px 0;
                    padding: 10px;
                    border: 1px solid #ccc;
                    min-height: 50px;
                }
            </style>
        </head>
        <body>
            <h1>Bardic AI - Voice Input</h1>
            <div id="status">Ready to record</div>
            <button id="recordBtn" onmousedown="startRecording()" onmouseup="stopRecording()">
                Hold to Record
            </button>
            <div id="transcription"></div>
            <form id="actionForm" method="POST" action="/action" style="display:none;">
                <input type="hidden" name="player_action" id="player_action">
                <button type="submit">Submit Action</button>
            </form>
            <br>
            <a href="/">Back to Text Input</a>

            <script>
                let mediaRecorder;
                let audioChunks = [];

                async function startRecording() {
                    try {
                        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                        mediaRecorder = new MediaRecorder(stream);
                        audioChunks = [];

                        mediaRecorder.ondataavailable = (event) => {
                            audioChunks.push(event.data);
                        };

                        mediaRecorder.onstop = async () => {
                            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                            await transcribeAudio(audioBlob);
                            stream.getTracks().forEach(track => track.stop());
                        };

                        mediaRecorder.start();
                        document.getElementById('recordBtn').classList.add('recording');
                        document.getElementById('status').textContent = 'Recording...';
                    } catch (error) {
                        document.getElementById('status').textContent = 'Error: ' + error.message;
                    }
                }

                function stopRecording() {
                    if (mediaRecorder && mediaRecorder.state === 'recording') {
                        mediaRecorder.stop();
                        document.getElementById('recordBtn').classList.remove('recording');
                        document.getElementById('status').textContent = 'Processing...';
                    }
                }

                async function transcribeAudio(audioBlob) {
                    const formData = new FormData();
                    formData.append('audio', audioBlob, 'recording.wav');

                    try {
                        const response = await fetch('/transcribe', {
                            method: 'POST',
                            body: formData
                        });

                        const data = await response.json();

                        if (data.text) {
                            document.getElementById('transcription').innerHTML =
                                '<strong>You said:</strong> ' + data.text;
                            document.getElementById('player_action').value = data.text;
                            document.getElementById('actionForm').style.display = 'block';
                            document.getElementById('status').textContent = 'Ready to submit';
                        } else {
                            document.getElementById('status').textContent = 'Error: ' + data.error;
                        }
                    } catch (error) {
                        document.getElementById('status').textContent = 'Error: ' + error.message;
                    }
                }
            </script>
        </body>
    </html>
    """

@app.route('/transcribe', methods=['POST'])
def transcribe():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400

    audio_file = request.files['audio']

    if audio_file.filename == '':
        return jsonify({'error': 'No audio file selected'}), 400

    try:
        transcribed_text = transcribe_audio(audio_file)
        return jsonify({'text': transcribed_text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/action', methods=['POST'])
def action():
    player_action = request.form['player_action']
    
    # Simple DM prompt
    dm_prompt = f"""You are a Dungeon Master running a D&D adventure. 
The player says: "{player_action}"

Respond as the DM, describing what happens. Keep it to 2-3 sentences."""
    
    dm_response = call_ollama(dm_prompt)
    
    return f"""
    <html>
        <head><title>Bardic AI</title></head>
        <body>
            <h1>Bardic AI</h1>
            <p><strong>You:</strong> {player_action}</p>
            <p><strong>DM:</strong> {dm_response}</p>
            <a href="/">Continue Adventure</a>
        </body>
    </html>
    """

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)