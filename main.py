# -*- coding: utf-8 -*-
"""
🤖 ربات پیشرفته مدیریت ساب‌لینک v3 (نسخه نهایی و بهینه‌شده)
--------------------------------------------------
پشته تکنولوژی: Python + FastAPI + Cloudflare D1 (SQL) + Cloudflare KV + Telegram Bot API
طراحی شده برای اجرا روی Railway / Cloudflare Webhook
"""

import os
import re
import json
import base64
import uuid
import socket
import datetime
import traceback
import asyncio
import httpx
from urllib.parse import urlparse, parse_qs, unquote
from fastapi import FastAPI, Request, Response
import uvicorn

# ---------------------------------------------------------------------
# 🔐 متغیرهای محیطی (Environment Variables)
# ---------------------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "7891234567:AAExampleTokenForSublinkBotHere")
ADMIN_IDS = os.getenv("ADMIN_IDS", "123456789")

CF_ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID", "your_cf_account_id")
CF_API_TOKEN = os.getenv("CF_API_TOKEN", "your_cf_api_token")
CF_D1_ID = os.getenv("CF_D1_ID", "your_d1_database_id")
CF_KV_ID = os.getenv("CF_KV_ID", "your_kv_namespace_id")

CF_HEADERS = {
    "Authorization": f"Bearer {CF_API_TOKEN}",
    "Content-Type": "application/json"
}

# ---------------------------------------------------------------------
# 📚 متون منو و پیام‌ها
# ---------------------------------------------------------------------
STRINGS = {
    "start_welcome": (
        "👋 **به ربات پیشرفته مدیریت ساب‌لینک خوش آمدید!**\n\n"
        "از طریق دکمه‌های زیر می‌توانید حساب، پلن‌ها و اشتراک‌های خود را مدیریت نمایید."
    ),
    "not_member": (
        "⚠️ **توجه:** برای استفاده از خدمات ربات، باید در کانال‌های زیر عضو شوید:\n\n"
        "{channels_list}\n\n"
        "پس از عضویت روی دکمه «✅ عضو شدم» کلیک کنید."
    ),
    "membership_confirmed": "✅ عضویت شما تایید شد! اکنون می‌توانید از تمام امکانات استفاده کنید.",
    "admin_welcome": "🛠 **پنل مدیریت ربات**\nجهت انجام عملیات مدیریتی، گزینه مورد نظر را انتخاب کنید:",
    "admin_demoted": "👤 شما به حالت کاربری (تست) منتقل شدید.\nبرای بازگشت به مدیریت کلمه `مدیریت` یا `/admin` را ارسال کنید.",
    "support_started": "🎧 **بخش ارتباط با پشتیبانی**\nپیام خود را بفرستید. جهت انصراف دکمه «🔚 پایان پشتیبانی» را فشار دهید.",
    "support_ended": "🔚 **نشست پشتیبانی پایان یافت.** به منوی اصلی بازگشتید.",
    "cancelled": "❌ **عملیات قبلی لغو شد.**",
    "user_not_found": "❌ کاربری با این آیدی عددی یافت نشد.",
}

# ---------------------------------------------------------------------
# 🔧 توابع ارتباط با D1 و KV کلادفلر
# ---------------------------------------------------------------------
def safe_int(val, default=0):
    try:
        return int(val)
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
            print(f"D1 API Error: {e}")
            return {"success": False, "error": str(e)}

async def execute_db(sql, *args):
    return await query_db(sql, *args)

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
    params = {"expiration_ttl": expiration_ttl} if expiration_ttl else {}
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

async def get_setting(key, default=""):
    cached = await get_kv(f"setting_{key}")
    if cached is not None:
        return cached
    res = await query_db("SELECT value FROM settings WHERE key = ?", key)
    row = get_first_row(res)
    if row:
        val = row["value"]
        await put_kv(f"setting_{key}", val, expiration_ttl=600)
        return val
    return default

async def set_setting(key, value):
    await execute_db("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", key, str(value))
    await put_kv(f"setting_{key}", str(value), expiration_ttl=600)

# ---------------------------------------------------------------------
# 📨 ارسال دستورات تلگرام
# ---------------------------------------------------------------------
async def call_telegram(method, payload):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    async with httpx.AsyncClient() as client:
        try:
            res = await client.post(url, json=payload, timeout=10.0)
            return res.json()
        except Exception as e:
            print(f"Telegram API Error ({method}): {e}")
            return {"ok": False, "description": str(e)}

# ---------------------------------------------------------------------
# 🌐 تشخیص آی‌پی و پرچم کشور (IP Geolocation & Flag)
# ---------------------------------------------------------------------
COUNTRY_FLAGS = {
    "DE": ("🇩🇪", "آلمان"),
    "FR": ("🇫🇷", "فرانسه"),
    "US": ("🇺🇸", "آمریکا"),
    "NL": ("🇳🇱", "هلند"),
    "GB": ("🇬🇧", "انگلیس"),
    "FI": ("🇫🇮", "فنلاند"),
    "TR": ("🇹🇷", "ترکیه"),
    "IR": ("🇮🇷", "ایران"),
    "CA": ("🇨🇦", "کانادا"),
    "RU": ("🇷🇺", "روسیه"),
    "SG": ("🇸🇬", "سنگاپور"),
    "JP": ("🇯🇵", "ژاپن"),
    "AE": ("🇦🇪", "امارات"),
}

