# daraja.py
import requests
from datetime import datetime
import base64
import os
from dotenv import load_dotenv

load_dotenv()

CONSUMER_KEY = os.getenv("DARAJA_CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("DARAJA_CONSUMER_SECRET")
BUSINESS_SHORTCODE = os.getenv("BUSINESS_SHORTCODE", "174379")
PASSKEY = os.getenv("PASSKEY")

def get_daraja_access_token():
    """Generates OAuth Bearer token from Safaricom Daraja API securely using environment variables."""
    url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    try:
        r = requests.get(url, auth=(CONSUMER_KEY, CONSUMER_SECRET), timeout=10)
        json_res = r.json()
        return json_res.get("access_token")
    except Exception as e:
        print(f"Token generation error: {e}")
        return None

def trigger_stk_push(phone_number: str, amount: int = 200):
    """Triggers an M-Pesa STK Push prompt on the client's phone."""
    access_token = get_daraja_access_token()
    if not access_token:
        return {"success": False, "message": "Failed to connect to Safaricom Daraja API."}

    url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    data_to_encode = BUSINESS_SHORTCODE + PASSKEY + timestamp
    password = base64.b64encode(data_to_encode.encode()).decode('utf-8')

    clean_phone = phone_number.strip()
    if clean_phone.startswith("0"):
        clean_phone = "254" + clean_phone[1:]
    elif clean_phone.startswith("+"):
        clean_phone = clean_phone[1:]

    payload = {
        "BusinessShortCode": BUSINESS_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": clean_phone,
        "PartyB": BUSINESS_SHORTCODE,
        "PhoneNumber": clean_phone,
        "CallBackURL": "https://mydomain.com/mpesa/callback",
        "AccountReference": "BiasharaPulseOS",
        "TransactionDesc": "Monthly Software Subscription"
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        res_json = response.json()
        
        if res_json.get("ResponseCode") == "0":
            return {
                "success": True, 
                "checkout_id": res_json.get("CheckoutRequestID"),
                "message": "STK Push successfully sent to phone!"
            }
        else:
            return {
                "success": False, 
                "message": res_json.get("errorMessage", "STK Push request rejected by Safaricom.")
            }
    except Exception as e:
        return {"success": False, "message": f"Connection Error: {str(e)}"}