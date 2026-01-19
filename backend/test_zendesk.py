from zenpy import Zenpy
import sys

def test_zenpy_auth(subdomain, email, token):
    print(f"Testing Zenpy with subdomain={subdomain}, email={email}")
    try:
        # Test 1: plain email (library usually handles /token)
        print("Attempt 1: Plain email...")
        client1 = Zenpy(subdomain=subdomain, email=email, token=token)
        me1 = client1.users.me()
        print(f"Success 1: {me1.name}")
    except Exception as e:
        print(f"Failed 1: {e}")

    try:
        # Test 2: email with /token (what I added)
        email_token = f"{email}/token" if not email.endswith('/token') else email
        print(f"Attempt 2: Email with /token suffix ({email_token}) and token param...")
        client2 = Zenpy(subdomain=subdomain, email=email_token, token=token)
        me2 = client2.users.me()
        print(f"Success 2: {me2.name}")
    except Exception as e:
        print(f"Failed 2: {e}")

    try:
        # Test 3: email with /token as email, and token as password
        email_token = f"{email}/token" if not email.endswith('/token') else email
        print(f"Attempt 3: Email with /token suffix ({email_token}) and password param...")
        client3 = Zenpy(subdomain=subdomain, email=email_token, password=token)
        me3 = client3.users.me()
        print(f"Success 3: {me3.name}")
    except Exception as e:
        print(f"Failed 3: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python test_zendesk.py subdomain email token")
    else:
        test_zenpy_auth(sys.argv[1], sys.argv[2], sys.argv[3])
