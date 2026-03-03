"""
UK IMD Enrichment Portal - Hybrid Version (app3.py)
Supports all UK regions: England (IMD 2025), Scotland (SIMD 2020), Wales (WIMD 2019), Northern Ireland (NIMDM 2017)
"""
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import plotly.express as px
import urllib.parse
import datetime
import requests
import time
import io
import contextlib
import pyodbc
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
import json
import os
import statistics
from collections import Counter

# H3 Hexagon imports
try:
    import h3
    import geopandas as gpd
    from shapely.geometry import Polygon
    from scipy import stats as scipy_stats
    H3_AVAILABLE = True
except ImportError:
    H3_AVAILABLE = False

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="IMD Intelligence Portal", page_icon="🇬🇧", layout="wide")

# --- SESSION TIMEOUT CONFIGURATION ---
if 'last_activity' not in st.session_state:
    st.session_state['last_activity'] = datetime.datetime.now()

if st.session_state.get('password_correct', False):
    current_time = datetime.datetime.now()
    time_diff = (current_time - st.session_state.get('last_activity', current_time)).total_seconds()
    
    if time_diff > 3600:  # 1 hour timeout
        st.warning("⏱️ Session expired due to inactivity. Please login again.")
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.stop()
    
    st.session_state['last_activity'] = current_time

# --- EMAIL CONFIGURATION ---
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_ADDRESS = "realbirthimdapp@gmail.com"
EMAIL_PASSWORD = "cxso stwg rlwh nljo"

# --- USER CREDENTIALS ---
AUTHORIZED_USERS = {
    "kirsti": {"email": "kirsti@therealbirthcompanyltd.com", "password_hash": "ecd71870d1963316a97e3ac3408c9835ad8cf0f3c1bc703527c30265534f75ae", "last_password_change": None},
    "dan": {"email": "dan@realbirthcompany.com", "password_hash": "ecd71870d1963316a97e3ac3408c9835ad8cf0f3c1bc703527c30265534f75ae", "last_password_change": None},
    "sarah": {"email": "sarah.price@therealbirthcompanyltd.com", "password_hash": "ecd71870d1963316a97e3ac3408c9835ad8cf0f3c1bc703527c30265534f75ae", "last_password_change": None},
    "joao": {"email": "joao@27webmanagement.com", "password_hash": "ecd71870d1963316a97e3ac3408c9835ad8cf0f3c1bc703527c30265534f75ae", "last_password_change": None},
    "zoe": {"email": "zoe@therealbirthcompanyltd.com", "password_hash": "ecd71870d1963316a97e3ac3408c9835ad8cf0f3c1bc703527c30265534f75ae", "last_password_change": None},
    "lamin": {"email": "admin@therealbirthcompanyltd.com", "password_hash": "ecd71870d1963316a97e3ac3408c9835ad8cf0f3c1bc703527c30265534f75ae", "last_password_change": None}
}

USER_DATA_FILE = "user_credentials.json"

def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as f:
            return json.load(f)
    else:
        save_user_data(AUTHORIZED_USERS)
        return AUTHORIZED_USERS

def save_user_data(data):
    data_copy = {}
    for username, info in data.items():
        data_copy[username] = info.copy()
        if info.get('last_password_change'):
            if isinstance(info['last_password_change'], datetime.datetime):
                data_copy[username]['last_password_change'] = info['last_password_change'].isoformat()
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(data_copy, f, indent=2)

def check_password_expiry(username):
    users = load_user_data()
    last_change = users[username].get('last_password_change')
    if not last_change:
        return True
    if isinstance(last_change, str):
        last_change = datetime.datetime.fromisoformat(last_change)
    days_since_change = (datetime.datetime.now() - last_change).days
    return days_since_change >= 90

def update_user_password(username, new_password):
    users = load_user_data()
    users[username]['password_hash'] = hashlib.sha256(new_password.encode()).hexdigest()
    users[username]['last_password_change'] = datetime.datetime.now()
    save_user_data(users)

def send_email_code(recipient_email, code):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = recipient_email
        msg['Subject'] = "IMD Portal - Your Login Code"
        body = f"""
        <html><body style="font-family: Arial, sans-serif;">
            <h2 style="color: #2c3e50;">🇬🇧 IMD Intelligence Portal</h2>
            <p>Your one-time login code is:</p>
            <h1 style="background-color: #f0f0f0; padding: 20px; text-align: center; letter-spacing: 5px;">{code}</h1>
            <p style="color: #666;">This code will expire in 10 minutes.</p>
        </body></html>
        """
        msg.attach(MIMEText(body, 'html'))
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False

def generate_code():
    return str(random.randint(100000, 999999))

# --- PASSWORD PROTECTION WITH EMAIL OTP ---
def check_password():
    def send_code_clicked():
        username = st.session_state.get("username_input", "")
        password = st.session_state.get("password_input", "")
        if not username or not password:
            st.session_state["login_error"] = "Please enter username and password"
            return
        users = load_user_data()
        if username not in users:
            st.session_state["login_error"] = "Invalid username or password"
            return
        entered_hash = hashlib.sha256(password.encode()).hexdigest()
        if entered_hash != users[username]["password_hash"]:
            st.session_state["login_error"] = "Invalid username or password"
            return
        code = generate_code()
        email = users[username]["email"]
        if send_email_code(email, code):
            st.session_state["otp_code"] = code
            st.session_state["otp_timestamp"] = datetime.datetime.now()
            st.session_state["current_username"] = username
            st.session_state["code_sent"] = True
            st.session_state["login_error"] = None
        else:
            st.session_state["login_error"] = "Failed to send code. Please try again."

    def verify_code_clicked():
        entered_code = st.session_state.get("code_input", "")
        stored_code = st.session_state.get("otp_code", "")
        timestamp = st.session_state.get("otp_timestamp")
        if not entered_code:
            st.session_state["login_error"] = "Please enter the code"
            return
        if timestamp:
            elapsed = (datetime.datetime.now() - timestamp).total_seconds()
            if elapsed > 600:
                st.session_state["login_error"] = "Code expired. Please request a new one."
                st.session_state["code_sent"] = False
                return
        if entered_code == stored_code:
            st.session_state["password_correct"] = True
            st.session_state["logged_in_user"] = st.session_state["current_username"]
            for key in ["otp_code", "password_input", "code_input", "otp_timestamp"]:
                if key in st.session_state:
                    del st.session_state[key]
        else:
            st.session_state["login_error"] = "Invalid code. Please try again."

    if st.session_state.get("password_correct"):
        return True

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("# 🇬🇧 IMD Intelligence Portal")
        st.markdown("### Secure Access")
        if st.session_state.get("login_error"):
            st.error(st.session_state["login_error"])
        
        if not st.session_state.get("code_sent"):
            with st.form("login_form"):
                st.text_input("Username", key="username_input", placeholder="Enter username")
                st.text_input("Password", type="password", key="password_input", placeholder="Enter password")
                submitted = st.form_submit_button("📧 Send Code to Email", use_container_width=True, type="primary")
                if submitted:
                    send_code_clicked()
                    st.rerun()
            st.caption("🔒 A verification code will be sent to your registered email")
        else:
            username = st.session_state.get("current_username", "")
            if username in AUTHORIZED_USERS:
                masked_email = AUTHORIZED_USERS[username]["email"]
                parts = masked_email.split('@')
                masked = parts[0][0] + "****" + "@" + parts[1] if len(parts) == 2 else masked_email
                st.info(f"📧 Code sent to: **{masked}**")
            
            with st.form("verify_form"):
                st.text_input("Enter 6-Digit Code", key="code_input", placeholder="000000", max_chars=6)
                col_a, col_b = st.columns(2)
                with col_a:
                    verify = st.form_submit_button("✅ Verify Code", use_container_width=True, type="primary")
                with col_b:
                    resend = st.form_submit_button("🔄 Resend Code", use_container_width=True)
                if verify:
                    verify_code_clicked()
                    st.rerun()
                if resend:
                    st.session_state["code_sent"] = False
                    st.session_state["login_error"] = None
                    st.rerun()
            st.caption("⏱️ Code expires in 10 minutes")
    return False

if not check_password():
    st.stop()

username = st.session_state.get("logged_in_user")
if username and check_password_expiry(username):
    st.error("🔐 Your password has expired. Please change it to continue.")
    st.session_state["show_password_change"] = True

