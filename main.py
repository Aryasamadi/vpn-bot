# -*- coding: utf-8 -*-
"""
ربات مدیریت ساب‌لینک v2 – نسخه Railway + Cloudflare API
- بازنویسی شده برای اجرای مستقل در پایتون استاندارد
- اتصال به D1 و KV از طریق Cloudflare API
"""

import os
import json
import base64
import uuid
import datetime
import traceback
import asyncio
import httpx
import re
import urllib.parse
from fastapi import FastAPI, Request, Response
import uvicorn

# ---------------------------------------------------------------------
# 🔐 متغیرهای محیطی (Environment Variables)
# ---------------------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = os.getenv("ADMIN_IDS", "")

CF_ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID", "")
CF_API_TOKEN = os.getenv("CF_API_TOKEN", "")
CF_D1_ID = os.getenv("CF_D1_ID", "")
CF_KV_ID = os.getenv("CF_KV_ID", "")

CF_HEADERS = {
    "Authorization": f"Bearer {CF_API_TOKEN}",
    "Content-Type": "application/json"
}

# ---------------------------------------------------------------------
# 📚 تمام متون فارسی در یک جا
# ---------------------------------------------------------------------
STRINGS = {
    "start_welcome": (
        "👋 به ربات هوشمند مدیریت ساب‌لینک خوش آمدید!\n\n"
        "از طریق دکمه‌های زیر می‌توانید حساب خود را مدیریت کرده و ساب‌لینک دریافت کنید."
    ),
    "not_member": (
        "⚠️ برای فعال‌سازی کامل امکانات ربات، ابتدا در کانال‌های زیر عضو شوید و سپس روی دکمه «عضو شدم» کلیک کنید."
    ),
    "membership_confirmed": "✅ عضویت شما تأیید شد! اکنون می‌توانید از ربات استفاده کنید.",
    "trial_already_used": "⚠️ شما قبلاً از تست رایگان ۱ روزه استفاده کرده‌اید.",
    "trial_activated": "🎁 اشتراک تست ۱ روزه شما با موفقیت فعال شد!",
    "wallet_info": "👛 جزئیات کیف پول شما:\n\n💰 موجودی فعلی: {balance:,} تومان\n👥 تعداد زیرمجموعه‌ها: {ref_count} نفر",
    "insufficient_balance": (
        "❌ موجودی حساب شما کافی نیست.\n\n"
        "💰 موجودی شما: {balance:,} تومان\n"
        "💵 مبلغ مورد نیاز: {price:,} تومان"
    ),
    "subscription_created": "✅ اشتراک {duration} روزه شما با موفقیت ساخته شد:\n\n`{sublink}`\n\n📅 تاریخ انقضا: {expires_at} (UTC)",
    "no_active_services": "⚠️ شما اشتراک فعالی در حال حاضر ندارید.",
    "services_list": "📋 لیست سرویس‌های فعال شما ({count} مورد):",
    "referral_info": (
        "👥 سیستم زیرمجموعه‌گیری و دعوت دوستان:\n\n"
        "با دعوت از دوستانتان کیف پولتان را شارژ کنید و رایگان خرید کنید!\n\n"
        "🎁 پاداش دعوت هر کاربر: {reward:,} تومان\n\n"
        "🔗 لینک اختصاصی شما برای دعوت:\n`{ref_link}`"
    ),
    "support_contact": "🎧 بخش ارتباط با پشتیبانی:",
    "support_session_started": "💬 پشتیبانی: پیام خود را ارسال کنید. (برای پایان، دکمه «🔚 پایان پشتیبانی» را بزنید)",
    "support_session_ended": "🔚 جلسه پشتیبانی پایان یافت.",
    "support_forwarded": "پیام از کاربر {user_id}:\n\n{text}",
    "admin_only": "⛔ این بخش فقط برای مدیران در دسترس است.",
    "admin_panel": "🛠 به بخش ادمین خوش آمدید. دستورات مدیریتی را انتخاب کنید:",
    "config_added": "✅ کانفیگ با موفقیت پردازش و ثبت شد (همراه با پرچم).\nمنتظر کانفیگ بعدی هستیم (یا دکمه خروج را بزنید):",
    "config_add_stopped": "⏹ عملیات افزودن کانفیگ متوقف شد.",
    "broadcast_start": "📢 متن پیام همگانی خود را ارسال کنید (برای لغو، «لغو» را بنویسید):",
    "broadcast_sending": "⏳ در حال ارسال همگانی...",
    "broadcast_done": "✅ پیام همگانی ارسال شد.\nتعداد کل: {success} از {total}",
    "settings_show": (
        "⚙️ تنظیمات ربات:\n\n"
        "🎁 پاداش دعوت: {reward:,} تومان\n"
        "📢 کانال‌های اجباری: `{channels}`\n"
    ),
    "user_not_found": "❌ کاربر یافت نشد.",
    "user_info": (
        "👤 جزئیات حساب کاربر:\n\n"
        "🆔 آیدی تلگرام: `{tg_id}`\n"
        "👤 نام و کاربری: {full_name} | {username}\n"
        "💰 موجودی کیف پول: {balance:,} تومان\n"
        "🎁 استفاده از تست رایگان: {trial_status}"
    ),
    "balance_added": "✅ مبلغ {amount:,} تومان به حساب کاربر {target_id} اضافه گردید.",
    "balance_subtracted": "✅ مبلغ {amount:,} تومان از موجودی کاربر {target_id} کسر شد.",
    "setting_updated": "✅ فیلد تنظیمات با موفقیت آپدیت شد.",
    "plan_add_step1": "📝 نام پلن را وارد کنید:",
    "plan_add_step2": "💰 قیمت (به تومان) را وارد کنید:",
    "plan_add_step3": "📆 مدت زمان (تعداد روز) را وارد کنید:",
    "plan_add_step4": "👥 محدودیت کاربر (حداکثر کاربر مجاز) را وارد کنید:",
    "plan_added": "✅ پلن «{name}» با موفقیت اضافه شد.",
    "plan_deleted": "🗑 پلن حذف شد.",
    "plan_toggled": "✅ وضعیت پلن تغییر کرد.",
    "no_plans": "هیچ پلنی وجود ندارد.",
    "plan_list_item": "📌 نام: {name}\n💰 قیمت: {price:,} تومان\n📆 مدت: {duration} روز\n👥 لیمیت کاربر: {max_users}\n🟢 وضعیت: {status}",
    "choose_plan": "پلن مورد نظر را انتخاب کنید:",
    "purchase_cancelled": "❌ عملیات لغو شد.",
}

# ---------------------------------------------------------------------
# 🔧 توابع کمکی و API کلاودفلر
# ---------------------------------------------------------------------
def safe_int(value, default=0):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def get_rows(db_res):
    if db_res and isinstance(db_res, dict) and db_res.get("success"):
        try:
            return db_res["result"][0].get("results", [])
        except (IndexError, KeyError):
            pass
    return []

def get_first_row(db_res):
    rows = get_rows(db_res)
    return rows[0] if rows else None

async def query_db(sql, *args):
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/d1/database/{CF_D1_ID}/query"
    payload = {"sql": sql, "params": list(args)}
    async with httpx.AsyncClient() as client:
        try:
            res = await client.post(url, headers=CF_HEADERS, json=payload, timeout=10.0)
            return res.json()
        except Exception as e:
            print(f"D1 API Error: {str(e)}")
            return {"success": False, "error": str(e)}

