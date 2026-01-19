"""
Configuration management for AI Data Platform.
 अलाows overriding settings via Django settings or environment variables.
"""
from django.conf import settings
from typing import Dict, Any

DEFAULTS = {
    'ENCRYPTION_KEY': None,
    'OPENAI_API_KEY': None,
    'PLATFORM_REGISTRY': {
        'stripe': 'ai_data_platform.services.stripe_service.StripeService',
        'zendesk': 'ai_data_platform.services.zendesk_service.ZendeskService',
        'github': 'ai_data_platform.services.github_service.GitHubService',
    },
    'LOG_QUERIES': True,
}

class AiDataPlatformSettings:
    def __init__(self, user_settings: Dict[str, Any] = None, defaults: Dict[str, Any] = None):
        self.user_settings = user_settings or {}
        self.defaults = defaults or DEFAULTS

    def __getattr__(self, attr):
        if attr not in self.defaults:
            raise AttributeError(f"Invalid setting: {attr}")

        # Try to get from user settings (e.g. in settings.AI_DATA_PLATFORM)
        try:
            val = self.user_settings.get(attr, self.defaults[attr])
        except Exception:
            val = self.defaults[attr]
            
        # Fallback to global Django settings if specific key exists there (e.g. OPENAI_API_KEY)
        if hasattr(settings, attr):
            val = getattr(settings, attr)
            
        return val

# Global settings instance
api_settings = AiDataPlatformSettings(
    getattr(settings, 'AI_DATA_PLATFORM', {}),
    DEFAULTS
)
