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
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID", "YOUR_CHAT_ID")
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
logger.info("🚀 ROHAN PAID BOT - RAILWAY.APP DEPLOYMENT")
logger.info("="*60)
logger.info("🚀 BOT INITIALIZED")
logger.info(f"BOT_TOKEN: {BOT_TOKEN[:10]}...")
logger.info(f"CHAT_ID: {CHAT_ID}")

# ========================
# CLEAR TELEGRAM CONFLICTS
# ========================
def clear_telegram_conflicts():
    """Clear any existing webhooks or conflicts"""
    try:
        logger.info("🧹 Clearing Telegram conflicts...")
        
        # Delete webhook with drop_pending_updates=true
        delete_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true"
        response = requests.get(delete_url, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                logger.info("✅ Webhook deleted and pending updates dropped")
            else:
                logger.warning(f"⚠️ Webhook deletion response: {result}")
        else:
            logger.warning(f"⚠️ Failed to delete webhook: {response.status_code}")
        
        # Wait a moment for Telegram to process
        time.sleep(2)
        
        return True
    except Exception as e:
        logger.error(f"❌ Error clearing conflicts: {e}")
        return False

# ========================
# TELEGRAM BOT SETUP WITH RETRY
# ========================
def setup_updater_with_retry(max_retries=5):
    """Setup updater with automatic retry on conflicts"""
    global updater
    
    for attempt in range(max_retries):
        try:
            logger.info(f"🔄 Setting up Telegram updater (attempt {attempt + 1}/{max_retries})")
            
            # Clear conflicts first
            clear_telegram_conflicts()
            
            # Create updater
            updater = Updater(token=BOT_TOKEN, use_context=True)
            dispatcher = updater.dispatcher
            
            # Add command handlers
            dispatcher.add_handler(CommandHandler("start", start_command))
            dispatcher.add_handler(CommandHandler("stop", stop_command))
            dispatcher.add_handler(CommandHandler("status", status_command))
            dispatcher.add_handler(CommandHandler("help", help_command))
            dispatcher.add_handler(CommandHandler("logs", logs_command))
            
            logger.info("✅ Telegram Bot Setup Complete")
            return updater
            
        except Conflict as e:
            logger.warning(f"⚠️ Conflict on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 10  # 10, 20, 30, 40, 50 seconds
                logger.info(f"⏰ Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
            else:
                logger.error("❌ Max retries reached for Telegram setup")
                return None
                
        except Exception as e:
            logger.error(f"❌ Telegram Setup Error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                logger.error("❌ Max retries reached for Telegram setup")
                return None
    
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
✅ **BOT STARTED**

🚀 Bot is now running 24/7 on Railway.app
📊 Hits will be sent to this chat automatically
🛑 Use /stop to stop the bot
📈 Use /status to check stats

🎯 **Starting threads...**
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
📊 **BOT STATUS**

✅ Running: {is_running}
📈 Total Hits: {total_hits}
🎯 Good Instagram Emails: {good_ig}
❌ Bad Instagram: {bad_insta}
📧 Bad Gmails: {bad_email}
🔄 Current Hits: {hits}

⏰ Uptime: Running on Railway.app
🚀 By: @ROHAN_DEAL_BOT
    """
    update.message.reply_text(status_text, parse_mode='Markdown')

def help_command(update: Update, context: CallbackContext):
    help_text = """
🤖 **ROHAN PAID BOT COMMANDS**

/start - Start the bot (runs 24/7)
/stop - Stop the bot
/status - Show bot stats
/logs - Show last 10 log lines
/help - Show this message

🎯 **Features:**
✅ Runs 24/7 on Railway.app
✅ Auto-restarts if crashes
✅ Sends hits to Telegram
✅ Auto-changes headers
✅ Conflict prevention
✅ Multi-threaded scraping

BY ~ @ROHAN_DEAL_BOT
    """
    update.message.reply_text(help_text, parse_mode='Markdown')

def logs_command(update: Update, context: CallbackContext):
    try:
        with open('bot.log', 'r') as f:
            lines = f.readlines()
        last_lines = ''.join(lines[-10:])  # Last 10 lines only
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
        }
        data = {'email': mail}
        res = requests.post(url, headers=headers, data=data, timeout=10).text
        return "email_is_taken" in res
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
            'User-Agent': str(user_agent.generate_user_agent())
        }
        
        recovery_url = "https://accounts.google.com/signin/v2/usernamerecovery?flowName=GlifWebSignIn&flowEntry=ServiceLogin&hl=en-GB"
        
        try:
            res1 = requests.get(recovery_url, headers=headers, timeout=10)
            tok = re.search(r'&quot;(.*?)&quot;,null,null,null,&quot;(.*?)&', res1.text)
            if tok:
                token = tok.group(2)
            else:
                logger.warning("Token extraction failed, generating new one...")
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
        cookies = {'__Host-GAPS': host}
        
        headers = {
            'User-Agent': user_agent.generate_user_agent(),
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        
        params = {'TL': tl}
        data = f"continue=https%3A%2F%2Fmail.google.com&f.req=%5B%22TL%3A{tl}%22%2C%22{email}%22%2C0%2C0%2C1%5D&flowName=GlifWebSignIn"
        
        response = requests.post('https://accounts.google.com/_/signup/usernameavailability',
                                params=params, cookies=cookies, headers=headers, data=data, timeout=10)
        
        if '"gf.uar",1' in response.text:
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
    except Exception as e:
        logger.error(f"Check Error: {e}")
        with lock:
            bad_insta += 1

# ========================
# FETCH ACCOUNT INFO & SEND TO TELEGRAM
# ========================
def fetch_account_info(username, domain):
    global total_hits
    try:
        with lock:
            total_hits += 1
        
        account_info = infoinsta.get(username, {})
        followers = account_info.get('follower_count', 'N/A')
        following = account_info.get('following_count', 'N/A')
        posts = account_info.get('media_count', 'N/A')
        bio = account_info.get('biography', 'N/A')
        full_name = account_info.get('full_name', 'N/A')
        
        reset_status = get_reset_info(username)
        
        info_text = f"""
🚀 **ROHAN PAID BOT HIT**

🎯 Hit #: `{total_hits}`
👤 Username: `@{username}`
📧 Email: `{username}@{domain}`
👥 Followers: `{followers}`
➡️ Following: `{following}`
📸 Posts: `{posts}`
📝 Bio: `{bio}`
🔁 Reset: `{reset_status}`

⏰ Time: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`

BY ~ @ROHAN_DEAL_BOT
        """
        
        log_to_file(info_text)
        send_to_telegram(info_text)
        logger.info(f"✅ HIT #{total_hits}: {username}@{domain}")
        
    except Exception as e:
        logger.error(f"Fetch Account Info Error: {e}")

# ========================
# LOG & TELEGRAM SENDER
# ========================
def log_to_file(text):
    try:
        with open('instahits.txt', 'a') as f:
            f.write(text + "\n" + "="*50 + "\n")
    except Exception as e:
        logger.error(f"Log Error: {e}")

def send_to_telegram(text):
    try:
        requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?chat_id={CHAT_ID}&text={text}&parse_mode=Markdown",
            timeout=10
        )
    except Exception as e:
        logger.error(f"Telegram Send Error: {e}")

# ========================
# MAIN INSTAGRAM SCRAPER LOOP
# ========================
def instagram_scraper():
    logger.info("🔄 Instagram Scraper Started")
    
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
            }
            
            response = requests.post(
                'https://www.instagram.com/api/graphql',
                headers=headers,
                data=data,
                timeout=15
            )
            
            account = response.json().get('data', {}).get('user', {})
            username = account.get('username')
            
            if username:
                infoinsta[username] = account
                emails = [username + instatool_domain]
                
                for email in emails:
                    check(email)
            
            time.sleep(random.uniform(3, 7))  # Increased delay
            
        except Exception as e:
            logger.error(f"Instagram Scraper Error: {e}")
            time.sleep(5)

# ========================
# START BOT THREADS
# ========================
def start_bot_threads():
    logger.info("📌 Starting Bot Threads...")
    
    # Start multiple scraper threads (reduced to prevent overload)
    for i in range(3):  # 3 concurrent threads instead of 5
        thread = threading.Thread(target=instagram_scraper, daemon=True, name=f"Scraper-{i+1}")
        thread.start()
        logger.info(f"✅ Thread {i+1} started")
    
    time.sleep(1)

# ========================
# MAIN EXECUTION WITH RETRY LOGIC
# ========================
def main():
    logger.info("🔑 Generating Google Token...")
    generate_google_token()
    
    # Setup updater with conflict handling
    updater = setup_updater_with_retry()
    
    if not updater:
        logger.error("❌ Failed to setup Telegram bot after all retries. Exiting...")
        sys.exit(1)
    
    # Start polling with error handling
    try:
        logger.info("🚀 Starting Telegram Polling...")
        updater.start_polling(
            poll_interval=2,  # Increased poll interval
            timeout=20,       # Increased timeout
            clean=True,       # Clean pending updates on start
            allowed_updates=['message']  # Only message updates
        )
        updater.idle()
        
    except KeyboardInterrupt:
        logger.info("⚠️ Bot interrupted by user")
        updater.stop()
        
    except NetworkError as e:
        logger.error(f"❌ Network Error: {e}")
        time.sleep(30)
        main()  # Restart
        
    except Conflict as e:
        logger.error(f"❌ Conflict Error: {e}")
        time.sleep(60)  # Wait longer for conflicts
        main()  # Restart
        
    except Exception as e:
        logger.error(f"❌ Main Error: {e}")
        time.sleep(30)
        main()  # Restart

if __name__ == '__main__':
    main()