async def execute_db(sql, *args):
    return await query_db(sql, *args)

# ---------------------------------------------------------------------
# 📨 ارتباط با تلگرام
# ---------------------------------------------------------------------
async def call_telegram(method, payload):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=10.0)
            return response.json()
        except Exception as e:
            print(f"Telegram API error: {str(e)}")
            return {"ok": False, "description": str(e)}

# ---------------------------------------------------------------------
# ⚙️ مدیریت تنظیمات با کش KV کلادفلر
# ---------------------------------------------------------------------
async def get_kv(key):
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_ID}/values/{key}"
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(url, headers={"Authorization": f"Bearer {CF_API_TOKEN}"})
            if r.status_code == 200:
                return r.text
        except Exception:
            pass
    return None

async def put_kv(key, value, expiration_ttl=None):
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_ID}/values/{key}"
    params = {}
    if expiration_ttl:
        params['expiration_ttl'] = expiration_ttl
    async with httpx.AsyncClient() as client:
        try:
            await client.put(url, headers={"Authorization": f"Bearer {CF_API_TOKEN}"}, params=params, content=str(value))
        except Exception:
            pass

async def delete_kv(key):
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_ID}/values/{key}"
    async with httpx.AsyncClient() as client:
        try:
            await client.delete(url, headers={"Authorization": f"Bearer {CF_API_TOKEN}"})
        except Exception:
            pass

async def get_setting(key, default=None):
    cached = await get_kv(f"setting_{key}")
    if cached is not None:
        return cached

    res = await query_db("SELECT value FROM settings WHERE key = ?", key)
    row = get_first_row(res)
    if row:
        value = row["value"]
        await put_kv(f"setting_{key}", value, expiration_ttl=600)
        return value
    return default

async def set_setting(key, value):
    await execute_db("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", key, str(value))
    await put_kv(f"setting_{key}", str(value), expiration_ttl=600)

# ---------------------------------------------------------------------
# 🗄️ مقداردهی اولیه دیتابیس و توابع پردازش کانفیگ
# ---------------------------------------------------------------------
def extract_ip_from_config(config_text):
    try:
        if config_text.startswith("vmess://"):
            j = json.loads(base64.b64decode(config_text[8:]).decode('utf-8'))
            return j.get('add', '')
        elif "://" in config_text:
            parsed = urllib.parse.urlparse(config_text)
            return parsed.hostname
    except:
        pass
    return ""

async def format_config_name(config_text):
    ip = extract_ip_from_config(config_text)
    if not ip:
        return config_text
    
    country_str = "🌍 Unknown"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://ip-api.com/json/{ip}?fields=country,countryCode", timeout=5.0)
            data = resp.json()
            if data.get("country"):
                code = data.get("countryCode")
                flag = chr(ord(code[0]) + 127397) + chr(ord(code[1]) + 127397) if len(code) == 2 else ""
                country_str = f"{flag} {data.get('country')}"
    except:
        pass

    new_name = f"{country_str} | @TechNowVpn"
    
    try:
        if config_text.startswith("vmess://"):
            j = json.loads(base64.b64decode(config_text[8:]).decode('utf-8'))
            j['ps'] = new_name
            return "vmess://" + base64.b64encode(json.dumps(j).encode('utf-8')).decode('utf-8')
        elif "://" in config_text:
            parsed = urllib.parse.urlparse(config_text)
            parsed = parsed._replace(fragment=urllib.parse.quote(new_name))
            return urllib.parse.urlunparse(parsed)
    except:
        pass
    return config_text

async def init_database_if_needed():
    initialized = await get_kv("db_initialized_v2_1")
    if initialized == "true":
        return

    queries = [
        """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id TEXT UNIQUE NOT NULL,
            username TEXT DEFAULT NULL,
            full_name TEXT DEFAULT NULL,
            balance INTEGER DEFAULT 0,
            referred_by TEXT DEFAULT NULL,
            has_used_trial INTEGER DEFAULT 0,
            state TEXT DEFAULT NULL,
            plan_data TEXT DEFAULT NULL,
            is_test_mode INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_id INTEGER DEFAULT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );""",
        """CREATE TABLE IF NOT EXISTS configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_text TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            fail_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );""",
        """CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            duration_days INTEGER NOT NULL,
            max_users INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );"""
    ]
    
    for q in queries:
        await execute_db(q)

    # Safe alter columns if they were missing in old DB
    try: await execute_db("ALTER TABLE configs ADD COLUMN fail_count INTEGER DEFAULT 0")
    except: pass
    try: await execute_db("ALTER TABLE users ADD COLUMN username TEXT DEFAULT NULL")
    except: pass
    try: await execute_db("ALTER TABLE users ADD COLUMN full_name TEXT DEFAULT NULL")
    except: pass
    try: await execute_db("ALTER TABLE users ADD COLUMN is_test_mode INTEGER DEFAULT 0")
    except: pass
    try: await execute_db("ALTER TABLE subscriptions ADD COLUMN plan_id INTEGER DEFAULT NULL")
    except: pass

    defaults = {
        "referral_reward": "2000",
        "force_channels": "",
    }
    for key, val in defaults.items():
        res = await query_db("SELECT value FROM settings WHERE key = ?", key)
        if not get_first_row(res):
            await execute_db("INSERT INTO settings (key, value) VALUES (?, ?)", key, val)

    await put_kv("db_initialized_v2_1", "true")

async def background_config_checker():
    while True:
        await asyncio.sleep(8 * 3600)  # Check every 8 hours
        try:
            res = await query_db("SELECT * FROM configs WHERE is_active = 1")
            configs = get_rows(res)
            for cfg in configs:
                is_healthy = False
                try:
                    ip = extract_ip_from_config(cfg["config_text"])
                    port = 443
                    if cfg["config_text"].startswith("vmess://"):
                        j = json.loads(base64.b64decode(cfg["config_text"][8:]).decode('utf-8'))
                        port = int(j.get('port', 443))
                    elif "://" in cfg["config_text"]:
                        parsed = urllib.parse.urlparse(cfg["config_text"])
                        port = parsed.port or 443
                        
                    if ip:
                        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=4.0)
                        writer.close()
                        await writer.wait_closed()
                        is_healthy = True
                except:
                    pass

                if not is_healthy:
                    fail_count = cfg.get("fail_count", 0) + 1
                    if fail_count >= 3:
                        await execute_db("DELETE FROM configs WHERE id = ?", cfg["id"])
                        await delete_kv("cached_configs_payload")
                        if ADMIN_IDS:
                            admins = [x.strip() for x in str(ADMIN_IDS).split(",") if x.strip()]
                            for admin_id in admins:
                                await call_telegram("sendMessage", {
                                    "chat_id": int(admin_id),
                                    "text": f"⚠️ کانفیگ زیر به دلیل 3 بار عدم اتصال متوالی (حذف خودکار) گردید:\n\n`{cfg['config_text']}`",
                                    "parse_mode": "Markdown"
                                })
                    else:
                        await execute_db("UPDATE configs SET fail_count = ? WHERE id = ?", fail_count, cfg["id"])
                else:
                    await execute_db("UPDATE configs SET fail_count = 0 WHERE id = ?", cfg["id"])
        except Exception as e:
            print(f"Checker error: {e}")

