from typing import Dict, List, Optional
import google.generativeai as genai
import hashlib
import json
from . import cache


class GeminiService:
    def __init__(self, api_key: str):
        """Initialize Gemini API service with the provided API key."""
        self.api_key = api_key
        genai.configure(api_key=api_key)

    def get_cache_key(self, prompt: str, transcripts: List[str]) -> str:
        """Generate a cache key for a specific prompt and transcripts combination."""
        content = prompt + json.dumps(transcripts)
        return hashlib.md5(content.encode()).hexdigest()

    @cache.memoize(timeout=3600)  # Cache results for 1 hour
    def analyze_transcripts(
        self,
        prompt: str,
        transcripts: List[Dict[str, str]],
        cache_key: Optional[str] = None,
    ) -> str:
        """Use Gemini to analyze video transcripts based on a prompt."""
        if not transcripts:
            return "No transcripts to analyze."

        # Format the prompt with clear instructions to avoid chain of thought
        formatted_prompt = """Analyze the following video(s) based on this prompt: 

{}

IMPORTANT: Provide a direct, well-formatted response. DO NOT include any statements about your process like 'Analyzing the video...' or similar phrases. Start immediately with your analysis.

""".format(prompt)

        for i, video in enumerate(transcripts, 1):
            formatted_prompt += f"VIDEO {i}: {video.get('title', 'Untitled')}\n"
            formatted_prompt += f"URL: {video.get('url', 'No URL')}\n"
            formatted_prompt += "TRANSCRIPT:\n"
            formatted_prompt += (
                video.get("transcript", "No transcript available") + "\n\n"
            )

        try:
            model = genai.GenerativeModel("gemini-2.0-flash-exp")

            response = model.generate_content(
                formatted_prompt,
                generation_config={
                    "temperature": 0.7,
                    "top_p": 0.95,
                    "top_k": 64,
                    "max_output_tokens": 8192,
                },
            )

            return response.text
        except Exception as e:
            return f"Error analyzing transcripts: {str(e)}"

    def stream_analysis(self, prompt: str, transcripts: List[Dict[str, str]]) -> str:
        """Stream Gemini analysis results - yields chunks of text as they are generated."""
        if not transcripts:
            yield "No transcripts to analyze."
            return

        # Format the prompt with clear instructions to avoid chain of thought
        formatted_prompt = """Analyze the following video(s) based on this prompt: 

{}

IMPORTANT: Provide a direct, well-formatted response. DO NOT include any statements about your process like 'Analyzing the video...' or similar phrases. Start immediately with your analysis.

""".format(prompt)

        for i, video in enumerate(transcripts, 1):
            formatted_prompt += f"VIDEO {i}: {video.get('title', 'Untitled')}\n"
            formatted_prompt += f"URL: {video.get('url', 'No URL')}\n"
            formatted_prompt += "TRANSCRIPT:\n"
            formatted_prompt += (
                video.get("transcript", "No transcript available") + "\n\n"
            )

        try:
            model = genai.GenerativeModel("gemini-2.0-flash-exp")

            response = model.generate_content(
                formatted_prompt,
                generation_config={
                    "temperature": 0.7,
                    "top_p": 0.95,
                    "top_k": 64,
                    "max_output_tokens": 8192,
                },
                stream=True,
            )

            for chunk in response:
                if hasattr(chunk, "text"):
                    yield chunk.text
        except Exception as e:
            yield f"Error analyzing transcripts: {str(e)}"