async def get_server_location(host):
    clean_host = host.split(":")[0].strip()
    # If domain name, try resolving to IP
    try:
        ip = socket.gethostbyname(clean_host)
    except Exception:
        ip = clean_host

    url = f"http://ip-api.com/json/{ip}?fields=status,countryCode,country"
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(url, timeout=5.0)
            if r.status_code == 200:
                data = r.json()
                if data.get("status") == "success":
                    cc = data.get("countryCode", "US")
                    flag_info = COUNTRY_FLAGS.get(cc, ("🌐", data.get("country", "بین‌المللی")))
                    return flag_info
        except Exception:
            pass
    return ("🌐", "اختصاصی")

async def format_config_with_flag(config_str):
    """
    دریافت کانفیگ و اضافه کردن پرچم + نام کشور + TechNowVpn@
    فرمت: پرچم کشور + نام کشور + | TechNowVpn@
    """
    config_str = config_str.strip()
    remark_suffix = "| TechNowVpn@"

    host = "1.1.1.1"
    # Extract host/IP
    if "://" in config_str:
        try:
            proto, rest = config_str.split("://", 1)
            if proto in ["vless", "trojan", "ss"]:
                # userinfo@host:port
                main_part = rest.split("#")[0]
                if "@" in main_part:
                    host_port = main_part.split("@")[1].split("?")[0]
                    host = host_port.split(":")[0]
            elif proto == "vmess":
                # Base64 VMess
                decoded = base64.b64decode(rest.split("#")[0]).decode('utf-8', errors='ignore')
                vm_json = json.loads(decoded)
                host = vm_json.get("add", "1.1.1.1")
        except Exception:
            pass

    flag, country_name = await get_server_location(host)
    formatted_remark = f"{flag} {country_name} {remark_suffix}"

    # Format according to protocol
    try:
        if config_str.startswith("vmess://"):
            raw_b64 = config_str.replace("vmess://", "").split("#")[0]
            decoded = base64.b64decode(raw_b64).decode('utf-8')
            vdata = json.loads(decoded)
            vdata["ps"] = formatted_remark
            encoded = base64.b64encode(json.dumps(vdata).encode('utf-8')).decode('utf-8')
            return f"vmess://{encoded}"
        elif "#" in config_str:
            base_part = config_str.split("#")[0]
            return f"{base_part}#{formatted_remark}"
        else:
            return f"{config_str}#{formatted_remark}"
    except Exception:
        return f"{config_str}#{formatted_remark}"

# ---------------------------------------------------------------------
# 🗄️ مقداردهی دیتابیس D1
# ---------------------------------------------------------------------
async def init_db():
    queries = [
        """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id TEXT UNIQUE NOT NULL,
            first_name TEXT DEFAULT '',
            username TEXT DEFAULT '',
            balance INTEGER DEFAULT 0,
            referred_by TEXT DEFAULT NULL,
            state TEXT DEFAULT NULL,
            view_mode TEXT DEFAULT 'admin',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS subscription_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL,
            ip TEXT NOT NULL,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_text TEXT NOT NULL,
            fail_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            duration_days INTEGER NOT NULL,
            max_users INTEGER DEFAULT 3,
            is_active INTEGER DEFAULT 1
        );""",
        """CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );"""
    ]
    for q in queries:
        await execute_db(q)

    # Defaults
    defaults = {
        "force_channels": "@MyChannel1, @MyChannel2",
        "referral_reward": "5000"
    }
    for k, v in defaults.items():
        r = await query_db("SELECT value FROM settings WHERE key = ?", k)
        if not get_first_row(r):
            await execute_db("INSERT INTO settings (key, value) VALUES (?, ?)", k, v)

# ---------------------------------------------------------------------
# 👤 مدیریت کاربر و احراز صلاحیت
# ---------------------------------------------------------------------
def is_admin(telegram_id):
    if not ADMIN_IDS:
        return False
    admins = [a.strip() for a in str(ADMIN_IDS).split(",") if a.strip()]
    return str(telegram_id) in admins

async def get_or_create_user(from_user, referred_by=None):
    tg_id = str(from_user.get("id"))
    fname = from_user.get("first_name", "")
    uname = from_user.get("username", "")

    res = await query_db("SELECT * FROM users WHERE telegram_id = ?", tg_id)
    user = get_first_row(res)

    if not user:
        ref_id = referred_by if referred_by and referred_by != tg_id else None
        await execute_db(
            "INSERT INTO users (telegram_id, first_name, username, referred_by) VALUES (?, ?, ?, ?)",
            tg_id, fname, uname, ref_id
        )
        res = await query_db("SELECT * FROM users WHERE telegram_id = ?", tg_id)
        user = get_first_row(res)
    else:
        # Update name/username
        await execute_db("UPDATE users SET first_name = ?, username = ? WHERE telegram_id = ?", fname, uname, tg_id)

    return user