# ---------------------------------------------------------------------
# 🧑‍💼 توابع کاربر و ادمین
# ---------------------------------------------------------------------
def is_admin(telegram_id, user_data=None):
    if not ADMIN_IDS:
        return False
    admins = [x.strip() for x in str(ADMIN_IDS).split(",") if x.strip()]
    if str(telegram_id) not in admins:
        return False
    if user_data and user_data.get("is_test_mode"):
        return False
    return True

async def get_or_create_user(telegram_id, referred_by=None, from_user=None):
    res = await query_db("SELECT * FROM users WHERE telegram_id = ?", str(telegram_id))
    user = get_first_row(res)
    
    username = ""
    full_name = ""
    if from_user:
        username = f"@{from_user.get('username')}" if from_user.get("username") else "ندارد"
        first_name = from_user.get("first_name", "")
        last_name = from_user.get("last_name", "")
        full_name = f"{first_name} {last_name}".strip()

    if not user:
        ref_id = None
        if referred_by and str(referred_by) != str(telegram_id):
            ref_res = await query_db("SELECT id FROM users WHERE telegram_id = ?", str(referred_by))
            if get_first_row(ref_res):
                ref_id = str(referred_by)
        if ref_id:
            await execute_db("INSERT INTO users (telegram_id, referred_by, username, full_name) VALUES (?, ?, ?, ?)", str(telegram_id), ref_id, username, full_name)
        else:
            await execute_db("INSERT INTO users (telegram_id, username, full_name) VALUES (?, ?, ?)", str(telegram_id), username, full_name)
        res = await query_db("SELECT * FROM users WHERE telegram_id = ?", str(telegram_id))
        user = get_first_row(res)
    else:
        # Update user names
        if from_user:
            await execute_db("UPDATE users SET username = ?, full_name = ? WHERE id = ?", username, full_name, user["id"])
            user["username"] = username
            user["full_name"] = full_name
            
    return user

async def check_channel_membership(telegram_id):
    force_channels = await get_setting("force_channels", "")
    if not force_channels:
        return True
    
    channels = [c.strip() for c in force_channels.split(",") if c.strip()]
    for channel in channels:
        if not channel.startswith("@") and not channel.startswith("-100"):
            channel = f"@{channel}"
        
        res = await call_telegram("getChatMember", {
            "chat_id": channel,
            "user_id": int(telegram_id)
        })
        if not res.get("ok"):
            return False
        status = res["result"].get("status")
        if status not in ["creator", "administrator", "member"]:
            return False
    return True

async def build_sub_url_async(token):
    # Retrieve current base url dynamically or rely on railway domain
    # Since fastAPI doesn't easily know its public railway URL in this context without request object, 
    # we'll assume a railway domain setup or simply relative.
    domain = os.environ.get("RAILWAY_STATIC_URL", "your-app.up.railway.app")
    domain = domain.replace("https://", "").replace("http://", "")
    return f"https://{domain}/sub/{token}"

# ---------------------------------------------------------------------
# 📋 کیبوردهای اینلاین
# ---------------------------------------------------------------------
def get_user_inline_keyboard(is_actual_admin=False):
    kb = [
        [{"text": "🛒 خرید سرویس (رایگان)", "callback_data": "buy_service"}, {"text": "🎁 تست رایگان", "callback_data": "free_trial"}],
        [{"text": "📱 سرویس‌های من", "callback_data": "my_services"}, {"text": "👛 کیف پول", "callback_data": "wallet"}],
        [{"text": "👥 دعوت دوستان", "callback_data": "referral"}, {"text": "🎧 پشتیبانی", "callback_data": "support"}],
        [{"text": "📖 راهنما", "callback_data": "help_btn"}]
    ]
    if is_actual_admin:
        kb.append([{"text": "👑 بازگشت به مدیریت", "callback_data": "admin_return"}])
    return {"inline_keyboard": kb}

def get_admin_inline_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "➕ افزودن کانفیگ", "callback_data": "adm_add_config"}, {"text": "📋 مدیریت کانفیگ‌ها", "callback_data": "adm_manage_configs"}],
            [{"text": "📢 ارسال همگانی", "callback_data": "adm_broadcast"}, {"text": "⚙️ تنظیمات", "callback_data": "adm_settings"}],
            [{"text": "👤 مدیریت کاربران", "callback_data": "adm_manage_users_1"}, {"text": "📦 مدیریت پلن‌ها", "callback_data": "adm_manage_plans"}],
            [{"text": "📖 تنظیم راهنما", "callback_data": "adm_set_help"}, {"text": "👤 نمای کاربری (تست)", "callback_data": "adm_test_user"}]
        ]
    }

def get_plans_inline_keyboard(plans):
    kb = []
    for p in plans:
        kb.append([{"text": f"{p['name']} - {p['price']:,} تومان", "callback_data": f"buy_plan_{p['id']}"}])
    kb.append([{"text": "❌ لغو", "callback_data": "cancel_action"}])
    return {"inline_keyboard": kb}

# ---------------------------------------------------------------------
# 🧠 توابع اصلی
# ---------------------------------------------------------------------
async def send_membership_requirement(chat_id):
    force_channels = await get_setting("force_channels", "")
    if not force_channels:
        return
    channels = [c.strip() for c in force_channels.split(",") if c.strip()]
    
    kb = []
    for ch in channels:
        ch_clean = ch.replace('@', '')
        kb.append([{"text": f"📢 عضویت در {ch}", "url": f"https://t.me/{ch_clean}"}])
    kb.append([{"text": "✅ عضو شدم (تایید)", "callback_data": "chk_membership"}])
    
    markup = {"inline_keyboard": kb}
    await call_telegram("sendMessage", {
        "chat_id": chat_id,
        "text": STRINGS["not_member"],
        "reply_markup": markup
    })

async def credit_referrer_if_pending(user, chat_id):
    ref_id = user.get("referred_by")
    if ref_id and not str(ref_id).endswith("_rewarded"):
        reward_val = await get_setting("referral_reward", "2000")
        reward = safe_int(reward_val, 2000)
        await execute_db("UPDATE users SET balance = balance + ? WHERE telegram_id = ?", reward, ref_id)
        await call_telegram("sendMessage", {
            "chat_id": int(ref_id),
            "text": f"🎉 یکی از کاربران با لینک دعوت شما عضو شد و مبلغ {reward:,} تومان به موجودی شما افزوده گردید!"
        })
        new_ref_status = f"{ref_id}_rewarded"
        await execute_db("UPDATE users SET referred_by = ? WHERE id = ?", new_ref_status, user["id"])

