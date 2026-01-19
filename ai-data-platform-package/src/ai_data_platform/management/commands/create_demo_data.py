from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from ai_data_platform.models import PlatformConnection

class Command(BaseCommand):
    help = 'Create demo data for testing'

    def handle(self, *args, **options):
        User = get_user_model()
        
        # Create Demo User
        user, created = User.objects.get_or_create(username='demo_user', email='demo@example.com')
        if created:
            user.set_password('demo123')
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Created demo user: {user.username}"))
        
        # Create Dummy Platform Connection
        PlatformConnection.objects.get_or_create(
            user=user,
            platform='stripe',
            defaults={
                'encrypted_api_key': 'mock_encrypted_key',
                'is_valid': True
            }
        )
        self.stdout.write(self.style.SUCCESS("Created demo platform connection."))