async def check_channels_membership(telegram_id):
    channels_str = await get_setting("force_channels", "")
    if not channels_str.strip():
        return True, []

    channels = [c.strip() for c in channels_str.split(",") if c.strip()]
    not_joined = []

    for ch in channels:
        ch_clean = ch if ch.startswith("@") or ch.startswith("-100") else f"@{ch}"
        res = await call_telegram("getChatMember", {"chat_id": ch_clean, "user_id": int(telegram_id)})
        if res.get("ok"):
            st = res["result"].get("status")
            if st not in ["creator", "administrator", "member"]:
                not_joined.append(ch_clean)
        else:
            not_joined.append(ch_clean)

    return len(not_joined) == 0, not_joined

# ---------------------------------------------------------------------
# ⌨️ چیدمان دکمه‌ها (2 در هر ردیف)
# ---------------------------------------------------------------------
def build_keyboard_2x2(buttons):
    """ساخت کیبورد تلگرام با چیدمان ۲ تایی (2-2)"""
    keyboard = []
    for i in range(0, len(buttons), 2):
        keyboard.append(buttons[i:i+2])
    return keyboard

def get_user_reply_keyboard():
    buttons = [
        {"text": "🛒 خرید سرویس (رایگان)"},
        {"text": "📱 سرویس‌های من"},
        {"text": "👛 کیف پول & شارژ"},
        {"text": "👥 دعوت دوستان"},
        {"text": "🎧 پشتیبانی"},
        {"text": "ℹ️ راهنمای اتصال"}
    ]
    return {"keyboard": build_keyboard_2x2(buttons), "resize_keyboard": True}

def get_admin_reply_keyboard():
    buttons = [
        {"text": "➕ افزودن کانفیگ"},
        {"text": "📋 مدیریت کانفیگ‌ها"},
        {"text": "📢 ارسال همگانی"},
        {"text": "⚙️ تنظیمات"},
        {"text": "👤 مدیریت کاربران"},
        {"text": "📦 مدیریت پلن‌ها"},
        {"text": "👤 حالت کاربری (تست)"}
    ]
    return {"keyboard": build_keyboard_2x2(buttons), "resize_keyboard": True}

def get_support_keyboard():
    return {
        "keyboard": [[{"text": "🔚 پایان پشتیبانی"}]],
        "resize_keyboard": True
    }

# ---------------------------------------------------------------------
# ⚙️ چک خودکار کانفیگ‌های غیرفعال (Auto Health Check & Cleanup)
# ---------------------------------------------------------------------
async def check_configs_health_job():
    """چک کردن سلامتی کانفیگ‌ها و حذف خودکار پس از ۳ بار خطا"""
    res = await query_db("SELECT * FROM configs WHERE is_active = 1")
    configs = get_rows(res)

    for cfg in configs:
        cfg_id = cfg["id"]
        cfg_text = cfg["config_text"]
        fail_count = cfg.get("fail_count", 0)

        # Extract IP/Host to test TCP connectivity
        is_alive = True
        try:
            host, port = "1.1.1.1", 443
            if "://" in cfg_text:
                clean = cfg_text.split("://")[1].split("#")[0]
                if "@" in clean:
                    hp = clean.split("@")[1].split("?")[0]
                    parts = hp.split(":")
                    host = parts[0]
                    port = int(parts[1]) if len(parts) > 1 else 443
            
            # Simple socket connect test
            conn = asyncio.open_connection(host, port)
            _, writer = await asyncio.wait_for(conn, timeout=3.0)
            writer.close()
            await writer.wait_closed()
            is_alive = True
        except Exception:
            is_alive = False

        if not is_alive:
            fail_count += 1
            if fail_count >= 3:
                # Auto delete config
                await execute_db("DELETE FROM configs WHERE id = ?", cfg_id)
                await delete_kv("cached_configs_payload")

                # Send notice to admin
                for admin_id in [a.strip() for a in str(ADMIN_IDS).split(",") if a.strip()]:
                    msg = (
                        "⚠️ **حذف خودکار کانفیگ به دلیل خاموش بودن!**\n\n"
                        "کانفیگ زیر به دلیل ۳ بار عدم پاسخ‌دهی متوالی به طور کامل از سیستم حذف شد:\n\n"
                        f"```\n{cfg_text}\n```"
                    )
                    await call_telegram("sendMessage", {
                        "chat_id": int(admin_id),
                        "text": msg,
                        "parse_mode": "Markdown"
                    })
            else:
                await execute_db("UPDATE configs SET fail_count = ? WHERE id = ?", fail_count, cfg_id)
        else:
            if fail_count > 0:
                await execute_db("UPDATE configs SET fail_count = 0 WHERE id = ?", cfg_id)

