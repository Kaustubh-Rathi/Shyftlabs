#app.py
from flask import Flask, render_template, request, jsonify
import uuid
import requests

app = Flask(__name__, static_folder='static', template_folder='templates')

# Configure backend URL (FastAPI runs on port 8000 by default)
BACKEND_URL = "http://localhost:8000"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_research', methods=['POST'])
def start_research():
    # Get JSON data from frontend
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request must be JSON"}), 400
    
    query = data.get('query')
    if not query:
        return jsonify({"error": "Query is required"}), 400
    
    try:
        # Forward request to FastAPI backend with all parameters
        response = requests.post(
            f"{BACKEND_URL}/start_research",
            json={
                "query": query,
                "tone": data.get('tone', 'objective'),
                "max_sections": data.get('max_sections', 3),
                "publish_formats": data.get('publish_formats', {
                    "markdown": True,
                    "pdf": True,
                    "docx": True
                }),
                "include_human_feedback": data.get('include_human_feedback', False),
                "follow_guidelines": data.get('follow_guidelines', True),
                "model": data.get('model', 'gpt-3.5-turbo'),
                "guidelines": data.get('guidelines', [
                    "The report MUST be written in APA format",
                    "Each sub section MUST include supporting sources using hyperlinks. If none exist, erase the sub section or rewrite it to be a part of the previous section",
                    "The report MUST be written in English"
                ]),
                "verbose": data.get('verbose', True)
            },
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Backend request failed: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=8080)