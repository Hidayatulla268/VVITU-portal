import json
import urllib.request
import urllib.parse

api_key = "djtql7uzQeUo6NyiExYM49wADPZR8cgJ0OpHBhbFITrKGWfk1SXgJxj03CoWE9mOe5yctDqVnh4IGbpK"
phone = "8121654552"
msg = "VVITU Portal: Test result SMS notification"

print("--- Testing Fast2SMS Route 'q' (Quick SMS) ---")
try:
    url = "https://www.fast2sms.com/dev/bulkV2"
    data = urllib.parse.urlencode({
        'route': 'q',
        'message': msg,
        'language': 'english',
        'flash': '0',
        'numbers': phone
    }).encode('utf-8')

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            'authorization': api_key,
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        print("HTTP Status Code:", response.status)
        print("Response Body:", response.read().decode('utf-8'))
except Exception as e:
    print("Error with route 'q':", e)
    if hasattr(e, 'read'):
        print("Error details:", e.read().decode('utf-8'))

print("\n--- Testing Fast2SMS Route 'otp' ---")
try:
    url = "https://www.fast2sms.com/dev/bulkV2"
    data = urllib.parse.urlencode({
        'variables_values': '9.4 CGPA',
        'route': 'otp',
        'numbers': phone
    }).encode('utf-8')

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            'authorization': api_key,
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        print("HTTP Status Code:", response.status)
        print("Response Body:", response.read().decode('utf-8'))
except Exception as e:
    print("Error with route 'otp':", e)
