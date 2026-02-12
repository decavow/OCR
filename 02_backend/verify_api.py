import requests
import sys

API_URL = "http://localhost:8000/api/v1"
EMAIL = "admin@gmail.com"
PASSWORD = "admin123"

def verify_api():
    print(f"Targeting API: {API_URL}")
    
    # 1. Login
    print("Logging in...")
    try:
        resp = requests.post(f"{API_URL}/auth/login", json={"email": EMAIL, "password": PASSWORD})
        if resp.status_code != 200:
            print(f"Login failed: {resp.status_code} {resp.text}")
            return
        data = resp.json()
        token = data["token"]
        print("Login successful. Token obtained.")
    except Exception as e:
        print(f"Login request failed: {e}")
        return

    # 2. Get Users
    print("Fetching admin users...")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{API_URL}/admin/dashboard/users", headers=headers, params={"page": 1, "page_size": 50})
        
        if resp.status_code == 200:
            users_data = resp.json()
            items = users_data.get("items", [])
            print(f"Success! Found {len(items)} users.")
            for u in items:
                print(f" - {u['email']} (Admin: {u['is_admin']})")
        else:
            print(f"Failed to fetch users: {resp.status_code} {resp.text}")

    except Exception as e:
        print(f"Fetch users request failed: {e}")

if __name__ == "__main__":
    verify_api()
