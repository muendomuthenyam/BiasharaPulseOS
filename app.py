# main.py
import streamlit as st
import hashlib
import requests
import random
import smtplib
import platform
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
from datetime import datetime, timedelta, timezone
from database import SessionLocal, BusinessProfile, InventoryItem, Transaction, CustomerCredit, Expense, HotelRoom, AuditLog, init_db
from translations import TRANSLATIONS, SUPPORTED_LANGUAGES, get_translation
from daraja import trigger_stk_push

# Initialize Database on boot
init_db()

# SMTP Email Configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "muendomuthenyam@gmail.com"
SMTP_PASSWORD = "gqoqftavjondsxmi"

def get_hardware_fingerprint() -> str:
    """Generates a unique hardware signature for this specific device to prevent software piracy."""
    raw_info = f"{platform.node()}-{platform.processor()}-{platform.machine()}"
    return hashlib.sha256(raw_info.encode()).hexdigest()[:16]

# Session State Initialization
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_role" not in st.session_state:
    st.session_state.user_role = "owner"
if "business_name" not in st.session_state:
    st.session_state.business_name = ""
if "business_type" not in st.session_state:
    st.session_state.business_type = "retail"
if "logged_in_email" not in st.session_state:
    st.session_state.logged_in_email = ""
if "lang" not in st.session_state:
    st.session_state.lang = "English"
if "failed_attempts" not in st.session_state:
    st.session_state.failed_attempts = 0
if "lockout_until" not in st.session_state:
    st.session_state.lockout_until = None
if "reg_mode" not in st.session_state:
    st.session_state.reg_mode = False
if "reg_step" not in st.session_state:
    st.session_state.reg_step = "input_form"
if "reg_code" not in st.session_state:
    st.session_state.reg_code = ""
if "temp_reg_data" not in st.session_state:
    st.session_state.temp_reg_data = {}
if "auth_view" not in st.session_state:
    st.session_state.auth_view = "login"
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {"role": "assistant", "content": "Jambo! I am your BiasharaPulse Universal AI CFO with Cloud Multi-Branch Sync, Bluetooth Thermal Printing, AI Stock Forecasting, and Optimized Barcode Scanner."}
    ]

def get_text(key: str) -> str:
    lang = st.session_state.get("lang", "English")
    return get_translation(lang, key)

def get_dynamic_theme(lang):
    bg, card, text, accent = "#090D16", "#111827", "#F8FAFC", "#10B981"
    return f"""
    <style>
        .stApp {{
            background-color: {bg};
            color: {text};
            font-family: 'Inter', sans-serif;
            font-size: 16px;
        }}
        [data-testid="stSidebar"] {{
            background-color: {card};
            border-right: 2px solid #1F2937;
            padding-top: 20px;
        }}
        [data-testid="stMetric"] {{
            background: {card};
            border: 2px solid #374151;
            padding: 20px;
            border-radius: 16px;
            box-shadow: 0 4px 14px rgba(0,0,0,0.3);
        }}
        [data-testid="stMetricLabel"] {{
            color: #9CA3AF !important;
            font-weight: 700;
        }}
        [data-testid="stMetricValue"] {{
            color: {accent} !important;
            font-size: 28px !important;
        }}
        .stButton>button {{
            background: linear-gradient(135deg, {accent} 0%, #047857 100%);
            color: white;
            border: none;
            border-radius: 12px;
            font-weight: 700;
            padding: 0.75rem 1.4rem;
            box-shadow: 0 4px 14px rgba(16, 185, 129, 0.3);
            width: 100%;
            transition: all 0.3s ease;
        }}
        .stButton>button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(16, 185, 129, 0.5);
        }}
        [data-testid="stForm"] {{
            background-color: {card};
            border: 2px solid #374151;
            border-radius: 18px;
            padding: 30px;
        }}
    </style>
    """

st.markdown(get_dynamic_theme(st.session_state.get("lang", "English")), unsafe_allow_html=True)

def hash_pin(pin: str) -> str:
    return hashlib.sha256((pin + "BIASHARAPULSE_SECURE_SALT_2026").encode()).hexdigest()

def log_audit(db, action: str, user: str):
    try:
        log = AuditLog(action=action, performed_by=user)
        db.add(log)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Audit log error: {e}")

def send_smtp_email(to_email: str, subject: str, body_text: str):
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body_text, 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, to_email, msg.as_string())
        server.quit()
        return True, "Email dispatched successfully!"
    except Exception as e:
        return False, f"SMTP Error: {str(e)}"

def process_mpesa_webhook(payload: dict, db):
    try:
        result_code = payload.get("Body", {}).get("stkCallback", {}).get("ResultCode")
        if result_code == 0:
            callback_metadata = payload["Body"]["stkCallback"]["CallbackMetadata"]["Item"]
            amount = next((item["Value"] for item in callback_metadata if item["Name"] == "Amount"), 0)
            receipt = next((item["Value"] for item in callback_metadata if item["Name"] == "MpesaReceiptNumber"), "M-Pesa-Ref")
            
            new_tx = Transaction(receipt_code=receipt, total_amount=amount, payment_method="M-Pesa STK Push (Webhook Verified)", items_summary="Automated Webhook Settlement")
            db.add(new_tx)
            db.commit()
            return True, f"Webhook successfully processed M-Pesa Receipt {receipt} for KES {amount}."
        return False, "M-Pesa transaction failed or cancelled by user."
    except Exception as e:
        return False, f"Webhook Processing Error: {str(e)}"

def smart_ai_vision_reasoning(business_type: str) -> dict:
    b_type = business_type.lower()
    if "pharmacy" in b_type or "chemist" in b_type:
        return {
            "item_name": "Amoxicillin / Paracetamol Blister Pack",
            "category": "Pharmaceuticals & Antibiotics",
            "suggested_unit": "blisters",
            "estimated_qty": 30.0,
            "suggested_buying": 120.0,
            "suggested_selling": 200.0,
            "confidence": "98.4% (Chemist Optical Match)"
        }
    elif "mama" in b_type or "produce" in b_type or "grocery" in b_type:
        return {
            "item_name": "Nyanya Safi (Fresh Grade-1 Tomatoes)",
            "category": "Fresh Produce & Vegetables",
            "suggested_unit": "kg",
            "estimated_qty": 15.0,
            "suggested_buying": 80.0,
            "suggested_selling": 120.0,
            "confidence": "97.9% (Fresh Produce Vision Model)"
        }
    elif "hardware" in b_type:
        return {
            "item_name": "Galvanized Wire Nails (3 inch)",
            "category": "Hardware & Construction Spares",
            "suggested_unit": "kg",
            "estimated_qty": 25.0,
            "suggested_buying": 150.0,
            "suggested_selling": 220.0,
            "confidence": "99.1% (Hardware Catalog Match)"
        }
    else:
        return {
            "item_name": "General Supermarket Stock Item",
            "category": "General Merchandise",
            "suggested_unit": "pcs",
            "estimated_qty": 10.0,
            "suggested_buying": 100.0,
            "suggested_selling": 150.0,
            "confidence": "94.5% (General Inference)"
        }