# ---------------------------------------------------------------------
# 🧩 هندلرهای کاربر
# ---------------------------------------------------------------------
async def handle_free_trial(user, chat_id):
    if user.get("has_used_trial"):
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["trial_already_used"]})
        return
    token = uuid.uuid4().hex
    expires_at = (datetime.datetime.utcnow() + datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    await execute_db("INSERT INTO subscriptions (user_id, token, expires_at) VALUES (?, ?, ?)", user["id"], token, expires_at)
    await execute_db("UPDATE users SET has_used_trial = 1 WHERE id = ?", user["id"])
    sub_url = await build_sub_url_async(token)
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={sub_url}"
    msg = STRINGS["trial_activated"] + f"\n\n🔗 ساب‌لینک:\n`{sub_url}`\n\n📅 انقضا: {expires_at} (UTC)"
    await call_telegram("sendPhoto", {
        "chat_id": chat_id,
        "photo": qr_url,
        "caption": msg,
        "parse_mode": "Markdown"
    })

async def handle_wallet(user, chat_id):
    telegram_id = user["telegram_id"]
    ref_count_res = await query_db("SELECT COUNT(*) as count FROM users WHERE referred_by LIKE ?", f"{telegram_id}%")
    ref_count_row = get_first_row(ref_count_res)
    ref_count = ref_count_row["count"] if ref_count_row else 0
    msg = STRINGS["wallet_info"].format(balance=user["balance"], ref_count=ref_count)
    await call_telegram("sendMessage", {"chat_id": chat_id, "text": msg})

async def handle_buy_service(user, chat_id):
    res = await query_db("SELECT * FROM plans WHERE is_active = 1")
    plans = get_rows(res)
    if not plans:
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ هیچ پلن فعالی در حال حاضر موجود نیست."})
        return
    
    txt = "🛒 پلن مورد نظر خود را انتخاب کنید:\n\n"
    for p in plans:
        txt += f"📌 {p['name']} | 👥 {p['max_users']} کاربر | 📆 {p['duration_days']} روز | 💰 {p['price']:,} تومان\n"
        
    markup = get_plans_inline_keyboard(plans)
    await call_telegram("sendMessage", {
        "chat_id": chat_id,
        "text": txt,
        "reply_markup": markup
    })

async def handle_my_services(user, chat_id):
    sub_res = await query_db("SELECT * FROM subscriptions WHERE user_id = ? AND status = 'active' ORDER BY id DESC", user["id"])
    subs = get_rows(sub_res)
    if not subs:
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["no_active_services"]})
        return
    await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["services_list"].format(count=len(subs))})
    for s in subs:
        sub_url = await build_sub_url_async(s["token"])
        
        markup = {
            "inline_keyboard": [
                [{"text": "🖼 نمایش کیوآرکد", "callback_data": f"qr_{s['token']}"}],
                [{"text": "♻️ تمدید سرویس", "callback_data": f"renew_sub_{s['token']}"}, {"text": "🗑 حذف سرویس", "callback_data": f"del_sub_req_{s['token']}"}]
            ]
        }
        await call_telegram("sendMessage", {
            "chat_id": chat_id,
            "text": f"🔗 ساب‌لینک شما:\n`{sub_url}`\n\n📅 تاریخ انقضا: {s['expires_at']} (UTC)",
            "parse_mode": "Markdown",
            "reply_markup": markup
        })

async def handle_referral(user, chat_id):
    reward_val = await get_setting("referral_reward", "2000")
    reward = safe_int(reward_val, 2000)
    bot_info = await call_telegram("getMe", {})
    bot_username = bot_info.get("result", {}).get("username", "V2rayBot")
    ref_link = f"https://t.me/{bot_username}?start={user['telegram_id']}"
    msg = STRINGS["referral_info"].format(reward=reward, ref_link=ref_link)
    await call_telegram("sendMessage", {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})

async def handle_support_start(user, chat_id):
    await execute_db("UPDATE users SET state = ? WHERE id = ?", f"support_session_{user['telegram_id']}", user["id"])
    markup = {
        "keyboard": [[{"text": "🔚 پایان پشتیبانی"}]],
        "resize_keyboard": True
    }
    await call_telegram("sendMessage", {
        "chat_id": chat_id,
        "text": STRINGS["support_session_started"],
        "reply_markup": markup
    })

async def forward_support_message(user, message, chat_id):
    if not ADMIN_IDS:
        return
    admins = [x.strip() for x in str(ADMIN_IDS).split(",") if x.strip()]
    text = message.get("text", "")
    
    for admin_id in admins:
        payload = {"chat_id": int(admin_id)}
        method = "sendMessage"
        caption = STRINGS["support_forwarded"].format(user_id=user["telegram_id"], text=message.get("caption", text))
        
        if message.get("photo"):
            method = "sendPhoto"
            payload["photo"] = message["photo"][-1]["file_id"]
            payload["caption"] = caption
        elif message.get("document"):
            method = "sendDocument"
            payload["document"] = message["document"]["file_id"]
            payload["caption"] = caption
        else:
            payload["text"] = caption
            
        await call_telegram(method, payload)
        
    await call_telegram("sendMessage", {
        "chat_id": chat_id,
        "text": "✅ پیام شما به پشتیبان‌ها ارسال شد. منتظر پاسخ باشید."
    })

async def create_subscription_from_plan(plan_id, user_id):
    res = await query_db("SELECT * FROM plans WHERE id = ? AND is_active = 1", plan_id)
    plan = get_first_row(res)
    if not plan:
        return None
    token = uuid.uuid4().hex
    expires_at = (datetime.datetime.utcnow() + datetime.timedelta(days=plan["duration_days"])).strftime("%Y-%m-%d %H:%M:%S")
    await execute_db("INSERT INTO subscriptions (user_id, plan_id, token, expires_at) VALUES (?, ?, ?, ?)", user_id, plan_id, token, expires_at)
    return token