# ---------------------------------------------------------------------
# 👥 مدیریت کاربران (Pagination & Search)
# ---------------------------------------------------------------------
async def show_users_page(chat_id, page=1):
    limit = 5
    offset = (page - 1) * limit

    total_res = await query_db("SELECT COUNT(*) as count FROM users")
    total_users = get_first_row(total_res)["count"] if get_first_row(total_res) else 0
    total_pages = max(1, (total_users + limit - 1) // limit)

    users_res = await query_db("SELECT * FROM users ORDER BY id DESC LIMIT ? OFFSET ?", limit, offset)
    users = get_rows(users_res)

    text = f"👥 **مدیریت کاربران (صفحه {page} از {total_pages})**\n\n"
    keyboard = []

    for idx, u in enumerate(users, 1):
        uname = f"@{u['username']}" if u.get("username") else "ندارد"
        fname = u.get("first_name") or "کاربر"
        text += f"{idx}. **{fname}** | یوزرنیم: {uname}\nآیدی عددی: `{u['telegram_id']}` | موجودی: {u['balance']:,} تومان\n\n"
        keyboard.append([{"text": f"👤 مدیریت کاربر ({u['telegram_id']})", "callback_data": f"adm_user_inspect_{u['telegram_id']}"}])

    # Pagination controls
    nav_buttons = []
    if page > 1:
        nav_buttons.append({"text": "◀️ قبلی", "callback_data": f"adm_users_page_{page - 1}"})
    nav_buttons.append({"text": f"📄 {page}/{total_pages}", "callback_data": "ignore"})
    if page < total_pages:
        nav_buttons.append({"text": "بعدی ▶️", "callback_data": f"adm_users_page_{page + 1}"})

    keyboard.append(nav_buttons)
    keyboard.append([{"text": "🔍 جستجو با آیدی عددی", "callback_data": "adm_search_user"}])

    await call_telegram("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": {"inline_keyboard": keyboard}
    })

