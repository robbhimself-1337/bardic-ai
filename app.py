from flask import Flask, render_template, request, jsonify
from services.ollama_client import call_ollama

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
        </body>
    </html>
    """

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