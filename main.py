# -*- coding: utf-8 -*-
"""
ربات مدیریت ساب‌لینک v3 – نسخه CAT Enhanced
- اصلاحات: بنر قابل تغییر توسط ادمین، لاگینگ، پاکسازی خودکار، بازخوانی کش، تلاش مجدد، بهبود نمایش سرویس‌ها
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
import time
import urllib.parse
import secrets
import string
import logging
from fastapi import FastAPI, Request, Response
import uvicorn

# ---------------------------------------------------------------------
# 📋 تنظیمات لاگینگ
# ---------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("CAT-BOT")

# ---------------------------------------------------------------------
# 🔐 متغیرهای محیطی (Environment Variables)
# ---------------------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = os.getenv("ADMIN_IDS", "")

CF_ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID", "")
CF_API_TOKEN = os.getenv("CF_API_TOKEN", "")
CF_D1_ID = os.getenv("CF_D1_ID", "")
CF_KV_ID = os.getenv("CF_KV_ID", "")

APP_BASE_URL = os.getenv("APP_BASE_URL", "https://technowvpnbot.ariyacompany-io.workers.dev")

# 🔥 بنر دائمی – این لینک به‌عنوان کانفیگ با id=0 در دیتابیس ذخیره می‌شود
DEFAULT_BANNER_CONFIG = "vless://1234@1.1.1.1:443?encryption=none&security=tls&sni=sertraline.adaspoloandco.com&fp=chrome&type=ws&host=sertraline.adaspoloandco.com&path=%2Fdownload.php#%F0%9F%8C%90%D9%87%D8%B1%20%D8%B1%D9%88%D8%B2%20%D9%84%DB%8C%D9%86%DA%A9%20%D8%AE%D9%88%D8%AF%20%D8%B1%D8%A7%20%D8%A2%D9%BE%D8%AF%DB%8C%D8%AA%20%DA%A9%D9%86%DB%8C%D8%AF%E2%9A%A1"

CF_HEADERS = {
    "Authorization": f"Bearer {CF_API_TOKEN}",
    "Content-Type": "application/json"
}

# ---------------------------------------------------------------------
# 🚀 Global HTTP Client & Local Cache
# ---------------------------------------------------------------------
http_client = None
_local_cache = {}

def get_local_cache(key):
    if key in _local_cache:
        val, exp = _local_cache[key]
        if time.time() < exp:
            return val
        else:
            del _local_cache[key]
    return None

def set_local_cache(key, value, ttl=300):
    _local_cache[key] = (value, time.time() + ttl)

def del_local_cache(key):
    _local_cache.pop(key, None)

# ---------------------------------------------------------------------
# 📚 تمام متون فارسی در یک جا (با اضافه‌های جدید)
# ---------------------------------------------------------------------
STRINGS = {
    "start_welcome": (
        "👋 به ربات هوشمند TechNowVpn کانفیگ رایگان خوش آمدید!\n\n"
        "از طریق دکمه‌های زیر می‌توانید حساب خود را مدیریت کرده و سرور دریافت کنید."
    ),
    "not_member": (
        "⚠️ برای فعال‌سازی کامل امکانات ربات، ابتدا در کانال‌های زیر عضو شوید و سپس روی دکمه «عضو شدم» کلیک کنید."
    ),
    "membership_confirmed": "✅ عضویت شما تأیید شد! اکنون می‌توانید از ربات استفاده کنید.",
    "trial_already_used": "⚠️ شما قبلاً از تست رایگان 1 روزه استفاده کرده‌اید.",
    "trial_activated": "🎁 اشتراک تست 1 روزه شما با موفقیت فعال شد!",
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
    "support_session_started": "💬 پیام خود را ارسال کنید.\nبرای خروج روی دکمه شیشه‌ای زیر کلیک کنید.",
    "support_session_ended": "🔚 جلسه پشتیبانی پایان یافت.",
    "support_forwarded": "پیام از کاربر {user_id}:\n\n{text}",
    "admin_only": "⛔ این بخش فقط برای مدیران در دسترس است.",
    "admin_panel": "🛠 به بخش ادمین خوش آمدید. دستورات مدیریتی را انتخاب کنید:",
    "config_added": "✅ کانفیگ جدید با موفقیت پردازش و ثبت شد . ",
    "config_add_stopped": "⏹ عملیات افزودن کانفیگ متوقف شد.",
    "broadcast_start": "📢 متن پیام همگانی خود را ارسال کنید :",
    "broadcast_sending": "⏳ در حال ارسال همگانی...",
    "broadcast_done": "✅ پیام همگانی ارسال شد.\nتعداد کل: {success} از {total}",
    "settings_show": (
        "⚙️ تنظیمات ربات:\n\n"
        "🎁 پاداش دعوت: {reward:,} تومان\n"
        "📢 کانال‌های اجباری:\n `{channels}`\n"
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
    "choose_plan": "پلن مورد نظر را انتخاب کنید:\n\n « تمامی پلن های زیر حجم نامحدود هستند »",
    "purchase_cancelled": "❌ عملیات لغو شد.",
    "banner_updated": "✅ بنر دائمی با موفقیت به‌روزرسانی شد.",
    "cache_refreshed": "🔄 کش کانفیگ‌ها با موفقیت بازخوانی شد.",
}

# ---------------------------------------------------------------------
# 🔧 توابع کمکی و API کلاودفلر (با تلاش مجدد)
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

async def query_db(sql, *args, retries=3):
    """اجرای کوئری با تلاش مجدد در صورت خطای موقت"""
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/d1/database/{CF_D1_ID}/query"
    payload = {"sql": sql, "params": list(args)}
    for attempt in range(retries):
        try:
            res = await http_client.post(url, headers=CF_HEADERS, json=payload, timeout=10.0)
            data = res.json()
            if data.get("success") is False:
                logger.error(f"D1 SQL Error: {data.get('errors')}")
            return data
        except Exception as e:
            logger.warning(f"D1 API Error (attempt {attempt+1}/{retries}): {str(e)}")
            if attempt == retries - 1:
                logger.error(f"D1 API final failure: {str(e)}")
                return {"success": False, "error": str(e)}
            await asyncio.sleep(1 * (attempt + 1))
    return {"success": False, "error": "Max retries exceeded"}

async def execute_db(sql, *args):
    return await query_db(sql, *args)

# ---------------------------------------------------------------------
# 📨 ارتباط با تلگرام و توابع ویرایش پیام
# ---------------------------------------------------------------------
async def call_telegram(method, payload):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    try:
        response = await http_client.post(url, json=payload, timeout=10.0)
        return response.json()
    except Exception as e:
        logger.error(f"Telegram API error: {str(e)}")
        return {"ok": False, "description": str(e)}

async def edit_message(chat_id, message_id, text, reply_markup=None, parse_mode=None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return await call_telegram("editMessageText", payload)

def get_back_markup(is_admin_user):
    return {"inline_keyboard": [[{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "admin_return" if is_admin_user else "user_return"}]]}

# ---------------------------------------------------------------------
# ⚙️ مدیریت تنظیمات با کش KV کلادفلر (با تلاش مجدد)
# ---------------------------------------------------------------------
async def get_kv(key, retries=3):
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_ID}/values/{key}"
    for attempt in range(retries):
        try:
            r = await http_client.get(url, headers={"Authorization": f"Bearer {CF_API_TOKEN}"}, timeout=5.0)
            if r.status_code == 200:
                return r.text
            else:
                logger.warning(f"KV get error: status {r.status_code}, attempt {attempt+1}")
        except Exception as e:
            logger.warning(f"KV get exception: {str(e)}, attempt {attempt+1}")
        await asyncio.sleep(0.5 * (attempt + 1))
    return None

async def put_kv(key, value, expiration_ttl=None, retries=3):
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_ID}/values/{key}"
    params = {}
    if expiration_ttl:
        params['expiration_ttl'] = expiration_ttl
    for attempt in range(retries):
        try:
            await http_client.put(
                url,
                headers={"Authorization": f"Bearer {CF_API_TOKEN}"},
                params=params,
                content=str(value),
                timeout=5.0
            )
            return
        except Exception as e:
            logger.warning(f"KV put error: {str(e)}, attempt {attempt+1}")
            await asyncio.sleep(0.5 * (attempt + 1))
    logger.error(f"KV put failed after {retries} attempts")

async def delete_kv(key, retries=3):
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_ID}/values/{key}"
    for attempt in range(retries):
        try:
            await http_client.delete(url, headers={"Authorization": f"Bearer {CF_API_TOKEN}"}, timeout=5.0)
            return
        except Exception as e:
            logger.warning(f"KV delete error: {str(e)}, attempt {attempt+1}")
            await asyncio.sleep(0.5 * (attempt + 1))

# ---------------------------------------------------------------------
# ✅ بهبود نمایش نام کانال‌های اجباری
# ---------------------------------------------------------------------
def normalize_channel_id(ch_id: str) -> str:
    ch_id = (ch_id or "").strip()
    if not ch_id:
        return ch_id
    if not ch_id.startswith("@") and not ch_id.startswith("-100"):
        ch_id = f"@{ch_id}"
    return ch_id

async def get_channel_pretty_name(ch_id: str) -> str:
    ch_id = normalize_channel_id(ch_id)
    if not ch_id:
        return ch_id

    cache_key = f"channel_title_{ch_id}"
    cached = get_local_cache(cache_key)
    if cached:
        return cached

    kv_val = await get_kv(cache_key)
    if kv_val and kv_val.strip():
        set_local_cache(cache_key, kv_val.strip(), 24 * 3600)
        return kv_val.strip()

    try:
        res = await call_telegram("getChat", {"chat_id": ch_id})
        if res.get("ok"):
            title = res.get("result", {}).get("title")
            if title:
                await put_kv(cache_key, title, expiration_ttl=30 * 24 * 3600)
                set_local_cache(cache_key, title, 24 * 3600)
                return title
    except Exception:
        pass

    return ch_id

# ---------------------------------------------------------------------
# 🗄️ مقداردهی اولیه دیتابیس و پردازش کانفیگ
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
        resp = await http_client.get(f"http://ip-api.com/json/{ip}?fields=country,countryCode", timeout=5.0)
        data = resp.json()
        if data.get("country"):
            code = data.get("countryCode")
            flag = chr(ord(code[0]) + 127397) + chr(ord(code[1]) + 127397) if len(code) == 2 else ""
            country_str = f"{flag} {data.get('country')}"
    except:
        pass

    rand_letter = secrets.choice(string.ascii_lowercase)
    rand_digits = f"{secrets.randbelow(100):02d}"
    rand_code = f"{rand_letter}{rand_digits}"

    new_name = f"{country_str} | @TechNowVpn | {rand_code}"

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
    initialized = await get_kv("db_initialized_v3_cat")
    await execute_db("ALTER TABLE subscriptions ADD COLUMN notified_level INTEGER DEFAULT 0")

    banner_exists = await query_db("SELECT id FROM configs WHERE id = 0")
    if not get_first_row(banner_exists):
        await execute_db("INSERT INTO configs (id, config_text, is_active, fail_count) VALUES (0, ?, 1, 0)", DEFAULT_BANNER_CONFIG)
        logger.info("Banner config created with id=0")
    else:
        await execute_db("UPDATE configs SET is_active = 1, config_text = ? WHERE id = 0", DEFAULT_BANNER_CONFIG)

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
            notified_level INTEGER DEFAULT 0,
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

    defaults = {
        "referral_reward": "2000",
        "force_channels": "",
    }
    for key, val in defaults.items():
        res = await query_db("SELECT value FROM settings WHERE key = ?", key)
        if not get_first_row(res):
            await execute_db("INSERT INTO settings (key, value) VALUES (?, ?)", key, val)

    await put_kv("db_initialized_v3_cat", "true")
    logger.info("Database initialized with v3 schema")

async def update_banner_config(new_config: str):
    await execute_db("UPDATE configs SET config_text = ?, is_active = 1, fail_count = 0 WHERE id = 0", new_config)
    await delete_kv("configs_payload")
    logger.info("Banner config updated")

async def refresh_configs_cache():
    await delete_kv("configs_payload")
    logger.info("Configs cache refreshed manually")

async def background_config_checker():
    while True:
        await asyncio.sleep(30 * 60)
        try:
            res = await query_db("SELECT * FROM configs WHERE is_active = 1 AND id != 0")
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
                    else:
                        is_healthy = False
                except:
                    is_healthy = False

                if not is_healthy:
                    fail_count = cfg.get("fail_count", 0) + 1
                    if fail_count >= 3:
                        await execute_db("DELETE FROM configs WHERE id = ?", cfg["id"])
                        await delete_kv("configs_payload")
                        if ADMIN_IDS:
                            admins = [x.strip() for x in str(ADMIN_IDS).split(",") if x.strip()]
                            for admin_id in admins:
                                await call_telegram("sendMessage", {
                                    "chat_id": int(admin_id),
                                    "text": f"⚠️ کانفیگ زیر به دلیل 3 بار عدم اتصال متوالی حذف گردید:\n\n`{cfg['config_text']}`",
                                    "parse_mode": "Markdown"
                                })
                        logger.info(f"Config {cfg['id']} removed due to health failures")
                    else:
                        await execute_db("UPDATE configs SET fail_count = ? WHERE id = ?", fail_count, cfg["id"])
                else:
                    await execute_db("UPDATE configs SET fail_count = 0 WHERE id = ?", cfg["id"])
        except Exception as e:
            logger.error(f"Checker error: {e}")

async def background_clean_expired_subs():
    while True:
        await asyncio.sleep(6 * 3600)
        try:
            now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            await execute_db("UPDATE subscriptions SET status = 'expired' WHERE expires_at < ? AND status = 'active'", now)
            cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
            await execute_db("DELETE FROM subscriptions WHERE expires_at < ? AND status = 'expired'", cutoff)
            logger.info("Expired subscriptions cleaned up")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

async def background_expiration_notifier():
    while True:
        await asyncio.sleep(15 * 60)
        try:
            now = datetime.datetime.utcnow()
            query = """
                SELECT s.id as sub_id, s.token, s.expires_at, s.notified_level,
                       u.telegram_id, u.balance
                FROM subscriptions s
                JOIN users u ON s.user_id = u.id
                WHERE s.status = 'active'
            """
            res = await query_db(query)
            subs = get_rows(res)

            for sub in subs:
                try:
                    expires_at = datetime.datetime.strptime(sub["expires_at"], "%Y-%m-%d %H:%M:%S")
                except Exception:
                    continue

                time_left = expires_at - now
                time_left_sec = time_left.total_seconds()

                if time_left_sec <= 0:
                    continue

                notified_level = sub.get("notified_level", 0)
                tg_id = sub["telegram_id"]
                sub_url = await build_sub_url_async(sub["token"])
                msg = ""
                new_level = notified_level

                if time_left_sec <= 3600 and notified_level < 3:
                    msg = (f"⚠️ **هشدار خیلی مهم** ⚠️\n\nفقط **۱ ساعت** تا پایان اعتبار سرویس شما باقی مانده است!\n\n"
                           f"🔗 لینک سرویس: `{sub_url}`\n💰 موجودی کیف پول: {sub['balance']:,} تومان\n\n"
                           f"جهت جلوگیری از قطعی سرویس، سریعاً از طریق دکمه زیر تمدید کنید.")
                    new_level = 3
                elif time_left_sec <= 86400 and notified_level < 2:
                    msg = (f"⏳ **یادآوری تمدید**\n\nسرویس شما **۲۴ ساعت** دیگر منقضی خواهد شد.\n\n"
                           f"🔗 لینک سرویس: `{sub_url}`\n💰 موجودی کیف پول: {sub['balance']:,} تومان\n\n"
                           f"لطفاً پیش از اتمام زمان، اکانت خود را شارژ و تمدید نمایید.")
                    new_level = 2
                elif time_left_sec <= 259200 and notified_level < 1:
                    msg = (f"📅 **اطلاعیه سرویس**\n\nکاربر گرامی، تنها **۳ روز** تا پایان اشتراک شما باقی مانده است.\n\n"
                           f"🔗 لینک سرویس: `{sub_url}`\n💰 موجودی کیف پول: {sub['balance']:,} تومان\n\n"
                           f"می‌توانید با دعوت دوستان حساب خود را رایگان شارژ کنید یا تمدید نمایید.")
                    new_level = 1

                if msg:
                    markup = {"inline_keyboard": [[{"text": "♻️ تمدید سریع سرویس", "callback_data": f"renew_sub_{sub['token']}"}]]}
                    res_tg = await call_telegram("sendMessage", {
                        "chat_id": int(tg_id),
                        "text": msg,
                        "parse_mode": "Markdown",
                        "reply_markup": markup
                    })
                    if res_tg.get("ok"):
                        await execute_db("UPDATE subscriptions SET notified_level = ? WHERE id = ?", new_level, sub["sub_id"])

        except Exception as e:
            logger.error(f"Notifier error: {e}")

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
            await execute_db("INSERT INTO users (telegram_id, referred_by, username, full_name) VALUES (?, ?, ?, ?)",
                             str(telegram_id), ref_id, username, full_name)
        else:
            await execute_db("INSERT INTO users (telegram_id, username, full_name) VALUES (?, ?, ?)",
                             str(telegram_id), username, full_name)
        res = await query_db("SELECT * FROM users WHERE telegram_id = ?", str(telegram_id))
        user = get_first_row(res)
    else:
        if from_user:
            await execute_db("UPDATE users SET username = ?, full_name = ? WHERE id = ?",
                             username, full_name, user["id"])
            user["username"] = username
            user["full_name"] = full_name

    return user

async def check_channel_membership(telegram_id, force_refresh=False):
    if is_admin(telegram_id):
        return True

    cache_key = f"membership_{telegram_id}"
    if not force_refresh:
        cached = get_local_cache(cache_key)
        if cached is not None:
            return cached

    force_channels = await get_setting("force_channels", "")
    if not force_channels:
        set_local_cache(cache_key, True, 30)
        return True

    channels = [c.strip() for c in force_channels.split(",") if c.strip()]
    for channel in channels:
        ch_parts = channel.split("|")
        ch_id = normalize_channel_id(ch_parts[0].strip())

        res = await call_telegram("getChatMember", {
            "chat_id": ch_id,
            "user_id": int(telegram_id)
        })
        if not res.get("ok"):
            set_local_cache(cache_key, False, 5)
            return False

        status = res["result"].get("status")
        if status not in ["creator", "administrator", "member"]:
            set_local_cache(cache_key, False, 5)
            return False

    set_local_cache(cache_key, True, 20)
    return True

async def build_sub_url_async(token: str) -> str:
    cache_key = f"sub_url_{token}"
    cached = get_local_cache(cache_key)
    if cached:
        return cached

    kv_val = await get_kv(cache_key)
    if kv_val:
        set_local_cache(cache_key, kv_val, 300)
        return kv_val

    sub_res = await query_db(
        "SELECT s.expires_at, s.plan_id, p.duration_days, p.max_users "
        "FROM subscriptions s "
        "LEFT JOIN plans p ON s.plan_id = p.id "
        "WHERE s.token = ? AND s.status = 'active'",
        token
    )
    row = get_first_row(sub_res)
    if not row:
        base = APP_BASE_URL.rstrip('/')
        fallback = f"{base}/sub/{token}"
        set_local_cache(cache_key, fallback, 60)
        return fallback

    expires_at_str = row["expires_at"]
    try:
        expires_at = datetime.datetime.strptime(expires_at_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        expires_at = datetime.datetime.strptime(expires_at_str.split(".")[0], "%Y-%m-%d %H:%M:%S")

    now = datetime.datetime.utcnow()
    days_left = (expires_at - now).days
    days_left_str = f"{days_left}روز" if days_left >= 0 else "منقضی"

    plan_id = row.get("plan_id")
    if plan_id:
        duration = row.get("duration_days", 0)
        max_users = row.get("max_users", 1)
        title = f"⏳{days_left_str}👥{max_users}کاربره♾️نامحدود📆{duration}روزه"
    else:
        title = f"⏳{days_left_str}👤۱کاربره♾️نامحدود🎁تست۱روزه"

    base = APP_BASE_URL.rstrip('/')
    full_url = f"{base}/sub/{token}#{title}"

    set_local_cache(cache_key, full_url, 300)
    await put_kv(cache_key, full_url, expiration_ttl=300)

    return full_url

async def get_user_inline_keyboard(is_actual_admin=False):
    kb = [
        [{"text": "🛒 خرید سرویس", "callback_data": "buy_service"}, {"text": "🎁 تست رایگان", "callback_data": "free_trial"}],
        [{"text": "📱 سرویس‌های من", "callback_data": "my_services"}, {"text": "👛 کیف پول", "callback_data": "wallet"}],
        [{"text": "👥 دعوت دوستان", "callback_data": "referral"}, {"text": "🎧 پشتیبانی", "callback_data": "support"}]
    ]

    bottom_row = [{"text": "📖 راهنما", "callback_data": "help_btn"}]
    dyn_btn_title = await get_setting("dyn_btn_title")
    if dyn_btn_title:
        bottom_row.insert(0, {"text": dyn_btn_title, "callback_data": "dyn_btn_click"})

    kb.append(bottom_row)

    if is_actual_admin:
        kb.append([{"text": "👑 مدیریت", "callback_data": "admin_return"}])
    return {"inline_keyboard": kb}

def get_admin_inline_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "📦 مدیریت پلن‌ها", "callback_data": "adm_manage_plans"}, {"text": "👤 مدیریت کاربران", "callback_data": "adm_manage_users_1"}],
            [{"text": "📋 مدیریت کانفیگ‌ها", "callback_data": "adm_manage_configs"}, {"text": "➕ افزودن کانفیگ", "callback_data": "adm_add_config"}],
            [{"text": "🔄 بازخوانی کش کانفیگ", "callback_data": "adm_refresh_cache"}, {"text": "🖼 تغییر بنر", "callback_data": "adm_update_banner"}],
            [{"text": "⚙️ تنظیمات", "callback_data": "adm_settings"}, {"text": "📢 ارسال همگانی", "callback_data": "adm_broadcast"}],
            [{"text": "👤 نمای کاربری", "callback_data": "adm_test_user"}]
        ]
    }

def get_plans_inline_keyboard(plans, is_admin_user):
    kb = []
    for p in plans:
        kb.append([{"text": f"{p['name']} - {p['price']:,} تومان", "callback_data": f"buy_plan_{p['id']}"}])
    kb.append([{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "admin_return" if is_admin_user else "user_return"}])
    return {"inline_keyboard": kb}

async def send_membership_requirement(chat_id, message_id=None):
    force_channels = await get_setting("force_channels", "")
    if not force_channels:
        return
    channels = [c.strip() for c in force_channels.split(",") if c.strip()]

    kb = []
    for ch in channels:
        ch_parts = ch.split("|")
        ch_id_raw = ch_parts[0].strip()
        ch_id = normalize_channel_id(ch_id_raw)

        if len(ch_parts) > 1 and ch_parts[1].strip():
            ch_name = ch_parts[1].strip()
        else:
            ch_name = await get_channel_pretty_name(ch_id)

        ch_clean = ch_id.replace('@', '')
        kb.append([{"text": f"📢 عضویت در {ch_name}", "url": f"https://t.me/{ch_clean}"}])

    kb.append([{"text": "✅ عضو شدم", "callback_data": "chk_membership"}])

    markup = {"inline_keyboard": kb}
    if message_id:
        await edit_message(chat_id, message_id, STRINGS["not_member"], reply_markup=markup)
    else:
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

        ref_user_res = await query_db("SELECT balance FROM users WHERE telegram_id = ?", ref_id)
        ref_user = get_first_row(ref_user_res)
        new_balance = ref_user["balance"] if ref_user else 0

        await call_telegram("sendMessage", {
            "chat_id": int(ref_id),
            "text": f"🎉 یکی از دوستان شما با لینک دعوت شما عضو شد و مبلغ {reward:,} تومان به موجودی شما افزوده گردید!\n💰 موجودی جدید شما: {new_balance:,} تومان"
        })
        new_ref_status = f"{ref_id}_rewarded"
        await execute_db("UPDATE users SET referred_by = ? WHERE id = ?", new_ref_status, user["id"])
        user["referred_by"] = new_ref_status

async def handle_free_trial(user, chat_id, message_id, is_admin_user):
    if user.get("has_used_trial"):
        await edit_message(chat_id, message_id, STRINGS["trial_already_used"], reply_markup=get_back_markup(is_admin_user))
        return
    token = secrets.token_hex(16)
    expires_at = (datetime.datetime.utcnow() + datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    await execute_db("INSERT INTO subscriptions (user_id, token, expires_at) VALUES (?, ?, ?)", user["id"], token, expires_at)
    await execute_db("UPDATE users SET has_used_trial = 1 WHERE id = ?", user["id"])
    sub_url = await build_sub_url_async(token)
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={sub_url}"
    msg = STRINGS["trial_activated"] + f"\n\n🔗 ساب‌لینک:\n`{sub_url}`\n\n📅 انقضا: {expires_at} (UTC)"

    await call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
    await call_telegram("sendPhoto", {
        "chat_id": chat_id,
        "photo": qr_url,
        "caption": msg,
        "parse_mode": "Markdown",
        "reply_markup": get_back_markup(is_admin_user)
    })

async def handle_wallet(user, chat_id, message_id, is_admin_user):
    telegram_id = user["telegram_id"]
    ref_count_res = await query_db("SELECT COUNT(*) as count FROM users WHERE referred_by LIKE ?", f"{telegram_id}%")
    ref_count_row = get_first_row(ref_count_res)
    ref_count = ref_count_row["count"] if ref_count_row else 0
    msg = STRINGS["wallet_info"].format(balance=user["balance"], ref_count=ref_count)
    await edit_message(chat_id, message_id, msg, reply_markup=get_back_markup(is_admin_user))

async def handle_buy_service(user, chat_id, message_id, is_admin_user):
    res = await query_db("SELECT * FROM plans WHERE is_active = 1")
    plans = get_rows(res)
    if not plans:
        await edit_message(chat_id, message_id, "❌ هیچ پلن فعالی در حال حاضر موجود نیست.", reply_markup=get_back_markup(is_admin_user))
        return

    txt = "🛒 پلن مورد نظر خود را انتخاب کنید:\n\n"
    for p in plans:
        txt += f"📌 {p['name']} \n 👥 {p['max_users']} کاربر \n 📆 {p['duration_days']} روز \n 💰 {p['price']:,} تومان\n\n"

    markup = get_plans_inline_keyboard(plans, is_admin_user)
    await edit_message(chat_id, message_id, txt, reply_markup=markup)

async def handle_my_services(user, chat_id, message_id, is_admin_user):
    sub_res = await query_db("SELECT * FROM subscriptions WHERE user_id = ? AND status = 'active' ORDER BY id DESC", user["id"])
    subs = get_rows(sub_res)
    if not subs:
        await edit_message(chat_id, message_id, STRINGS["no_active_services"], reply_markup=get_back_markup(is_admin_user))
        return

    await edit_message(chat_id, message_id, STRINGS["services_list"].format(count=len(subs)))
    for s in subs:
        sub_url = await build_sub_url_async(s["token"])

        markup = {
            "inline_keyboard": [
                [{"text": "🖼 نمایش کیوآرکد", "callback_data": f"qr_{s['token']}"}],
                [{"text": "♻️ تمدید سرویس", "callback_data": f"renew_sub_{s['token']}"},
                 {"text": "🗑 حذف سرویس", "callback_data": f"del_sub_req_{s['token']}"}]
            ]
        }
        await call_telegram("sendMessage", {
            "chat_id": chat_id,
            "text": f"🔗 ساب‌لینک شما:\n`{sub_url}`\n\n📅 تاریخ انقضا: {s['expires_at']} (UTC)",
            "parse_mode": "Markdown",
            "reply_markup": markup
        })

    await call_telegram("sendMessage", {
        "chat_id": chat_id,
        "text": "برای بازگشت از دکمه زیر استفاده کنید:",
        "reply_markup": get_back_markup(is_admin_user)
    })

async def handle_referral(user, chat_id, message_id, is_admin_user):
    reward_val = await get_setting("referral_reward", "2000")
    reward = safe_int(reward_val, 2000)
    bot_info = await call_telegram("getMe", {})
    bot_username = bot_info.get("result", {}).get("username", "V2rayBot")
    ref_link = f"https://t.me/{bot_username}?start={user['telegram_id']}"
    msg = STRINGS["referral_info"].format(reward=reward, ref_link=ref_link)
    await edit_message(chat_id, message_id, msg, reply_markup=get_back_markup(is_admin_user), parse_mode="Markdown")

async def handle_support_start(user, chat_id, message_id, is_admin_user):
    if user.get("state") == f"support_session_{user['telegram_id']}":
        return

    await execute_db("UPDATE users SET state = ? WHERE id = ?", f"support_session_{user['telegram_id']}", user["id"])

    markup = {"inline_keyboard": [[{"text": "🔚 پایان پشتیبانی", "callback_data": "end_support"}]]}
    await edit_message(chat_id, message_id, STRINGS["support_session_started"], reply_markup=markup)

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
        "text": "✅ پیام شما ارسال شد. منتظر پاسخ باشید."
    })

async def create_subscription_from_plan(plan_id, user_id):
    res = await query_db("SELECT * FROM plans WHERE id = ? AND is_active = 1", plan_id)
    plan = get_first_row(res)
    if not plan:
        return None
    token = secrets.token_hex(16)
    expires_at = (datetime.datetime.utcnow() + datetime.timedelta(days=plan["duration_days"])).strftime("%Y-%m-%d %H:%M:%S")
    await execute_db("INSERT INTO subscriptions (user_id, plan_id, token, expires_at) VALUES (?, ?, ?, ?)", user_id, plan_id, token, expires_at)
    return token

async def handle_state(user, state, message, chat_id, is_admin_user, actual_is_admin):
    text = message.get("text", "").strip()

    if text in ["❌ خروج / اتمام ارسال", "لغو", "/cancel"]:
        await execute_db("UPDATE users SET state = NULL, plan_data = NULL WHERE id = ?", user["id"])
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": "عملیات لغو شد."})
        if is_admin_user:
            await show_admin_panel(chat_id)
        else:
            markup = await get_user_inline_keyboard(actual_is_admin)
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["start_welcome"], "reply_markup": markup})
        return True

    if is_admin_user:
        if state == "waiting_for_banner_update":
            await update_banner_config(text)
            await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])
            markup = {"inline_keyboard": [[{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "admin_return"}]]}
            await call_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": STRINGS["banner_updated"],
                "reply_markup": markup
            })
            return True

        if state == "waiting_for_config":
            formatted_cfg = await format_config_name(text)
            await execute_db("INSERT INTO configs (config_text) VALUES (?)", formatted_cfg)
            await delete_kv("configs_payload")
            markup = {"inline_keyboard": [[{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "admin_return"}]]}
            await call_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": STRINGS["config_added"],
                "reply_markup": markup
            })
            return True

        if state == "waiting_for_broadcast":
            if not text or text.strip() == "":
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ متن پیام نمی‌تواند خالی باشد. مجدداً ارسال کنید:"})
                return True
            await put_kv(f"broadcast_{user['id']}", text, expiration_ttl=3600)
            await execute_db("UPDATE users SET state = ? WHERE id = ?", "waiting_for_broadcast_confirm", user["id"])
            markup = {"inline_keyboard": [[{"text": "✅ تایید و ارسال", "callback_data": "adm_broadcast_yes"},
                                          {"text": "🔙 بازگشت به منوی اصلی", "callback_data": "admin_return"}]]}
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

            raw_plan_data = user.get("plan_data")
            if not raw_plan_data or raw_plan_data == "null":
                raw_plan_data = "{}"

            try:
                plan_data = json.loads(raw_plan_data)
            except:
                plan_data = {}

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

        if state == "waiting_dyn_title":
            await set_setting("dyn_btn_title", text.strip())
            await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": "✅ عنوان دکمه در منوی کاربری ذخیره شد.", "reply_markup": get_admin_inline_keyboard()})
            return True

        if state == "waiting_dyn_content":
            dyn_data = {}
            if text:
                dyn_data = {"type": "text", "content": text}
            elif message.get("photo"):
                dyn_data = {"type": "photo", "file_id": message["photo"][-1]["file_id"], "caption": message.get("caption", "")}
            elif message.get("video"):
                dyn_data = {"type": "video", "file_id": message["video"]["file_id"], "caption": message.get("caption", "")}
            elif message.get("document"):
                dyn_data = {"type": "document", "file_id": message["document"]["file_id"], "caption": message.get("caption", "")}

            if dyn_data:
                await set_setting("dyn_btn_content", json.dumps(dyn_data))
                await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": "✅ محتوای دکمه داینامیک ثبت شد.", "reply_markup": get_admin_inline_keyboard()})
            return True

    if state and state.startswith("support_session_"):
        await forward_support_message(user, message, chat_id)
        return True

    return False

async def process_callback(callback):
    cq_id = callback["id"]
    message = callback.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    message_id = message.get("message_id")
    data = callback.get("data", "")
    from_user = callback.get("from", {})
    telegram_id = str(from_user.get("id", ""))

    user = await get_or_create_user(telegram_id, from_user=from_user)
    actual_is_admin = is_admin(telegram_id, user_data=None)
    is_admin_user = is_admin(telegram_id, user_data=user)

    defer_answer = data.startswith("confirm_buy_") or data == "chk_membership" or data.startswith("qr_") or data.startswith("confirm_renew_")
    if not defer_answer and data != "end_support":
        await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id})

    if data == "end_support":
        await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])

        await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "✅ نشست پشتیبانی پایان یافت.", "show_alert": True})
        await edit_message(chat_id, message_id, "🔚 نشست پشتیبانی پایان یافت.", reply_markup=None)

        markup = await get_user_inline_keyboard(actual_is_admin)
        await call_telegram("sendMessage", {
            "chat_id": chat_id,
            "text": STRINGS["start_welcome"],
            "reply_markup": markup
        })

        async def delete_old_message_later():
            await asyncio.sleep(5)
            await call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": message_id})

        asyncio.create_task(delete_old_message_later())
        return

    if data in ["user_return", "admin_return"]:
        if user.get("state") is not None:
            await execute_db("UPDATE users SET state = NULL, plan_data = NULL WHERE id = ?", user["id"])
            user["state"] = None
            user["plan_data"] = None

    if data == "admin_return" and actual_is_admin:
        await execute_db("UPDATE users SET is_test_mode = 0 WHERE id = ?", user["id"])
        res = await edit_message(chat_id, message_id, STRINGS["admin_panel"], reply_markup=get_admin_inline_keyboard())
        if not res.get("ok"):
            await call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
            await show_admin_panel(chat_id)
        return

    if data == "user_return":
        markup = await get_user_inline_keyboard(actual_is_admin)
        res = await edit_message(chat_id, message_id, STRINGS["start_welcome"], reply_markup=markup)
        if not res.get("ok"):
            await call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
            await call_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": STRINGS["start_welcome"],
                "reply_markup": markup
            })
        return

    if data != "chk_membership" and not await check_channel_membership(telegram_id, force_refresh=False):
        await send_membership_requirement(chat_id, message_id)
        return

    if data == "chk_membership":
        if await check_channel_membership(telegram_id, force_refresh=True):
            await credit_referrer_if_pending(user, chat_id)
            await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "✅ عضویت تایید شد!"})
            markup = get_admin_inline_keyboard() if is_admin_user else await get_user_inline_keyboard(actual_is_admin)
            res = await edit_message(chat_id, message_id, STRINGS["start_welcome"], reply_markup=markup)
            if not res.get("ok"):
                await call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["start_welcome"], "reply_markup": markup})
        else:
            await call_telegram("answerCallbackQuery", {
                "callback_query_id": cq_id,
                "text": "❌ هنوز در کانال عضو نشده‌اید!\nبعد از عضویت دوباره تلاش کنید.",
                "show_alert": True
            })
        return

    if data == "cancel_action":
        await edit_message(chat_id, message_id, STRINGS["purchase_cancelled"], reply_markup=get_back_markup(is_admin_user))
        return

    if data == "free_trial": return await handle_free_trial(user, chat_id, message_id, is_admin_user)
    if data == "wallet": return await handle_wallet(user, chat_id, message_id, is_admin_user)
    if data == "buy_service": return await handle_buy_service(user, chat_id, message_id, is_admin_user)
    if data == "my_services": return await handle_my_services(user, chat_id, message_id, is_admin_user)
    if data == "referral": return await handle_referral(user, chat_id, message_id, is_admin_user)
    if data == "support": return await handle_support_start(user, chat_id, message_id, is_admin_user)

    if data == "help_btn":
        help_val = await get_setting("help_content")
        if not help_val:
            await edit_message(chat_id, message_id, "محتوای راهنما هنوز تنظیم نشده است.", reply_markup=get_back_markup(is_admin_user))
            return
        try:
            help_data = json.loads(help_val)
            if help_data["type"] == "text":
                await edit_message(chat_id, message_id, help_data["content"], reply_markup=get_back_markup(is_admin_user))
            else:
                await call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
                if help_data["type"] == "photo":
                    await call_telegram("sendPhoto", {"chat_id": chat_id, "photo": help_data["file_id"], "caption": help_data.get("caption", ""), "reply_markup": get_back_markup(is_admin_user)})
                elif help_data["type"] == "video":
                    await call_telegram("sendVideo", {"chat_id": chat_id, "video": help_data["file_id"], "caption": help_data.get("caption", ""), "reply_markup": get_back_markup(is_admin_user)})
                elif help_data["type"] == "document":
                    await call_telegram("sendDocument", {"chat_id": chat_id, "document": help_data["file_id"], "caption": help_data.get("caption", ""), "reply_markup": get_back_markup(is_admin_user)})
        except:
            pass
        return

    if data == "dyn_btn_click":
        content_val = await get_setting("dyn_btn_content")

        if not content_val:
            await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "محتوایی تنظیم نشده است.", "show_alert": True})
            return

        markup = {"inline_keyboard": [[{"text": "🔙 بازگشت", "callback_data": "user_return"}]]}

        try:
            dyn_data = json.loads(content_val)
            if dyn_data["type"] == "text":
                await edit_message(chat_id, message_id, dyn_data["content"], reply_markup=markup)
            else:
                await call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
                if dyn_data["type"] == "photo":
                    await call_telegram("sendPhoto", {"chat_id": chat_id, "photo": dyn_data["file_id"], "caption": dyn_data.get("caption", ""), "reply_markup": markup})
                elif dyn_data["type"] == "video":
                    await call_telegram("sendVideo", {"chat_id": chat_id, "video": dyn_data["file_id"], "caption": dyn_data.get("caption", ""), "reply_markup": markup})
                elif dyn_data["type"] == "document":
                    await call_telegram("sendDocument", {"chat_id": chat_id, "document": dyn_data["file_id"], "caption": dyn_data.get("caption", ""), "reply_markup": markup})
        except:
            pass
        return

    if data.startswith("qr_"):
        token = data.replace("qr_", "")
        sub_res = await query_db("SELECT * FROM subscriptions WHERE token = ? AND status = 'active'", token)
        if not get_first_row(sub_res):
            await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "❌ اشتراک یافت نشد.", "show_alert": True})
            return

        await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id})

        sub_url = await build_sub_url_async(token)
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={sub_url}"
        await call_telegram("sendPhoto", {
            "chat_id": chat_id,
            "photo": qr_url,
            "caption": f"📱 کیوآرکد اتصال شما:\n\n`{sub_url}`",
            "parse_mode": "Markdown",
            "reply_markup": {"inline_keyboard": [[{"text": "🔙 بازگشت", "callback_data": "my_services"}]]}
        })
        return

    if data.startswith("renew_sub_"):
        token = data.replace("renew_sub_", "")
        sub_res = await query_db("SELECT * FROM subscriptions WHERE token = ?", token)
        sub = get_first_row(sub_res)
        if not sub or not sub.get("plan_id"):
            await edit_message(chat_id, message_id, "❌ امکان تمدید این سرویس وجود ندارد.", reply_markup={"inline_keyboard": [[{"text": "🔙 بازگشت", "callback_data": "my_services"}]]})
            return
        plan_res = await query_db("SELECT * FROM plans WHERE id = ?", sub["plan_id"])
        plan = get_first_row(plan_res)
        if not plan:
            await edit_message(chat_id, message_id, "❌ پلن مرتبط با این سرویس حذف شده است.", reply_markup={"inline_keyboard": [[{"text": "🔙 بازگشت", "callback_data": "my_services"}]]})
            return

        markup = {"inline_keyboard": [[{"text": "✅ تایید پرداخت", "callback_data": f"confirm_renew_{token}"}, {"text": "❌ لغو", "callback_data": "my_services"}]]}
        await edit_message(chat_id, message_id, f"هزینه تمدید {plan['duration_days']} روزه: {plan['price']:,} تومان\nآیا تایید میکنید؟", reply_markup=markup)
        return

    if data.startswith("confirm_renew_"):
        token = data.replace("confirm_renew_", "")
        sub_res = await query_db("SELECT * FROM subscriptions WHERE token = ?", token)
        sub = get_first_row(sub_res)
        plan_res = await query_db("SELECT * FROM plans WHERE id = ?", sub["plan_id"])
        plan = get_first_row(plan_res)

        if user["balance"] < plan["price"]:
            await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "❌ موجودی کافی نیست.", "show_alert": True})
            return

        await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id})
        await execute_db("UPDATE users SET balance = balance - ? WHERE id = ?", plan["price"], user["id"])

        try:
            expires_at = datetime.datetime.strptime(sub["expires_at"], "%Y-%m-%d %H:%M:%S")
            if expires_at < datetime.datetime.utcnow():
                expires_at = datetime.datetime.utcnow()
        except:
            expires_at = datetime.datetime.utcnow()

        new_expires_at = (expires_at + datetime.timedelta(days=plan["duration_days"])).strftime("%Y-%m-%d %H:%M:%S")
        await execute_db("UPDATE subscriptions SET expires_at = ?, status = 'active', notified_level = 0 WHERE id = ?", new_expires_at, sub["id"])
        await edit_message(chat_id, message_id, f"✅ سرویس با موفقیت تمدید شد.\nانقضای جدید: {new_expires_at} (UTC)", reply_markup={"inline_keyboard": [[{"text": "🔙 بازگشت", "callback_data": "my_services"}]]})
        return

    if data.startswith("del_sub_req_"):
        token = data.replace("del_sub_req_", "")
        markup = {"inline_keyboard": [[{"text": "✅ بله، حذف کن", "callback_data": f"del_sub_yes_{token}"}, {"text": "❌ خیر", "callback_data": "my_services"}]]}
        await edit_message(chat_id, message_id, "آیا از حذف این سرویس اطمینان دارید؟", reply_markup=markup)
        return

    if data.startswith("del_sub_yes_"):
        token = data.replace("del_sub_yes_", "")
        await execute_db("DELETE FROM subscriptions WHERE token = ?", token)
        await edit_message(chat_id, message_id, "✅ سرویس با موفقیت حذف شد.", reply_markup={"inline_keyboard": [[{"text": "🔙 بازگشت", "callback_data": "my_services"}]]})
        return

    if data.startswith("buy_plan_"):
        plan_id = int(data.replace("buy_plan_", ""))
        res = await query_db("SELECT * FROM plans WHERE id = ? AND is_active = 1", plan_id)
        plan = get_first_row(res)
        if not plan:
            await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "❌ پلن مورد نظر فعال نیست.", "show_alert": True})
            return

        markup = {"inline_keyboard": [[{"text": "✅ تایید خرید", "callback_data": f"confirm_buy_{plan_id}"}, {"text": "❌ لغو", "callback_data": "buy_service"}]]}
        await edit_message(chat_id, message_id, f"آیا از خرید این پلن به مبلغ {plan['price']:,} تومان اطمینان دارید؟", reply_markup=markup)
        return

    if data.startswith("confirm_buy_"):
        plan_id = int(data.replace("confirm_buy_", ""))
        res = await query_db("SELECT * FROM plans WHERE id = ?", plan_id)
        plan = get_first_row(res)

        if not plan:
            await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "❌ این پلن حذف شده یا نامعتبر است.", "show_alert": True})
            return

        price = plan["price"]

        if user["balance"] < price:
            msg = STRINGS["insufficient_balance"].format(balance=user["balance"], price=price)
            await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": msg, "show_alert": True})
            return

        await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id})

        await execute_db("UPDATE users SET balance = balance - ? WHERE id = ?", price, user["id"])
        token = await create_subscription_from_plan(plan_id, user["id"])
        if not token:
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ خطا در ایجاد اشتراک."})
            return

        sub_url = await build_sub_url_async(token)
        expires_at = (datetime.datetime.utcnow() + datetime.timedelta(days=plan["duration_days"])).strftime("%Y-%m-%d %H:%M:%S")
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={sub_url}"
        msg = STRINGS["subscription_created"].format(duration=plan["duration_days"], sublink=sub_url, expires_at=expires_at)

        await call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
        await call_telegram("sendPhoto", {
            "chat_id": chat_id,
            "photo": qr_url,
            "caption": msg,
            "parse_mode": "Markdown",
            "reply_markup": get_back_markup(is_admin_user)
        })
        return

    if not is_admin_user:
        await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": STRINGS["admin_only"], "show_alert": True})
        return

    if data == "adm_test_user":
        await execute_db("UPDATE users SET is_test_mode = 1 WHERE id = ?", user["id"])
        markup = await get_user_inline_keyboard(actual_is_admin)
        await edit_message(chat_id, message_id, "شما اکنون در نمای کاربری هستید. برای بازگشت دکمه مربوطه را بزنید.", reply_markup=markup)
        return

    if data == "adm_refresh_cache":
        await refresh_configs_cache()
        await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "✅ کش بازخوانی شد!"})
        await edit_message(chat_id, message_id, STRINGS["cache_refreshed"], reply_markup=get_admin_inline_keyboard())
        return

    if data == "adm_update_banner":
        await execute_db("UPDATE users SET state = 'waiting_for_banner_update' WHERE id = ?", user["id"])
        await edit_message(chat_id, message_id, "📥 لطفاً کانفیگ جدید بنر را ارسال کنید (این کانفیگ به‌عنوان id=0 ذخیره می‌شود):", reply_markup={"inline_keyboard": [[{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "admin_return"}]]})
        return

    if data == "adm_add_config":
        await execute_db("UPDATE users SET state = 'waiting_for_config' WHERE id = ?", user["id"])
        await edit_message(chat_id, message_id, "📥 لطفا کانفیگ خود را ارسال کنید.\nبرای پایان، دکمه زیر را بزنید:", reply_markup={"inline_keyboard": [[{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "admin_return"}]]})
        return

    if data == "adm_manage_configs":
        cfg_res = await query_db("SELECT id, config_text, is_active FROM configs ORDER BY id DESC LIMIT 20")
        configs = get_rows(cfg_res)
        if not configs:
            await edit_message(chat_id, message_id, "هیچ کانفیگی موجود نیست.", reply_markup=get_back_markup(True))
            return

        await call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
        for c in configs:
            markup = {
                "inline_keyboard": [
                    [{"text": "❌ حذف", "callback_data": f"adm_cfg_del_req_{c['id']}"}]
                ]
            }
            await call_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": f"شناسه کانفیگ: {c['id']}\n```{c['config_text']}```",
                "parse_mode": "Markdown",
                "reply_markup": markup
            })

        await call_telegram("sendMessage", {
            "chat_id": chat_id,
            "text": "بازگشت به پنل مدیریت:",
            "reply_markup": get_back_markup(True)
        })
        return

    if data.startswith("adm_cfg_del_req_"):
        cfg_id = data.replace("adm_cfg_del_req_", "")
        markup = {"inline_keyboard": [[{"text": "✅ بله، حذف کن", "callback_data": f"adm_cfg_del_yes_{cfg_id}"},
                                      {"text": "❌ لغو", "callback_data": f"adm_cfg_del_cancel_{cfg_id}"}]]}
        await edit_message(chat_id, message_id, "آیا از حذف این کانفیگ اطمینان دارید؟", reply_markup=markup)
        return

    if data.startswith("adm_cfg_del_cancel_"):
        cfg_id = data.replace("adm_cfg_del_cancel_", "")
        res = await query_db("SELECT config_text FROM configs WHERE id = ?", cfg_id)
        cfg = get_first_row(res)
        if cfg:
            markup = {"inline_keyboard": [[{"text": "❌ حذف", "callback_data": f"adm_cfg_del_req_{cfg_id}"}]]}
            await edit_message(chat_id, message_id, f"شناسه کانفیگ: {cfg_id}\n```{cfg['config_text']}```", reply_markup=markup, parse_mode="Markdown")
        else:
            await call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
        return

    if data.startswith("adm_cfg_del_yes_"):
        cfg_id = data.replace("adm_cfg_del_yes_", "")
        if int(cfg_id) == 0:
            await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "❌ بنر دائمی قابل حذف نیست!", "show_alert": True})
            return
        await execute_db("DELETE FROM configs WHERE id = ?", cfg_id)
        await delete_kv("configs_payload")
        await call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
        return

    if data == "adm_broadcast":
        await execute_db("UPDATE users SET state = 'waiting_for_broadcast' WHERE id = ?", user["id"])
        await edit_message(chat_id, message_id, STRINGS["broadcast_start"], reply_markup=get_back_markup(True))
        return

    if data == "adm_broadcast_yes":
        if user.get("state") != "waiting_for_broadcast_confirm":
            await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "❌ وضعیت نامعتبر.", "show_alert": True})
            return

        msg_text = await get_kv(f"broadcast_{user['id']}")
        if not msg_text or msg_text.strip() == "":
            await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "❌ متن پیام یافت نشد.", "show_alert": True})
            return

        await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])
        await delete_kv(f"broadcast_{user['id']}")

        all_users_res = await query_db("SELECT telegram_id FROM users")
        all_users = get_rows(all_users_res)
        await edit_message(chat_id, message_id, STRINGS["broadcast_sending"])

        success = 0
        for u in all_users:
            res = await call_telegram("sendMessage", {
                "chat_id": int(u["telegram_id"]),
                "text": msg_text
            })
            if res.get("ok"):
                success += 1
            await asyncio.sleep(0.05)

        await edit_message(chat_id, message_id, STRINGS["broadcast_done"].format(success=success, total=len(all_users)), reply_markup=get_admin_inline_keyboard())
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
                [{"text": "📖 تنظیم راهنما", "callback_data": "adm_set_help"},
                 {"text": "🔘 تنظیم دکمه داینامیک", "callback_data": "adm_dyn_btn"}],
                [{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "admin_return"}]
            ]
        }
        await edit_message(chat_id, message_id, settings_text, reply_markup=markup, parse_mode="Markdown")
        return

    if data == "adm_set_channels":
        channels_str = await get_setting("force_channels", "")
        ch_list = [c.strip() for c in channels_str.split(",") if c.strip()]
        kb = []
        for ch in ch_list:
            kb.append([{"text": f"❌ حذف {ch}", "callback_data": f"adm_del_ch_{ch}"}])
        kb.append([{"text": "➕ افزودن کانال", "callback_data": "adm_add_channel"}])
        kb.append([{"text": "🔙 بازگشت", "callback_data": "adm_settings"}])
        await edit_message(chat_id, message_id, "مدیریت کانال‌های اجباری:", reply_markup={"inline_keyboard": kb})
        return

    if data == "adm_add_channel":
        await execute_db("UPDATE users SET state = 'waiting_for_new_channel' WHERE id = ?", user["id"])
        await edit_message(chat_id, message_id, "یوزرنیم کانال را بفرستید (در صورت تمایل عنوان را با خط عمودی جدا کنید، مثال: @TechNews|کانال اخبار):", reply_markup={"inline_keyboard": [[{"text": "🔙 بازگشت", "callback_data": "adm_settings"}]]})
        return

    if data.startswith("adm_del_ch_"):
        ch_to_del = data.replace("adm_del_ch_", "")
        channels_str = await get_setting("force_channels", "")
        ch_list = [c.strip() for c in channels_str.split(",") if c.strip()]
        if ch_to_del in ch_list:
            ch_list.remove(ch_to_del)
            await set_setting("force_channels", ",".join(ch_list))
            await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "✅ کانال حذف شد."})

            channels_str = await get_setting("force_channels", "")
            ch_list = [c.strip() for c in channels_str.split(",") if c.strip()]
            kb = []
            for ch in ch_list:
                kb.append([{"text": f"❌ حذف {ch}", "callback_data": f"adm_del_ch_{ch}"}])
            kb.append([{"text": "➕ افزودن کانال", "callback_data": "adm_add_channel"}])
            kb.append([{"text": "🔙 بازگشت", "callback_data": "adm_settings"}])
            await edit_message(chat_id, message_id, "مدیریت کانال‌های اجباری:", reply_markup={"inline_keyboard": kb})
        return

    if data == "adm_set_referral_reward":
        await execute_db("UPDATE users SET state = 'waiting_setting_referral_reward' WHERE id = ?", user["id"])
        await edit_message(chat_id, message_id, "✏️ لطفاً مقدار جدید پاداش دعوت را بفرستید:", reply_markup={"inline_keyboard": [[{"text": "🔙 بازگشت", "callback_data": "adm_settings"}]]})
        return

    if data == "adm_set_help":
        await execute_db("UPDATE users SET state = 'waiting_for_help_content' WHERE id = ?", user["id"])
        await edit_message(chat_id, message_id, "محتوای دکمه راهنما را ارسال کنید (پشتیبانی از متن، عکس، ویدیو و فایل):", reply_markup={"inline_keyboard": [[{"text": "🔙 بازگشت", "callback_data": "adm_settings"}]]})
        return

    if data == "adm_dyn_btn":
        markup = {
            "inline_keyboard": [
                [{"text": "✏️ عنوان دکمه در منو", "callback_data": "adm_dyn_title"}],
                [{"text": "✏️ محتوای دکمه (پیام اصلی)", "callback_data": "adm_dyn_content"}],
                [{"text": "🔙 بازگشت", "callback_data": "adm_settings"}]
            ]
        }
        await edit_message(chat_id, message_id, "تنظیمات دکمه داینامیک:", reply_markup=markup)
        return

    if data == "adm_dyn_title":
        await execute_db("UPDATE users SET state = 'waiting_dyn_title' WHERE id = ?", user["id"])
        await edit_message(chat_id, message_id, "لطفاً عنوانی که می‌خواهید برای دکمه در منوی کاربری نمایش داده شود را ارسال کنید:", reply_markup={"inline_keyboard": [[{"text": "🔙 بازگشت", "callback_data": "adm_dyn_btn"}]]})
        return

    if data == "adm_dyn_content":
        await execute_db("UPDATE users SET state = 'waiting_dyn_content' WHERE id = ?", user["id"])
        await edit_message(chat_id, message_id, "محتوای دکمه داینامیک را ارسال کنید (پشتیبانی کامل از عکس، متن، ویدیو و فایل):", reply_markup={"inline_keyboard": [[{"text": "🔙 بازگشت", "callback_data": "adm_dyn_btn"}]]})
        return

    if data.startswith("adm_manage_users_"):
        page = safe_int(data.replace("adm_manage_users_", ""), 1)
        limit = 5
        offset = (page - 1) * limit
        res = await query_db("SELECT * FROM users ORDER BY id DESC LIMIT ? OFFSET ?", limit, offset)
        users = get_rows(res)

        txt = f"👤 لیست کاربران (صفحه {page}):\n\n"
        for u in users:
            txt += f"🆔 <code>{u['telegram_id']}</code> | {u['username']} | {u['full_name']}\n"

        kb = [[{"text": "🔍 جستجوی کاربر", "callback_data": "adm_search_user"}]]
        nav = []
        if page > 1:
            nav.append({"text": "◀️ قبلی", "callback_data": f"adm_manage_users_{page-1}"})
        nav.append({"text": f"صفحه {page}", "callback_data": "ignore"})
        if len(users) == limit:
            nav.append({"text": "▶️ بعدی", "callback_data": f"adm_manage_users_{page+1}"})

        kb.append(nav)
        kb.append([{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "admin_return"}])

        await edit_message(chat_id, message_id, txt, reply_markup={"inline_keyboard": kb}, parse_mode="HTML")
        return

    if data == "adm_search_user":
        await execute_db("UPDATE users SET state = 'waiting_for_user_search' WHERE id = ?", user["id"])
        await edit_message(chat_id, message_id, "🔍 شناسه عددی تلگرام کاربر مورد نظر را بفرستید:", reply_markup={"inline_keyboard": [[{"text": "🔙 بازگشت", "callback_data": "adm_manage_users_1"}]]})
        return

    if data.startswith("adm_add_bal_") or data.startswith("adm_sub_bal_"):
        is_addition = "add" in data
        target_tg_id = data.replace("adm_add_bal_", "").replace("adm_sub_bal_", "")
        state_val = f"waiting_for_add_{target_tg_id}" if is_addition else f"waiting_for_sub_{target_tg_id}"
        await execute_db("UPDATE users SET state = ? WHERE id = ?", state_val, user["id"])
        action_text = "افزایش" if is_addition else "کاهش"
        await edit_message(chat_id, message_id, f"💵 میزان شارژ مایل به {action_text} (به تومان) را بفرستید:", reply_markup=get_back_markup(True))
        return

    if data == "adm_manage_plans":
        await show_plan_management(chat_id, message_id)
        return

    if data == "adm_add_plan":
        await execute_db("UPDATE users SET state = 'waiting_plan_name', plan_data = NULL WHERE id = ?", user["id"])
        await edit_message(chat_id, message_id, STRINGS["plan_add_step1"], reply_markup={"inline_keyboard": [[{"text": "🔙 بازگشت", "callback_data": "adm_manage_plans"}]]})
        return

    if data.startswith("adm_plan_toggle_"):
        plan_id = data.replace("adm_plan_toggle_", "")
        res = await query_db("SELECT is_active FROM plans WHERE id = ?", plan_id)
        plan = get_first_row(res)
        if plan:
            new_state = 0 if plan["is_active"] else 1
            await execute_db("UPDATE plans SET is_active = ? WHERE id = ?", new_state, plan_id)
            await show_plan_management(chat_id, message_id)
        return

    if data.startswith("adm_plan_del_"):
        plan_id = data.replace("adm_plan_del_", "")
        await execute_db("DELETE FROM plans WHERE id = ?", plan_id)
        await show_plan_management(chat_id, message_id)
        return

async def show_plan_management(chat_id, message_id=None):
    res = await query_db("SELECT * FROM plans ORDER BY id DESC")
    plans = get_rows(res)
    if not plans:
        if message_id:
            await edit_message(chat_id, message_id, STRINGS["no_plans"], reply_markup={"inline_keyboard": [[{"text": "➕ افزودن پلن جدید", "callback_data": "adm_add_plan"}], [{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "admin_return"}]]})
        else:
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["no_plans"], "reply_markup": {"inline_keyboard": [[{"text": "➕ افزودن پلن جدید", "callback_data": "adm_add_plan"}], [{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "admin_return"}]]}})
    else:
        txt = "📦 لیست پلن‌ها:\n\n"
        kb = []
        for p in plans:
            status = "فعال" if p["is_active"] else "غیرفعال"
            txt += STRINGS["plan_list_item"].format(name=p["name"], price=p["price"], duration=p["duration_days"], max_users=p["max_users"], status=status) + "\n\n"
            kb.append([{"text": f"تغییر وضعیت {p['name']}", "callback_data": f"adm_plan_toggle_{p['id']}"}])
            kb.append([{"text": f"❌ حذف {p['name']}", "callback_data": f"adm_plan_del_{p['id']}"}])

        kb.append([{"text": "➕ افزودن پلن جدید", "callback_data": "adm_add_plan"}])
        kb.append([{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "admin_return"}])

        if message_id:
            await edit_message(chat_id, message_id, txt, reply_markup={"inline_keyboard": kb})
        else:
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": txt, "reply_markup": {"inline_keyboard": kb}})

async def show_admin_panel(chat_id):
    await call_telegram("sendMessage", {
        "chat_id": chat_id,
        "text": STRINGS["admin_panel"],
        "reply_markup": get_admin_inline_keyboard()
    })

async def process_message(message):
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()
    from_user = message.get("from", {})
    telegram_id = str(from_user.get("id", ""))
    if not telegram_id:
        return

    referred_by = None
    if text.startswith("/start ") and len(text.split()) > 1:
        referred_by = text.split()[1]

    user = await get_or_create_user(telegram_id, referred_by, from_user=from_user)
    actual_is_admin = is_admin(telegram_id, user_data=None)
    is_admin_user = is_admin(telegram_id, user_data=user)

    if text.startswith("/start"):
        user["state"] = None
        user["plan_data"] = None
        await execute_db("UPDATE users SET state = NULL, plan_data = NULL WHERE id = ?", user["id"])

        await credit_referrer_if_pending(user, chat_id)
        if is_admin_user:
            await show_admin_panel(chat_id)
        else:
            markup = await get_user_inline_keyboard(actual_is_admin)
            await call_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": STRINGS["start_welcome"],
                "reply_markup": markup
            })
        return

    if text in ["/admin", "admin", "مدیریت"] and actual_is_admin:
        await execute_db("UPDATE users SET state = NULL, plan_data = NULL, is_test_mode = 0 WHERE id = ?", user["id"])
        await show_admin_panel(chat_id)
        return

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

    if not await check_channel_membership(telegram_id, force_refresh=False):
        await send_membership_requirement(chat_id)
        return

    state = user.get("state")
    if state:
        if await handle_state(user, state, message, chat_id, is_admin_user, actual_is_admin):
            return

    if text.startswith("/"):
        markup = get_admin_inline_keyboard() if is_admin_user else await get_user_inline_keyboard(actual_is_admin)
        await call_telegram("sendMessage", {
            "chat_id": chat_id,
            "text": "❌ دستور ناشناس است. لطفاً از دکمه‌های منوی اصلی استفاده کنید.",
            "reply_markup": markup
        })
    else:
        markup = get_admin_inline_keyboard() if is_admin_user else await get_user_inline_keyboard(actual_is_admin)
        await call_telegram("sendMessage", {
            "chat_id": chat_id,
            "text": "❌ دستور ناشناس است. لطفاً از دکمه‌های منوی اصلی استفاده کنید.",
            "reply_markup": markup
        })

async def process_update(update):
    try:
        if "message" in update:
            await process_message(update["message"])
        elif "callback_query" in update:
            await process_callback(update["callback_query"])
    except Exception:
        logger.error("Error in process_update:")
        traceback.print_exc()

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    global http_client
    http_client = httpx.AsyncClient(limits=httpx.Limits(max_keepalive_connections=50, max_connections=100))
    await init_database_if_needed()
    asyncio.create_task(background_config_checker())
    asyncio.create_task(background_expiration_notifier())
    asyncio.create_task(background_clean_expired_subs())
    logger.info("🚀 Bot Server Started! (CAT Enhanced v3)")

@app.on_event("shutdown")
async def shutdown_event():
    global http_client
    if http_client:
        await http_client.aclose()

@app.post("/webhook")
async def handle_webhook(request: Request):
    update = await request.json()
    asyncio.create_task(process_update(update))
    return Response(content="OK", status_code=200)

# =====================================================================
# 🔥 سرویس ساب‌لینک – کش شامل بنر + کانفیگ‌ها
# =====================================================================
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

    now = datetime.datetime.utcnow()
    if expires_at < now:
        await execute_db("UPDATE subscriptions SET status = 'expired' WHERE id = ?", sub["id"])
        return Response(content="", media_type="text/plain")

    days_left = (expires_at - now).days
    days_left_str = f"{days_left}روز" if days_left >= 0 else "منقضی"
    plan_id = sub.get("plan_id")
    if plan_id:
        plan_res = await query_db("SELECT duration_days, max_users FROM plans WHERE id = ?", plan_id)
        plan = get_first_row(plan_res)
        if plan:
            duration = plan.get("duration_days", 0)
            max_users = plan.get("max_users", 1)
            plan_title = f"⏳{days_left_str}👥{max_users}کاربره♾️نامحدود📆{duration}روزه"
        else:
            plan_title = f"⏳{days_left_str}نامشخص"
    else:
        plan_title = f"⏳{days_left_str}👤۱کاربره♾️نامحدود🎁تست۱روزه"

    cache_key = "configs_payload"
    cached_payload = await get_kv(cache_key)
    if cached_payload is None:
        cfg_res = await query_db("SELECT config_text FROM configs WHERE is_active = 1 ORDER BY id ASC")
        confs = get_rows(cfg_res)
        payload_lines = [c["config_text"].strip() for c in confs if c["config_text"].strip()]
        combined = "\n".join(payload_lines)
        cached_payload = base64.b64encode(combined.encode('utf-8')).decode('utf-8')
        await put_kv(cache_key, cached_payload, expiration_ttl=300)

    # =============================================================
    # 🚨 این دو خط اصلی‌ترین جاهایی هستن که باید درست باشن
    # =============================================================
    title_b64 = base64.b64encode(plan_title.encode('utf-8')).decode('utf-8')
    safe_title = urllib.parse.quote(plan_title)

    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "profile-title": f"base64:{title_b64}",
        "profile-update-interval": "12",
        "Subscription-Userinfo": f"upload=0; download=0; total=53687091200; expire={int(expires_at.timestamp())}",
        "Content-Disposition": f"attachment; filename*=UTF-8''{safe_title}; filename=\"{safe_title}\""
    }

    return Response(content=cached_payload, media_type="text/plain", headers=headers)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)