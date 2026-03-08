# ========== Flask API للسبام الفائق - نسخة مصححة ==========
from flask import Flask, request, jsonify
import threading
import time
import random
import logging
import os
import asyncio
import urllib3
from datetime import datetime
import httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

# إلغاء تحذيرات SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ========== إنشاء تطبيق Flask ==========
app = Flask(__name__)

# ========== الإعدادات الأساسية ==========
API_KEY = "your-secret-api-key-here"  # غير هذا بمفتاح سري
MAX_ACCOUNTS_PER_USER = 500
REQUESTS_PER_ACCOUNT = 20

# User Agents متنوعة
USER_AGENTS = [
    "Dalvik/2.1.0 (Linux; U; Android 7.1.2; ASUS_Z01QD Build/QKQ1.190825.002)",
    "Dalvik/2.1.0 (Linux; U; Android 8.0.0; SM-G960F Build/R16NW)",
    "Dalvik/2.1.0 (Linux; U; Android 9; Redmi Note 7 Build/PKQ1.190616.001)",
    "Dalvik/2.1.0 (Linux; U; Android 10; SM-G975F Build/QP1A.190711.020)",
    "Dalvik/2.1.0 (Linux; U; Android 11; Pixel 4 Build/RQ3A.211001.001)",
    "Dalvik/2.1.0 (Linux; U; Android 12; SM-G998B Build/SP1A.210812.016)",
]

