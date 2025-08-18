import os
from dotenv import load_dotenv

# WhatsApp Cloud API via pywa
from pywa import WhatsApp

# Load credentials from environment variables (adjust path if needed)
load_dotenv("../.env")

# Expect WhatsApp Cloud API creds
WA_PHONE_ID = os.getenv("WA_PHONE_ID") or os.getenv("WHATSAPP_PHONE_ID") or ""
WA_TOKEN = os.getenv("WA_TOKEN") or os.getenv("WHATSAPP_TOKEN") or ""
print(WA_PHONE_ID)
print(WA_TOKEN)
if not WA_PHONE_ID or not WA_TOKEN:
    raise ValueError("WA_PHONE_ID/WA_TOKEN (or WHATSAPP_PHONE_ID/WHATSAPP_TOKEN) must be set in .env file")

# Example chat IDs (numeric only, country code + number)
CHAT_IDS = [
    "6581899220",
    # Add more phone numbers as needed (no +, include country code)
]

def send_message_to_multiple_chats(message: str, chat_ids):
    wa = WhatsApp(phone_id=WA_PHONE_ID, token=WA_TOKEN)
    for chat_id in chat_ids:
        to_number = str(chat_id)
        try:
            wa.send_message(to=to_number, text=message)
            print(f"Sent to {to_number}")
        except Exception as e:
            print(f"Failed to send to {to_number}: {e}")

if __name__ == "__main__":
    example_message = "Hello! This is a test message sent to multiple WhatsApp numbers via pywa."
    send_message_to_multiple_chats(example_message, CHAT_IDS)