# ---------------------------------------------------------------------
# 💬 هندلر اصلی پیام‌ها و حالت‌ها
# ---------------------------------------------------------------------
async def process_message(message):
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()
    from_user = message.get("from", {})
    tg_id = str(from_user.get("id"))

    # Check for direct admin reply to forward to user
    if message.get("reply_to_message") and is_admin(tg_id):
        reply_txt = message["reply_to_message"].get("text", "")
        if "پیام از کاربر" in reply_txt:
            try:
                target_user_id = reply_txt.split("پیام از کاربر ")[1].split("\n")[0].strip()
                await call_telegram("sendMessage", {
                    "chat_id": int(target_user_id),
                    "text": f"🎧 **پاسخ پشتیبانی:**\n\n{text}"
                })
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": "✅ پاسخ شما با موفقیت برای کاربر ارسال شد."})
                return
            except Exception as e:
                print(f"Error forwarding support reply: {e}")

    # Check if command is admin restore
    if text in ["مدیریت", "/admin", "admin"] and is_admin(tg_id):
        user = await get_or_create_user(from_user)
        await execute_db("UPDATE users SET state = NULL, view_mode = 'admin' WHERE telegram_id = ?", tg_id)
        await call_telegram("sendMessage", {
            "chat_id": chat_id,
            "text": "🛠 **به منوی مدیریت بازگشتید.**",
            "reply_markup": get_admin_reply_keyboard()
        })
        return

    user = await get_or_create_user(from_user)
    is_admin_user = is_admin(tg_id) and user.get("view_mode") != "user"

    # Mandatory Channel Check for non-admin actions
    if not is_admin_user:
        is_ok, missing = await check_channels_membership(tg_id)
        if not is_ok and text != "/start":
            ch_list = "\n".join([f"🔹 {ch}" for ch in missing])
            await call_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": STRINGS["not_member"].format(channels_list=ch_list),
                "reply_markup": {"inline_keyboard": [[{"text": "✅ عضو شدم", "callback_data": "check_membership"}]]}
            })
            return

    current_state = user.get("state")

    # 🚨 CANCEL RULE: If user presses a main menu button or sends /start, cancel pending state!
    main_menu_buttons = [
        "/start", "🛒 خرید سرویس (رایگان)", "📱 سرویس‌های من", "👛 کیف پول & شارژ",
        "👥 دعوت دوستان", "🎧 پشتیبانی", "➕ افزودن کانفیگ", "📋 مدیریت کانفیگ‌ها",
        "📢 ارسال همگانی", "⚙️ تنظیمات", "👤 مدیریت کاربران", "📦 مدیریت پلن‌ها", "👤 حالت کاربری (تست)"
    ]

    if text in main_menu_buttons and current_state:
        await execute_db("UPDATE users SET state = NULL WHERE telegram_id = ?", tg_id)
        current_state = None

    # Handle Active State
    if current_state:
        # Support Chat Session
        if current_state == "support_session":
            if text == "🔚 پایان پشتیبانی":
                await execute_db("UPDATE users SET state = NULL WHERE telegram_id = ?", tg_id)
                await call_telegram("sendMessage", {
                    "chat_id": chat_id,
                    "text": STRINGS["support_ended"],
                    "reply_markup": get_user_reply_keyboard()
                })
                return
            else:
                # Forward to admins
                for admin_id in [a.strip() for a in str(ADMIN_IDS).split(",") if a.strip()]:
                    await call_telegram("sendMessage", {
                        "chat_id": int(admin_id),
                        "text": f"📩 **پیام از کاربر `{tg_id}`:**\n\n{text}",
                        "parse_mode": "Markdown"
                    })
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": "✅ پیام شما برای پشتیبانی ارسال شد."})
                return

        # Adding Configs (Admin)
        if current_state == "waiting_for_config":
            if text.lower() in ["انصراف", "لغو", "/cancel"]:
                await execute_db("UPDATE users SET state = NULL WHERE telegram_id = ?", tg_id)
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ عملیات لغو شد.", "reply_markup": get_admin_reply_keyboard()})
                return

            # Format config with Flag
            formatted_config = await format_config_with_flag(text)
            await execute_db("INSERT INTO configs (config_text) VALUES (?)", formatted_config)
            await delete_kv("cached_configs_payload")

            await call_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": f"✅ **کانفیگ اضافه شد:**\n\n`{formatted_config}`\n\nکانفیگ بعدی را بفرستید یا دکمه لغو را بزنید.",
                "parse_mode": "Markdown"
            })
            return

        # Broadcast Confirmation Step
        if current_state == "waiting_broadcast_text":
            await execute_db("UPDATE users SET state = NULL WHERE telegram_id = ?", tg_id)
            markup = {
                "inline_keyboard": [
                    [{"text": "✅ بله، ارسال همگانی شود", "callback_data": f"confirm_bc_{uuid.uuid4().hex[:8]}"}],
                    [{"text": "❌ انصراف", "callback_data": "cancel_broadcast"}]
                ]
            }
            # Save broadcast text temporarily in KV
            await put_kv(f"pending_broadcast_{tg_id}", text, expiration_ttl=600)
            await call_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": f"❓ **تاییدیه ارسال همگانی**\n\nپیش‌نمایش پیام:\n\n{text}\n\nآیا از ارسال برای تمام کاربران اطمینان دارید؟",
                "reply_markup": markup
            })
            return

        # Search user by ID
        if current_state == "waiting_search_user":
            await execute_db("UPDATE users SET state = NULL WHERE telegram_id = ?", tg_id)
            res = await query_db("SELECT * FROM users WHERE telegram_id = ?", text.strip())
            u = get_first_row(res)
            if not u:
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["user_not_found"]})
                return
            uname = f"@{u['username']}" if u.get('username') else "ندارد"
            info = f"👤 **پروفایل کاربر:**\n\nنام: {u['first_name']}\nیوزرنیم: {uname}\nآیدی عددی: `{u['telegram_id']}`\nموجودی: {u['balance']:,} تومان"
            markup = {
                "inline_keyboard": [
                    [{"text": "➕ افزایش موجودی", "callback_data": f"adm_add_bal_{u['telegram_id']}"},
                     {"text": "➖ کاهش موجودی", "callback_data": f"adm_sub_bal_{u['telegram_id']}"}]
                ]
            }
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": info, "parse_mode": "Markdown", "reply_markup": markup})
            return

        # Balance Add/Sub
        if current_state.startswith("waiting_bal_"):
            parts = current_state.split("_")
            action = parts[2] # add or sub
            target_id = parts[3]
            amount = safe_int(text)
            await execute_db("UPDATE users SET state = NULL WHERE telegram_id = ?", tg_id)
            if amount <= 0:
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ مبلغ باید عدد مثبت باشد."})
                return
            if action == "add":
                await execute_db("UPDATE users SET balance = balance + ? WHERE telegram_id = ?", amount, target_id)
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": f"✅ مبلغ {amount:,} تومان به حساب `{target_id}` افزوده شد."})
                await call_telegram("sendMessage", {"chat_id": int(target_id), "text": f"🎁 مبلغ {amount:,} تومان به کیف پول شما افزوده شد!"})
            else:
                await execute_db("UPDATE users SET balance = MAX(0, balance - ?) WHERE telegram_id = ?", amount, target_id)
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": f"✅ مبلغ {amount:,} تومان از حساب `{target_id}` کسر شد."})
            return

        # Mandatory Channels Edit
        if current_state == "waiting_edit_channels":
            await set_setting("force_channels", text.strip())
            await execute_db("UPDATE users SET state = NULL WHERE telegram_id = ?", tg_id)
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": f"✅ کانال‌های اجباری جدید ثبت شدند:\n`{text.strip()}`", "parse_mode": "Markdown"})
            return

    # Handle Main Menu Commands & Buttons
    if text == "/start":
        if is_admin_user:
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["admin_welcome"], "reply_markup": get_admin_reply_keyboard()})
        else:
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["start_welcome"], "reply_markup": get_user_reply_keyboard()})
        return

    # User Button Actions
    if text == "🛒 خرید سرویس (رایگان)":
        plans_res = await query_db("SELECT * FROM plans WHERE is_active = 1")
        plans = get_rows(plans_res)
        if not plans:
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ هیچ پلن فعالی موجود نیست."})
            return
        kb = []
        for p in plans:
            kb.append([{"text": f"📌 {p['name']} | {p['price']:,} تومان | {p['duration_days']} روزه ({p['max_users']} کاربره)", "callback_data": f"buy_plan_confirm_{p['id']}"}])
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": "🛒 **پلن مورد نظر خود را انتخاب کنید:**", "reply_markup": {"inline_keyboard": kb}})
        return

    if text == "📱 سرویس‌های من":
        subs_res = await query_db("SELECT * FROM subscriptions WHERE user_id = (SELECT id FROM users WHERE telegram_id = ?) AND status = 'active'", tg_id)
        subs = get_rows(subs_res)
        if not subs:
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": "⚠️ شما در حال حاضر هیچ سرویس فعالی ندارید."})
            return
        domain = await get_setting("sub_domain", "your-railway-app.up.railway.app")
        for s in subs:
            sublink = f"https://{domain}/sub/{s['token']}"
            markup = {
                "inline_keyboard": [
                    [{"text": "🔄 تمدید سرویس", "callback_data": f"renew_sub_{s['token']}"},
                     {"text": "❌ حذف سرویس", "callback_data": f"delete_sub_ask_{s['token']}"}]
                ]
            }
            await call_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": f"🔗 **ساب‌لینک اختصاصی شما:**\n`{sublink}`\n\n📅 انقضا: {s['expires_at']}",
                "parse_mode": "Markdown",
                "reply_markup": markup
            })
        return

    if text == "👛 کیف پول & شارژ":
        balance = user.get("balance", 0)
        await call_telegram("sendMessage", {
            "chat_id": chat_id,
            "text": f"👛 **کیف پول شما:**\n\n💰 موجودی فعلی: **{balance:,} تومان**\n\nجهت افزایش دستی موجودی، به پشتیبانی پیام دهید."
        })
        return

    if text == "👥 دعوت دوستان":
        bot_info = await call_telegram("getMe", {})
        bot_uname = bot_info.get("result", {}).get("username", "SubLinkBot")
        reward = safe_int(await get_setting("referral_reward", "5000"))
        ref_link = f"https://t.me/{bot_uname}?start={tg_id}"
        await call_telegram("sendMessage", {
            "chat_id": chat_id,
            "text": f"👥 **دعوت از دوستان:**\n\nبا دعوت هر دوست، مبلغ **{reward:,} تومان** هدیه دریافت کنید!\n\n🔗 **لینک اختصاصی شما:**\n`{ref_link}`",
            "parse_mode": "Markdown"
        })
        return

    if text == "🎧 پشتیبانی":
        await execute_db("UPDATE users SET state = 'support_session' WHERE telegram_id = ?", tg_id)
        await call_telegram("sendMessage", {
            "chat_id": chat_id,
            "text": STRINGS["support_started"],
            "reply_markup": get_support_keyboard()
        })
        return

    # Admin Buttons
    if is_admin_user:
        if text == "➕ افزودن کانفیگ":
            await execute_db("UPDATE users SET state = 'waiting_for_config' WHERE telegram_id = ?", tg_id)
            await call_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": "📥 **افزودن کانفیگ جدید:**\n\nکانفیگ مورد نظر (VLESS / VMess / Trojan) را ارسال کنید. آی‌پی شناسایی شده و پرچم کشور به طور خودکار اضافه می‌شود.\n(برای لغو کلمه `انصراف` را بفرستید)",
                "parse_mode": "Markdown"
            })
            return

        if text == "📋 مدیریت کانفیگ‌ها":
            cfgs_res = await query_db("SELECT * FROM configs ORDER BY id DESC LIMIT 10")
            cfgs = get_rows(cfgs_res)
            if not cfgs:
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": "هیچ کانفیگی یافت نشد."})
                return
            for c in cfgs:
                msg_text = f"```\n{c['config_text']}\n```"
                markup = {
                    "inline_keyboard": [
                        [{"text": "❌ حذف کانفیگ", "callback_data": f"adm_ask_del_cfg_{c['id']}"}]
                    ]
                }
                await call_telegram("sendMessage", {
                    "chat_id": chat_id,
                    "text": msg_text,
                    "parse_mode": "Markdown",
                    "reply_markup": markup
                })
            return

        if text == "📢 ارسال همگانی":
            await execute_db("UPDATE users SET state = 'waiting_broadcast_text' WHERE telegram_id = ?", tg_id)
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": "📢 متن پیام همگانی را بفرستید:"})
            return

        if text == "⚙️ تنظیمات":
            ch = await get_setting("force_channels", "تنظیم نشده")
            msg = f"⚙️ **تنظیمات سیستم:**\n\n📢 **کانال‌های اجباری:** `{ch}`"
            markup = {
                "inline_keyboard": [
                    [{"text": "✏️ ویرایش کانال‌های اجباری", "callback_data": "adm_edit_channels"}]
                ]
            }
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown", "reply_markup": markup})
            return

        if text == "👤 مدیریت کاربران":
            await show_users_page(chat_id, 1)
            return

        if text == "📦 مدیریت پلن‌ها":
            plans_res = await query_db("SELECT * FROM plans")
            plans = get_rows(plans_res)
            text_out = "📦 **لیست پلن‌های موجود:**\n\n"
            kb = []
            for p in plans:
                text_out += f"📌 **{p['name']}**\n💰 قیمت: {p['price']:,} تومان | 📅 مدت: {p['duration_days']} روز | 👥 کاربر: {p['max_users']}\n\n"
                kb.append([{"text": f"❌ حذف پلن {p['name']}", "callback_data": f"adm_del_plan_{p['id']}"}])
            kb.append([{"text": "➕ ساخت پلن جدید", "callback_data": "adm_create_plan"}])
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": text_out, "parse_mode": "Markdown", "reply_markup": {"inline_keyboard": kb}})
            return

        if text == "👤 حالت کاربری (تست)":
            await execute_db("UPDATE users SET view_mode = 'user' WHERE telegram_id = ?", tg_id)
            await call_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": STRINGS["admin_demoted"],
                "reply_markup": get_user_reply_keyboard()
            })
            return

