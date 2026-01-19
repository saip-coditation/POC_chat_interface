import requests

def test_variation(subdomain, email, token, suffix=True):
    u = email
    if suffix and not u.endswith('/token'):
        u = f"{u}/token"
        
    print(f"\n--- Testing with suffix={suffix} (User: {u}) ---")
    headers = {"Accept": "application/json"}
    
    # Test Identity
    r_me = requests.get(f"https://{subdomain}.zendesk.com/api/v2/users/me.json", auth=(u, token), headers=headers)
    print(f"ME: {r_me.status_code} - {r_me.json().get('user', {}).get('email') if r_me.status_code==200 else r_me.text[:50]}")
    
    # Test Tickets
    r_t = requests.get(f"https://{subdomain}.zendesk.com/api/v2/tickets.json?per_page=1", auth=(u, token), headers=headers)
    print(f"TICKETS: {r_t.status_code} - {r_t.text[:50]}")

if __name__ == "__main__":
    sub = "xyz-37134"
    em = "phapalesai25@gmail.com"
    tok = "srGRptnlQxxSnoadEd778Wl5y4duM2kvooDhXgOD"
    
    test_variation(sub, em, tok, suffix=True)
    test_variation(sub, em, tok, suffix=False)
