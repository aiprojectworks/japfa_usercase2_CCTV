
import os, json, requests
from dotenv import load_dotenv

# --- Load creds (.env) ---
load_dotenv(".env")
PHONE_NUMBER_ID = os.getenv("WA_PHONE_ID") or os.getenv("WHATSAPP_PHONE_ID")
ACCESS_TOKEN    = os.getenv("WA_TOKEN") or os.getenv("WHATSAPP_TOKEN")
TEMPLATE_NAME   = os.getenv("WA_TEMPLATE_NAME", "alert_template")  # exact name
LANG_CODE       = os.getenv("WA_TEMPLATE_LANG", "en")                   # must match approved translation

if not PHONE_NUMBER_ID or not ACCESS_TOKEN:
    raise ValueError("Set WA_PHONE_ID/WA_TOKEN (or WHATSAPP_PHONE_ID/WHATSAPP_TOKEN) in .env")

# --- Recipients (E.164 without '+') ---
RECIPIENTS = [
    "6596370843",
    # add more numbers...
]

# --- Sample body values (map to {{1}}..{{5}} in the template body) ---
DEFAULT_PARAMS = dict(
    case_id   = "96",                     # {{1}}
    time_sg   = "07/27/25 06:18 AM ",      # {{2}}
    area      = "KP2",                    # {{3}}
    section   = "Shower Area",            # {{4}}
    violation = "Shoes not in the rack"   # {{5}}
)

def send_violation_template(
    to: str,
    case_id: str,
    time_sg: str,
    area: str,
    section: str,
    violation: str,
    include_dynamic_url_button: bool = True
):
    """
    Sends the 'new_violation_detected' (or your TEMPLATE_NAME) template.
    If your template has a dynamic URL (…/{{1}}), keep include_dynamic_url_button=True
    so the Case ID is passed into the URL button.
    """
    components = [
        {
            "type": "body",
            "parameters": [
                {"type": "text", "text": case_id},
                {"type": "text", "text": time_sg},
                {"type": "text", "text": area},
                {"type": "text", "text": section},
                {"type": "text", "text": violation}
            ]
        }
    ]
    if include_dynamic_url_button:
        components.append({
            "type": "button",
            "sub_type": "url",
            "index": "0",
            "parameters": [{"type": "text", "text": case_id}]
        })

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": TEMPLATE_NAME,
            "language": {"code": LANG_CODE},
            "components": components
        }
    }

    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    r = requests.post(url, headers=headers, json=payload, timeout=30)

    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text}

    ok = 200 <= r.status_code < 300
    return ok, r.status_code, body

if __name__ == "__main__":
    for number in RECIPIENTS:
        ok, code, body = send_violation_template(number, **DEFAULT_PARAMS)
        print(f"{'SENT' if ok else 'FAILED'} → {number} [{code}]")
        print(json.dumps(body, indent=2))