# ---------------------------------------------------------------------
# 🔘 پردازش Callback Query ها
# ---------------------------------------------------------------------
async def process_callback(callback):
    cq_id = callback["id"]
    chat_id = callback["message"]["chat"]["id"]
    data = callback.get("data", "")
    from_user = callback.get("from", {})
    tg_id = str(from_user.get("id"))

    user = await get_or_create_user(from_user)
    await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id})

    # Confirmation step for config deletion
    if data.startswith("adm_ask_del_cfg_"):
        cfg_id = data.replace("adm_ask_del_cfg_", "")
        markup = {
            "inline_keyboard": [
                [{"text": "✅ بله، حذف شود", "callback_data": f"adm_confirm_del_cfg_{cfg_id}"}],
                [{"text": "❌ انصراف", "callback_data": "cancel_action"}]
            ]
        }
        await call_telegram("sendMessage", {
            "chat_id": chat_id,
            "text": "❓ **آیا از حذف این کانفیگ اطمینان دارید؟**",
            "reply_markup": markup
        })
        return

    if data.startswith("adm_confirm_del_cfg_"):
        cfg_id = data.replace("adm_confirm_del_cfg_", "")
        await execute_db("DELETE FROM configs WHERE id = ?", cfg_id)
        await delete_kv("cached_configs_payload")
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": "🗑 کانفیگ با موفقیت حذف شد."})
        return

    # Broadcast Confirmation
    if data.startswith("confirm_bc_"):
        bc_text = await get_kv(f"pending_broadcast_{tg_id}")
        if bc_text:
            users_res = await query_db("SELECT telegram_id FROM users")
            all_u = get_rows(users_res)
            success = 0
            for u in all_u:
                r = await call_telegram("sendMessage", {"chat_id": int(u["telegram_id"]), "text": bc_text})
                if r.get("ok"):
                    success += 1
                await asyncio.sleep(0.04)
            await delete_kv(f"pending_broadcast_{tg_id}")
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": f"✅ **ارسال همگانی تکمیل شد.**\nموفق: {success} از {len(all_u)}"})
        return

    # Pagination Users
    if data.startswith("adm_users_page_"):
        p = safe_int(data.replace("adm_users_page_", ""), 1)
        await show_users_page(chat_id, p)
        return

    if data == "adm_search_user":
        await execute_db("UPDATE users SET state = 'waiting_search_user' WHERE telegram_id = ?", tg_id)
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": "🔍 **آیدی عددی کاربر مورد نظر را بفرستید:**"})
        return

    if data.startswith("adm_add_bal_") or data.startswith("adm_sub_bal_"):
        action = "add" if "add" in data else "sub"
        target_id = data.replace("adm_add_bal_", "").replace("adm_sub_bal_", "")
        await execute_db("UPDATE users SET state = ? WHERE telegram_id = ?", f"waiting_bal_{action}_{target_id}", tg_id)
        action_name = "افزایش" if action == "add" else "کاهش"
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": f"💵 **مبلغ مورد نظر جهت {action_name} موجودی (به تومان) را بفرستید:**"})
        return

    if data == "adm_edit_channels":
        await execute_db("UPDATE users SET state = 'waiting_edit_channels' WHERE telegram_id = ?", tg_id)
        await call_telegram("sendMessage", {
            "chat_id": chat_id,
            "text": "✏️ **کانال‌های اجباری جدید را با ویرگول جدا کرده و ارسال کنید:**\n\nمثال: `@Channel1, @Channel2`"
        })
        return

    # Plan Confirmation & Purchase
    if data.startswith("buy_plan_confirm_"):
        plan_id = data.replace("buy_plan_confirm_", "")
        plan_res = await query_db("SELECT * FROM plans WHERE id = ?", plan_id)
        plan = get_first_row(plan_res)
        if not plan:
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ پلن یافت نشد."})
            return
        markup = {
            "inline_keyboard": [
                [{"text": "✅ بله، خرید انجام شود", "callback_data": f"buy_plan_do_{plan['id']}"}],
                [{"text": "❌ انصراف", "callback_data": "cancel_action"}]
            ]
        }
        msg = f"❓ **تاییدیه خرید اشتراک**\n\n📌 نام پلن: {plan['name']}\n💰 قیمت: {plan['price']:,} تومان\n📅 مدت زمان: {plan['duration_days']} روز\n👥 محدودیت: {plan['max_users']} کاربره\n\nآیا از خرید این اشتراک اطمینان دارید؟"
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown", "reply_markup": markup})
        return

    if data.startswith("buy_plan_do_"):
        plan_id = data.replace("buy_plan_do_", "")
        plan_res = await query_db("SELECT * FROM plans WHERE id = ?", plan_id)
        plan = get_first_row(plan_res)
        if not plan:
            return
        
        balance = user.get("balance", 0)
        if balance < plan["price"]:
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": f"❌ **موجودی ناکافی!**\nموجودی شما {balance:,} تومان است اما قیمت این پلن {plan['price']:,} تومان می‌باشد."})
            return

        # Deduct balance & create sub
        await execute_db("UPDATE users SET balance = balance - ? WHERE telegram_id = ?", plan["price"], tg_id)
        token = uuid.uuid4().hex
        expires_at = (datetime.datetime.utcnow() + datetime.timedelta(days=plan["duration_days"])).strftime("%Y-%m-%d %H:%M:%S")

        await execute_db("INSERT INTO subscriptions (user_id, plan_id, token, expires_at) VALUES (?, ?, ?, ?)", user["id"], plan["id"], token, expires_at)

        domain = await get_setting("sub_domain", "your-railway-app.up.railway.app")
        sublink = f"https://{domain}/sub/{token}"
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={sublink}"

        await call_telegram("sendPhoto", {
            "chat_id": chat_id,
            "photo": qr_url,
            "caption": f"🎉 **خرید شما با موفقیت انجام شد!**\n\n📌 **پلن:** {plan['name']}\n🔗 **ساب‌لینک اختصاصی:**\n`{sublink}`\n\n📅 **انقضا:** {expires_at} (UTC)",
            "parse_mode": "Markdown"
        })
        return

    if data == "cancel_action":
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ عملیات لغو شد."})
        return