# --- HOSPITAL LIST ---
def get_hospital_list(engine):
    try:
        query = "SELECT DISTINCT hospital FROM dbo.RefHospital WHERE hospital IS NOT NULL ORDER BY hospital"
        hospitals_df = pd.read_sql(query, engine)
        return hospitals_df['hospital'].tolist()
    except:
        return ["All Hospitals"]

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: 600; }
    div.stMetric { background-color: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
</style>
""", unsafe_allow_html=True)

if st.session_state.get('processing', False):
    st.markdown("""<style>[data-testid="stSidebar"] { pointer-events: none; opacity: 0.6; }</style>""", unsafe_allow_html=True)

# --- STATE MANAGEMENT ---
def lock_ui(): 
    st.session_state['processing'] = True

def unlock_ui(rerun=False): 
    st.session_state['processing'] = False
    if rerun:
        st.rerun()

# --- DATABASE CONNECTION ---
@st.cache_resource
def get_connection(server="45.145.102.83,1433", database="onlinewov4"):
    try:
        drivers = pyodbc.drivers()
        preferred_drivers = ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "FreeTDS"]
        driver = None
        for d in preferred_drivers:
            if d in drivers:
                driver = d
                break
        if not driver:
            raise ConnectionError(f"No compatible ODBC driver found. Available: {drivers}")
        
        params = [f"Driver={{{driver}}}", f"Server={server}", f"Database={database}", 
                  "UID=Sarah", "PWD=RasberryPi111", "TrustServerCertificate=yes"]
        conn_str = "mssql+pyodbc:///?odbc_connect=" + urllib.parse.quote_plus(";".join(params))
        engine = create_engine(conn_str, fast_executemany=True)
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        raise

engine_local = None

# --- UK POSTCODE VALIDATION ---
import re

def validate_postcode(postcode):
    """
    Validate UK postcode format and detect fake/invalid postcodes.
    Returns (is_valid, clean_postcode, error_reason)
    """
    if pd.isna(postcode) or str(postcode).strip() == '' or str(postcode).upper() == 'NULL':
        return False, None, 'No Postcode'
    
    clean_pc = str(postcode).strip().upper().replace(' ', '')
    
    # Too short (less than 3 chars is definitely invalid) or too long
    if len(clean_pc) < 3:
        return False, clean_pc, 'Too Short'
    if len(clean_pc) > 8:
        return False, clean_pc, 'Invalid Postcode'
    
    # Check for common fake patterns
    fake_patterns = [
        r'^[A-Z]{5,}$',  # All letters, no numbers (e.g., "XXXXX")
        r'^[0-9]{5,}$',  # All numbers (US zip code style)
        r'^TEST',
        r'^FAKE',
        r'^XXXX',
        r'^0000',
        r'^1111',
        r'^AA11AA$',  # Common test postcode
        r'^ZZ',  # ZZ prefix is invalid (except ZE for Shetland)
    ]
    
    for pattern in fake_patterns:
        if re.match(pattern, clean_pc):
            return False, clean_pc, 'Fake/Invalid'
    
    # Check for valid UK postcode area prefix (first 1-2 letters)
    valid_areas = [
        'AB', 'AL', 'B', 'BA', 'BB', 'BD', 'BH', 'BL', 'BN', 'BR', 'BS', 'BT',
        'CA', 'CB', 'CF', 'CH', 'CM', 'CO', 'CR', 'CT', 'CV', 'CW',
        'DA', 'DD', 'DE', 'DG', 'DH', 'DL', 'DN', 'DT', 'DY',
        'E', 'EC', 'EH', 'EN', 'EX',
        'FK', 'FY',
        'G', 'GL', 'GU', 'GY',
        'HA', 'HD', 'HG', 'HP', 'HR', 'HS', 'HU', 'HX',
        'IG', 'IM', 'IP', 'IV',
        'JE',
        'KA', 'KT', 'KW', 'KY',
        'L', 'LA', 'LD', 'LE', 'LL', 'LN', 'LS', 'LU',
        'M', 'ME', 'MK', 'ML',
        'N', 'NE', 'NG', 'NN', 'NP', 'NR', 'NW',
        'OL', 'OX',
        'PA', 'PE', 'PH', 'PL', 'PO', 'PR',
        'RG', 'RH', 'RM',
        'S', 'SA', 'SE', 'SG', 'SK', 'SL', 'SM', 'SN', 'SO', 'SP', 'SR', 'SS', 'ST', 'SW', 'SY',
        'TA', 'TD', 'TF', 'TN', 'TQ', 'TR', 'TS', 'TW',
        'UB',
        'W', 'WA', 'WC', 'WD', 'WF', 'WN', 'WR', 'WS', 'WV',
        'YO',
        'ZE'
    ]
    
    # Extract area prefix (1-2 letters at start)
    area_match = re.match(r'^([A-Z]{1,2})', clean_pc)
    if area_match:
        area = area_match.group(1)
        # Check if 2-letter area exists, otherwise check 1-letter
        if len(area) == 2 and area not in valid_areas:
            # Try single letter
            if area[0] not in valid_areas:
                return False, clean_pc, f'Invalid Area ({area})'
    
    # UK postcode regex - validates outward and inward codes
    # Outward: A9, A99, A9A, AA9, AA99, AA9A
    # Inward: 9AA
    uk_pattern = r'^([A-Z]{1,2}[0-9][0-9A-Z]?)[0-9][A-Z]{2}$'
    
    if not re.match(uk_pattern, clean_pc):
        # Allow partial postcodes (outward code + optional partial inward) for lookup
        partial_pattern = r'^[A-Z]{1,2}[0-9][0-9A-Z]?[0-9]?[A-Z]?$'
        if re.match(partial_pattern, clean_pc):
            return True, clean_pc, 'Partial'  # Mark as partial but allow lookup
        return False, clean_pc, 'Invalid Format'
    
    return True, clean_pc, None

# --- UK REGION DETECTION ---
def get_region_from_postcode(postcode):
    """Determine UK region from postcode prefix"""
    if not postcode:
        return 'Unknown'
    clean_pc = str(postcode).replace(' ', '').upper()
    
    # Northern Ireland: BT prefix
    if clean_pc.startswith('BT'):
        return 'NI'
    
    # Scotland prefixes - more specific matching
    scotland_prefixes = {
        'AB': True,   # Aberdeen
        'DD': True,   # Dundee
        'DG': True,   # Dumfries
        'EH': True,   # Edinburgh
        'FK': True,   # Falkirk
        'HS': True,   # Outer Hebrides
        'IV': True,   # Inverness
        'KA': True,   # Kilmarnock
        'KW': True,   # Kirkwall
        'KY': True,   # Kirkcaldy
        'ML': True,   # Motherwell
        'PA': True,   # Paisley
        'PH': True,   # Perth
        'TD': True,   # Galashiels (partial - some in England)
        'ZE': True,   # Shetland
    }
    
    # Check 2-letter prefix first
    if len(clean_pc) >= 2:
        prefix2 = clean_pc[:2]
        if prefix2 in scotland_prefixes:
            return 'Scotland'
    
    # Glasgow - single letter G followed by digit
    if clean_pc.startswith('G') and len(clean_pc) > 1 and clean_pc[1].isdigit():
        return 'Scotland'
    
    # Wales prefixes
    wales_prefixes = {
        'CF': True,   # Cardiff
        'LD': True,   # Llandrindod Wells
        'LL': True,   # Llandudno
        'NP': True,   # Newport (some border areas may be England)
        'SA': True,   # Swansea
        'SY': True,   # Shrewsbury (border - some in England)
    }
    
    if len(clean_pc) >= 2:
        prefix2 = clean_pc[:2]
        if prefix2 in wales_prefixes:
            # SY and NP have some English postcodes - check more carefully
            if prefix2 == 'SY':
                # SY1-SY11 are mostly Shropshire (England), SY15-SY25 are Wales
                if len(clean_pc) >= 3:
                    try:
                        num = int(re.match(r'SY(\d+)', clean_pc).group(1))
                        if num >= 15:
                            return 'Wales'
                        else:
                            return 'England'  # SY1-SY11 are England
                    except:
                        pass
            return 'Wales'
    
    return 'England'

def calculate_mode(values):
    """Calculate mode, handling ties"""
    if not values:
        return None
    try:
        return statistics.mode(values)
    except statistics.StatisticsError:
        counts = Counter(values)
        max_count = max(counts.values())
        modes = [k for k, v in counts.items() if v == max_count]
        return min(modes)

# --- ENRICHMENT WITH ALL UK REGIONS ---
def enrich_postcode_all_regions(postcode, engine):
    """Enrich a single postcode with IMD data from any UK region"""
    
    # Validate postcode first
    is_valid, clean_pc, error_reason = validate_postcode(postcode)
    
    if not is_valid:
        return {'IMD_Decile': None, 'IMD_Source': error_reason or 'Invalid Postcode', 'IMD_Data_Source': None,
                'IMD_Mean': None, 'IMD_Median': None, 'IMD_Mode': None,
                'IMD_Min': None, 'IMD_Max': None, 'IMD_Range': None, 'Postcode_Count': None}
    
    region = get_region_from_postcode(clean_pc)
    
    result = {'IMD_Decile': None, 'IMD_Source': None, 'IMD_Data_Source': None,
              'IMD_Mean': None, 'IMD_Median': None, 'IMD_Mode': None,
              'IMD_Min': None, 'IMD_Max': None, 'IMD_Range': None, 'Postcode_Count': None}
    
    try:
        with engine.connect() as conn:
            if region == 'Scotland':
                # Try Scotland SIMD
                sql = text("SELECT IMD_Decile FROM SIMD_Scotland WHERE REPLACE(Postcode, ' ', '') = :pc")
                res = conn.execute(sql, {"pc": clean_pc}).fetchone()
                if res:
                    return {'IMD_Decile': int(res[0]), 'IMD_Source': 'Exact', 'IMD_Data_Source': 'SIMD 2020 (Scotland)',
                            'IMD_Mean': res[0], 'IMD_Median': res[0], 'IMD_Mode': int(res[0]),
                            'IMD_Min': int(res[0]), 'IMD_Max': int(res[0]), 'IMD_Range': f"{int(res[0])}-{int(res[0])}", 'Postcode_Count': 1}
                
                # Partial match
                sql = text("SELECT IMD_Decile FROM SIMD_Scotland WHERE REPLACE(Postcode, ' ', '') LIKE :pc + '%'")
                res = conn.execute(sql, {"pc": clean_pc}).fetchall()
                if res:
                    deciles = [r[0] for r in res if r[0] is not None]
                    if deciles:
                        return _calc_stats(deciles, 'Partial Average', 'SIMD 2020 (Scotland)')
                
                return {'IMD_Decile': None, 'IMD_Source': 'Scotland - No Match', 'IMD_Data_Source': None,
                        'IMD_Mean': None, 'IMD_Median': None, 'IMD_Mode': None,
                        'IMD_Min': None, 'IMD_Max': None, 'IMD_Range': None, 'Postcode_Count': None}
            
            elif region == 'Wales':
                # Try Wales WIMD
                sql = text("SELECT WIMD_Decile FROM WIMD_Wales WHERE Postcode = :pc")
                res = conn.execute(sql, {"pc": clean_pc}).fetchone()
                if res:
                    return {'IMD_Decile': int(res[0]), 'IMD_Source': 'Exact', 'IMD_Data_Source': 'WIMD 2019 (Wales)',
                            'IMD_Mean': res[0], 'IMD_Median': res[0], 'IMD_Mode': int(res[0]),
                            'IMD_Min': int(res[0]), 'IMD_Max': int(res[0]), 'IMD_Range': f"{int(res[0])}-{int(res[0])}", 'Postcode_Count': 1}
                
                # Partial match
                sql = text("SELECT WIMD_Decile FROM WIMD_Wales WHERE Postcode LIKE :pc + '%'")
                res = conn.execute(sql, {"pc": clean_pc}).fetchall()
                if res:
                    deciles = [r[0] for r in res if r[0] is not None]
                    if deciles:
                        return _calc_stats(deciles, 'Partial Average', 'WIMD 2019 (Wales)')
                
                # Fallback to England (some SY/NP postcodes are border areas)
                return _try_england_lookup(clean_pc, conn)
            
            elif region == 'NI':
                # Try Northern Ireland NIMDM
                sql = text("SELECT NIMDM_Decile FROM NIMDM_NI WHERE Postcode = :pc")
                res = conn.execute(sql, {"pc": clean_pc}).fetchone()
                if res:
                    return {'IMD_Decile': int(res[0]), 'IMD_Source': 'Exact', 'IMD_Data_Source': 'NIMDM 2017 (Northern Ireland)',
                            'IMD_Mean': res[0], 'IMD_Median': res[0], 'IMD_Mode': int(res[0]),
                            'IMD_Min': int(res[0]), 'IMD_Max': int(res[0]), 'IMD_Range': f"{int(res[0])}-{int(res[0])}", 'Postcode_Count': 1}
                
                # Partial match
                sql = text("SELECT NIMDM_Decile FROM NIMDM_NI WHERE Postcode LIKE :pc + '%'")
                res = conn.execute(sql, {"pc": clean_pc}).fetchall()
                if res:
                    deciles = [r[0] for r in res if r[0] is not None]
                    if deciles:
                        return _calc_stats(deciles, 'Partial Average', 'NIMDM 2017 (Northern Ireland)')
                
                return {'IMD_Decile': None, 'IMD_Source': 'NI - No Data', 'IMD_Data_Source': None,
                        'IMD_Mean': None, 'IMD_Median': None, 'IMD_Mode': None,
                        'IMD_Min': None, 'IMD_Max': None, 'IMD_Range': None, 'Postcode_Count': None}
            
            else:  # England
                return _try_england_lookup(clean_pc, conn)
                
    except Exception as e:
        return {'IMD_Decile': None, 'IMD_Source': f'Error: {str(e)[:30]}', 'IMD_Data_Source': None,
                'IMD_Mean': None, 'IMD_Median': None, 'IMD_Mode': None,
                'IMD_Min': None, 'IMD_Max': None, 'IMD_Range': None, 'Postcode_Count': None}

def _try_england_lookup(clean_pc, conn):
    """Try England IMD lookup"""
    # Exact match
    sql = text("""
        SELECT i.IMD_Decile FROM PostcodeData p 
        JOIN IMD_2025 i ON p.LSOA_Code = i.LSOA_Code 
        WHERE REPLACE(p.Postcode, ' ', '') = :pc
    """)
    res = conn.execute(sql, {"pc": clean_pc}).fetchone()
    if res:
        return {'IMD_Decile': int(res[0]), 'IMD_Source': 'Exact', 'IMD_Data_Source': 'IMD 2025 (England)',
                'IMD_Mean': res[0], 'IMD_Median': res[0], 'IMD_Mode': int(res[0]),
                'IMD_Min': int(res[0]), 'IMD_Max': int(res[0]), 'IMD_Range': f"{int(res[0])}-{int(res[0])}", 'Postcode_Count': 1}
    
    # Partial match
    sql = text("""
        SELECT i.IMD_Decile FROM PostcodeData p 
        JOIN IMD_2025 i ON p.LSOA_Code = i.LSOA_Code 
        WHERE REPLACE(p.Postcode, ' ', '') LIKE :pc + '%'
    """)
    res = conn.execute(sql, {"pc": clean_pc}).fetchall()
    if res:
        deciles = [r[0] for r in res if r[0] is not None]
        if deciles:
            return _calc_stats(deciles, 'Partial Average', 'IMD 2025 (England)')
    
    return {'IMD_Decile': None, 'IMD_Source': 'No Match Found', 'IMD_Data_Source': None,
            'IMD_Mean': None, 'IMD_Median': None, 'IMD_Mode': None,
            'IMD_Min': None, 'IMD_Max': None, 'IMD_Range': None, 'Postcode_Count': None}

def _calc_stats(deciles, source, data_source):
    """Calculate statistics from decile list"""
    mean_val = round(statistics.mean(deciles), 1)
    median_val = round(statistics.median(deciles), 1)
    mode_val = calculate_mode([int(d) for d in deciles])
    min_val = int(min(deciles))
    max_val = int(max(deciles))
    return {
        'IMD_Decile': round(mean_val),
        'IMD_Source': source,
        'IMD_Data_Source': data_source,
        'IMD_Mean': mean_val,
        'IMD_Median': median_val,
        'IMD_Mode': mode_val,
        'IMD_Min': min_val,
        'IMD_Max': max_val,
        'IMD_Range': f"{min_val}-{max_val}",
        'Postcode_Count': len(deciles)
    }

# --- HELPERS ---
def get_coordinates_bulk(postcodes):
    if not postcodes: return {}
    unique = list(set(postcodes))
    results = {}
    for i in range(0, len(unique), 100):
        chunk = unique[i:i+100]
        try:
            r = requests.post("https://api.postcodes.io/postcodes", json={"postcodes": chunk}, timeout=5)
            if r.status_code == 200:
                for res in r.json()['result']:
                    if res and res.get('result'): 
                        results[res['query']] = {'lat': res['result']['latitude'], 'lon': res['result']['longitude']}
            time.sleep(0.1)
        except:
            pass
    return results

# --- H3 HEXAGON HEATMAP FUNCTIONS ---
def assign_points_to_hexagons(df, resolution=7):
    """
    Assign each point (postcode) to its corresponding H3 hexagon.
    """
    if not H3_AVAILABLE:
        return df
    df = df.copy()
    df['hex_id'] = df.apply(
        lambda row: h3.latlng_to_cell(row['lat'], row['lon'], resolution) if pd.notna(row['lat']) and pd.notna(row['lon']) else None,
        axis=1
    )
    return df

def aggregate_by_hexagon(df):
    """
    Aggregate data by hexagon ID with mean, median, and mode.
    """
    if not H3_AVAILABLE:
        return pd.DataFrame()
    
    def calc_mode(x):
        """Calculate mode, return first value if multiple modes"""
        mode_result = scipy_stats.mode(x, keepdims=True)
        return mode_result.mode[0] if len(mode_result.mode) > 0 else x.iloc[0]
    
    # Group by hex_id and aggregate
    agg_df = df.groupby('hex_id').agg({
        'Final_Decile': ['mean', 'median', calc_mode, 'min', 'max', 'count'],
        'postcode': lambda x: '<br>'.join(str(p) for p in x),
        'lat': 'mean',
        'lon': 'mean',
        'IMD_Data_Source': 'first'
    }).reset_index()
    
    # Flatten column names
    agg_df.columns = ['hex_id', 'mean_imd', 'median_imd', 'mode_imd', 'min_imd', 'max_imd', 'postcode_count',
                      'postcodes', 'center_lat', 'center_lon', 'data_source']
    return agg_df

def create_hexagon_geojson(hex_ids):
    """
    Create GeoJSON features for hexagons.
    """
    if not H3_AVAILABLE:
        return {"type": "FeatureCollection", "features": []}
    
    features = []
    for hex_id in hex_ids:
        if hex_id is None:
            continue
        boundary = h3.cell_to_boundary(hex_id)
        coordinates = [[lng, lat] for lat, lng in boundary]
        coordinates.append(coordinates[0])  # Close the polygon
        
        features.append({
            "type": "Feature",
            "id": hex_id,
            "properties": {"hex_id": hex_id},
            "geometry": {
                "type": "Polygon",
                "coordinates": [coordinates]
            }
        })
    
    return {
        "type": "FeatureCollection",
        "features": features
    }

def create_hexagon_choropleth(df, resolution=7, color_by='mean_imd', stat_type='mean', show_labels=True, title="Hexagonal Heatmap"):
    """
    Create an interactive hexagonal choropleth map.
    """
    if not H3_AVAILABLE:
        return go.Figure(), pd.DataFrame()
    
    import plotly.graph_objects as go
    
    # Assign postcodes to hexagons
    df_hex = assign_points_to_hexagons(df, resolution)
    df_hex = df_hex.dropna(subset=['hex_id'])
    
    # Aggregate by hexagon
    hex_stats = aggregate_by_hexagon(df_hex)
    
    if hex_stats.empty:
        return go.Figure(), pd.DataFrame()
    
    # Create GeoJSON for hexagons
    geojson = create_hexagon_geojson(hex_stats['hex_id'].tolist())
    
    # Color settings
    if color_by in ['mean_imd', 'median_imd', 'mode_imd']:
        color_scale = "RdYlGn"  # Red (deprived) to Green (least deprived)
        color_range = [1, 10]
        stat_labels = {'mean_imd': 'Mean IMD', 'median_imd': 'Median IMD', 'mode_imd': 'Mode IMD'}
        color_label = stat_labels.get(color_by, 'IMD Decile')
    else:
        color_scale = "Viridis"
        color_range = [hex_stats['postcode_count'].min(), hex_stats['postcode_count'].max()]
        color_label = "User Count"
    
    # Create choropleth
    fig = px.choropleth_mapbox(
        hex_stats,
        geojson=geojson,
        locations='hex_id',
        color=color_by,
        color_continuous_scale=color_scale,
        range_color=color_range,
        mapbox_style="carto-positron",
        zoom=5,
        center={"lat": hex_stats['center_lat'].mean(), "lon": hex_stats['center_lon'].mean()},
        opacity=0.7,
        hover_data={
            'hex_id': False,
            'mean_imd': ':.1f',
            'median_imd': ':.1f',
            'mode_imd': ':.0f',
            'min_imd': ':.0f',
            'max_imd': ':.0f',
            'postcode_count': True,
            'data_source': True,
            'postcodes': True
        },
        labels={
            'mean_imd': 'Mean IMD',
            'median_imd': 'Median IMD',
            'mode_imd': 'Mode IMD',
            'min_imd': 'Min IMD',
            'max_imd': 'Max IMD',
            'postcode_count': 'Postcodes',
            'data_source': 'Region',
            'postcodes': 'Postcode List'
        }
    )
    
    # Add text labels inside hexagons
    if show_labels:
        stat_column = f'{stat_type}_imd'
        display_texts = []
        for _, row in hex_stats.iterrows():
            imd_val = row[stat_column]
            pc_count = row['postcode_count']
            display_texts.append(f"IMD:{imd_val:.1f}\nN:{pc_count}")
        
        fig.add_trace(go.Scattermapbox(
            lat=hex_stats['center_lat'],
            lon=hex_stats['center_lon'],
            mode='text',
            text=display_texts,
            textfont=dict(size=9, color='black', family='Arial Black'),
            textposition='middle center',
            hoverinfo='skip',
            showlegend=False
        ))
    
    fig.update_layout(
        title=dict(text=title, x=0.5),
        margin={"r": 0, "t": 50, "l": 0, "b": 0},
        height=700,
        coloraxis_colorbar=dict(title=color_label)
    )
    
    return fig, hex_stats

# --- SIDEBAR ---
with st.sidebar:
    st.title("Navigation")
    
    if st.session_state.get("logged_in_user"):
        username = st.session_state["logged_in_user"]
        st.success(f"👤 Logged in as: **{username}**")
        
        users = load_user_data()
        last_change = users[username].get('last_password_change')
        if last_change:
            if isinstance(last_change, str):
                last_change = datetime.datetime.fromisoformat(last_change)
            days_since_change = (datetime.datetime.now() - last_change).days
            days_remaining = 90 - days_since_change
            if days_remaining <= 0:
                st.error(f"🔐 Password expired!")
            elif days_remaining <= 14:
                st.warning(f"⚠️ Password expires in {days_remaining} days")
        
        if st.button("🔑 Change Password", use_container_width=True):
            st.session_state["show_password_change"] = True
        
        if st.button("🚪 Logout", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        
        st.markdown("---")
    
    st.sidebar.markdown("### 🗄️ Database Connection")
    target_db_name = st.sidebar.text_input("Target DB", value="onlinewov4", disabled=True)
    
    try:
        engine_local = get_connection(database=target_db_name)
    except Exception:
        st.stop()

    st.sidebar.markdown("### 📑 Navigation")
    is_processing = st.session_state.get('processing', False)
    
    page = st.radio("Go to:", [
        "📅 Date & Hospital Reports",
        "👥 Live User Audit",
        "📊 IMD Statistics",
        "📤 File Upload",
        "🗺️ Heatmap Engine",
        "📊 Power BI",
        "🛠️ Connection Diagnostics"
    ], disabled=is_processing)
    
    st.markdown("---")
    st.caption(f"Connected to: **{target_db_name}**")
    
    # UK Coverage Info
    st.markdown("### 🇬🇧 UK Coverage")
    st.caption("✅ England (IMD 2025)")
    st.caption("✅ Scotland (SIMD 2020)")
    st.caption("✅ Wales (WIMD 2019)")
    st.caption("✅ N. Ireland (NIMDM 2017)")

# --- PASSWORD CHANGE MODAL ---
if st.session_state.get("show_password_change"):
    with st.container(border=True):
        st.markdown("### 🔑 Change Your Password")
        username = st.session_state.get("logged_in_user")
        users = load_user_data()
        
        with st.form("change_password_form"):
            current_password = st.text_input("Current Password", type="password")
            new_password = st.text_input("New Password", type="password")
            confirm_password = st.text_input("Confirm New Password", type="password")
            col1, col2 = st.columns(2)
            with col1:
                submit = st.form_submit_button("✅ Update Password", use_container_width=True, type="primary")
            with col2:
                cancel = st.form_submit_button("❌ Cancel", use_container_width=True)
            
            if cancel:
                st.session_state["show_password_change"] = False
                st.rerun()
            
            if submit:
                current_hash = hashlib.sha256(current_password.encode()).hexdigest()
                if current_hash != users[username]["password_hash"]:
                    st.error("❌ Current password is incorrect")
                elif len(new_password) < 8:
                    st.error("❌ New password must be at least 8 characters")
                elif new_password != confirm_password:
                    st.error("❌ New passwords don't match")
                elif new_password == current_password:
                    st.error("❌ New password must be different from current password")
                else:
                    update_user_password(username, new_password)
                    st.success("✅ Password updated successfully!")
                    st.session_state["show_password_change"] = False
                    time.sleep(1)
                    st.rerun()
    st.stop()

# === PAGES ===

if page == "📅 Date & Hospital Reports":
    st.header("📅 Date & Hospital Reports")
    
    with st.expander("ℹ️ What is this page?", expanded=False):
        st.markdown("""
        **Purpose:** Filter and analyze IMD data by date ranges and hospitals.
        
        **Features:**
        - Filter by user creation date (when profile was added to database)
        - Filter by IMD enrichment date (when postcode data was processed)
        - Filter by specific hospital or view all hospitals
        - View month-by-month breakdowns
        - Export filtered data with full statistics
        """)
    
    # Get hospital list
    try:
        hospitals = get_hospital_list(engine_local)
        hospitals.insert(0, "All Hospitals")
    except:
        hospitals = ["All Hospitals"]
    
    # Filters
    with st.container(border=True):
        st.markdown("### 🔍 Filters")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📅 Date Filters")
            date_type = st.radio(
                "Date Type:",
                ["User Creation Date", "IMD Enrichment Date", "Both"],
                help="User Creation Date = when user profile was added to database\nIMD Enrichment Date = when postcode was processed for IMD data"
            )
            
            # Date range selection
            date_range_type = st.selectbox(
                "Time Period:",
                ["Custom Range", "Last 7 Days", "Last 30 Days", "Last 3 Months", "Last 6 Months", "Last Year", "Year to Date", "All Time"]
            )
            
            today = datetime.datetime.now()
            
            if date_range_type == "Custom Range":
                col_start, col_end = st.columns(2)
                with col_start:
                    start_date = st.date_input("Start Date", value=today - datetime.timedelta(days=30))
                with col_end:
                    end_date = st.date_input("End Date", value=today)
            else:
                # Calculate date ranges
                if date_range_type == "Last 7 Days":
                    start_date, end_date = today - datetime.timedelta(days=7), today
                elif date_range_type == "Last 30 Days":
                    start_date, end_date = today - datetime.timedelta(days=30), today
                elif date_range_type == "Last 3 Months":
                    start_date, end_date = today - datetime.timedelta(days=90), today
                elif date_range_type == "Last 6 Months":
                    start_date, end_date = today - datetime.timedelta(days=180), today
                elif date_range_type == "Last Year":
                    start_date, end_date = today - datetime.timedelta(days=365), today
                elif date_range_type == "Year to Date":
                    start_date, end_date = datetime.datetime(today.year, 1, 1), today
                else:  # All Time
                    start_date, end_date = datetime.datetime(2020, 1, 1), today
                
                st.info(f"📅 {start_date.strftime('%Y/%m/%d')} to {end_date.strftime('%Y/%m/%d')}")
        
        with col2:
            st.markdown("#### 🏥 Hospital Filters")
            selected_hospital = st.selectbox(
                "Hospital:",
                hospitals,
                help="Select a specific hospital or 'All Hospitals' to view data from all locations"
            )
            
            # Grouping options
            group_by = st.selectbox(
                "Group Results By:",
                ["None", "Month", "Hospital", "Month & Hospital", "IMD Decile", "Data Source"]
            )
            
            show_summary = st.checkbox("Show Summary Statistics", value=True)
    
    # Execute button
    if st.button("🔍 Generate Report", type="primary", use_container_width=True):
        with st.spinner("Generating report..."):
            try:
                # Build SQL query with all statistics columns
                base_query = """
                SELECT 
                    u.userKey,
                    COALESCE(ud.registrationDate, u.lastUpdated) as UserCreatedDate,
                    u.email,
                    imd.postcode,
                    imd.IMD_Decile,
                    imd.IMD_Source,
                    imd.IMD_Data_Source,
                    imd.IMD_Mean,
                    imd.IMD_Median,
                    imd.IMD_Mode,
                    imd.IMD_Min,
                    imd.IMD_Max,
                    imd.IMD_Range,
                    imd.Postcode_Count,
                    h.hospital as Hospital,
                    imd.Lat,
                    imd.Lon,
                    imd.LastEnrichedDate as IMDEnrichedDate,
                    YEAR(COALESCE(ud.registrationDate, u.lastUpdated)) as UserCreatedYear,
                    MONTH(COALESCE(ud.registrationDate, u.lastUpdated)) as UserCreatedMonth,
                    FORMAT(COALESCE(ud.registrationDate, u.lastUpdated), 'yyyy-MM') as UserCreatedYearMonth,
                    YEAR(imd.LastEnrichedDate) as IMDEnrichedYear,
                    MONTH(imd.LastEnrichedDate) as IMDEnrichedMonth,
                    FORMAT(imd.LastEnrichedDate, 'yyyy-MM') as IMDEnrichedYearMonth
                FROM dbo.[user] u
                LEFT JOIN dbo.UserDetail ud ON u.userKey = ud.userKey
                LEFT JOIN dbo.IMD_Data imd ON u.userKey = imd.userKey
                LEFT JOIN dbo.RefHospital h ON u.hospitalKey = h.hospitalKey
                WHERE 1=1
                """
                
                params = {}
                
                # Adjust end_date to include the full day
                if isinstance(end_date, datetime.date) and not isinstance(end_date, datetime.datetime):
                    end_date_inclusive = datetime.datetime.combine(end_date, datetime.time(23, 59, 59))
                    start_date_dt = datetime.datetime.combine(start_date, datetime.time(0, 0, 0))
                else:
                    end_date_inclusive = end_date
                    start_date_dt = start_date
                
                # Add date filters
                if date_type == "User Creation Date":
                    base_query += " AND COALESCE(ud.registrationDate, u.lastUpdated) BETWEEN :start_date AND :end_date"
                    params['start_date'] = start_date_dt
                    params['end_date'] = end_date_inclusive
                elif date_type == "IMD Enrichment Date":
                    base_query += " AND imd.LastEnrichedDate BETWEEN :start_date AND :end_date"
                    params['start_date'] = start_date_dt
                    params['end_date'] = end_date_inclusive
                else:  # Both
                    base_query += " AND (COALESCE(ud.registrationDate, u.lastUpdated) BETWEEN :start_date AND :end_date OR imd.LastEnrichedDate BETWEEN :start_date AND :end_date)"
                    params['start_date'] = start_date_dt
                    params['end_date'] = end_date_inclusive
                
                # Add hospital filter
                if selected_hospital != "All Hospitals":
                    base_query += " AND h.hospital = :hospital"
                    params['hospital'] = selected_hospital
                
                # Add ORDER BY
                base_query += " ORDER BY COALESCE(ud.registrationDate, u.lastUpdated) DESC"
                
                # Execute query
                df = pd.read_sql(text(base_query), engine_local, params=params)
                
                if df.empty:
                    st.warning("⚠️ No data found for the selected filters.")
                else:
                    st.success(f"✅ Retrieved **{len(df):,}** records")
                    
                    # Summary Statistics
                    if show_summary:
                        st.markdown("---")
                        st.markdown("### 📊 Summary Statistics")
                        
                        col1, col2, col3, col4, col5 = st.columns(5)
                        
                        with col1:
                            st.metric("Total Users", f"{len(df):,}")
                        with col2:
                            enriched_count = df['IMD_Decile'].notna().sum()
                            st.metric("✅ Enriched", f"{enriched_count:,}")
                        with col3:
                            unenriched_count = df['IMD_Decile'].isna().sum()
                            st.metric("⏳ Unenriched", f"{unenriched_count:,}")
                        with col4:
                            avg_decile = df['IMD_Decile'].mean()
                            st.metric("Avg IMD Decile", f"{avg_decile:.1f}" if pd.notna(avg_decile) else "N/A")
                        with col5:
                            hospital_count = df['Hospital'].nunique()
                            st.metric("Hospitals", f"{hospital_count}")
                        
                        # Region breakdown - match actual database values
                        st.markdown("#### 🇬🇧 By UK Region")
                        rcol1, rcol2, rcol3, rcol4 = st.columns(4)
                        with rcol1:
                            # England: IMD_2025, IMD 2025, or contains 'England'
                            england = len(df[df['IMD_Data_Source'].str.contains('IMD.?2025|England', na=False, regex=True, case=False)])
                            st.metric("🏴󠁧󠁢󠁥󠁮󠁧󠁿 England", england)
                        with rcol2:
                            # Scotland: SIMD or contains 'Scotland'
                            scotland = len(df[df['IMD_Data_Source'].str.contains('SIMD|Scotland', na=False, regex=True, case=False)])
                            st.metric("🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scotland", scotland)
                        with rcol3:
                            # Wales: WIMD or contains 'Wales'
                            wales = len(df[df['IMD_Data_Source'].str.contains('WIMD|Wales', na=False, regex=True, case=False)])
                            st.metric("🏴󠁧󠁢󠁷󠁬󠁳󠁿 Wales", wales)
                        with rcol4:
                            # NI: NIMDM or contains 'Ireland'
                            ni = len(df[df['IMD_Data_Source'].str.contains('NIMDM|Ireland', na=False, regex=True, case=False)])
                            st.metric("🇬🇧 N. Ireland", ni)
                    
                    # Grouped Results
                    if group_by != "None":
                        st.markdown("---")
                        st.markdown(f"### 📈 Grouped by {group_by}")
                        
                        if group_by == "Month":
                            if date_type == "IMD Enrichment Date":
                                grouped = df.groupby('IMDEnrichedYearMonth').agg({'userKey': 'count', 'IMD_Decile': 'mean'}).reset_index()
                                grouped.columns = ['Month', 'User Count', 'Avg IMD Decile']
                            else:
                                grouped = df.groupby('UserCreatedYearMonth').agg({'userKey': 'count', 'IMD_Decile': 'mean'}).reset_index()
                                grouped.columns = ['Month', 'User Count', 'Avg IMD Decile']
                            
                            st.dataframe(grouped, use_container_width=True)
                            fig = px.bar(grouped, x='Month', y='User Count', title='Users by Month')
                            st.plotly_chart(fig, use_container_width=True)
                        
                        elif group_by == "Hospital":
                            grouped = df.groupby('Hospital').agg({'userKey': 'count', 'IMD_Decile': 'mean'}).reset_index()
                            grouped.columns = ['Hospital', 'User Count', 'Avg IMD Decile']
                            grouped = grouped.sort_values('User Count', ascending=False)
                            
                            st.dataframe(grouped, use_container_width=True)
                            fig = px.bar(grouped.head(10), x='Hospital', y='User Count', title='Top 10 Hospitals')
                            st.plotly_chart(fig, use_container_width=True)
                        
                        elif group_by == "Month & Hospital":
                            if date_type == "IMD Enrichment Date":
                                grouped = df.groupby(['IMDEnrichedYearMonth', 'Hospital']).agg({'userKey': 'count', 'IMD_Decile': 'mean'}).reset_index()
                                grouped.columns = ['Month', 'Hospital', 'User Count', 'Avg IMD Decile']
                            else:
                                grouped = df.groupby(['UserCreatedYearMonth', 'Hospital']).agg({'userKey': 'count', 'IMD_Decile': 'mean'}).reset_index()
                                grouped.columns = ['Month', 'Hospital', 'User Count', 'Avg IMD Decile']
                            st.dataframe(grouped, use_container_width=True)
                        
                        elif group_by == "IMD Decile":
                            grouped = df[df['IMD_Decile'].notna()].groupby('IMD_Decile').agg({'userKey': 'count'}).reset_index()
                            grouped.columns = ['IMD Decile', 'User Count']
                            
                            st.dataframe(grouped, use_container_width=True)
                            fig = px.bar(grouped, x='IMD Decile', y='User Count', title='Users by IMD Decile', color='IMD Decile', color_continuous_scale='RdYlGn')
                            st.plotly_chart(fig, use_container_width=True)
                        
                        elif group_by == "Data Source":
                            grouped = df.groupby('IMD_Data_Source').agg({'userKey': 'count', 'IMD_Decile': 'mean'}).reset_index()
                            grouped.columns = ['Data Source', 'User Count', 'Avg IMD Decile']
                            grouped = grouped.sort_values('User Count', ascending=False)
                            
                            st.dataframe(grouped, use_container_width=True)
                            fig = px.pie(grouped, values='User Count', names='Data Source', title='Users by Data Source')
                            st.plotly_chart(fig, use_container_width=True)
                    
                    # Full Data Table
                    st.markdown("---")
                    st.markdown("### 📋 Detailed Records")
                    
                    # Format dates for display
                    display_df = df.copy()
                    if 'UserCreatedDate' in display_df.columns:
                        display_df['UserCreatedDate'] = pd.to_datetime(display_df['UserCreatedDate']).dt.strftime('%Y-%m-%d %H:%M')
                    if 'IMDEnrichedDate' in display_df.columns:
                        display_df['IMDEnrichedDate'] = pd.to_datetime(display_df['IMDEnrichedDate']).dt.strftime('%Y-%m-%d %H:%M')
                    
                    st.dataframe(display_df, use_container_width=True, height=400)
                    
                    # Download button - Full data with all columns
                    date_str = f"{start_date.strftime('%Y%m%d') if hasattr(start_date, 'strftime') else start_date}_{end_date.strftime('%Y%m%d') if hasattr(end_date, 'strftime') else end_date}"
                    csv = df.to_csv(index=False)
                    st.download_button(
                        "📥 Download Full Report (CSV)",
                        csv,
                        f"imd_report_{date_str}.csv",
                        "text/csv",
                        use_container_width=True
                    )
                    
            except Exception as e:
                st.error(f"❌ Error generating report: {e}")
                st.exception(e)

elif page == "👥 Live User Audit":
    st.header("👥 Live User Enrichment (All UK Regions)")
    
    st.info("🇬🇧 Now supports **England**, **Scotland**, **Wales**, and **Northern Ireland**")
    
    try:
        target_table = "dbo.[user]"
        id_col = "userKey"
        pcd_col = "postcode"
        
        st.markdown("### 🔒 Configuration (Locked)")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.text_input("Target Table", value=target_table, disabled=True)
        with col2:
            st.text_input("ID Column", value=id_col, disabled=True)
        with col3:
            st.text_input("Postcode Column", value=pcd_col, disabled=True)

        # Statistics
        try:
            total_source = pd.read_sql(f"SELECT COUNT(*) as c FROM dbo.[user] WHERE [{pcd_col}] IS NOT NULL", engine_local).iloc[0]['c']
            total_enriched = pd.read_sql("SELECT COUNT(*) as c FROM dbo.IMD_Data WHERE IMD_Decile IS NOT NULL", engine_local).iloc[0]['c']
            total_in_imd = pd.read_sql("SELECT COUNT(*) as c FROM dbo.IMD_Data", engine_local).iloc[0]['c']
            remaining = max(0, total_source - total_in_imd)
            
            st.markdown("### 📊 Status Overview")
            k1, k2, k3 = st.columns(3)
            k1.metric("Total Users", f"{total_source:,}")
            k2.metric("✅ Enriched", f"{total_enriched:,}")
            k3.metric("🆕 New", f"{remaining:,}")
            
            # Show by data source
            source_stats = pd.read_sql("""
                SELECT COALESCE(IMD_Data_Source, IMD_Source) as Source, COUNT(*) as Count
                FROM dbo.IMD_Data
                GROUP BY COALESCE(IMD_Data_Source, IMD_Source)
                ORDER BY Count DESC
            """, engine_local)
            
            if not source_stats.empty:
                st.markdown("### 📊 Records by Data Source")
                st.dataframe(source_stats, use_container_width=True)
            
        except Exception as ex:
            st.warning(f"Could not load statistics: {ex}")

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            run_global = st.button("🚀 Run Global Update", type="primary", on_click=lock_ui)
        with col_btn2:
            reprocess_failed = st.button("🔄 Re-process Failed Records", type="secondary", on_click=lock_ui)
        
        if run_global or reprocess_failed:
            try:
                st.info("Starting enrichment...")
                
                # Create table if needed
                create_table_sql = """
                IF OBJECT_ID('dbo.IMD_Data', 'U') IS NULL
                CREATE TABLE dbo.IMD_Data (
                    userKey INT PRIMARY KEY, postcode NVARCHAR(20), IMD_Decile FLOAT,
                    IMD_Source NVARCHAR(50), Lat FLOAT, Lon FLOAT, LastEnrichedDate DATETIME,
                    IMD_Mean FLOAT, IMD_Median FLOAT, IMD_Mode INT, IMD_Min INT, IMD_Max INT,
                    IMD_Range NVARCHAR(20), Postcode_Count INT, Decile_Distribution NVARCHAR(100),
                    IMD_Data_Source NVARCHAR(50)
                )
                """
                with engine_local.connect() as c:
                    c.execute(text(create_table_sql))
                    c.commit()
                
                if reprocess_failed:
                    with engine_local.connect() as c:
                        c.execute(text("DELETE FROM dbo.IMD_Data WHERE IMD_Decile IS NULL"))
                        c.commit()
                    st.info("🗑️ Removed failed records for re-processing")
                
                existing_ids = pd.read_sql("SELECT userKey FROM dbo.IMD_Data", engine_local)['userKey'].tolist()
                all_users = pd.read_sql(f"SELECT [{id_col}], [{pcd_col}] FROM {target_table} WHERE [{pcd_col}] IS NOT NULL", engine_local)
                new_users = all_users[~all_users[id_col].isin(existing_ids)]
                
                if new_users.empty:
                    st.success("✅ All users are already enriched.")
                else:
                    progress = st.progress(0)
                    status_text = st.empty()
                    
                    BATCH = 100
                    total_batches = (len(new_users) + BATCH - 1) // BATCH
                    
                    for batch_num, i in enumerate(range(0, len(new_users), BATCH), 1):
                        batch = new_users.iloc[i:i+BATCH].copy()
                        progress.progress(int((batch_num / total_batches) * 100))
                        status_text.caption(f"📄 Batch {batch_num}/{total_batches}...")
                        
                        # Enrich each postcode
                        results = []
                        for _, row in batch.iterrows():
                            result = enrich_postcode_all_regions(row[pcd_col], engine_local)
                            result['userKey'] = row[id_col]
                            result['postcode'] = row[pcd_col]
                            result['Lat'] = None
                            result['Lon'] = None
                            result['LastEnrichedDate'] = datetime.datetime.now()
                            results.append(result)
                        
                        results_df = pd.DataFrame(results)
                        
                        cols_to_save = ['userKey', 'postcode', 'IMD_Decile', 'IMD_Source', 'Lat', 'Lon',
                                       'LastEnrichedDate', 'IMD_Mean', 'IMD_Median', 'IMD_Mode',
                                       'IMD_Min', 'IMD_Max', 'IMD_Range', 'Postcode_Count', 'IMD_Data_Source']
                        
                        for col in cols_to_save:
                            if col not in results_df.columns:
                                results_df[col] = None
                        
                        try:
                            results_df[cols_to_save].to_sql("IMD_Data", engine_local, if_exists='append', index=False)
                        except Exception as e:
                            status_text.caption(f"⚠️ Save error: {str(e)[:40]}")
                    
                    progress.progress(100)
                    st.success(f"✅ Processed {len(new_users):,} users!")
                    st.balloons()
            
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                unlock_ui()
                st.rerun()
    
    except Exception as e:
        st.error(f"Setup Error: {e}")

elif page == "📊 IMD Statistics":
    st.header("📊 IMD Statistics")
    
    try:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Records by Data Source")
            stats = pd.read_sql("""
                SELECT COALESCE(IMD_Data_Source, 'No Data') as Source, COUNT(*) as Count
                FROM IMD_Data GROUP BY IMD_Data_Source ORDER BY Count DESC
            """, engine_local)
            st.dataframe(stats, use_container_width=True)
        
        with col2:
            st.subheader("Records by Match Type")
            match_stats = pd.read_sql("""
                SELECT IMD_Source as Match_Type, COUNT(*) as Count
                FROM IMD_Data GROUP BY IMD_Source ORDER BY Count DESC
            """, engine_local)
            st.dataframe(match_stats, use_container_width=True)
        
        # Database totals
        st.subheader("Database Totals")
        totals = {}
        for table, name in [('PostcodeData', 'England Postcodes'), ('IMD_2025', 'England LSOAs'),
                           ('SIMD_Scotland', 'Scotland'), ('WIMD_Wales', 'Wales'), ('NIMDM_NI', 'N. Ireland')]:
            try:
                cursor = engine_local.raw_connection().cursor()
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                totals[name] = cursor.fetchone()[0]
                cursor.close()
            except:
                totals[name] = 'N/A'
        
        cols = st.columns(5)
        for i, (name, count) in enumerate(totals.items()):
            with cols[i]:
                st.metric(name, f"{count:,}" if isinstance(count, int) else count)
    
    except Exception as e:
        st.error(f"Error: {e}")

elif page == "📤 File Upload":
    st.header("📤 File Upload & Enrichment")
    
    hospitals = get_hospital_list(engine_local)
    hospital_name = st.selectbox("Select Hospital", hospitals)
    
    uploaded_file = st.file_uploader("Upload CSV/Excel with postcodes", type=['csv', 'xlsx'])
    
    if uploaded_file and st.button("🚀 Process File", type="primary"):
        with st.spinner("Processing..."):
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            pcd_col = next((c for c in df.columns if "postcode" in c.lower()), None)
            if not pcd_col:
                st.error("No 'Postcode' column found")
            else:
                st.info(f"Processing {len(df)} postcodes...")
                
                results = []
                progress = st.progress(0)
                for i, row in df.iterrows():
                    result = enrich_postcode_all_regions(row[pcd_col], engine_local)
                    result['postcode'] = row[pcd_col]
                    results.append(result)
                    progress.progress((i+1) / len(df))
                
                results_df = pd.DataFrame(results)
                enriched_df = pd.concat([df, results_df.drop(columns=['postcode'])], axis=1)
                
                st.success(f"✅ Processed {len(enriched_df)} records!")
                
                # Summary - match actual database values
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    england = len(enriched_df[enriched_df['IMD_Data_Source'].str.contains('IMD.?2025|England', na=False, regex=True, case=False)])
                    st.metric("🏴󠁧󠁢󠁥󠁮󠁧󠁿 England", england)
                with col2:
                    scotland = len(enriched_df[enriched_df['IMD_Data_Source'].str.contains('SIMD|Scotland', na=False, regex=True, case=False)])
                    st.metric("🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scotland", scotland)
                with col3:
                    wales = len(enriched_df[enriched_df['IMD_Data_Source'].str.contains('WIMD|Wales', na=False, regex=True, case=False)])
                    st.metric("🏴󠁧󠁢󠁷󠁬󠁳󠁿 Wales", wales)
                with col4:
                    ni = len(enriched_df[enriched_df['IMD_Data_Source'].str.contains('NIMDM|Ireland', na=False, regex=True, case=False)])
                    st.metric("🇬🇧 N. Ireland", ni)
                
                st.dataframe(enriched_df, use_container_width=True)
                
                csv = enriched_df.to_csv(index=False)
                st.download_button("📥 Download Enriched CSV", csv, "enriched_data.csv", "text/csv")

elif page == "🗺️ Heatmap Engine":
    st.header("🗺️ Heatmap Engine")
    
    with st.expander("ℹ️ What is this page?", expanded=False):
        st.markdown("""
        **Purpose:** Visualize IMD data on an interactive map with multiple aggregation options.
        
        **Features:**
        - **Point Markers**: Individual postcodes as pins on the map
        - **Choropleth**: Aggregate by postcode sector (circle size = user count, color = IMD level)
        - **Hexagon Heatmap (H3)**: Uber's H3 hexagonal grid for uniform area analysis - eliminates bias from irregular admin boundaries
        - Filter by hospital, date range, and IMD decile
        - Export filtered data to Excel
        """)
    
    # Hospital filter in sidebar
    hospitals = get_hospital_list(engine_local)
    hospitals.insert(0, "All Hospitals")
    selected_hospital_filter = st.sidebar.selectbox("🏥 Hospital Filter", hospitals, key="heatmap_hospital")
    
    # Data type filter
    data_type_filter = st.sidebar.selectbox("📊 Data Type", ["All Data", "Partial Averages Only"], key="heatmap_data_type")
    
    try:
        # Load data with coordinates
        if selected_hospital_filter == 'All Hospitals':
            df = pd.read_sql("""
                SELECT imd.Lat as lat, imd.Lon as lon, imd.IMD_Decile as Final_Decile, 
                       h.hospital as Hospital, COALESCE(ud.registrationDate, u.lastUpdated) as CollectionDate, 
                       imd.postcode as postcode, imd.IMD_Source as Match_Type, imd.IMD_Data_Source
                FROM dbo.IMD_Data imd
                INNER JOIN dbo.[user] u ON imd.userKey = u.userKey
                LEFT JOIN dbo.UserDetail ud ON u.userKey = ud.userKey
                INNER JOIN dbo.RefHospital h ON u.hospitalKey = h.hospitalKey
                WHERE imd.IMD_Decile IS NOT NULL
            """, engine_local)
        else:
            df = pd.read_sql(f"""
                SELECT imd.Lat as lat, imd.Lon as lon, imd.IMD_Decile as Final_Decile, 
                       h.hospital as Hospital, COALESCE(ud.registrationDate, u.lastUpdated) as CollectionDate, 
                       imd.postcode as postcode, imd.IMD_Source as Match_Type, imd.IMD_Data_Source
                FROM dbo.IMD_Data imd
                INNER JOIN dbo.[user] u ON imd.userKey = u.userKey
                LEFT JOIN dbo.UserDetail ud ON u.userKey = ud.userKey
                INNER JOIN dbo.RefHospital h ON u.hospitalKey = h.hospitalKey
                WHERE imd.IMD_Decile IS NOT NULL AND h.hospital = '{selected_hospital_filter}'
            """, engine_local)
        
        if df.empty:
            st.warning("⚠️ No data found. Please run 'Live User Audit' first to enrich postcodes.")
            st.stop()
        
        # Convert types
        df['CollectionDate'] = pd.to_datetime(df['CollectionDate'], errors='coerce')
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
        df['Final_Decile'] = pd.to_numeric(df['Final_Decile'], errors='coerce')
        
        # Apply data type filter
        if data_type_filter == "Partial Averages Only":
            if 'Match_Type' in df.columns:
                df = df[df['Match_Type'] == 'Partial Average'].copy()
                st.sidebar.success(f"✅ Showing {len(df)} Partial Average records")
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📍 Total Postcodes", f"{len(df):,}")
        with col2:
            avg_decile = df['Final_Decile'].mean()
            st.metric("📊 Avg IMD Decile", f"{avg_decile:.1f}")
        with col3:
            st.metric("🏥 Hospitals", df['Hospital'].nunique())
        with col4:
            most_common = df['Final_Decile'].mode()[0] if not df.empty else "N/A"
            st.metric("🎯 Most Common Decile", int(most_common) if most_common != "N/A" else "N/A")
        
        # Date range
        min_date = df['CollectionDate'].min()
        max_date = df['CollectionDate'].max()
        
        if pd.isna(min_date): min_date = datetime.datetime.now()
        if pd.isna(max_date): max_date = datetime.datetime.now()
        if min_date == max_date: min_date = min_date - datetime.timedelta(days=1)
        
        with st.expander("🔎 Additional Filter Options", expanded=True):
            st.caption("📅 **Filtering by User Registration Date**")
            
            c1, c2, c3 = st.columns(3)
            with c1:
                dr = st.slider("Date Range", min_value=min_date.date(), max_value=max_date.date(), 
                              value=(min_date.date(), max_date.date()))
            with c2:
                decile_r = st.slider("IMD Decile Range", 1.0, 10.0, (1.0, 10.0))
            with c3:
                hosps = df['Hospital'].dropna().unique().tolist()
                sel_hosp = st.multiselect("Filter Hospitals (Optional)", hosps, default=[])
        
        # Apply Filters
        mask = (
            (df['CollectionDate'].dt.date >= dr[0]) & 
            (df['CollectionDate'].dt.date <= dr[1]) &
            (df['Final_Decile'] >= decile_r[0]) &
            (df['Final_Decile'] <= decile_r[1])
        )
        if sel_hosp: 
            mask = mask & (df['Hospital'].isin(sel_hosp))
        
        df_filtered = df[mask].copy()
        
        # Export button
        col_export1, col_export2 = st.columns([1, 3])
        with col_export1:
            if st.button("📥 Export Filtered Data", use_container_width=True):
                csv = df_filtered.to_csv(index=False)
                st.download_button("⬇️ Download CSV", csv, f"heatmap_export_{selected_hospital_filter.replace(' ', '_')}.csv", "text/csv")
        
        with col_export2:
            st.info(f"ℹ️ **{selected_hospital_filter}** | {len(df_filtered):,} records after filters | {len(df_filtered[df_filtered['lat'].notna()]):,} with coordinates")
        
        st.markdown("---")
        
        # Map type selection
        map_options = ["📍 Point Markers", "🗺️ Area Choropleth (by Postcode Sector)"]
        if H3_AVAILABLE:
            map_options.append("⬡ Hexagon Heatmap (H3)")
        
        map_type = st.radio(
            "Map Display Type:",
            map_options,
            horizontal=True,
            help="Point markers show individual postcodes. Choropleth shows postcode sectors. Hexagon uses H3 for uniform area analysis."
        )
        
        # Hexagon-specific options
        if H3_AVAILABLE and map_type == "⬡ Hexagon Heatmap (H3)":
            with st.expander("⬡ Hexagon Settings", expanded=True):
                hex_col1, hex_col2, hex_col3, hex_col4 = st.columns(4)
                with hex_col1:
                    hex_resolution = st.slider("H3 Resolution", min_value=4, max_value=9, value=7, 
                                               help="Higher = smaller hexagons. 7 ≈ 5km², 8 ≈ 0.7km²")
                with hex_col2:
                    hex_stat = st.selectbox("IMD Statistic", ["mean", "median", "mode"])
                with hex_col3:
                    hex_color = st.selectbox("Color By", ["IMD Decile", "User Count"])
                with hex_col4:
                    hex_labels = st.checkbox("Show Labels", value=True)
        
        # Filter to only records with coordinates for mapping
        df_map = df_filtered.dropna(subset=['lat', 'lon', 'Final_Decile'])
        
        if df_map.empty:
            st.warning("⚠️ No records with coordinates to display. Run 'Update Coordinates' below to fetch missing coordinates.")
        elif map_type == "📍 Point Markers":
            st.info(f"📍 Mapping **{len(df_map)}** points")
            fig = px.scatter_mapbox(
                df_map, lat="lat", lon="lon", color="Final_Decile",
                size_max=15, zoom=6, height=600,
                hover_data=['Hospital', 'CollectionDate', 'postcode', 'IMD_Data_Source'],
                color_continuous_scale="RdYlGn", range_color=[1, 10]
            )
            fig.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":40,"l":0,"b":0})
            st.plotly_chart(fig, use_container_width=True)
        
        elif map_type == "🗺️ Area Choropleth (by Postcode Sector)":
            st.info("🗺️ Generating Postcode Sector Choropleth Map...")
            
            import plotly.graph_objects as go
            
            # Extract postcode sector from full postcode
            def extract_sector(pc):
                if pd.isna(pc): return None
                pc = str(pc).upper().strip().replace(' ', '')
                if len(pc) >= 4:
                    return pc[:-2] + ' ' + pc[-3] if len(pc) > 3 else pc
                return pc
            
            df_sectors = df_map.copy()
            df_sectors['Sector'] = df_sectors['postcode'].apply(extract_sector)
            
            # Aggregate by sector
            sector_stats = df_sectors.groupby('Sector').agg({
                'Final_Decile': 'mean',
                'postcode': 'count',
                'lat': 'mean',
                'lon': 'mean'
            }).reset_index()
            sector_stats.columns = ['Sector', 'Avg_IMD', 'User_Count', 'lat', 'lon']
            sector_stats = sector_stats.dropna(subset=['lat', 'lon'])
            
            # IMD category for colors
            def imd_category(decile):
                if decile <= 2: return '1-2 (Most Deprived)'
                elif decile <= 4: return '3-4 (High Deprivation)'
                elif decile <= 6: return '5-6 (Medium)'
                elif decile <= 8: return '7-8 (Low Deprivation)'
                else: return '9-10 (Least Deprived)'
            
            sector_stats['IMD_Category'] = sector_stats['Avg_IMD'].apply(imd_category)
            
            st.markdown(f"**Showing {len(sector_stats)} postcode sectors** (aggregated from {len(df_map)} postcodes)")
            
            # Color map
            color_map = {
                '1-2 (Most Deprived)': '#d73027',
                '3-4 (High Deprivation)': '#fc8d59',
                '5-6 (Medium)': '#fee08b',
                '7-8 (Low Deprivation)': '#91cf60',
                '9-10 (Least Deprived)': '#1a9850'
            }
            
            fig = go.Figure()
            
            # Add traces for each IMD category
            for category in ['1-2 (Most Deprived)', '3-4 (High Deprivation)', '5-6 (Medium)', '7-8 (Low Deprivation)', '9-10 (Least Deprived)']:
                df_cat = sector_stats[sector_stats['IMD_Category'] == category]
                if len(df_cat) > 0:
                    sizes = df_cat['User_Count'].apply(lambda x: min(max(x/3, 15), 60)).tolist()
                    
                    fig.add_trace(go.Scattermapbox(
                        lat=df_cat['lat'],
                        lon=df_cat['lon'],
                        mode='markers+text',
                        marker=dict(size=sizes, color=color_map[category], opacity=0.8, sizemode='diameter'),
                        text=df_cat['User_Count'].astype(str),
                        textposition='middle center',
                        textfont=dict(size=10, color='black', family='Arial Black'),
                        name=category,
                        hovertemplate='<b>%{customdata[0]}</b><br>Users: %{customdata[1]}<br>Avg IMD: %{customdata[2]:.1f}<extra></extra>',
                        customdata=df_cat[['Sector', 'User_Count', 'Avg_IMD']].values
                    ))
            
            fig.update_layout(
                mapbox=dict(style="open-street-map", center=dict(lat=sector_stats['lat'].mean(), lon=sector_stats['lon'].mean()), zoom=8),
                margin={"r":0,"t":40,"l":0,"b":0}, height=650,
                title="Postcode Sectors - Circle Size & Number = User Count, Color = IMD Level",
                legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor="rgba(255,255,255,0.8)", font=dict(size=11)),
                showlegend=True
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("""
            **🎨 Color Guide:**
            - 🔴 **Red** = Most Deprived (Decile 1-2)
            - 🟠 **Orange** = High Deprivation (Decile 3-4)
            - 🟡 **Yellow** = Medium (Decile 5-6)
            - 🟢 **Light Green** = Low Deprivation (Decile 7-8)
            - 🟢 **Dark Green** = Least Deprived (Decile 9-10)
            """)
            
            with st.expander("📊 Sector Summary Table"):
                display_df = sector_stats[['Sector', 'User_Count', 'Avg_IMD', 'IMD_Category']].copy()
                display_df['Avg_IMD'] = display_df['Avg_IMD'].round(1)
                display_df = display_df.sort_values('User_Count', ascending=False)
                st.dataframe(display_df, use_container_width=True)
        
        elif H3_AVAILABLE and map_type == "⬡ Hexagon Heatmap (H3)":
            # Hexagon Heatmap using H3
            st.info(f"⬡ Generating Hexagon Heatmap (H3 Resolution: {hex_resolution})...")
            
            # Check for required columns
            if len(df_map) == 0:
                st.warning("⚠️ No records with coordinates to display.")
            else:
                # Determine color column
                if hex_color == "IMD Decile":
                    color_column = f'{hex_stat}_imd'
                else:
                    color_column = 'postcode_count'
                
                # Create hexagon choropleth
                fig, hex_stats = create_hexagon_choropleth(
                    df_map, 
                    resolution=hex_resolution,
                    color_by=color_column,
                    stat_type=hex_stat,
                    show_labels=hex_labels,
                    title=f"UK IMD Hexagon Heatmap (H3 Res: {hex_resolution}, Stat: {hex_stat.capitalize()})"
                )
                
                if hex_stats.empty:
                    st.warning("⚠️ Could not create hexagon map. Check if data has valid coordinates.")
                else:
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Statistics Summary
                    st.markdown("### 📊 Hexagon Statistics")
                    
                    hcol1, hcol2, hcol3, hcol4, hcol5 = st.columns(5)
                    with hcol1:
                        st.metric("Total Postcodes", f"{len(df_map):,}")
                    with hcol2:
                        st.metric("Unique Hexagons", f"{len(hex_stats):,}")
                    with hcol3:
                        weighted_mean = (df_map['Final_Decile'] * 1).sum() / len(df_map)
                        st.metric("Mean IMD", f"{weighted_mean:.2f}")
                    with hcol4:
                        st.metric("Median IMD", f"{df_map['Final_Decile'].median():.1f}")
                    with hcol5:
                        st.metric("IMD Range", f"{int(df_map['Final_Decile'].min())} - {int(df_map['Final_Decile'].max())}")
                    
                    st.markdown("""
                    **⬡ Hexagon Advantages:**
                    - Uniform area representation (no bias from irregular admin boundaries)
                    - Better for comparing regions of different sizes
                    - Consistent visualization across zoom levels
                    """)
                    
                    st.markdown("""
                    **🎨 Color Guide:**
                    - 🔴 **Red** = Most Deprived (Decile 1-2)
                    - 🟠 **Orange** = High Deprivation (Decile 3-4)
                    - 🟡 **Yellow** = Medium (Decile 5-6)
                    - 🟢 **Light Green** = Low Deprivation (Decile 7-8)
                    - 🟢 **Dark Green** = Least Deprived (Decile 9-10)
                    """)
                    
                    with st.expander("📊 Hexagon Summary Table"):
                        display_df = hex_stats[['hex_id', 'postcode_count', 'mean_imd', 'median_imd', 'mode_imd', 'min_imd', 'max_imd', 'data_source']].copy()
                        display_df.columns = ['Hexagon ID', 'Postcodes', 'Mean IMD', 'Median IMD', 'Mode IMD', 'Min IMD', 'Max IMD', 'Region']
                        display_df['Mean IMD'] = display_df['Mean IMD'].round(1)
                        display_df['Median IMD'] = display_df['Median IMD'].round(1)
                        display_df = display_df.sort_values('Postcodes', ascending=False)
                        st.dataframe(display_df, use_container_width=True)
                    
                    with st.expander("📖 H3 Resolution Guide"):
                        st.markdown("""
                        | Resolution | Avg Hexagon Area | Avg Edge Length | Use Case |
                        |:----------:|:----------------:|:---------------:|:---------|
                        | 4 | ~1,770 km² | ~22 km | Country-level overview |
                        | 5 | ~252 km² | ~8 km | Regional analysis |
                        | 6 | ~36 km² | ~3.2 km | County/district level |
                        | 7 | ~5.16 km² | ~1.2 km | City districts |
                        | 8 | ~0.74 km² | ~460 m | Neighborhood level |
                        | 9 | ~0.11 km² | ~174 m | Street level |
                        """)
        
        # Coordinate update tool
        st.markdown("---")
        with st.expander("🔧 Update Missing Coordinates", expanded=False):
            missing_coords = len(df_filtered[df_filtered['lat'].isna()])
            st.warning(f"⚠️ {missing_coords:,} records missing coordinates")
            
            if st.button("🔄 Fetch Coordinates via postcodes.io API", type="primary"):
                with st.spinner("Fetching coordinates..."):
                    postcodes_to_fetch = df_filtered[df_filtered['lat'].isna()]['postcode'].dropna().unique().tolist()[:500]  # Limit to 500
                    
                    if postcodes_to_fetch:
                        coords_map = get_coordinates_bulk(postcodes_to_fetch)
                        st.success(f"✅ Retrieved coordinates for {len(coords_map)} postcodes")
                        
                        # Update in database
                        updated = 0
                        with engine_local.connect() as conn:
                            for pc, coords in coords_map.items():
                                try:
                                    conn.execute(text("UPDATE IMD_Data SET Lat = :lat, Lon = :lon WHERE REPLACE(postcode, ' ', '') = :pc"),
                                               {"lat": coords['lat'], "lon": coords['lon'], "pc": pc.replace(' ', '').upper()})
                                    updated += 1
                                except:
                                    pass
                            conn.commit()
                        
                        st.success(f"✅ Updated {updated} records in database. Refresh page to see changes.")
                    else:
                        st.info("No postcodes need coordinate updates")
    
    except Exception as e:
        st.error(f"Error: {e}")
        st.exception(e)

elif page == "📊 Power BI":
    st.header("📊 Interactive Analytics")
    
    try:
        df = pd.read_sql("""
            SELECT h.hospital as Hospital, imd.IMD_Decile as Final_Decile, 
                   imd.LastEnrichedDate as CollectionDate, imd.IMD_Data_Source
            FROM dbo.IMD_Data imd
            INNER JOIN dbo.[user] u ON imd.userKey = u.userKey
            INNER JOIN dbo.RefHospital h ON u.hospitalKey = h.hospitalKey
            WHERE imd.IMD_Decile IS NOT NULL
        """, engine_local)
        
        if df.empty:
            st.warning("No data available")
        else:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Records", f"{len(df):,}")
            with col2:
                st.metric("Hospitals", df['Hospital'].nunique())
            with col3:
                st.metric("Avg IMD Decile", f"{df['Final_Decile'].mean():.1f}")
            
            # Decile distribution
            decile_counts = df['Final_Decile'].value_counts().sort_index().reset_index()
            decile_counts.columns = ['Decile', 'Count']
            
            fig = px.bar(decile_counts, x='Decile', y='Count', title="IMD Decile Distribution",
                        color='Count', color_continuous_scale='RdYlGn')
            st.plotly_chart(fig, use_container_width=True)
            
            # By data source
            source_counts = df['IMD_Data_Source'].value_counts().reset_index()
            source_counts.columns = ['Source', 'Count']
            
            fig2 = px.pie(source_counts, values='Count', names='Source', title="Records by Region")
            st.plotly_chart(fig2, use_container_width=True)
    
    except Exception as e:
        st.error(f"Error: {e}")

elif page == "🛠️ Connection Diagnostics":
    st.header("🛠️ Connection Diagnostics")
    
    st.markdown("### 🔒 Password Update Tool")
    new_pass = st.text_input("Enter New Password", type="password")
    if st.button("Generate New Hash"):
        if new_pass:
            new_hash = hashlib.sha256(new_pass.encode()).hexdigest()
            st.code(f'password_hash = "{new_hash}"')
            st.success("✅ Copy this hash")
    
    st.markdown("---")
    if st.button("Test Database Connection"):
        try:
            with engine_local.connect() as c:
                st.success(f"✅ Connected to: {c.execute(text('SELECT DB_NAME()')).scalar()}")
                
                # Check all tables
                tables = ['PostcodeData', 'IMD_2025', 'SIMD_Scotland', 'WIMD_Wales', 'NIMDM_NI', 'IMD_Data']
                for table in tables:
                    try:
                        result = c.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                        st.write(f"✅ {table}: {result:,} records")
                    except:
                        st.write(f"❌ {table}: Not found")
        except Exception as e:
            st.error(f"❌ Connection failed: {e}")