# ---------------------------------------------------------------------
# 💬 مدیریت state ها
# ---------------------------------------------------------------------
async def handle_state(user, state, message, chat_id, is_admin_user, actual_is_admin):
    text = message.get("text", "").strip()
    
    if text in ["❌ خروج / اتمام ارسال", "لغو", "/cancel"]:
        await execute_db("UPDATE users SET state = NULL, plan_data = NULL WHERE id = ?", user["id"])
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": "عملیات لغو شد."})
        if is_admin_user:
            await show_admin_panel(chat_id)
        else:
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["start_welcome"], "reply_markup": get_user_inline_keyboard(actual_is_admin)})
        return True

    if is_admin_user:
        if state == "waiting_for_config":
            formatted_cfg = await format_config_name(text)
            await execute_db("INSERT INTO configs (config_text) VALUES (?)", formatted_cfg)
            await delete_kv("cached_configs_payload")
            markup = {"inline_keyboard": [[{"text": "❌ خروج", "callback_data": "admin_return"}]]}
            await call_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": STRINGS["config_added"],
                "reply_markup": markup
            })
            return True

        if state == "waiting_for_broadcast":
            await execute_db("UPDATE users SET state = ?, plan_data = ? WHERE id = ?", "waiting_for_broadcast_confirm", text, user["id"])
            markup = {"inline_keyboard": [[{"text": "✅ تایید و ارسال", "callback_data": "adm_broadcast_yes"}, {"text": "❌ لغو", "callback_data": "admin_return"}]]}
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": f"آیا از ارسال این پیام به همه کاربران اطمینان دارید؟\n\nمتن پیام:\n{text}", "reply_markup": markup})
            return True

        if state == "waiting_for_user_search":
            target_tg = text.strip()
            res = await query_db("SELECT * FROM users WHERE telegram_id = ?", target_tg)
            target_user = get_first_row(res)
            if not target_user:
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["user_not_found"]})
                return True
            await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])
            info = STRINGS["user_info"].format(
                tg_id=target_user["telegram_id"],
                full_name=target_user["full_name"] or "ندارد",
                username=target_user["username"] or "ندارد",
                balance=target_user["balance"],
                trial_status="بله" if target_user["has_used_trial"] else "خیر"
            )
            markup = {
                "inline_keyboard": [
                    [{"text": "➕ افزایش موجودی", "callback_data": f"adm_add_bal_{target_user['telegram_id']}"},
                     {"text": "➖ کاهش موجودی", "callback_data": f"adm_sub_bal_{target_user['telegram_id']}"}],
                    [{"text": "🔙 بازگشت", "callback_data": "adm_manage_users_1"}]
                ]
            }
            await call_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": info,
                "parse_mode": "Markdown",
                "reply_markup": markup
            })
            return True

        if state.startswith("waiting_for_add_"):
            target_id = state.replace("waiting_for_add_", "")
            amount = safe_int(text)
            if amount <= 0:
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ لطفاً عدد مثبت وارد کنید:"})
                return True
            await execute_db("UPDATE users SET balance = balance + ?, state = NULL WHERE telegram_id = ?", amount, target_id)
            await call_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": STRINGS["balance_added"].format(amount=amount, target_id=target_id),
                "reply_markup": get_admin_inline_keyboard()
            })
            await call_telegram("sendMessage", {
                "chat_id": int(target_id),
                "text": f"💰 کیف پول شما به مقدار {amount:,} تومان توسط مدیر شارژ شد."
            })
            return True

        if state.startswith("waiting_for_sub_"):
            target_id = state.replace("waiting_for_sub_", "")
            amount = safe_int(text)
            if amount <= 0:
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ لطفاً عدد مثبت وارد کنید:"})
                return True
            await execute_db("UPDATE users SET balance = CASE WHEN balance - ? < 0 THEN 0 ELSE balance - ? END, state = NULL WHERE telegram_id = ?", amount, amount, target_id)
            await call_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": STRINGS["balance_subtracted"].format(amount=amount, target_id=target_id),
                "reply_markup": get_admin_inline_keyboard()
            })
            return True
            
        if state == "waiting_for_new_channel":
            cur_ch = await get_setting("force_channels", "")
            ch_list = [c.strip() for c in cur_ch.split(",") if c.strip()]
            new_ch = text.strip()
            if new_ch not in ch_list:
                ch_list.append(new_ch)
                await set_setting("force_channels", ",".join(ch_list))
            await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": "✅ کانال اضافه شد.", "reply_markup": get_admin_inline_keyboard()})
            return True

        if state.startswith("waiting_setting_"):
            setting_key = state.replace("waiting_setting_", "")
            await set_setting(setting_key, text.strip())
            await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])
            await call_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": STRINGS["setting_updated"],
                "parse_mode": "Markdown",
                "reply_markup": get_admin_inline_keyboard()
            })
            return True

        if state.startswith("waiting_plan_"):
            parts = state.split("_")
            step = parts[2] if len(parts) > 2 else "name"
            plan_data = json.loads(user.get("plan_data") or "{}")
            if step == "name":
                plan_data["name"] = text
                await execute_db("UPDATE users SET state = 'waiting_plan_price', plan_data = ? WHERE id = ?", json.dumps(plan_data), user["id"])
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["plan_add_step2"]})
                return True
            elif step == "price":
                price = safe_int(text)
                if price <= 0:
                    await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ قیمت باید عدد مثبت باشد:"})
                    return True
                plan_data["price"] = price
                await execute_db("UPDATE users SET state = 'waiting_plan_duration', plan_data = ? WHERE id = ?", json.dumps(plan_data), user["id"])
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["plan_add_step3"]})
                return True
            elif step == "duration":
                dur = safe_int(text)
                if dur <= 0:
                    await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ مدت باید عدد مثبت باشد:"})
                    return True
                plan_data["duration_days"] = dur
                await execute_db("UPDATE users SET state = 'waiting_plan_maxusers', plan_data = ? WHERE id = ?", json.dumps(plan_data), user["id"])
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["plan_add_step4"]})
                return True
            elif step == "maxusers":
                max_users = safe_int(text)
                if max_users <= 0:
                    await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ محدودیت کاربر باید عدد مثبت باشد:"})
                    return True
                name = plan_data.get("name", "بدون نام")
                price = plan_data.get("price", 0)
                duration = plan_data.get("duration_days", 0)
                await execute_db("""
                    INSERT INTO plans (name, price, duration_days, max_users, is_active)
                    VALUES (?, ?, ?, ?, 1)
                """, name, price, duration, max_users)
                await execute_db("UPDATE users SET state = NULL, plan_data = NULL WHERE id = ?", user["id"])
                await call_telegram("sendMessage", {
                    "chat_id": chat_id,
                    "text": STRINGS["plan_added"].format(name=name),
                    "reply_markup": get_admin_inline_keyboard()
                })
                return True
                
        if state == "waiting_for_help_content":
            help_data = {}
            if text:
                help_data = {"type": "text", "content": text}
            elif message.get("photo"):
                help_data = {"type": "photo", "file_id": message["photo"][-1]["file_id"], "caption": message.get("caption", "")}
            elif message.get("video"):
                help_data = {"type": "video", "file_id": message["video"]["file_id"], "caption": message.get("caption", "")}
            elif message.get("document"):
                help_data = {"type": "document", "file_id": message["document"]["file_id"], "caption": message.get("caption", "")}
                
            if help_data:
                await set_setting("help_content", json.dumps(help_data))
                await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": "✅ محتوای راهنما با موفقیت ثبت شد.", "reply_markup": get_admin_inline_keyboard()})
            return True

    if state and state.startswith("support_session_"):
        await forward_support_message(user, message, chat_id)
        return True

    return False