# ========== تحميل الحسابات ==========
def load_accounts():
    accounts = {}
    if not os.path.exists("accounts.txt"):
        logger.error("ملف accounts.txt غير موجود!")
        # حسابات تجريبية إذا الملف مش موجود
        accounts = {"test1": "pass1", "test2": "pass2"}
        return accounts
    
    try:
        with open("accounts.txt", 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and ':' in line and not line.startswith('#'):
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        uid, pwd = parts
                        accounts[uid.strip()] = pwd.strip()
    except Exception as e:
        logger.error(f"خطأ في قراءة الملف: {e}")
        accounts = {"test1": "pass1", "test2": "pass2"}
    
    logger.info(f"✅ تم تحميل {len(accounts)} حساب")
    return accounts

ALL_ACCOUNTS = load_accounts()

# ========== تخزين الجلسات ==========
active_sessions = {}  # {session_id: {'target': str, 'accounts': list, 'active': bool, 'user': str}}
jwt_cache = {}        # {uid: {'token': str, 'expiry': float}}

# ========== دوال التشفير ==========
def encrypt_api(plain_text):
    plain_text = bytes.fromhex(plain_text)
    key = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
    iv  = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.encrypt(pad(plain_text, AES.block_size)).hex()

def Encrypt_ID(x):
    x = int(x)
    dec = ['80','81','82','83','84','85','86','87','88','89','8a','8b','8c','8d','8e','8f',
           '90','91','92','93','94','95','96','97','98','99','9a','9b','9c','9d','9e','9f',
           'a0','a1','a2','a3','a4','a5','a6','a7','a8','a9','aa','ab','ac','ad','ae','af',
           'b0','b1','b2','b3','b4','b5','b6','b7','b8','b9','ba','bb','bc','bd','be','bf',
           'c0','c1','c2','c3','c4','c5','c6','c7','c8','c9','ca','cb','cc','cd','ce','cf',
           'd0','d1','d2','d3','d4','d5','d6','d7','d8','d9','da','db','dc','dd','de','df',
           'e0','e1','e2','e3','e4','e5','e6','e7','e8','e9','ea','eb','ec','ed','ee','ef',
           'f0','f1','f2','f3','f4','f5','f6','f7','f8','f9','fa','fb','fc','fd','fe','ff']
    
    try:
        result = ""
        for _ in range(5):
            x = x / 128
            idx = int((x - int(x)) * 128)
            if 0 <= idx < len(dec):
                result = dec[idx] + result
        return result
    except:
        return ""

# ========== جلب JWT سريع مع كاش ==========
async def get_jwt(uid, password):
    if uid in jwt_cache and time.time() < jwt_cache[uid]['expiry']:
        return jwt_cache[uid]['token']
    
    try:
        async with httpx.AsyncClient(verify=False, timeout=5) as client:
            resp = await client.get(f"https://jwt-zenith.vercel.app/get?uid={uid}&password={password}")
            if resp.status_code == 200:
                data = resp.json()
                token = data.get('token') or data.get('jwt')
                if token and token.count('.') >= 2:
                    jwt_cache[uid] = {'token': token, 'expiry': time.time() + 3600}
                    return token
    except Exception as e:
        logger.error(f"خطأ في جلب JWT: {e}")
    return None

# ========== إرسال طلب الصداقة ==========
FRIEND_URLS = [
    "https://clientbp.ggblueshark.com/RequestAddingFriend",
    "https://clientbp.common.ggbluefox.com/RequestAddingFriend",
    "https://clientbp.ggwhitehawk.com/RequestAddingFriend",
]

async def send_friend_request(target_id, uid, password, session):
    token = await get_jwt(uid, password)
    if not token:
        return False

    headers = {
        'Accept-Encoding': 'gzip',
        'Authorization': f'Bearer {token}',
        'Connection': 'Keep-Alive',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Host': 'clientbp.ggblueshark.com',
        'ReleaseVersion': 'OB52',
        'User-Agent': random.choice(USER_AGENTS),
        'X-GA': 'v1 1',
        'X-Unity-Version': '2018.4.11f1'
    }

    try:
        encrypted_id = Encrypt_ID(int(target_id))
        if not encrypted_id:
            return False
        
        payload_hex = f'08a7c4839f1e10{encrypted_id}1801'
        data = bytes.fromhex(encrypt_api(payload_hex))

        for url in FRIEND_URLS:
            try:
                if 'ggbluefox' in url:
                    headers['Host'] = 'clientbp.common.ggbluefox.com'
                elif 'ggwhitehawk' in url:
                    headers['Host'] = 'clientbp.ggwhitehawk.com'
                else:
                    headers['Host'] = 'clientbp.ggblueshark.com'
                    
                response = await session.post(url, headers=headers, data=data, timeout=10)
                if response.status_code == 200:
                    return True
                elif response.status_code == 503:
                    continue
            except:
                continue
    except Exception as e:
        logger.error(f"خطأ في الإرسال: {e}")
    
    return False

# ========== سبام لكل حساب ==========
async def account_spammer(target_id, uid, password, request_count):
    success = 0
    failed = 0
    
    try:
        async with httpx.AsyncClient(verify=False, timeout=30) as session:
            for i in range(request_count):
                try:
                    if await send_friend_request(target_id, uid, password, session):
                        success += 1
                    else:
                        failed += 1
                        
                    if i % 50 == 0 and i > 0:
                        await asyncio.sleep(0.1)
                except:
                    failed += 1
    except Exception as e:
        logger.error(f"خطأ في account_spammer: {e}")
    
    return success, failed

# ========== المدير الرئيسي للسبام ==========
def spam_worker(session_id, target_id, accounts):
    """تشغيل السبام في thread منفصل"""
    logger.info(f"🚀 بدء سبام للجلسة {session_id} على {target_id}")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    total_success = 0
    total_failed = 0
    account_index = 0
    accounts_list = list(accounts)  # تحويل للقائمة
    
    while session_id in active_sessions and active_sessions[session_id]['active']:
        if account_index >= len(accounts_list):
            account_index = 0
            random.shuffle(accounts_list)
        
        uid, pwd = accounts_list[account_index]
        account_index += 1
        
        logger.info(f"📤 حساب {uid} يبدأ بإرسال {REQUESTS_PER_ACCOUNT} طلب")
        
        try:
            success, failed = loop.run_until_complete(
                account_spammer(target_id, uid, pwd, REQUESTS_PER_ACCOUNT)
            )
            
            total_success += success
            total_failed += failed
        except Exception as e:
            logger.error(f"خطأ في تشغيل account_spammer: {e}")
            total_failed += REQUESTS_PER_ACCOUNT
        
        if account_index % 5 == 0:
            logger.info(f"📊 تقدم: {account_index}/{len(accounts_list)} حسابات - نجاح: {total_success}, فشل: {total_failed}")
    
    loop.close()
    
    if session_id in active_sessions:
        active_sessions[session_id]['result'] = {
            'success': total_success,
            'failed': total_failed,
            'total': total_success + total_failed
        }
        active_sessions[session_id]['active'] = False
        logger.info(f"✅ انتهت الجلسة {session_id} - نجاح: {total_success}, فشل: {total_failed}")

# ========== مسار الصفحة الرئيسية ==========
@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'name': 'Spam API',
        'version': '1.0',
        'status': 'running',
        'endpoints': {
            '/spam': 'POST - بدء سبام جديد',
            '/stop': 'POST - إيقاف سبام',
            '/status': 'GET - حالة سبام',
            '/stats': 'GET - إحصائيات'
        }
    })