# ---------------------------------------------------------------------
# 🚀 FastAPI Server & Sublink Endpoint
# ---------------------------------------------------------------------
app = FastAPI()

@app.on_event("startup")
async def startup():
    await init_db()
    # Run background health check every 12 hours
    asyncio.create_task(periodic_health_checker())

async def periodic_health_checker():
    while True:
        try:
            await check_configs_health_job()
        except Exception as e:
            print(f"Health checker error: {e}")
        await asyncio.sleep(43200) # 12 hours

@app.post("/webhook")
async def webhook(request: Request):
    update = await request.json()
    if "message" in update:
        asyncio.create_task(process_message(update["message"]))
    elif "callback_query" in update:
        asyncio.create_task(process_callback(update["callback_query"]))
    return Response(content="OK", status_code=200)

@app.get("/sub/{token}")
async def handle_sublink(token: str, request: Request):
    """
    مبدل ساب‌لینک + بررسی انقضا + محدودیت تعداد کاربر / آی‌پی متصل
    """
    sub_res = await query_db("SELECT s.*, p.max_users FROM subscriptions s JOIN plans p ON s.plan_id = p.id WHERE s.token = ? AND s.status = 'active'", token)
    sub = get_first_row(sub_res)

    if not sub:
        return Response(content="INVALID_OR_EXPIRED_SUBLINK", media_type="text/plain", status_code=404)

    # Check Expiration
    expires_at = datetime.datetime.strptime(sub["expires_at"], "%Y-%m-%d %H:%M:%S")
    if expires_at < datetime.datetime.utcnow():
        await execute_db("UPDATE subscriptions SET status = 'expired' WHERE id = ?", sub["id"])
        return Response(content="EXPIRED_SUBSCRIPTION", media_type="text/plain", status_code=403)

    # User IP / Concurrent Device Limitation Check
    client_ip = request.client.host if request.client else "0.0.0.0"
    max_users = sub.get("max_users", 3)

    # Track usage in database
    await execute_db("INSERT INTO subscription_usage (token, ip) VALUES (?, ?)", token, client_ip)

    # Count distinct active IPs in the last 10 minutes
    time_limit = (datetime.datetime.utcnow() - datetime.timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    distinct_ips_res = await query_db("SELECT COUNT(DISTINCT ip) as ip_count FROM subscription_usage WHERE token = ? AND last_seen >= ?", token, time_limit)
    active_ips = get_first_row(distinct_ips_res)["ip_count"] if get_first_row(distinct_ips_res) else 1

    if active_ips > max_users:
        # Temporary 3-minute rate limit block for device limit violation
        return Response(
            content=f"LIMIT_EXCEEDED: Maximum allowed concurrent users ({max_users}) exceeded. Try again in 3 minutes.",
            media_type="text/plain",
            status_code=429
        )

    # Get active configs
    cached_payload = await get_kv("cached_configs_payload")
    if not cached_payload:
        cfgs_res = await query_db("SELECT config_text FROM configs WHERE is_active = 1")
        cfgs = get_rows(cfgs_res)
        combined = "\n".join([c["config_text"].strip() for c in cfgs if c["config_text"].strip()])
        cached_payload = base64.b64encode(combined.encode("utf-8")).decode("utf-8")
        await put_kv("cached_configs_payload", cached_payload, expiration_ttl=300)

    return Response(content=cached_payload, media_type="text/plain")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
