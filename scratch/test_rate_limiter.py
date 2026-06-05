import os
import sys
import django

# Set up paths and Django environment
sys.path.append('c:/Users/HP/OneDrive/Desktop/vvitu/vvitu-portal/vvitu_portal')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
django.setup()

from django.test import Client
from django.core.cache import cache

def run_tests():
    client = Client()
    
    # 1. Clear any existing cache to ensure clean tests
    cache.clear()
    print("Cache cleared.")
    
    # 2. Simulate 5 failed attempts from same IP / Username
    username = 'admin'
    password = 'wrong_password'
    
    print("\n--- Testing IP / Username Rate Limiting ---")
    for i in range(1, 6):
        response = client.post('/accounts/login/', {'username': username, 'password': password})
        print(f"Attempt {i}: Response Status Code = {response.status_code}")
        
    # The 6th attempt should return 429 Too Many Requests
    response = client.post('/accounts/login/', {'username': username, 'password': password})
    print(f"Attempt 6 (should lock out): Response Status Code = {response.status_code}")
    if response.status_code == 429:
        print("[SUCCESS] Rate limiting successfully blocked brute force (returned 429).")
    else:
        print("[FAILURE] Rate limiting did not block brute force!")

    # 3. Clear cache and test reset on success
    cache.clear()
    print("\n--- Testing Reset on Success ---")
    
    # 4 failed attempts
    for i in range(1, 5):
        client.post('/accounts/login/', {'username': username, 'password': password})
        
    # 5th attempt is a successful login
    print("Attempting successful login...")
    response = client.post('/accounts/login/', {'username': username, 'password': 'vvit@1234'})
    print(f"Success Login status: {response.status_code} (Redirect is expected)")
    
    # The attempts count in cache should be deleted now
    ip_key = "login_attempts_127.0.0.1"
    user_key = f"login_attempts_user_{username}"
    
    print(f"IP cache attempts: {cache.get(ip_key)}")
    print(f"User cache attempts: {cache.get(user_key)}")
    
    if cache.get(ip_key) is None and cache.get(user_key) is None:
        print("[SUCCESS] Successful login cleared brute-force attempt cache counters.")
    else:
        print("[FAILURE] Cache counters were not cleared!")

if __name__ == "__main__":
    run_tests()