# ========== بدء سبام ==========
@app.route('/spam', methods=['POST'])
def start_spam():
    # التحقق من API Key
    auth_header = request.headers.get('Authorization')
    if not auth_header or auth_header != f"Bearer {API_KEY}":
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    target_id = data.get('target')
    user_id = data.get('user_id', 'anonymous')
    
    if not target_id:
        return jsonify({'error': 'Target ID required'}), 400
    
    # التحقق من الحسابات
    accounts_list = list(ALL_ACCOUNTS.items())
    if len(accounts_list) < 2:  # على الأقل حسابين
        return jsonify({'error': 'Not enough accounts'}), 400
    
    # اختيار حسابات
    accounts_count = min(MAX_ACCOUNTS_PER_USER, len(accounts_list))
    selected = random.sample(accounts_list, accounts_count)
    
    # إنشاء معرف جلسة
    session_id = f"{user_id}_{int(time.time())}"
    
    # تسجيل الجلسة
    active_sessions[session_id] = {
        'target': target_id,
        'accounts': selected,
        'active': True,
        'user': user_id,
        'start_time': time.time(),
        'result': None
    }
    
    # تشغيل السبام في thread منفصل
    thread = threading.Thread(
        target=spam_worker,
        args=(session_id, target_id, selected),
        daemon=True
    )
    thread.start()
    
    total_requests = len(selected) * REQUESTS_PER_ACCOUNT
    
    return jsonify({
        'message': 'Spam started',
        'session_id': session_id,
        'target': target_id,
        'accounts': len(selected),
        'requests_per_account': REQUESTS_PER_ACCOUNT,
        'total_requests': total_requests
    })

# ========== إيقاف سبام ==========
@app.route('/stop', methods=['POST'])
def stop_spam():
    auth_header = request.headers.get('Authorization')
    if not auth_header or auth_header != f"Bearer {API_KEY}":
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    session_id = data.get('session_id')
    if not session_id:
        return jsonify({'error': 'Session ID required'}), 400
    
    if session_id not in active_sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    active_sessions[session_id]['active'] = False
    
    return jsonify({
        'message': 'Spam stopped',
        'session_id': session_id
    })

# ========== حالة سبام ==========
@app.route('/status', methods=['GET'])
def get_status():
    auth_header = request.headers.get('Authorization')
    if not auth_header or auth_header != f"Bearer {API_KEY}":
        return jsonify({'error': 'Unauthorized'}), 401
    
    session_id = request.args.get('session_id')
    if not session_id:
        return jsonify({'error': 'Session ID required'}), 400
    
    if session_id not in active_sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    session = active_sessions[session_id]
    
    return jsonify({
        'session_id': session_id,
        'target': session['target'],
        'active': session['active'],
        'user': session['user'],
        'running_time': round(time.time() - session['start_time'], 2),
        'result': session['result']
    })

# ========== إحصائيات ==========
@app.route('/stats', methods=['GET'])
def get_stats():
    auth_header = request.headers.get('Authorization')
    if not auth_header or auth_header != f"Bearer {API_KEY}":
        return jsonify({'error': 'Unauthorized'}), 401
    
    total_accounts = len(ALL_ACCOUNTS)
    active = sum(1 for s in active_sessions.values() if s['active'])
    completed = sum(1 for s in active_sessions.values() if not s['active'] and s['result'])
    
    return jsonify({
        'total_accounts': total_accounts,
        'active_sessions': active,
        'completed_sessions': completed,
        'total_sessions': len(active_sessions),
        'requests_per_account': REQUESTS_PER_ACCOUNT
    })

# ========== تنظيف الجلسات القديمة ==========
def cleanup_loop():
    """تنظيف الجلسات المنتهية كل ساعة"""
    while True:
        try:
            now = time.time()
            # حذف الجلسات المكتملة الأقدم من ساعة
            expired = []
            for sid, session in active_sessions.items():
                if not session['active'] and session['result'] and (now - session['start_time']) > 3600:
                    expired.append(sid)
            
            for sid in expired:
                del active_sessions[sid]
                logger.info(f"🧹 تم حذف الجلسة القديمة {sid}")
            
        except Exception as e:
            logger.error(f"خطأ في التنظيف: {e}")
        
        time.sleep(3600)  # كل ساعة

# ========== تشغيل التطبيق ==========
if __name__ == "__main__":
    logger.info("✅ Flask API للسبام الفائق يعمل...")
    logger.info(f"⚡ كل حساب سيرسل {REQUESTS_PER_ACCOUNT} طلب")
    logger.info(f"📊 إجمالي الحسابات: {len(ALL_ACCOUNTS)}")
    
    # تشغيل thread التنظيف
    cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
    cleanup_thread.start()
    
    # تشغيل Flask
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)