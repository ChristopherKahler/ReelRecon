"""
Multi-provider LLM client for Content Skeleton Ripper.

Supports:
- OpenAI (gpt-4o-mini, gpt-4o, gpt-4-turbo)
- Anthropic (claude-3-haiku, claude-3-sonnet, claude-3-opus)
- Google (gemini-1.5-flash, gemini-1.5-pro)
- Local (Ollama - llama3, mistral, etc.)

Uses requests for API calls to minimize dependencies.
"""

import os
import json
import time
import traceback
import requests
from dataclasses import dataclass
from typing import Optional
from utils.logger import get_logger

logger = get_logger()


# =============================================================================
# PROVIDER CONFIGURATION
# =============================================================================

@dataclass
class ModelInfo:
    """Information about a specific model."""
    id: str
    name: str
    cost_tier: str  # 'free', 'low', 'medium', 'high'


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider."""
    id: str
    name: str
    api_key_env: str  # Environment variable name for API key
    base_url: str
    models: list[ModelInfo]


PROVIDERS = {
    'openai': ProviderConfig(
        id='openai',
        name='OpenAI',
        api_key_env='OPENAI_API_KEY',
        base_url='https://api.openai.com/v1',
        models=[
            ModelInfo('gpt-4o-mini', 'GPT-4o Mini (Recommended)', 'low'),
            ModelInfo('gpt-4o', 'GPT-4o', 'medium'),
            ModelInfo('gpt-4-turbo', 'GPT-4 Turbo', 'high'),
        ]
    ),
    'anthropic': ProviderConfig(
        id='anthropic',
        name='Anthropic',
        api_key_env='ANTHROPIC_API_KEY',
        base_url='https://api.anthropic.com/v1',
        models=[
            ModelInfo('claude-3-haiku-20240307', 'Claude 3 Haiku', 'low'),
            ModelInfo('claude-3-sonnet-20240229', 'Claude 3 Sonnet', 'medium'),
            ModelInfo('claude-3-opus-20240229', 'Claude 3 Opus', 'high'),
        ]
    ),
    'google': ProviderConfig(
        id='google',
        name='Google',
        api_key_env='GOOGLE_API_KEY',
        base_url='https://generativelanguage.googleapis.com/v1beta',
        models=[
            ModelInfo('gemini-1.5-flash', 'Gemini 1.5 Flash', 'low'),
            ModelInfo('gemini-1.5-pro', 'Gemini 1.5 Pro', 'medium'),
        ]
    ),
    'local': ProviderConfig(
        id='local',
        name='Local (Ollama)',
        api_key_env='',  # No API key needed
        base_url='http://localhost:11434/api',
        models=[
            ModelInfo('qwen3', 'Qwen 3 (Recommended)', 'free'),
            ModelInfo('qwen3:14b', 'Qwen 3 14B', 'free'),
            ModelInfo('llama3', 'Llama 3', 'free'),
            ModelInfo('llama3.1', 'Llama 3.1', 'free'),
            ModelInfo('mistral', 'Mistral', 'free'),
            ModelInfo('mixtral', 'Mixtral', 'free'),
            ModelInfo('phi3', 'Phi-3', 'free'),
        ]
    ),
}


# =============================================================================
# LLM CLIENT
# =============================================================================

class LLMClient:
    """
    Unified client for multiple LLM providers.

    Usage:
        client = LLMClient(provider='openai', model='gpt-4o-mini')
        response = client.complete(prompt)
        response = client.chat(system_prompt, user_prompt)
    """

    # Retry configuration
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_BASE_DELAY = 1.0  # seconds
    DEFAULT_MAX_DELAY = 30.0  # seconds
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(
        self,
        provider: str,
        model: str,
        timeout: int = 120,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
        max_delay: float = DEFAULT_MAX_DELAY
    ):
        """
        Initialize LLM client.

        Args:
            provider: Provider ID ('openai', 'anthropic', 'google', 'local')
            model: Model ID (e.g., 'gpt-4o-mini', 'claude-3-haiku-20240307')
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts on transient failures
            base_delay: Base delay for exponential backoff (seconds)
            max_delay: Maximum delay between retries (seconds)
        """
        if provider not in PROVIDERS:
            raise ValueError(f"Unknown provider: {provider}. Valid: {list(PROVIDERS.keys())}")

        self.provider = provider
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.config = PROVIDERS[provider]

        # Get API key (except for local)
        self.api_key = None
        if self.config.api_key_env:
            self.api_key = os.getenv(self.config.api_key_env)
            if not self.api_key:
                raise ValueError(
                    f"Missing API key for {provider}. "
                    f"Set {self.config.api_key_env} environment variable."
                )

        logger.info("LLM", f"LLM client initialized: {provider}/{model} (retries={max_retries})")

    def complete(self, prompt: str, temperature: float = 0.7) -> str:
        """
        Simple completion (single prompt, no system message).

        Args:
            prompt: The prompt text
            temperature: Sampling temperature (0-1)

        Returns:
            Generated text response
        """
        return self.chat(system_prompt=None, user_prompt=prompt, temperature=temperature)

    def chat(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """
        Chat completion with optional system prompt and retry logic.

        Args:
            user_prompt: User message
            system_prompt: Optional system message
            temperature: Sampling temperature (0-1)

        Returns:
            Generated text response

        Raises:
            Exception: If all retries fail
        """
        start_time = time.time()
        prompt_preview = user_prompt[:100] + "..." if len(user_prompt) > 100 else user_prompt
        logger.debug("LLM", f"Request to {self.provider}/{self.model}: {prompt_preview}")

        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                if self.provider == 'openai':
                    response = self._call_openai(system_prompt, user_prompt, temperature)
                elif self.provider == 'anthropic':
                    response = self._call_anthropic(system_prompt, user_prompt, temperature)
                elif self.provider == 'google':
                    response = self._call_google(system_prompt, user_prompt, temperature)
                elif self.provider == 'local':
                    response = self._call_ollama(system_prompt, user_prompt, temperature)
                else:
                    raise ValueError(f"Provider not implemented: {self.provider}")

                # Success - log timing and response preview
                elapsed = time.time() - start_time
                response_preview = response[:100] + "..." if len(response) > 100 else response
                logger.debug("LLM", f"Response ({elapsed:.2f}s): {response_preview}")
                logger.info("LLM", f"LLM call complete: {self.provider}/{self.model} in {elapsed:.2f}s")

                return response

            except requests.exceptions.HTTPError as e:
                last_exception = e
                status_code = e.response.status_code if e.response is not None else 0

                # Check if retryable
                if status_code in self.RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    logger.warning(
                        "LLM",
                        f"HTTP {status_code} error (attempt {attempt + 1}/{self.max_retries + 1}), "
                        f"retrying in {delay:.1f}s: {e}"
                    )
                    time.sleep(delay)
                    continue
                else:
                    # Non-retryable or max retries reached
                    logger.error("LLM", f"HTTP error (non-retryable or max retries): {e}")
                    logger.debug("LLM", f"Stack trace:\n{traceback.format_exc()}")
                    raise

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                last_exception = e

                if attempt < self.max_retries:
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    logger.warning(
                        "LLM",
                        f"Connection error (attempt {attempt + 1}/{self.max_retries + 1}), "
                        f"retrying in {delay:.1f}s: {e}"
                    )
                    time.sleep(delay)
                    continue
                else:
                    logger.error("LLM", f"Connection error after {self.max_retries + 1} attempts: {e}")
                    logger.debug("LLM", f"Stack trace:\n{traceback.format_exc()}")
                    raise

            except Exception as e:
                # Unexpected error - log stack trace and don't retry
                logger.error("LLM", f"Unexpected error: {e}")
                logger.debug("LLM", f"Stack trace:\n{traceback.format_exc()}")
                raise

        # Should not reach here, but just in case
        raise last_exception or Exception("Max retries exceeded")

    def _call_openai(
        self,
        system_prompt: Optional[str],
        user_prompt: str,
        temperature: float
    ) -> str:
        """Call OpenAI API."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        response = requests.post(
            f"{self.config.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature
            },
            timeout=self.timeout
        )
        response.raise_for_status()
        data = response.json()
        return data['choices'][0]['message']['content']

    def _call_anthropic(
        self,
        system_prompt: Optional[str],
        user_prompt: str,
        temperature: float
    ) -> str:
        """Call Anthropic API."""
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "temperature": temperature,
            "messages": [{"role": "user", "content": user_prompt}]
        }
        if system_prompt:
            payload["system"] = system_prompt

        response = requests.post(
            f"{self.config.base_url}/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()
        data = response.json()
        return data['content'][0]['text']

    def _call_google(
        self,
        system_prompt: Optional[str],
        user_prompt: str,
        temperature: float
    ) -> str:
        """Call Google Gemini API."""
        # Combine system and user prompts for Gemini
        full_prompt = user_prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"

        response = requests.post(
            f"{self.config.base_url}/models/{self.model}:generateContent?key={self.api_key}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": full_prompt}]}],
                "generationConfig": {"temperature": temperature}
            },
            timeout=self.timeout
        )
        response.raise_for_status()
        data = response.json()
        return data['candidates'][0]['content']['parts'][0]['text']

    def _call_ollama(
        self,
        system_prompt: Optional[str],
        user_prompt: str,
        temperature: float
    ) -> str:
        """Call local Ollama API."""
        # Combine system and user prompts
        full_prompt = user_prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"

        response = requests.post(
            f"{self.config.base_url}/generate",
            json={
                "model": self.model,
                "prompt": full_prompt,
                "stream": False,
                "options": {"temperature": temperature}
            },
            timeout=self.timeout
        )
        response.raise_for_status()
        data = response.json()
        return data['response']


