from django.core.management.base import BaseCommand
from django.conf import settings
from ai_data_platform.core.encryption import get_fernet

class Command(BaseCommand):
    help = 'Initialize AI Data Platform configuration and checks'

    def handle(self, *args, **options):
        self.stdout.write("Initializing AI Data Platform...")
        
        # Check Encryption Key
        key = getattr(settings, 'AI_DATA_PLATFORM', {}).get('ENCRYPTION_KEY') or settings.SECRET_KEY
        if len(key) < 32:
            self.stdout.write(self.style.WARNING("WARNING: Your encryption key seems short. Ensure it is secure for production."))
        
        # Check OpenAI Key
        openai_key = getattr(settings, 'AI_DATA_PLATFORM', {}).get('OPENAI_API_KEY')
        if not openai_key:
            self.stdout.write(self.style.ERROR("ERROR: OPENAI_API_KEY is missing in settings."))
        else:
            self.stdout.write(self.style.SUCCESS("✓ OpenAI key configuration found."))

        self.stdout.write(self.style.SUCCESS("Initialization check complete."))
