import requests
import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434/api/generate')
MODEL = os.getenv('OLLAMA_MODEL', 'qwen2.5:14b')


def call_ollama(prompt, model=None, stream=False):
    """
    Send a prompt to Ollama and get the response.

    Args:
        prompt (str): The prompt to send to the LLM
        model (str, optional): Model to use. Defaults to OLLAMA_MODEL from env
        stream (bool, optional): Whether to stream the response. Defaults to False

    Returns:
        str: The LLM's response text
    """
    payload = {
        "model": model or MODEL,
        "prompt": prompt,
        "stream": stream
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        return response.json()['response']
    except requests.exceptions.RequestException as e:
        return f"Error calling Ollama: {str(e)}"
