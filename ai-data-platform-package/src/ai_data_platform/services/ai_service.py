import json
import logging
from openai import OpenAI
from ..conf import api_settings

logger = logging.getLogger(__name__)

class AiService:
    def __init__(self):
        self.client = None
        self._setup_client()

    def _setup_client(self):
        api_key = api_settings.OPENAI_API_KEY
        if not api_key:
            return # Delay error until usage?
            
        if api_key.startswith('sk-or-'):
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1"
            )
        else:
            self.client = OpenAI(api_key=api_key)

    def _get_model(self):
        # Could also be configurable
        api_key = api_settings.OPENAI_API_KEY
        if api_key and api_key.startswith('sk-or-'):
            return "openai/gpt-4o-mini"
        return "gpt-4o-mini"

    def interpret_query(self, query: str, platform: str, system_prompt: str) -> dict:
        """
        Generic query interpretation.
        The caller (PlatformService) provides the system prompt specific to that platform.
        """
        if not self.client:
             # Try refreshing key in case it was set late
             self._setup_client()
             if not self.client:
                return {'action': 'error', 'error': 'OpenAI API key not configured'}

        try:
            response = self.client.chat.completions.create(
                model=self._get_model(),
                messages=[
                    {"role": "system", "content": system_prompt + "\nIMPORTANT: Return ONLY valid JSON. No preamble."},
                    {"role": "user", "content": query}
                ],
                temperature=0,
                max_tokens=250
            )
            content = response.choices[0].message.content.strip()
            # Clean possible markdown code blocks
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
            
            return json.loads(content)
        except Exception as e:
            logger.error(f"AI Interpretation error: {e}")
            return {'action': 'error', 'error': str(e)}

    def summarize_results(self, query: str, data: dict, platform: str, summary_rules: str = "") -> str:
        if not self.client:
             self._setup_client()
             if not self.client:
                return "Error: OpenAI not configured."

        try:
            data_str = json.dumps(data, default=str)
            if len(data_str) > 3000:
                data_str = data_str[:3000] + "... (truncated)"

            system_prompt = f"""You summarize {platform} data.
{summary_rules}
RULES:
- Use **bold** for key numbers.
- Be concise (3-4 sentences).
"""
            response = self.client.chat.completions.create(
                model=self._get_model(),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Query: {query}\nData: {data_str}"}
                ],
                temperature=0.2,
                max_tokens=200
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"AI Summarization error: {e}")
            return "Failed to generate summary."

# Singleton
ai_service = AiService()