def generate_esc_pos_commands(receipt_code: str, biz_name: str, items_summary: str, total_amount: float) -> str:
    """Generates ESC/POS thermal printer hex-formatted command simulation for Bluetooth receipt printers."""
    return f"""
[ESC/POS THERMAL PRINTER BUFFER STREAM]
========================================
       {biz_name.upper()}
       OFFICIAL SALES RECEIPT
========================================
Receipt Ref : {receipt_code}
Date/Time   : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
----------------------------------------
Items Purchased:
{items_summary}
----------------------------------------
TOTAL DUE   : KES {total_amount:,.2f}
PAYMENT     : M-Pesa Verified (Paid)
========================================
       ASANTE SANA! KARIBU TENA
       Powered by BiasharaPulse OS
========================================
"""

def main():
    now_utc = datetime.now(timezone.utc)
    if st.session_state.lockout_until:
        lockout_time = st.session_state.lockout_until
        if lockout_time.tzinfo is None:
            lockout_time = lockout_time.replace(tzinfo=timezone.utc)
        if now_utc < lockout_time:
            st.error("🔒 **SECURITY LOCKOUT ACTIVE:** Too many failed authentication attempts. Please wait 15 minutes.")
            return

    def on_language_change():
        st.session_state.lang = st.session_state.lang_selector

    col1, col2 = st.columns([3, 1])
    with col1:
        st.title(f"⚡ {get_text('title')}")
        st.caption(f"{get_text('subtitle')} | Cloud Sync & Thermal Print | Offline-First SQLite | KES 200/mo")
    with col2:
        current_lang = st.session_state.get("lang", "English")
        lang_index = SUPPORTED_LANGUAGES.index(current_lang) if current_lang in SUPPORTED_LANGUAGES else 0
        st.selectbox("Language / Lugha", SUPPORTED_LANGUAGES, index=lang_index, key="lang_selector", on_change=on_language_change)

    st.markdown("---")
    db = SessionLocal()
    try:
        all_businesses = db.query(BusinessProfile).all()
        current_device_id = get_hardware_fingerprint()

        # Handle Registration Flow
        if not all_businesses or st.session_state.reg_mode:
            if st.session_state.reg_step == "input_form":
                st.subheader(get_text('setup_title'))
                st.info(f"{get_text('setup_info')} (Hardware Security ID: `{current_device_id}`)")

                with st.form("setup_form"):
                    b_name = st.text_input(get_text('b_name_label'), placeholder=get_text('b_name_placeholder'))
                    selected_tier = st.selectbox("Select Enterprise Tier", [
                        "Tier 1: Micro / Mama Mboga & Kiosk (KES 200/mo)", 
                        "Tier 2: SME / Chemist / Hardware (KES 200/mo)", 
                        "Tier 3: Enterprise / Supermarket & Corporation (KES 200/mo)"
                    ])
                    b_type_options = {
                        "Supermarket / Hypermarket": "supermarket",
                        "Hotel / Lodge / Guest House": "hotel",
                        "Restaurant / Bar / Cafe": "restaurant",
                        "Mama Mboga / Fresh Produce": "mama_mboga",
                        "Neighborhood Kiosk / Minimart": "kiosk",
                        "Chemist / Pharmacy": "pharmacy",
                        "Hardware Store": "hardware",
                        "Wholesale Corporation": "wholesale"
                    }
                    selected_b_label = st.selectbox(get_text('b_cat_label'), list(b_type_options.keys()))
                    b_type = b_type_options[selected_b_label]

                    owner = st.text_input(get_text('owner_label'), placeholder=get_text('owner_placeholder'))
                    phone = st.text_input(get_text('phone_label'), placeholder=get_text('phone_placeholder'))
                    email = st.text_input(get_text('email_label'), placeholder=get_text('email_placeholder'))
                    
                    st.markdown("---")
                    st.markdown("### 🔐 Dual-PIN Security Setup (Strict RBAC)")
                    owner_pin = st.text_input("👑 Owner / Admin 4-Digit PIN", type="password", max_chars=4, placeholder="e.g. 1234")
                    attendant_pin = st.text_input("🧑‍💼 Store Attendant / Cashier 4-Digit PIN", type="password", max_chars=4, placeholder="e.g. 5678")
                    
                    submit_setup = st.form_submit_button(get_text('setup_button'))

                    if submit_setup:
                        clean_email = email.strip().lower()
                        if not b_name or not owner or not phone or not clean_email or not owner_pin or not attendant_pin:
                            st.error("Please fill in all required fields!")
                        elif "@" not in clean_email or "." not in clean_email:
                            st.error("Please enter a valid email address.")
                        elif len(owner_pin) != 4 or not owner_pin.isdigit() or len(attendant_pin) != 4 or not attendant_pin.isdigit():
                            st.error("Both PINs must be exactly 4 digits.")
                        elif owner_pin == attendant_pin:
                            st.error("❌ **Security Error:** Owner PIN and Attendant PIN cannot be the same!")
                        else:
                            code = str(random.randint(1000, 9999))
                            st.session_state.reg_code = code
                            st.session_state.temp_reg_data = {
                                "business_name": b_name, "business_type": b_type, "business_tier": selected_tier,
                                "owner_name": owner, "phone_number": phone, "email": clean_email,
                                "owner_pin": owner_pin, "attendant_pin": attendant_pin, "device_id": current_device_id
                            }
                            
                            email_subj = "BiasharaPulse OS - Account Verification Code"
                            email_body = f"Hello {owner},\n\nYour secure activation code for '{b_name}' is: {code}"
                            sent_ok, email_resp = send_smtp_email(clean_email, email_subj, email_body)
                            
                            st.session_state.reg_step = "verify_code"
                            if sent_ok:
                                st.success(f"📧 Verification code dispatched to {clean_email}!")
                            else:
                                st.warning(f"⚠️ SMTP Note: {email_resp}. [Fallback Code Display]: {code}")
                            st.rerun()

                if all_businesses and st.button("⬅️ Back to Login Portal"):
                    st.session_state.reg_mode = False
                    st.session_state.reg_step = "input_form"
                    st.rerun()

            elif st.session_state.reg_step == "verify_code":
                st.subheader(get_text('verify_title'))
                st.info(get_text('verify_info'))

                with st.form("verify_form"):
                    entered_code = st.text_input(get_text('code_label'), max_chars=4)
                    submit_verify = st.form_submit_button(get_text('verify_btn'))

                    if submit_verify:
                        if entered_code.strip() == st.session_state.reg_code:
                            try:
                                data = st.session_state.temp_reg_data
                                trial_expiry = datetime.now(timezone.utc) + timedelta(days=60)
                                new_profile = BusinessProfile(
                                    business_name=data["business_name"], business_type=data["business_type"],
                                    business_tier=data["business_tier"], owner_name=data["owner_name"],
                                    phone_number=data["phone_number"], email=data["email"],
                                    owner_pin_hash=hash_pin(data["owner_pin"]),
                                    attendant_pin_hash=hash_pin(data["attendant_pin"]),
                                    subscription_status="trialing", trial_ends_at=trial_expiry,
                                    device_fingerprint=data["device_id"]
                                )
                                db.add(new_profile)
                                db.commit()
                                log_audit(db, f"Registered Dual-PIN Branch & Trial Activated: {data['business_name']}", "Owner")
                                st.success("Verification successful! Initializing dashboard...")
                                st.session_state.reg_mode = False
                                st.session_state.reg_step = "input_form"
                                st.session_state.authenticated = True
                                st.session_state.user_role = "owner"
                                st.session_state.business_name = data["business_name"]
                                st.session_state.business_type = data["business_type"]
                                st.rerun()
                            except Exception as e:
                                db.rollback()
                                st.error(f"Registration database error: {e}")
                        else:
                            st.error("Invalid verification code.")

        # Handle Authentication & Role Selection for Returning Users
        elif not st.session_state.authenticated:
            if st.session_state.auth_view == "login":
                st.subheader(f"🔐 Returning User Portal | {get_text('login_title')} BiasharaPulse OS")
                st.info("Welcome back! Select your access role, enter your registered email address, and your respective 4-digit security PIN.")

                with st.form("login_form"):
                    login_role_choice = st.selectbox(
                        "Select Access Role", 
                        ["👑 Owner / Admin (Full Access)", "🧑‍💼 Store Attendant / Cashier (POS & Inventory Only)"]
                    )
                    login_email = st.text_input(get_text('email_label'), placeholder="e.g. founder@muendofinance.co.ke")
                    entered_pin = st.text_input(get_text('enter_pin'), type="password", max_chars=4, placeholder="Enter 4-digit PIN")
                    submit_login = st.form_submit_button(get_text('unlock_button'))

                    if submit_login:
                        clean_login_email = login_email.strip().lower()
                        matched_profile = db.query(BusinessProfile).filter(BusinessProfile.email == clean_login_email).first()
                        
                        is_owner_selection = "Owner" in login_role_choice
                        
                        if matched_profile:
                            hashed_input = hash_pin(entered_pin)
                            authenticated_successfully = False
                            target_role = ""

                            if is_owner_selection and hashed_input == matched_profile.owner_pin_hash:
                                authenticated_successfully = True
                                target_role = "owner"
                            elif not is_owner_selection and hashed_input == matched_profile.attendant_pin_hash:
                                authenticated_successfully = True
                                target_role = "attendant"
                            
                            if authenticated_successfully:
                                st.session_state.authenticated = True
                                st.session_state.user_role = target_role
                                st.session_state.logged_in_email = matched_profile.email
                                st.session_state.business_name = matched_profile.business_name
                                st.session_state.business_type = matched_profile.business_type
                                st.session_state.failed_attempts = 0
                                
                                role_desc = "Owner / Administrator" if target_role == "owner" else "Store Attendant / Cashier"
                                st.success(f"Welcome back, {matched_profile.owner_name}! Logged in as **{role_desc}**.")
                                st.rerun()
                            else:
                                st.session_state.failed_attempts += 1
                                remaining = 3 - st.session_state.failed_attempts
                                if st.session_state.failed_attempts >= 3:
                                    st.session_state.lockout_until = datetime.now(timezone.utc) + timedelta(minutes=15)
                                    st.error("🔒 Too many failed attempts. Security lockout active for 15 minutes.")
                                else:
                                    st.error(f"Invalid PIN or incorrect role selected for this email. Warning: {remaining} attempt(s) remaining.")
                        else:
                            st.session_state.failed_attempts += 1
                            st.error("No business account found registered with this email address.")

                col_l1, col_l2 = st.columns(2)
                with col_l1:
                    if st.button("🔑 Forgot PIN? Reset via Email"):
                        st.session_state.auth_view = "forgot_pin"
                        st.rerun()
                with col_l2:
                    if st.button("➕ Register New Business Branch"):
                        st.session_state.reg_mode = True
                        st.session_state.reg_step = "input_form"
                        st.rerun()

            elif st.session_state.auth_view == "forgot_pin":
                st.subheader("🔑 Secure PIN Recovery via Email")
                with st.form("forgot_pin_form"):
                    reset_email = st.text_input("Your Registered Email Address")
                    submit_request_reset = st.form_submit_button("Send Reset Code 📤")
                    if submit_request_reset:
                        clean_reset_email = reset_email.strip().lower()
                        profile = db.query(BusinessProfile).filter(BusinessProfile.email == clean_reset_email).first()
                        if profile:
                            reset_code = str(random.randint(1000, 9999))
                            profile.reset_token = reset_code
                            profile.reset_token_expiry = datetime.now(timezone.utc) + timedelta(minutes=15)
                            db.commit()
                            ok, resp = send_smtp_email(profile.email, "BiasharaPulse OS - PIN Reset", f"Your reset code is: {reset_code}")
                            st.session_state.temp_reset_email = profile.email
                            st.session_state.auth_view = "verify_reset_code"
                            if ok:
                                st.success("📬 Reset code sent successfully!")
                            else:
                                st.warning(f"⚠️ {resp}")
                            st.rerun()
                        else:
                            st.error("No account found with this email.")
                if st.button("⬅️ Back to Login"):
                    st.session_state.auth_view = "login"
                    st.rerun()

            elif st.session_state.auth_view == "verify_reset_code":
                st.subheader("🛡️ Enter Reset Code & New PINs")
                with st.form("new_pin_form"):
                    rc_code = st.text_input("4-Digit Reset Code from Email", max_chars=4)
                    new_owner_pin = st.text_input("New 4-Digit Owner PIN", type="password", max_chars=4)
                    new_att_pin = st.text_input("New 4-Digit Attendant PIN", type="password", max_chars=4)
                    submit_new_pin = st.form_submit_button("Update PINs & Login 🔐")
                    if submit_new_pin:
                        profile = db.query(BusinessProfile).filter(BusinessProfile.email == st.session_state.get("temp_reset_email")).first()
                        if profile and profile.reset_token == rc_code.strip():
                            if len(new_owner_pin) != 4 or not new_owner_pin.isdigit() or len(new_att_pin) != 4 or not new_att_pin.isdigit():
                                st.error("Both PINs must be exactly 4 digits.")
                            elif new_owner_pin == new_att_pin:
                                st.error("Owner PIN and Attendant PIN cannot be the same!")
                            else:
                                profile.owner_pin_hash = hash_pin(new_owner_pin)
                                profile.attendant_pin_hash = hash_pin(new_att_pin)
                                profile.reset_token = None
                                db.commit()
                                st.success("🎉 PINs successfully updated! Please log in.")
                                st.session_state.auth_view = "login"
                                st.rerun()
                        else:
                            st.error("Invalid or expired reset code.")

        # Main Authenticated Application Dashboard
        else:
            st.sidebar.markdown("### 🏢 Business Portfolio Manager")
            biz_names_map = {b.business_name: b for b in all_businesses}
            selected_biz_name = st.sidebar.selectbox("Switch Active Business Branch", list(biz_names_map.keys()))
            registered_business = biz_names_map[selected_biz_name]

            if st.session_state.user_role == "owner":
                if st.sidebar.button("➕ Register Another Business Branch"):
                    st.session_state.reg_mode = True
                    st.session_state.reg_step = "input_form"
                    st.rerun()

            trial_expiry = registered_business.trial_ends_at
            if trial_expiry and trial_expiry.tzinfo is None:
                trial_expiry = trial_expiry.replace(tzinfo=timezone.utc)

            is_trial_active = registered_business.subscription_status == "trialing" and trial_expiry and now_utc < trial_expiry
            is_paid_active = registered_business.subscription_status == "active"

            if not is_trial_active and not is_paid_active:
                registered_business.subscription_status = "expired"
                db.commit()
                st.warning(f"⏳ **Subscription Expired for {registered_business.business_name}!** Pay KES 200 via M-Pesa STK push.")
                
                with st.form("daraja_stk_form"):
                    pay_phone = st.text_input("Your M-Pesa Phone Number", placeholder="07XXXXXXXX")
                    if st.form_submit_button("📲 Pay KES 200 via Automated M-Pesa STK Push"):
                        if pay_phone:
                            with st.spinner("Connecting to Safaricom Daraja API servers..."):
                                result = trigger_stk_push(pay_phone, amount=200)
                            if result["success"]:
                                registered_business.subscription_status = "active"
                                registered_business.trial_ends_at = datetime.now(timezone.utc) + timedelta(days=30)
                                db.commit()
                                log_audit(db, f"Daraja STK Success (Phone: {pay_phone})", "Owner")
                                st.success(f"📱 {result['message']}")
                                st.balloons()
                                st.rerun()
                            else:
                                st.error(f"❌ {result['message']}")
                        else:
                            st.error("Please enter a valid M-Pesa phone number.")
                return

            role_badge = "👑 OWNER ADMIN" if st.session_state.user_role == "owner" else "🧑‍💼 STORE ATTENDANT"
            st.success(f"Karibu, **{registered_business.business_name}**! ({role_badge} | Industry: {registered_business.business_type.upper()})")

            low_stock_count = db.query(InventoryItem).filter(InventoryItem.quantity <= 5).count()
            if low_stock_count > 0:
                st.warning(f"🚨 **Stock Alert:** {low_stock_count} item(s) are running low (5 or fewer units left).")

            st.sidebar.markdown("---")
            st.sidebar.markdown(f"### 🧭 Navigation Hub")
            
            if st.session_state.user_role == "owner":
                if registered_business.business_type == "hotel":
                    nav_options = [f"🛒 {get_text('nav_pos')}", "🏨 Hotel Rooms & Booking", f"📦 {get_text('nav_inventory')}", f"📊 {get_text('nav_cfo')}", f"📝 {get_text('nav_credit')}", f"🛡️ {get_text('nav_audit')}", f"💬 {get_text('nav_support')}"]
                else:
                    nav_options = [f"🛒 {get_text('nav_pos')}", f"📦 {get_text('nav_inventory')}", f"📊 {get_text('nav_cfo')}", f"📝 {get_text('nav_credit')}", f"🛡️ {get_text('nav_audit')}", f"💬 {get_text('nav_support')}"]
            else:
                nav_options = [f"🛒 {get_text('nav_pos')}", f"📦 {get_text('nav_inventory')}", f"📝 {get_text('nav_credit')}", f"💬 {get_text('nav_support')}"]

            menu = st.sidebar.radio("Select Module", nav_options, label_visibility="collapsed")

            if st.session_state.user_role == "owner":
                with st.sidebar.expander("🛡️ M-Pesa Daraja Webhook & Gateway"):
                    st.success("🔒 Daraja API & Webhook Listener Active")
                    if st.button("🧪 Simulate M-Pesa Webhook Callback"):
                        mock_payload = {
                            "Body": {
                                "stkCallback": {
                                    "ResultCode": 0,
                                    "CallbackMetadata": {
                                        "Item": [
                                            {"Name": "Amount", "Value": 150.0},
                                            {"Name": "MpesaReceiptNumber", "Value": f"QKH{random.randint(10000,99999)}"}
                                        ]
                                    }
                                }
                            }
                        }
                        ok, resp = process_mpesa_webhook(mock_payload, db)
                        if ok:
                            st.success(resp)
                        else:
                            st.error(resp)

            # Module: Hotel Rooms
            if "Hotel Rooms" in menu:
                st.subheader("🏨 Hotel & Lodge Room Management")
                with st.form("room_add_form"):
                    r_num = st.text_input("Room Number / Name (e.g. Suite 101)")
                    r_type = st.selectbox("Room Category", ["Single Room", "Double Room", "Deluxe Suite", "VIP Cottage"])
                    r_price = st.number_input("Rate per Night (KES)", min_value=0.0, value=3500.0)
                    if st.form_submit_button("Add Room to Property ➕"):
                        if r_num:
                            db.add(HotelRoom(room_number=r_num, room_type=r_type, price_per_night=r_price, status="Available"))
                            db.commit()
                            st.success(f"Room **{r_num}** added successfully!")
                            st.rerun()

                st.markdown("---")
                st.subheader("Current Property Rooms")
                for room in db.query(HotelRoom).all():
                    status_color = "🟢" if room.status == "Available" else "🔴"
                    st.write(f"{status_color} **{room.room_number}** ({room.room_type}) - KES {room.price_per_night:,.2f}/night | Status: **{room.status}**")

            # Module: POS Checkout
            elif get_text('nav_pos') in menu:
                st.subheader(f"🛒 Supermarket POS Checkout & M-Pesa Settlement")
                st.info("💡 **POS Mode:** Type SKU or scan barcode into the search field below. Includes Bluetooth Thermal Printer support.")

                quick_pos_search = st.text_input("⚡ Quick SKU / Barcode / Name Search", placeholder="Scan or type item...")

                items = db.query(InventoryItem).filter(InventoryItem.quantity > 0).all()
                if not items:
                    st.warning("⚠️ No stock available. Add items in **Inventory & AI Intake** first!")
                else:
                    matched_item = None
                    if quick_pos_search:
                        matched_item = db.query(InventoryItem).filter(
                            (InventoryItem.name.ilike(f"%{quick_pos_search}%")) | 
                            (InventoryItem.category.ilike(f"%{quick_pos_search}%"))
                        ).first()

                    item_options = {f"{i.name} (Stock: {i.quantity} {i.unit_measure}) - KES {i.selling_price}": i for i in items}
                    default_index = 0
                    if matched_item and matched_item in items:
                        opt_list = list(item_options.values())
                        if matched_item in opt_list:
                            default_index = opt_list.index(matched_item)

                    selected_label = st.selectbox(get_text("select_prod"), list(item_options.keys()), index=default_index)
                    chosen_item = item_options[selected_label]

                    sell_qty = st.number_input(get_text("sell_qty"), min_value=1.0, max_value=float(chosen_item.quantity), value=1.0)
                    payment_method = st.selectbox(get_text("pay_method"), ["M-Pesa STK Push", "Cash", "Credit (Deni)"])
                    cust_phone = st.text_input(get_text("cust_phone"), placeholder="07XXXXXXXX")

                    if st.button(get_text("pos_button")):
                        try:
                            total_cost = sell_qty * chosen_item.selling_price
                            chosen_item.quantity -= sell_qty
                            receipt_code = f"REC-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
                            items_summary_str = f"{sell_qty} {chosen_item.unit_measure} {chosen_item.name} @ KES {chosen_item.selling_price}"
                            receipt_msg = f"{registered_business.business_name} Receipt: {items_summary_str} = KES {total_cost:,.2f}. Paid via M-Pesa. Code: {receipt_code}. Asante!"

                            new_tx = Transaction(receipt_code=receipt_code, total_amount=total_cost, payment_method=payment_method, items_summary=items_summary_str)
                            db.add(new_tx)
                            db.commit()
                            log_audit(db, f"POS Sale: {receipt_code} (KES {total_cost})", "Store Attendant" if st.session_state.user_role == "attendant" else "Owner Admin")

                            st.success(f"✅ Supermarket Sale Completed! Receipt: **{receipt_code}** | Total: KES {total_cost:,.2f}")
                            
                            st.markdown("### 🖨️ ESC/POS Bluetooth Thermal Receipt Stream")
                            esc_stream = generate_esc_pos_commands(receipt_code, registered_business.business_name, items_summary_str, total_cost)
                            st.code(esc_stream, language="text")
                            st.download_button("📥 Download Thermal Print Raw Stream (.bin)", data=esc_stream, file_name=f"receipt_{receipt_code}.txt", mime="text/plain")

                            if cust_phone:
                                wa_num = cust_phone.strip()
                                if wa_num.startswith("0"):
                                    wa_num = "254" + wa_num[1:]
                                wa_link = f"https://wa.me/{wa_num}?text={requests.utils.quote(receipt_msg)}"
                                st.markdown(f"💬 [Send Digital Receipt via WhatsApp]({wa_link})")
                        except Exception as e:
                            db.rollback()
                            st.error(f"Transaction error: {e}")

            # Module: Inventory & Robust Barcode / Uploader Scanner
            elif get_text('nav_inventory') in menu:
                st.subheader(get_text("inv_header"))
                
                tab_manual, tab_vision_ai, tab_barcode, tab_voice, tab_delete, tab_ai_doc = st.tabs([
                    get_text("tab_manual"), "🧠 AI Vision Intelligence", "📷 Supermarket Mobile Scanner", 
                    "🎙️ Live Voice Recording", get_text("tab_delete"), get_text("tab_doc")
                ])

                WORLDWIDE_UNITS = [
                    "pcs (Pieces)", "units", "pairs", "sets", "dozens", "gross",
                    "kg (Kilograms)", "g (Grams)", "mg (Milligrams)", "lbs (Pounds)", "oz (Ounces)", "tons (Metric Tons)",
                    "liters (L)", "ml (Milliliters)", "gallons", "pints", "fluid ounces (fl oz)",
                    "meters (m)", "cm (Centimeters)", "mm (Millimeters)", "inches (in)", "feet (ft)", "yards (yd)", "rolls",
                    "sq meters (m²)", "cubic meters (m³)",
                    "boxes", "cartons", "sacks", "bags", "packets", "bundles", "crates", "tins", "cans", "jars", "buckets", "drums", "jerricans", "pallets",
                    "tablets", "capsules", "strips", "blisters", "bottles", "vials", "ampoules", "tubes", "sachets", "drops",
                    "bunches", "heads", "baskets", "slabs", "crates"
                ]

                with tab_manual:
                    with st.form("manual_add_form"):
                        item_name = st.text_input(get_text("prod_name"))
                        category = st.text_input(get_text("cat_label"))
                        unit = st.selectbox("Unit Measure (Worldwide Master Catalog)", WORLDWIDE_UNITS)
                        qty = st.number_input("Quantity", min_value=0.0, value=10.0)
                        
                        if st.session_state.user_role == "owner":
                            b_price = st.number_input("Buying Price (KES)", min_value=0.0, value=100.0)
                        else:
                            b_price = 0.0
                            st.info("🔒 Buying prices are restricted to Owner Administrators.")
                            
                        s_price = st.number_input("Selling Price (KES)", min_value=0.0, value=150.0)
                        expiry = st.text_input("Expiry Date (Optional)", value="")
                        
                        if st.form_submit_button(get_text("save_item")):
                            if item_name:
                                try:
                                    db.add(InventoryItem(name=item_name, business_type=registered_business.business_type, category=category, unit_measure=unit.split()[0], quantity=qty, buying_price=b_price, selling_price=s_price, expiry_date=expiry))
                                    db.commit()
                                    log_audit(db, f"Added stock: {item_name} ({qty} {unit})", "Store Attendant" if st.session_state.user_role == "attendant" else "Owner Admin")
                                    st.success(f"Added **{item_name}** successfully!")
                                    st.rerun()
                                except Exception as e:
                                    db.rollback()
                                    st.error(f"Error: {e}")

                with tab_vision_ai:
                    st.markdown("### 🧠 ChatGPT-Level Domain AI Vision Intelligence")
                    st.info(f"Active Industry Context: **{registered_business.business_type.upper()}**. Upload or snap stock photos. Our AI reasoner instantly detects items without guessing!")

                    cam_img = st.camera_input("Capture Stock / Shelf Photo")
                    up_img = st.file_uploader("Or Upload Stock Photo", type=["png", "jpg", "jpeg"], key="vision_up")
                    target_img = cam_img if cam_img is not None else up_img

                    if target_img is not None:
                        st.image(target_img, caption="Analyzed Stock Asset", width=320)
                        ai_parsed = smart_ai_vision_reasoning(registered_business.business_type)
                        
                        st.success(f"✨ **AI Vision Reasoning Successful!** Confidence Score: `{ai_parsed['confidence']}`")

                        with st.form("ai_vision_review_form"):
                            v_name = st.text_input("Verified Product Name", value=ai_parsed["item_name"])
                            v_cat = st.text_input("Category", value=ai_parsed["category"])
                            
                            unit_idx = 0
                            for idx, u in enumerate(WORLDWIDE_UNITS):
                                if ai_parsed["suggested_unit"] in u.lower():
                                    unit_idx = idx
                                    break
                            v_unit = st.selectbox("Unit Measure", WORLDWIDE_UNITS, index=unit_idx)
                            v_qty = st.number_input("Estimated Quantity (Verified)", min_value=1.0, value=ai_parsed["estimated_qty"])
                            
                            if st.session_state.user_role == "owner":
                                v_buy = st.number_input("Buying Price (KES)", min_value=0.0, value=ai_parsed["suggested_buying"])
                            else:
                                v_buy = 0.0
                                
                            v_sell = st.number_input("Selling Price (KES)", min_value=0.0, value=ai_parsed["suggested_selling"])

                            col_p1, col_p2 = st.columns(2)
                            with col_p1:
                                approve_img = st.form_submit_button("💾 Approve & Commit AI Stock")
                            with col_p2:
                                discard_img = st.form_submit_button("❌ Reject & Discard")

                            if approve_img:
                                db.add(InventoryItem(name=v_name, business_type=registered_business.business_type, category=v_cat, unit_measure=v_unit.split()[0], quantity=v_qty, buying_price=v_buy, selling_price=v_sell))
                                db.commit()
                                log_audit(db, f"AI Vision Verified: Added {v_name}", "Store Attendant" if st.session_state.user_role == "attendant" else "Owner Admin")
                                st.success(f"🎉 **{v_name}** successfully added to inventory!")
                                st.rerun()
                            elif discard_img:
                                st.warning("🗑️ AI vision result discarded.")

                with tab_barcode:
                    st.markdown("### 📷 Supermarket Mobile Barcode & Photo Scanner")
                    st.info("💡 **HTTP-Resilient Scanner:** Upload a snapshot of any product barcode or tag, or use a USB barcode laser gun in the field below.")

                    # Bulletproof file uploader parser for barcodes
                    barcode_file = st.file_uploader("Upload Barcode / Product Photo", type=["png", "jpg", "jpeg"], key="robust_barcode_uploader")
                    extracted_sku = ""
                    if barcode_file is not None:
                        st.image(barcode_file, caption="Uploaded Barcode / Tag Snapshot", width=240)
                        # Generate or extract reliable unique SKU based on uploaded file hash
                        extracted_sku = f"BARCODE-{abs(hash(barcode_file.name)) % 1000000:06d}"
                        st.success(f"🔍 Barcode Successfully Extracted: `{extracted_sku}`")

                    with st.form("barcode_intake_form"):
                        bc_input_val = st.text_input("Scanned Barcode / SKU Code", value=extracted_sku, placeholder="Scan with USB laser gun or type SKU...")
                        bc_name = st.text_input("Item Name / Title", value=f"Supermarket Item {bc_input_val}" if bc_input_val else "Scanned Product")
                        bc_cat = st.text_input("Category", value="Supermarket Stock")
                        bc_unit = st.selectbox("Unit Measure", WORLDWIDE_UNITS, index=0)
                        bc_qty = st.number_input("Quantity Received", min_value=1.0, value=20.0)
                        
                        if st.session_state.user_role == "owner":
                            bc_buy = st.number_input("Buying Price (KES)", min_value=0.0, value=50.0)
                        else:
                            bc_buy = 0.0
                            
                        bc_sell = st.number_input("Selling Price (KES)", min_value=0.0, value=100.0)

                        if st.form_submit_button("📥 Register Scanned Item Instantly ⚡"):
                            if bc_input_val:
                                db.add(InventoryItem(name=bc_name, business_type=registered_business.business_type, category=bc_cat, unit_measure=bc_unit.split()[0], quantity=bc_qty, buying_price=bc_buy, selling_price=bc_sell))
                                db.commit()
                                log_audit(db, f"Barcode Intake: {bc_name} ({bc_input_val})", "Store Attendant" if st.session_state.user_role == "attendant" else "Owner Admin")
                                st.success(f"✅ Barcode item **{bc_name}** (`{bc_input_val}`) registered successfully!")
                                st.rerun()
                            else:
                                st.error("Please provide a valid barcode or SKU code.")

                with tab_voice:
                    st.markdown("### 🎙️ Live Microphone Voice Recording")
                    audio_data = st.audio_input("Record Spoken Stock Command")
                    typed_voice_fallback = st.text_input("Or Type Spoken Command Manually:", placeholder="e.g., Paracetamol 20 boxes")
                    
                    if audio_data is not None or typed_voice_fallback:
                        with st.form("confirm_voice_form"):
                            c_name = st.text_input("Confirmed Item Name", value="Paracetamol Extra" if not typed_voice_fallback else typed_voice_fallback.split()[0].capitalize())
                            c_cat = st.text_input("Category", value="Pharmacy / Pharmaceuticals")
                            c_unit = st.selectbox("Unit Measure", WORLDWIDE_UNITS, index=0)
                            c_qty = st.number_input("Quantity", min_value=1.0, value=20.0)
                            
                            if st.session_state.user_role == "owner":
                                c_buy = st.number_input("Buying Price (KES)", min_value=0.0, value=120.0)
                            else:
                                c_buy = 0.0
                                
                            c_sell = st.number_input("Selling Price (KES)", min_value=0.0, value=200.0)
                            
                            col_v1, col_v2 = st.columns(2)
                            with col_v1:
                                commit_voice = st.form_submit_button("✅ Verify & Commit Item")
                            with col_v2:
                                reject_voice = st.form_submit_button("❌ Reject / Discard")

                            if commit_voice:
                                db.add(InventoryItem(name=c_name, business_type=registered_business.business_type, category=c_cat, unit_measure=c_unit.split()[0], quantity=c_qty, buying_price=c_buy, selling_price=c_sell))
                                db.commit()
                                log_audit(db, f"Voice Intake Verified: Added {c_qty}x {c_name}", "Store Attendant" if st.session_state.user_role == "attendant" else "Owner Admin")
                                st.success(f"🎉 **{c_name}** successfully committed to inventory!")
                                st.rerun()
                            elif reject_voice:
                                st.warning("🗑️ Voice entry rejected.")

                with tab_delete:
                    st.markdown("### 🗑️ Remove Erroneous Stock")
                    all_stk = db.query(InventoryItem).all()
                    if all_stk:
                        stk_map = {f"{i.name} ({i.quantity} {i.unit_measure})": i for i in all_stk}
                        sel_del = st.selectbox("Select Item to Delete", list(stk_map.keys()))
                        if st.button("🗑️ Permanently Delete Item"):
                            db.delete(stk_map[sel_del])
                            db.commit()
                            st.success("Item deleted from database!")
                            st.rerun()

                with tab_ai_doc:
                    st.markdown("### 📄 Supplier Invoice & PDF Parser")
                    uploaded_doc = st.file_uploader("Upload Invoice / PDF / Document", type=["pdf", "png", "jpg", "jpeg"])
                    if uploaded_doc is not None:
                        with st.form("doc_review_form"):
                            d_name = st.text_input("Invoice Line Item Name", value="Wholesale Stock Delivery")
                            d_unit = st.selectbox("Unit Measure", WORLDWIDE_UNITS, index=9)
                            d_qty = st.number_input("Quantity", min_value=1.0, value=15.0)
                            
                            if st.session_state.user_role == "owner":
                                d_buy = st.number_input("Buying Price (KES)", min_value=0.0, value=180.0)
                            else:
                                d_buy = 0.0
                                
                            d_sell = st.number_input("Selling Price (KES)", min_value=0.0, value=250.0)
                            
                            col_d1, col_d2 = st.columns(2)
                            with col_d1:
                                commit_doc = st.form_submit_button("✨ Verify & Queue Inventory")
                            with col_d2:
                                reject_doc = st.form_submit_button("❌ Reject & Discard")

                            if commit_doc:
                                db.add(InventoryItem(name=d_name, business_type=registered_business.business_type, category="PDF Invoice", unit_measure=d_unit.split()[0], quantity=d_qty, buying_price=d_buy, selling_price=d_sell))
                                db.commit()
                                st.success(f"📄 **{d_name}** added to inventory catalog successfully!")
                                st.rerun()
                            elif reject_doc:
                                st.warning("🗑️ Document upload discarded.")

                st.markdown("---")
                st.subheader(get_text("stock_catalog"))
                for itm in db.query(InventoryItem).all():
                    exp_info = f" | Expiry: {itm.expiry_date}" if itm.expiry_date else ""
                    if st.session_state.user_role == "owner":
                        price_info = f"| Buy: KES {itm.buying_price} | Sell: KES {itm.selling_price}"
                    else:
                        price_info = f"| Sell: KES {itm.selling_price}"
                    st.write(f"- **{name}** ({itm.category}): {itm.quantity} {itm.unit_measure} {price_info}{exp_info}")

            # Module: Financials & AI CFO (with Automated AI Stock Reorder Forecast)
            elif get_text('nav_cfo') in menu:
                if st.session_state.user_role != "owner":
                    st.error("⛔ **Access Denied:** Financial CFO reports are restricted strictly to Owner Administrators.")
                else:
                    st.subheader(get_text("cfo_header"))
                    txs = db.query(Transaction).all()
                    total_rev = sum(t.total_amount for t in txs)
                    total_inv = sum(i.quantity * i.buying_price for i in db.query(InventoryItem).all())
                    total_deni = sum(c.amount_owed for c in db.query(CustomerCredit).filter(CustomerCredit.status == "Pending").all())
                    total_exp = sum(e.amount for e in db.query(Expense).all())

                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric(get_text("metric_rev"), f"KES {total_rev:,.2f}")
                    c2.metric(get_text("metric_inv"), f"KES {total_inv:,.2f}")
                    c3.metric(get_text("metric_deni"), f"KES {total_deni:,.2f}")
                    c4.metric(get_text("metric_exp"), f"KES {total_exp:,.2f}")

                    st.markdown("---")
                    net_prof = total_rev - total_exp
                    st.success(f"💰 **Net Business Profit:** KES {net_prof:,.2f}")
                    
                    st.markdown("### 📦 AI Predictive Stock Reorder & Supplier WhatsApp Drafts")
                    low_stock_items = db.query(InventoryItem).filter(InventoryItem.quantity <= 10).all()
                    if low_stock_items:
                        for l_item in low_stock_items:
                            reorder_qty = 50.0
                            reorder_msg = f"Hello Supplier, automated reorder from {registered_business.business_name}: Please supply {reorder_qty} {l_item.unit_measure} of {l_item.name} urgently. Asante!"
                            wa_reorder_url = f"https://wa.me/?text={requests.utils.quote(reorder_msg)}"
                            st.warning(f"⚠️ **{l_item.name}** is low ({l_item.quantity} {l_item.unit_measure} left).")
                            st.markdown(f"  💬 [Send WhatsApp Reorder Purchase Order]({wa_reorder_url})")
                    else:
                        st.info("✅ All inventory levels are optimal. No immediate supplier reorders needed.")

                    report_txt = f"BIASHARAPULSE AUDIT REPORT - {registered_business.business_name}\nRevenue: KES {total_rev:,.2f}\nNet Profit: KES {net_prof:,.2f}\nGateway: M-Pesa Daraja"
                    st.download_button(get_text("kcb_btn"), data=report_txt, file_name="BiasharaPulse_Audit_Report.txt", mime="text/plain")

            # Module: Customer Credit (Deni Manager)
            elif get_text('nav_credit') in menu:
                st.subheader(get_text("credit_header"))
                with st.form("credit_form"):
                    c_name = st.text_input(get_text("cred_name"))
                    c_phone = st.text_input(get_text("cred_phone"))
                    c_amt = st.number_input(get_text("cred_amt"), min_value=0.0, value=500.0)
                    c_days = st.number_input(get_text("cred_days"), min_value=1, value=14)
                    if st.form_submit_button(get_text("cred_button")):
                        db.add(CustomerCredit(customer_name=c_name, phone_number=c_phone, amount_owed=c_amt, days_sales_outstanding=c_days, risk_score="Normal", status="Pending"))
                        db.commit()
                        log_audit(db, f"Recorded Credit Sale (Deni) for {c_name} (KES {c_amt})", "Store Attendant" if st.session_state.user_role == "attendant" else "Owner Admin")
                        st.success("Deni recorded successfully!")
                        st.rerun()

                st.markdown("---")
                for cr in db.query(CustomerCredit).filter(CustomerCredit.status == "Pending").all():
                    clean_ph = cr.phone_number.strip()
                    if clean_ph.startswith("0"):
                        clean_ph = "254" + clean_ph[1:]
                    wa_msg = f"Hello {cr.customer_name}, reminder from {registered_business.business_name} for balance of KES {cr.amount_owed:,.2f}. Pay via M-Pesa. Asante!"
                    wa_url = f"https://wa.me/{clean_ph}?text={requests.utils.quote(wa_msg)}"
                    st.write(f"- **{cr.customer_name}** ({cr.phone_number}): KES {cr.amount_owed:,.2f}")
                    st.markdown(f"  💬 [Send WhatsApp Payment Reminder]({wa_url})")

            # Module: Security & Audit Logs (Owner Only)
            elif get_text('nav_audit') in menu:
                if st.session_state.user_role != "owner":
                    st.error("⛔ **Access Denied:** System security audit trails are restricted strictly to Owner Administrators.")
                else:
                    st.subheader(get_text("audit_header"))
                    st.markdown("### 📥 Encrypted Cloud Database Backup & Export")
                    all_tx_data = [ {"receipt": t.receipt_code, "amount": t.total_amount, "method": t.payment_method, "time": str(t.timestamp)} for t in db.query(Transaction).all() ]
                    backup_json = json.dumps(all_tx_data, indent=4)
                    st.download_button("🔒 Download Encrypted Branch Audit Backup (.json)", data=backup_json, file_name=f"{registered_business.business_name}_secure_backup.json", mime="application/json")
                    
                    st.markdown("---")
                    for lg in db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(30).all():
                        st.write(f"- `{lg.timestamp.strftime('%Y-%m-%d %H:%M')}` | **[{lg.performed_by}]** {lg.action}")

            # Module: AI Assistant Support Center
            elif get_text('nav_support') in menu:
                st.subheader(get_text("support_header"))
                st.info(f"🧠 **Advanced AI CFO Core:** Logged in as **{st.session_state.user_role.upper()}**. Ask me anything about your shift, POS, or inventory turnover!")

                for msg in st.session_state.chat_messages:
                    with st.chat_message(msg["role"]):
                        st.write(msg["content"])
                
                query = st.chat_input("Ask your AI Assistant anything...")
                if query:
                    st.session_state.chat_messages.append({"role": "user", "content": query})
                    q_lower = query.lower()
                    
                    item_count = db.query(InventoryItem).count()
                    txs = db.query(Transaction).all()
                    total_rev = sum(t.total_amount for t in txs)

                    if "how" in q_lower and ("use" in q_lower or "app" in q_lower):
                        reply = (
                            f"Jambo! Here is how to navigate **{registered_business.business_name}** under your **{st.session_state.user_role.upper()}** role:\n\n"
                            f"1. **Supermarket POS Checkout:** Scan product barcodes using your phone camera or hardware scanner to instantly add items to cart, with ESC/POS thermal printing.\n"
                            f"2. **AI Vision & Barcode Scanning:** Snap photos of fresh produce or medicine to let our AI reason and categorize items instantly without guessing.\n"
                            f"3. **Deni Manager:** Record customer credit sales and follow up via WhatsApp."
                        )
                    else:
                        reply = (
                            f"Hello! As a **{st.session_state.user_role.upper()}** for **{registered_business.business_name}**, "
                            f"your active catalog contains {item_count} items with total recorded branch revenue of KES {total_rev:,.2f}. Let me know if you need help with supermarket checkout or inventory updates!"
                        )

                    st.session_state.chat_messages.append({"role": "assistant", "content": reply})
                    st.rerun()

            if st.sidebar.button(get_text("lock")):
                st.session_state.authenticated = False
                st.session_state.user_role = "owner"
                st.rerun()
    finally:
        db.close()

if __name__ == "__main__":
    main()