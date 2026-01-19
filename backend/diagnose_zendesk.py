import requests
import sys

def test(subdomain, email, token):
    if not email.endswith('/token'):
        email = f"{email}/token"
        
    print(f"Testing {subdomain} as {email}...")
    
    headers = {
        "User-Agent": "ZendeskDataFetcher/1.0",
        "Accept": "application/json"
    }
    
    # 1. Test Identity
    url_me = f"https://{subdomain}.zendesk.com/api/v2/users/me.json"
    r_me = requests.get(url_me, auth=(email, token), headers=headers)
    print(f"ME: {r_me.status_code}")
    if r_me.status_code == 200:
        print(f"ME User: {r_me.json().get('user', {}).get('email')}")
    else:
        print(f"ME Error: {r_me.text}")
        
    # 2. Test Tickets
    url_t = f"https://{subdomain}.zendesk.com/api/v2/tickets.json?per_page=1"
    r_t = requests.get(url_t, auth=(email, token), headers=headers)
    print(f"TICKETS: {r_t.status_code}")
    if r_t.status_code != 200:
        print(f"TICKETS Error: {r_t.text}")

if __name__ == "__main__":
    test("xyz-37134", "phapalesai25@gmail.com", "srGRptnlQxxSnoadEd778Wl5y4duM2kvooDhXgOD")
