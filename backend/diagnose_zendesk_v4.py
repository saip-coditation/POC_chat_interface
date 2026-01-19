import requests

def run_diagnostics(subdomain, email, token):
    # Clean email from any existing /token suffix for variation testing
    clean_email = email.split('/token')[0]
    
    auth_with_suffix = (f"{clean_email}/token", token)
    auth_no_suffix = (clean_email, token)
    
    headers = {"Accept": "application/json"}
    
    print(f"--- DIAGNOSTIC V4 FOR {subdomain} ---")
    
    def test_auth(label, auth_tuple):
        print(f"\n[{label}] Testing with username: {auth_tuple[0]}")
        
        # 1. Identity
        r_me = requests.get(f"https://{subdomain}.zendesk.com/api/v2/users/me.json", auth=auth_tuple, headers=headers)
        print(f"  ME Endpoint: {r_me.status_code}")
        if r_me.status_code == 200:
            user = r_me.json().get('user', {})
            print(f"    Role: {user.get('role')}")
            print(f"    Email: {user.get('email')}")
            print(f"    Verified: {user.get('verified')}")
        
        # 2. Tickets
        r_t = requests.get(f"https://{subdomain}.zendesk.com/api/v2/tickets.json?per_page=1", auth=auth_tuple, headers=headers)
        print(f"  TICKETS Endpoint: {r_t.status_code}")
        if r_t.status_code != 200:
             print(f"    Error: {r_t.text[:100]}")

    test_auth("Standard (With /token)", auth_with_suffix)
    test_auth("Non-Standard (No /token)", auth_no_suffix)
    
    # 3. Check for Account Info (Requires Admin)
    print("\n[Admin Check] Checking Account Settings...")
    r_acc = requests.get(f"https://{subdomain}.zendesk.com/api/v2/account/settings.json", auth=auth_with_suffix, headers=headers)
    print(f"  Account Settings Endpoint: {r_acc.status_code}")

if __name__ == "__main__":
    # Using the exact credentials provided by the user in the latest message
    run_diagnostics("xyz-37134", "phapalesai25@gmail.com", "srGRptnlQxxSnoadEd778Wl5y4duM2kvooDhXgOD")