# =============================================================================
# PROVIDER AVAILABILITY
# =============================================================================

def get_available_providers() -> list[dict]:
    """
    Get list of providers with availability status.

    Returns:
        List of provider dicts with 'id', 'name', 'available', 'models'
    """
    result = []

    for provider_id, config in PROVIDERS.items():
        available = False
        models = []

        if provider_id == 'local':
            # Check if Ollama is running
            try:
                response = requests.get(
                    'http://localhost:11434/api/tags',
                    timeout=2
                )
                if response.status_code == 200:
                    available = True
                    # Get actually installed models
                    data = response.json()
                    installed = {m['name'].split(':')[0] for m in data.get('models', [])}
                    models = [
                        {'id': m.id, 'name': m.name, 'cost_tier': m.cost_tier}
                        for m in config.models
                        if m.id in installed
                    ]
            except requests.exceptions.RequestException:
                pass
        else:
            # Check if API key is set
            api_key = os.getenv(config.api_key_env)
            if api_key:
                available = True
                models = [
                    {'id': m.id, 'name': m.name, 'cost_tier': m.cost_tier}
                    for m in config.models
                ]

        result.append({
            'id': config.id,
            'name': config.name,
            'available': available,
            'models': models
        })

    return result


def check_provider_health(provider: str) -> tuple[bool, str]:
    """
    Check if a provider is accessible.

    Args:
        provider: Provider ID

    Returns:
        Tuple of (is_healthy, message)
    """
    if provider not in PROVIDERS:
        return False, f"Unknown provider: {provider}"

    config = PROVIDERS[provider]

    if provider == 'local':
        try:
            response = requests.get('http://localhost:11434/api/tags', timeout=5)
            if response.status_code == 200:
                return True, "Ollama is running"
            return False, f"Ollama returned status {response.status_code}"
        except requests.exceptions.RequestException as e:
            return False, f"Cannot connect to Ollama: {e}"
    else:
        api_key = os.getenv(config.api_key_env)
        if not api_key:
            return False, f"Missing {config.api_key_env} environment variable"
        return True, f"API key configured for {config.name}"
