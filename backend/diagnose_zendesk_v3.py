import requests

def run_diagnostics(subdomain, email, token):
    u = f"{email}/token"
    print(f"Diagnostics for {u}...")
    headers = {"Accept": "application/json"}
    auth = (u, token)
    
    # 1. Who am I? (Detailed)
    r_me = requests.get(f"https://{subdomain}.zendesk.com/api/v2/users/me.json", auth=auth, headers=headers)
    if r_me.status_code == 200:
        user = r_me.json().get('user', {})
        print(f"ROLE: {user.get('role')}")
        print(f"VERIFIED: {user.get('verified')}")
        print(f"ACTIVE: {user.get('active')}")
        print(f"EMAIL: {user.get('email')}")
    else:
        print(f"ME ERROR: {r_me.status_code} {r_me.text}")

    # 2. Can I see tickets?
    r_t = requests.get(f"https://{subdomain}.zendesk.com/api/v2/tickets.json?per_page=1", auth=auth, headers=headers)
    print(f"TICKETS endpoint: {r_t.status_code}")

    # 3. Can I see MY requests (as an end-user)?
    r_r = requests.get(f"https://{subdomain}.zendesk.com/api/v2/requests.json", auth=auth, headers=headers)
    print(f"REQUESTS endpoint: {r_r.status_code}")
    if r_r.status_code == 200:
        print(f"Found {len(r_r.json().get('requests', []))} requests")

    # 4. Search?
    r_s = requests.get(f"https://{subdomain}.zendesk.com/api/v2/search.json?query=type:ticket", auth=auth, headers=headers)
    print(f"SEARCH endpoint: {r_s.status_code}")

if __name__ == "__main__":
    run_diagnostics("xyz-37134", "phapalesai25@gmail.com", "srGRptnlQxxSnoadEd778Wl5y4duM2kvooDhXgOD")
