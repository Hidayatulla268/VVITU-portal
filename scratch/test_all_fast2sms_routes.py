import urllib.request
import urllib.parse
import json

api_key = "djtql7uzQeUo6NyiExYM49wADPZR8cgJ0OpHBhbFITrKGWfk1SXgJxj03CoWE9mOe5yctDqVnh4IGbpK"
phone = "8121654552"

routes_to_test = [
    {"name": "Quick SMS (q)", "params": {"route": "q", "message": "VVITU Test SMS", "language": "english", "flash": "0", "numbers": phone}},
    {"name": "OTP Route (otp)", "params": {"route": "otp", "variables_values": "9.4 CGPA", "numbers": phone}},
    {"name": "DLT Route (dlt)", "params": {"route": "dlt", "sender_id": "TXTIND", "message": "12345", "numbers": phone}},
    {"name": "Bulk V2 GET", "url": f"https://www.fast2sms.com/dev/bulkV2?authorization={api_key}&route=q&message=VVITU%20Test&language=english&flash=0&numbers={phone}"},
]

print("============================================================")
print("  TESTING ALL FAST2SMS API ROUTES WITH YOUR API KEY")
print("============================================================")

for item in routes_to_test:
    name = item["name"]
    print(f"\n--- Testing: {name} ---")
    try:
        url = item.get("url", "https://www.fast2sms.com/dev/bulkV2")
        if "params" in item:
            data = urllib.parse.urlencode(item["params"]).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=data,
                headers={'authorization': api_key, 'Content-Type': 'application/x-www-form-urlencoded'},
                method='POST'
            )
        else:
            req = urllib.request.Request(url, headers={'authorization': api_key}, method='GET')

        with urllib.request.urlopen(req, timeout=10) as response:
            res_text = response.read().decode('utf-8')
            print(f"[{name} SUCCESS] Status Code: {response.status}")
            print(f"Response: {res_text}")
    except Exception as e:
        print(f"[{name} FAILED] {e}")
        if hasattr(e, 'read'):
            try:
                print("Error Details:", e.read().decode('utf-8'))
            except Exception:
                pass

print("\n============================================================")
