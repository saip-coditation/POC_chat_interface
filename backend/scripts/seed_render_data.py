
import os
import django
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.platforms.models import PlatformConnection
from utils.encryption import encrypt_api_key

User = get_user_model()

def seed_data():
    print("--- Starting Render Data Seeding ---")
    email = os.environ.get('SEED_USER_EMAIL', 'sumitphapale@gmail.com')
    password = os.environ.get('SEED_USER_PASSWORD', 'sumit@1234')
    
    if not email or not password:
        print("SEED_USER_EMAIL or SEED_USER_PASSWORD not set, skipping user creation.")
        return

    # Check if user exists
    if User.objects.filter(username=email).exists():
         user = User.objects.get(username=email)
         print(f"User already exists: {email}")
    else:
        user = User.objects.create_user(username=email, email=email, password=password)
        print(f"Created user: {email}")

    # Seed Zoho
    zoho_refresh = os.environ.get('ZOHO_REFRESH_TOKEN')
    zoho_client_id = os.environ.get('ZOHO_CLIENT_ID')
    zoho_client_secret = os.environ.get('ZOHO_CLIENT_SECRET')
    
    if zoho_refresh and zoho_client_id and zoho_client_secret:
        try:
            # Encrypt the refresh token using the key from environment
            encrypted_key = encrypt_api_key(zoho_refresh)
            
            metadata = {
                'last_four': zoho_refresh[-4:],
                'client_id': zoho_client_id,
                'client_secret': zoho_client_secret,
                'message': 'Auto-connected via Render Env Vars'
            }
            
            conn, created = PlatformConnection.objects.update_or_create(
                user=user,
                platform='zoho',
                defaults={
                    'encrypted_api_key': encrypted_key,
                    'is_valid': True,
                    'metadata': metadata
                }
            )
            print(f"Seeded Zoho connection for {email}")
        except Exception as e:
            print(f"Failed to seed Zoho: {e}")
    else:
        print("Zoho env vars missing (ZOHO_REFRESH_TOKEN, ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET), skipping connection seed.")

if __name__ == '__main__':
    seed_data()