# ---------------------------------------------------------------------
# 📞 پردازش Callback
# ---------------------------------------------------------------------
async def process_callback(callback):
    cq_id = callback["id"]
    chat_id = callback["message"]["chat"]["id"]
    data = callback.get("data", "")
    from_user = callback.get("from", {})
    telegram_id = str(from_user.get("id", ""))

    user = await get_or_create_user(telegram_id, from_user=from_user)
    actual_is_admin = is_admin(telegram_id, user_data=None)
    is_admin_user = is_admin(telegram_id, user_data=user)

    await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id})

    # Clear state on any callback click
    if user.get("state") is not None and not data.startswith("adm_users_page_"):
        await execute_db("UPDATE users SET state = NULL, plan_data = NULL WHERE id = ?", user["id"])
        user["state"] = None

    if data != "chk_membership" and not await check_channel_membership(telegram_id):
        await send_membership_requirement(chat_id)
        return

    if data == "chk_membership":
        if await check_channel_membership(telegram_id):
            await credit_referrer_if_pending(user, chat_id)
            await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "✅ عضویت تایید شد!"})
            await call_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": STRINGS["membership_confirmed"],
                "reply_markup": get_admin_inline_keyboard() if is_admin_user else get_user_inline_keyboard(actual_is_admin)
            })
        else:
            await call_telegram("answerCallbackQuery", {
                "callback_query_id": cq_id,
                "text": "❌ شما هنوز عضو کانال نشده‌اید!",
                "show_alert": True
            })
        return
        
    if data == "admin_return" and actual_is_admin:
        await execute_db("UPDATE users SET is_test_mode = 0 WHERE id = ?", user["id"])
        await show_admin_panel(chat_id)
        return

    if data == "cancel_action":
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["purchase_cancelled"]})
        return

    if data == "free_trial": return await handle_free_trial(user, chat_id)
    if data == "wallet": return await handle_wallet(user, chat_id)
    if data == "buy_service": return await handle_buy_service(user, chat_id)
    if data == "my_services": return await handle_my_services(user, chat_id)
    if data == "referral": return await handle_referral(user, chat_id)
    if data == "support": return await handle_support_start(user, chat_id)
    
    if data == "help_btn":
        help_val = await get_setting("help_content")
        if not help_val:
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": "محتوای راهنما هنوز تنظیم نشده است."})
            return
        try:
            help_data = json.loads(help_val)
            if help_data["type"] == "text":
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": help_data["content"]})
            elif help_data["type"] == "photo":
                await call_telegram("sendPhoto", {"chat_id": chat_id, "photo": help_data["file_id"], "caption": help_data.get("caption", "")})
            elif help_data["type"] == "video":
                await call_telegram("sendVideo", {"chat_id": chat_id, "video": help_data["file_id"], "caption": help_data.get("caption", "")})
            elif help_data["type"] == "document":
                await call_telegram("sendDocument", {"chat_id": chat_id, "document": help_data["file_id"], "caption": help_data.get("caption", "")})
        except:
            pass
        return

    if data.startswith("qr_"):
        token = data.replace("qr_", "")
        sub_res = await query_db("SELECT * FROM subscriptions WHERE token = ? AND status = 'active'", token)
        if not get_first_row(sub_res):
            await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "❌ اشتراک یافت نشد.", "show_alert": True})
            return
        sub_url = await build_sub_url_async(token)
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={sub_url}"
        await call_telegram("sendPhoto", {
            "chat_id": chat_id,
            "photo": qr_url,
            "caption": f"📱 کیوآرکد اتصال شما:\n\n`{sub_url}`",
            "parse_mode": "Markdown"
        })
        return

    if data.startswith("renew_sub_"):
        token = data.replace("renew_sub_", "")
        sub_res = await query_db("SELECT * FROM subscriptions WHERE token = ?", token)
        sub = get_first_row(sub_res)
        if not sub or not sub.get("plan_id"):
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ امکان تمدید این سرویس وجود ندارد."})
            return
        plan_res = await query_db("SELECT * FROM plans WHERE id = ?", sub["plan_id"])
        plan = get_first_row(plan_res)
        if not plan:
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ پلن مرتبط با این سرویس حذف شده است."})
            return
            
        markup = {"inline_keyboard": [[{"text": "✅ تایید پرداخت", "callback_data": f"confirm_renew_{token}"}, {"text": "❌ لغو", "callback_data": "cancel_action"}]]}
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": f"هزینه تمدید {plan['duration_days']} روزه: {plan['price']:,} تومان\nآیا تایید میکنید؟", "reply_markup": markup})
        return
        
    if data.startswith("confirm_renew_"):
        token = data.replace("confirm_renew_", "")
        sub_res = await query_db("SELECT * FROM subscriptions WHERE token = ?", token)
        sub = get_first_row(sub_res)
        plan_res = await query_db("SELECT * FROM plans WHERE id = ?", sub["plan_id"])
        plan = get_first_row(plan_res)
        if user["balance"] < plan["price"]:
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ موجودی کافی نیست."})
            return
            
        await execute_db("UPDATE users SET balance = balance - ? WHERE id = ?", plan["price"], user["id"])
        
        # Add duration to expires_at
        try:
            expires_at = datetime.datetime.strptime(sub["expires_at"], "%Y-%m-%d %H:%M:%S")
            if expires_at < datetime.datetime.utcnow():
                expires_at = datetime.datetime.utcnow()
        except:
            expires_at = datetime.datetime.utcnow()
            
        new_expires_at = (expires_at + datetime.timedelta(days=plan["duration_days"])).strftime("%Y-%m-%d %H:%M:%S")
        await execute_db("UPDATE subscriptions SET expires_at = ?, status = 'active' WHERE id = ?", new_expires_at, sub["id"])
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": f"✅ سرویس با موفقیت تمدید شد.\nانقضای جدید: {new_expires_at} (UTC)"})
        return

    if data.startswith("del_sub_req_"):
        token = data.replace("del_sub_req_", "")
        markup = {"inline_keyboard": [[{"text": "✅ بله، حذف کن", "callback_data": f"del_sub_yes_{token}"}, {"text": "❌ خیر", "callback_data": "cancel_action"}]]}
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": "آیا از حذف این سرویس اطمینان دارید؟", "reply_markup": markup})
        return
        
    if data.startswith("del_sub_yes_"):
        token = data.replace("del_sub_yes_", "")
        await execute_db("DELETE FROM subscriptions WHERE token = ?", token)
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": "✅ سرویس با موفقیت حذف شد."})
        return

    if data.startswith("buy_plan_"):
        plan_id = int(data.replace("buy_plan_", ""))
        res = await query_db("SELECT * FROM plans WHERE id = ? AND is_active = 1", plan_id)
        plan = get_first_row(res)
        if not plan:
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ پلن مورد نظر فعال نیست."})
            return
            
        markup = {"inline_keyboard": [[{"text": "✅ تایید خرید", "callback_data": f"confirm_buy_{plan_id}"}, {"text": "❌ لغو", "callback_data": "cancel_action"}]]}
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": f"آیا از خرید این پلن به مبلغ {plan['price']:,} تومان اطمینان دارید؟", "reply_markup": markup})
        return
        
    if data.startswith("confirm_buy_"):
        plan_id = int(data.replace("confirm_buy_", ""))
        res = await query_db("SELECT * FROM plans WHERE id = ?", plan_id)
        plan = get_first_row(res)
        price = plan["price"]
        
        if user["balance"] < price:
            msg = STRINGS["insufficient_balance"].format(balance=user["balance"], price=price)
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": msg})
            return
        await execute_db("UPDATE users SET balance = balance - ? WHERE id = ?", price, user["id"])
        token = await create_subscription_from_plan(plan_id, user["id"])
        if not token:
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ خطا در ایجاد اشتراک."})
            return
        sub_url = await build_sub_url_async(token)
        expires_at = (datetime.datetime.utcnow() + datetime.timedelta(days=plan["duration_days"])).strftime("%Y-%m-%d %H:%M:%S")
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={sub_url}"
        msg = STRINGS["subscription_created"].format(duration=plan["duration_days"], sublink=sub_url, expires_at=expires_at)
        await call_telegram("sendPhoto", {
            "chat_id": chat_id,
            "photo": qr_url,
            "caption": msg,
            "parse_mode": "Markdown"
        })
        return

    if not is_admin_user:
        await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": STRINGS["admin_only"], "show_alert": True})
        return

    if data == "adm_test_user":
        await execute_db("UPDATE users SET is_test_mode = 1 WHERE id = ?", user["id"])
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": "شما اکنون در نمای کاربری (تست) هستید. برای بازگشت دکمه مربوطه را بزنید.", "reply_markup": get_user_inline_keyboard(actual_is_admin)})
        return

    if data == "adm_add_config":
        await execute_db("UPDATE users SET state = 'waiting_for_config' WHERE id = ?", user["id"])
        await call_telegram("sendMessage", {
            "chat_id": chat_id,
            "text": "📥 لطفا کانفیگ خود را ارسال کنید.\nبرای پایان، دکمه زیر را بزنید:",
            "reply_markup": {"inline_keyboard": [[{"text": "❌ خروج", "callback_data": "admin_return"}]]}
        })
        return

    if data == "adm_manage_configs":
        cfg_res = await query_db("SELECT id, config_text, is_active FROM configs ORDER BY id DESC LIMIT 20")
        configs = get_rows(cfg_res)
        if not configs:
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": "هیچ کانفیگی موجود نیست."})
            return
        for c in configs:
            status_emoji = "🟢 فعال" if c["is_active"] else "🔴 غیرفعال"
            markup = {
                "inline_keyboard": [
                    [{"text": f"تغییر وضعیت ({status_emoji})", "callback_data": f"adm_cfg_toggle_{c['id']}"},
                     {"text": "❌ حذف", "callback_data": f"adm_cfg_del_req_{c['id']}"}]
                ]
            }
            await call_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": f"شناسه کانفیگ: {c['id']}\n```{c['config_text']}```",
                "parse_mode": "Markdown",
                "reply_markup": markup
            })
        return

    if data.startswith("adm_cfg_toggle_"):
        cfg_id = data.replace("adm_cfg_toggle_", "")
        cfg_res = await query_db("SELECT is_active FROM configs WHERE id = ?", cfg_id)
        cfg = get_first_row(cfg_res)
        if cfg:
            new_state = 0 if cfg["is_active"] else 1
            await execute_db("UPDATE configs SET is_active = ? WHERE id = ?", new_state, cfg_id)
            await delete_kv("cached_configs_payload")
            await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "✅ تغییر وضعیت انجام شد."})
        return

    if data.startswith("adm_cfg_del_req_"):
        cfg_id = data.replace("adm_cfg_del_req_", "")
        markup = {"inline_keyboard": [[{"text": "✅ بله، حذف کن", "callback_data": f"adm_cfg_del_yes_{cfg_id}"}, {"text": "❌ خیر", "callback_data": "admin_return"}]]}
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": "آیا از حذف این کانفیگ اطمینان دارید؟", "reply_markup": markup})
        return

    if data.startswith("adm_cfg_del_yes_"):
        cfg_id = data.replace("adm_cfg_del_yes_", "")
        await execute_db("DELETE FROM configs WHERE id = ?", cfg_id)
        await delete_kv("cached_configs_payload")
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": "🗑 کانفیگ حذف شد."})
        return

    if data == "adm_broadcast":
        await execute_db("UPDATE users SET state = 'waiting_for_broadcast' WHERE id = ?", user["id"])
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["broadcast_start"]})
        return
        
    if data == "adm_broadcast_yes":
        msg_text = user.get("plan_data")
        await execute_db("UPDATE users SET state = NULL, plan_data = NULL WHERE id = ?", user["id"])
        all_users_res = await query_db("SELECT telegram_id FROM users")
        all_users = get_rows(all_users_res)
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["broadcast_sending"]})
        success = 0
        for u in all_users:
            res = await call_telegram("sendMessage", {
                "chat_id": int(u["telegram_id"]),
                "text": msg_text
            })
            if res.get("ok"):
                success += 1
            await asyncio.sleep(0.05)
        await call_telegram("sendMessage", {
            "chat_id": chat_id,
            "text": STRINGS["broadcast_done"].format(success=success, total=len(all_users)),
            "reply_markup": get_admin_inline_keyboard()
        })
        return

    if data == "adm_settings":
        reward = await get_setting("referral_reward", "2000")
        channels = await get_setting("force_channels", "غیرفعال")
        settings_text = STRINGS["settings_show"].format(
            reward=safe_int(reward), channels=channels
        )
        markup = {
            "inline_keyboard": [
                [{"text": "✏️ ویرایش کانال‌های اجباری", "callback_data": "adm_set_channels"},
                 {"text": "✏️ ویرایش پاداش دعوت", "callback_data": "adm_set_referral_reward"}],
                [{"text": "🔙 بازگشت", "callback_data": "admin_return"}]
            ]
        }
        await call_telegram("sendMessage", {
            "chat_id": chat_id,
            "text": settings_text,
            "parse_mode": "Markdown",
            "reply_markup": markup
        })
        return

    if data == "adm_set_channels":
        channels_str = await get_setting("force_channels", "")
        ch_list = [c.strip() for c in channels_str.split(",") if c.strip()]
        kb = []
        for ch in ch_list:
            kb.append([{"text": f"❌ حذف {ch}", "callback_data": f"adm_del_ch_{ch}"}])
        kb.append([{"text": "➕ افزودن کانال", "callback_data": "adm_add_channel"}])
        kb.append([{"text": "🔙 بازگشت", "callback_data": "adm_settings"}])
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": "مدیریت کانال‌های اجباری:", "reply_markup": {"inline_keyboard": kb}})
        return
        
    if data == "adm_add_channel":
        await execute_db("UPDATE users SET state = 'waiting_for_new_channel' WHERE id = ?", user["id"])
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": "یوزرنیم کانال را همراه با @ بفرستید:"})
        return
        
    if data.startswith("adm_del_ch_"):
        ch_to_del = data.replace("adm_del_ch_", "")
        channels_str = await get_setting("force_channels", "")
        ch_list = [c.strip() for c in channels_str.split(",") if c.strip()]
        if ch_to_del in ch_list:
            ch_list.remove(ch_to_del)
            await set_setting("force_channels", ",".join(ch_list))
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": "✅ کانال حذف شد."})
        return

    if data == "adm_set_referral_reward":
        await execute_db("UPDATE users SET state = 'waiting_setting_referral_reward' WHERE id = ?", user["id"])
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": "✏️ لطفاً مقدار جدید پاداش دعوت را بفرستید:"})
        return
        
    if data == "adm_set_help":
        await execute_db("UPDATE users SET state = 'waiting_for_help_content' WHERE id = ?", user["id"])
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": "محتوای دکمه راهنما را ارسال کنید (پشتیبانی از متن، عکس، ویدیو و فایل):"})
        return

    if data.startswith("adm_manage_users_"):
        page = safe_int(data.replace("adm_manage_users_", ""), 1)
        limit = 5
        offset = (page - 1) * limit
        res = await query_db("SELECT * FROM users ORDER BY id DESC LIMIT ? OFFSET ?", limit, offset)
        users = get_rows(res)
        
        txt = f"👤 لیست کاربران (صفحه {page}):\n\n"
        for u in users:
            txt += f"🆔 `{u['telegram_id']}` | {u['username']} | {u['full_name']}\n"
            
        kb = [[{"text": "🔍 جستجوی کاربر", "callback_data": "adm_search_user"}]]
        nav = []
        if page > 1:
            nav.append({"text": "◀️ قبلی", "callback_data": f"adm_manage_users_{page-1}"})
        nav.append({"text": f"صفحه {page}", "callback_data": "ignore"})
        if len(users) == limit:
            nav.append({"text": "▶️ بعدی", "callback_data": f"adm_manage_users_{page+1}"})
            
        kb.append(nav)
        kb.append([{"text": "🔙 بازگشت", "callback_data": "admin_return"}])
        
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": txt, "parse_mode": "Markdown", "reply_markup": {"inline_keyboard": kb}})
        return
        
    if data == "adm_search_user":
        await execute_db("UPDATE users SET state = 'waiting_for_user_search' WHERE id = ?", user["id"])
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": "🔍 شناسه عددی تلگرام کاربر مورد نظر را بفرستید:"})
        return

    if data.startswith("adm_add_bal_") or data.startswith("adm_sub_bal_"):
        is_addition = "add" in data
        target_tg_id = data.replace("adm_add_bal_", "").replace("adm_sub_bal_", "")
        state_val = f"waiting_for_add_{target_tg_id}" if is_addition else f"waiting_for_sub_{target_tg_id}"
        await execute_db("UPDATE users SET state = ? WHERE id = ?", state_val, user["id"])
        action_text = "افزایش" if is_addition else "کاهش"
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": f"💵 میزان شارژ مایل به {action_text} (به تومان) را بفرستید:"})
        return

    if data == "adm_manage_plans": return await show_plan_management(chat_id)

    if data == "adm_add_plan":
        await execute_db("UPDATE users SET state = 'waiting_plan_name', plan_data = NULL WHERE id = ?", user["id"])
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["plan_add_step1"]})
        return

    if data.startswith("adm_plan_toggle_"):
        plan_id = data.replace("adm_plan_toggle_", "")
        res = await query_db("SELECT is_active FROM plans WHERE id = ?", plan_id)
        plan = get_first_row(res)
        if plan:
            new_state = 0 if plan["is_active"] else 1
            await execute_db("UPDATE plans SET is_active = ? WHERE id = ?", new_state, plan_id)
            await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": STRINGS["plan_toggled"]})
            await show_plan_management(chat_id)
        return

    if data.startswith("adm_plan_del_"):
        plan_id = data.replace("adm_plan_del_", "")
        await execute_db("DELETE FROM plans WHERE id = ?", plan_id)
        await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": STRINGS["plan_deleted"]})
        await show_plan_management(chat_id)
        return

