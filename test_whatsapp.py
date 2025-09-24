# send_violation_template.py
# pip install requests
import requests, json

# --- CONFIG: replace these ---
PHONE_NUMBER_ID = "815997364923803"
ACCESS_TOKEN     = "EAAKlsRsZCkqgBPXUZALkn6EgfP1mxY6HFi96xBmEZAtdyH3jbalSnXxRESiVNTb4hyYZB0JIn4SLw3ynOQgObxZCZCncSppClmm1SamioHWxeqtjkeIFwLJIS1Xc8kkzCDYiMtF30PRh9WuP0B8lDytqk291An05ONlCOaNZCDnKiQEkGkZC4HfTimKltb2FQpWcienwklxdAg0pG4NKqhS2pjWN27x3bUN3866BjAkpQqRovQZDZD"
TO_NUMBER        = "6596370843"                 # E.164
TEMPLATE_NAME    = "alert_template"     # exact template name
LANG_CODE        = "en"

# --- Sample payload values (map to {{1}}..{{5}} in body) ---
case_id   = "96"                  # {{1}}
time_sg   = "07/27/25 06:18 AM"   # {{2}}
area      = "KP2"                 # {{3}}
section   = "Shower Area"         # {{4}}
violation = "Shoes not in the rack"  # {{5}}

url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

payload = {
    "messaging_product": "whatsapp",
    "to": TO_NUMBER,
    "type": "template",
    "template": {
        "name": TEMPLATE_NAME,
        "language": {"code": LANG_CODE},
        "components": [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": case_id},
                    {"type": "text", "text": time_sg},
                    {"type": "text", "text": area},
                    {"type": "text", "text": section},
                    {"type": "text", "text": violation}
                ]
            },
            # Dynamic URL button: plugs case_id into .../{{1}} in your template URL
            {
                "type": "button",
                "sub_type": "url",
                "index": "0",
                "parameters": [
                    {"type": "text", "text": case_id}
                ]
            }
        ]
    }
}

resp = requests.post(url, headers=headers, json=payload, timeout=30)
print(resp.status_code)
try:
    data = resp.json()
    print(json.dumps(data, indent=2))
    if resp.status_code != 200:
        err = data.get("error", {})
        print(f"Error {err.get('code')} ({err.get('type')}): {err.get('message')}")
except Exception:
    print(resp.text)
