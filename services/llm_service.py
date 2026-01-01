"""
Unified LLM Service - Supports both Ollama (local) and Anthropic Claude (API)

Usage:
    Set LLM_PROVIDER in .env to 'ollama' or 'anthropic'
    
    For Anthropic:
        ANTHROPIC_API_KEY=your-key-here
        ANTHROPIC_MODEL=claude-sonnet-4-20250514
    
    For Ollama:
        OLLAMA_URL=http://localhost:11434/api/generate
        OLLAMA_MODEL=qwen2.5:14b
"""

import os
import logging
import requests
from dotenv import load_dotenv
from abc import ABC, abstractmethod
from typing import Optional

load_dotenv()
logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate a response from the LLM."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging."""
        pass


class OllamaProvider(LLMProvider):
    """Local Ollama LLM provider."""
    
    def __init__(self):
        self.url = os.getenv('OLLAMA_URL', 'http://localhost:11434/api/generate')
        self.model = os.getenv('OLLAMA_MODEL', 'qwen2.5:14b')
        logger.info(f"Initialized Ollama provider: {self.model}")
    
    @property
    def name(self) -> str:
        return f"Ollama ({self.model})"
    
    def generate(self, prompt: str) -> str:
        """Send prompt to Ollama and get response."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        
        try:
            response = requests.post(self.url, json=payload, timeout=120)
            response.raise_for_status()
            return response.json()['response']
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama error: {e}")
            return f"Error calling Ollama: {str(e)}"


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""
    
    def __init__(self):
        self.api_key = os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set in environment")
        
        self.model = os.getenv('ANTHROPIC_MODEL', 'claude-sonnet-4-20250514')
        self.max_tokens = int(os.getenv('ANTHROPIC_MAX_TOKENS', '1024'))
        self.api_url = "https://api.anthropic.com/v1/messages"
        
        logger.info(f"Initialized Anthropic provider: {self.model}")
    
    @property
    def name(self) -> str:
        return f"Anthropic ({self.model})"
    
    def generate(self, prompt: str) -> str:
        """Send prompt to Claude API and get response."""
        headers = {
            "x-api-key": self.api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
        try:
            response = requests.post(
                self.api_url, 
                headers=headers, 
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Extract text from response
            if 'content' in result and len(result['content']) > 0:
                return result['content'][0]['text']
            else:
                logger.error(f"Unexpected API response format: {result}")
                return "Error: Unexpected response format from Claude API"
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Anthropic API error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response body: {e.response.text}")
            return f"Error calling Claude API: {str(e)}"


# Global provider instance
_provider: Optional[LLMProvider] = None


def get_provider() -> LLMProvider:
    """Get or create the LLM provider based on config."""
    global _provider
    
    if _provider is None:
        provider_type = os.getenv('LLM_PROVIDER', 'ollama').lower()
        
        if provider_type == 'anthropic':
            _provider = AnthropicProvider()
        else:
            _provider = OllamaProvider()
        
        logger.info(f"Using LLM provider: {_provider.name}")
    
    return _provider


def call_llm(prompt: str) -> str:
    """
    Universal LLM call function - works with any configured provider.
    
    This is the main function to use throughout the app.
    """
    provider = get_provider()
    return provider.generate(prompt)


# Backwards compatibility - alias for existing code
def call_ollama(prompt: str, model: str = None, stream: bool = False) -> str:
    """
    Backwards compatible function that routes to the configured provider.
    
    Note: model and stream params are ignored when using Anthropic.
    """
    return call_llm(prompt)