async def show_plan_management(chat_id):
    res = await query_db("SELECT * FROM plans ORDER BY id DESC")
    plans = get_rows(res)
    if not plans:
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["no_plans"]})
    else:
        for p in plans:
            status = "فعال" if p["is_active"] else "غیرفعال"
            txt = STRINGS["plan_list_item"].format(
                name=p["name"], price=p["price"], duration=p["duration_days"],
                max_users=p["max_users"], status=status
            )
            markup = {
                "inline_keyboard": [
                    [{"text": f"تغییر وضعیت ({status})", "callback_data": f"adm_plan_toggle_{p['id']}"},
                     {"text": "❌ حذف", "callback_data": f"adm_plan_del_{p['id']}"}]
                ]
            }
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": txt, "reply_markup": markup})
    await call_telegram("sendMessage", {
        "chat_id": chat_id,
        "text": "برای افزودن پلن جدید، دکمه زیر را بزنید:",
        "reply_markup": {"inline_keyboard": [[{"text": "➕ افزودن پلن جدید", "callback_data": "adm_add_plan"}], [{"text": "🔙 بازگشت", "callback_data": "admin_return"}]]}
    })

async def show_admin_panel(chat_id):
    await call_telegram("sendMessage", {
        "chat_id": chat_id,
        "text": STRINGS["admin_panel"],
        "reply_markup": get_admin_inline_keyboard()
    })

# ---------------------------------------------------------------------
# 📨 پردازش پیام
# ---------------------------------------------------------------------
async def process_message(message):
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()
    from_user = message.get("from", {})
    telegram_id = str(from_user.get("id", ""))
    if not telegram_id: return

    referred_by = None
    if text.startswith("/start ") and len(text.split()) > 1:
        referred_by = text.split()[1]

    user = await get_or_create_user(telegram_id, referred_by, from_user=from_user)
    actual_is_admin = is_admin(telegram_id, user_data=None)
    is_admin_user = is_admin(telegram_id, user_data=user)

    # Admin returning from test mode
    if text in ["/admin", "admin", "مدیریت"] and actual_is_admin:
        await execute_db("UPDATE users SET state = NULL, plan_data = NULL, is_test_mode = 0 WHERE id = ?", user["id"])
        await show_admin_panel(chat_id)
        return

    # Clear state on command or end support
    if text in ["/start", "🔚 پایان پشتیبانی"]:
        await execute_db("UPDATE users SET state = NULL, plan_data = NULL WHERE id = ?", user["id"])
        user["state"] = None
        if text == "🔚 پایان پشتیبانی":
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["support_session_ended"], "reply_markup": {"remove_keyboard": True}})
            # Send main menu afterward
            if is_admin_user:
                await show_admin_panel(chat_id)
            else:
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["start_welcome"], "reply_markup": get_user_inline_keyboard(actual_is_admin)})
            return

    # Handle Admin reply to user's support message
    if actual_is_admin and message.get("reply_to_message"):
        replied_text = message["reply_to_message"].get("text", "") or message["reply_to_message"].get("caption", "")
        if "پیام از کاربر" in replied_text:
            match = re.search(r"پیام از کاربر (\d+):", replied_text)
            if match:
                target_id = match.group(1)
                payload = {"chat_id": target_id}
                method = "sendMessage"
                if text:
                    payload["text"] = f"پاسخ پشتیبانی:\n\n{text}"
                elif message.get("photo"):
                    method = "sendPhoto"
                    payload["photo"] = message["photo"][-1]["file_id"]
                    payload["caption"] = f"پاسخ پشتیبانی:\n{message.get('caption', '')}"
                elif message.get("document"):
                    method = "sendDocument"
                    payload["document"] = message["document"]["file_id"]
                    payload["caption"] = f"پاسخ پشتیبانی:\n{message.get('caption', '')}"
                
                await call_telegram(method, payload)
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": "✅ پاسخ شما به کاربر ارسال شد."})
                return

    if not await check_channel_membership(telegram_id) and text != "/start":
        await send_membership_requirement(chat_id)
        return

    state = user.get("state")
    if state:
        if await handle_state(user, state, message, chat_id, is_admin_user, actual_is_admin):
            return

    if text == "/start":
        await credit_referrer_if_pending(user, chat_id)
        if is_admin_user:
            await show_admin_panel(chat_id)
        else:
            await call_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": STRINGS["start_welcome"],
                "reply_markup": get_user_inline_keyboard(actual_is_admin)
            })
    elif text.startswith("/"):
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ دستور نامعتبر."})

async def process_update(update):
    try:
        if "message" in update:
            await process_message(update["message"])
        elif "callback_query" in update:
            await process_callback(update["callback_query"])
    except Exception:
        print("Error in process_update:")
        traceback.print_exc()

# ---------------------------------------------------------------------
# 🚀 سرور FastAPI
# ---------------------------------------------------------------------
app = FastAPI()

@app.on_event("startup")
async def startup_event():
    await init_database_if_needed()
    asyncio.create_task(background_config_checker())
    print("🚀 Bot Server Started!")

@app.post("/webhook")
async def handle_webhook(request: Request):
    update = await request.json()
    asyncio.create_task(process_update(update))
    return Response(content="OK", status_code=200)

@app.get("/sub/{token}")
async def handle_sublink(token: str):
    sub_res = await query_db("SELECT * FROM subscriptions WHERE token = ? AND status = 'active'", token)
    sub = get_first_row(sub_res)
    if not sub:
        return Response(content="", media_type="text/plain")

    expires_str = sub["expires_at"]
    try:
        expires_at = datetime.datetime.strptime(expires_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        expires_at = datetime.datetime.strptime(expires_str.split(".")[0], "%Y-%m-%d %H:%M:%S")

    if expires_at < datetime.datetime.utcnow():
        await execute_db("UPDATE subscriptions SET status = 'expired' WHERE id = ?", sub["id"])
        return Response(content="", media_type="text/plain")

    cached_payload = await get_kv("cached_configs_payload")

    if cached_payload is None:
        cfg_res = await query_db("SELECT config_text FROM configs WHERE is_active = 1")
        confs = get_rows(cfg_res)
        payload_lines = [c["config_text"].strip() for c in confs if c["config_text"].strip()]
        combined = "\n".join(payload_lines)
        cached_payload = base64.b64encode(combined.encode("utf-8")).decode("utf-8")
        await put_kv("cached_configs_payload", cached_payload, expiration_ttl=300)

    headers = {"Cache-Control": "public, max-age=120"}
    return Response(content=cached_payload, media_type="text/plain", headers=headers)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
