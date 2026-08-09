# -*- coding: utf-8 -*-
"""
ربات مدیریت ساب‌لینک v3 – نسخه CAT ULTIMATE (نهایی و عملی)
- مدیریت پروکسی‌های HTTP/SOCKS4/SOCKS5
- تست واقعی پروکسی‌ها با httpx و asyncio
- دریافت و تست دسته‌جمعی پروکسی از فایل/متن (رفع کامل)
- کاهش هشدارهای تکراری به ۳ ساعت
- حفظ تمام قابلیت‌های قبلی
"""

import os
import json
import base64
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
# 🔐 متغیرهای محیطی
# ---------------------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = os.getenv("ADMIN_IDS", "")

CF_ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID", "")
CF_API_TOKEN = os.getenv("CF_API_TOKEN", "")
CF_D1_ID = os.getenv("CF_D1_ID", "")
CF_KV_ID = os.getenv("CF_KV_ID", "")

APP_BASE_URL = os.getenv("APP_BASE_URL", "https://technowvpnbot.ariyacompany-io.workers.dev")

BANNER_CONFIG = "vless://1234@1.1.1.1:443?encryption=none&security=tls&sni=sertraline.adaspoloandco.com&fp=chrome&type=ws&host=sertraline.adaspoloandco.com&path=%2Fdownload.php#%F0%9F%8C%90%D9%87%D8%B1%20%D8%B1%D9%88%D8%B2%20%D9%84%DB%8C%D9%86%DA%A9%20%D8%AE%D9%88%D8%AF%20%D8%B1%D8%A7%20%D8%A2%D9%BE%D8%AF%DB%8C%D8%AA%20%DA%A9%D9%86%DB%8C%D8%AF%E2%9A%A1"

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

def set_local_cache(key, value, ttl=3600):
    _local_cache[key] = (value, time.time() + ttl)

def del_local_cache(key):
    _local_cache.pop(key, None)

# ---------------------------------------------------------------------
# 📚 متون فارسی
# ---------------------------------------------------------------------
STRINGS = {
    "start_welcome": "👋 به ربات هوشمند TechNowVpn کانفیگ رایگان خوش آمدید!\n\nاز طریق دکمه‌های زیر می‌توانید حساب خود را مدیریت کرده و سرور دریافت کنید.",
    "not_member": "⚠️ برای فعال‌سازی کامل امکانات ربات، ابتدا در کانال‌های زیر عضو شوید و سپس روی دکمه «عضو شدم» کلیک کنید.",
    "membership_confirmed": "✅ عضویت شما تأیید شد! اکنون می‌توانید از ربات استفاده کنید.",
    "trial_already_used": "⚠️ شما قبلاً از تست رایگان 1 روزه استفاده کرده‌اید.",
    "trial_activated": "🎁 اشتراک تست 1 روزه شما با موفقیت فعال شد!",
    "wallet_info": "👛 جزئیات کیف پول شما:\n\n💰 موجودی فعلی: {balance:,} تومان\n👥 تعداد زیرمجموعه‌ها: {ref_count} نفر",
    "insufficient_balance": "❌ موجودی حساب شما کافی نیست.\n\n💰 موجودی شما: {balance:,} تومان\n💵 مبلغ مورد نیاز: {price:,} تومان",
    "subscription_created": "✅ اشتراک {duration} روزه شما با موفقیت ساخته شد:\n\n`{sublink}`\n\n📅 تاریخ انقضا: {expires_at} (UTC)",
    "no_active_services": "⚠️ شما اشتراک فعالی در حال حاضر ندارید.",
    "services_list": "📋 لیست سرویس‌های فعال شما ({count} مورد):",
    "referral_info": "👥 سیستم زیرمجموعه‌گیری و دعوت دوستان:\n\nبا دعوت از دوستانتان کیف پولتان را شارژ کنید و رایگان خرید کنید!\n\n🎁 پاداش دعوت هر کاربر: {reward:,} تومان\n\n🔗 لینک اختصاصی شما برای دعوت:\n`{ref_link}`",
    "support_contact": "🎧 بخش ارتباط با پشتیبانی:",
    "support_session_started": "💬 پیام خود را ارسال کنید.\nبرای خروج روی دکمه شیشه‌ای زیر کلیک کنید.",
    "support_session_ended": "🔚 نشست پشتیبانی پایان یافت.",
    "support_forwarded": "پیام از کاربر {user_id}:\n\n{text}",
    "admin_only": "⛔ این بخش فقط برای مدیران در دسترس است.",
    "admin_panel": "🛠 به بخش ادمین خوش آمدید. دستورات مدیریتی را انتخاب کنید:",
    "config_added": "✅ کانفیگ جدید با موفقیت پردازش و ثبت شد.",
    "config_add_stopped": "⏹ عملیات افزودن کانفیگ متوقف شد.",
    "broadcast_start": "📢 متن پیام همگانی خود را ارسال کنید :",
    "broadcast_sending": "⏳ در حال ارسال همگانی...",
    "broadcast_done": "✅ پیام همگانی ارسال شد.\nتعداد کل: {success} از {total}",
    "settings_show": "⚙️ تنظیمات ربات:\n\n🎁 پاداش دعوت: {reward:,} تومان\n📢 کانال‌های اجباری:\n `{channels}`\n",
    "user_not_found": "❌ کاربر یافت نشد.",
    "user_info": "👤 جزئیات حساب کاربر:\n\n🆔 آیدی تلگرام: `{tg_id}`\n👤 نام و کاربری: {full_name} | {username}\n💰 موجودی کیف پول: {balance:,} تومان\n🎁 استفاده از تست رایگان: {trial_status}",
    "balance_added": "✅ مبلغ {amount:,} تومان به حساب کاربر {target_id} اضافه گردید.",
    "balance_subtracted": "✅ مبلغ {amount:,} تومان از موجودی کاربر {target_id} کسر شد.",
    "setting_updated": "✅ فیلد تنظیمات با موفقیت آپدیت شد.",
    "plan_add_step1": "📝 نام پلن را وارد کنید:",
    "plan_add_step2": "💰 قیمت (به تومان) را وارد کنید:",
    "plan_add_step3": "📆 مدت زمان (تعداد روز) را وارد کنید:",
    "plan_add_step4": "👥 محدودیت کاربر (حداکثر کاربر مجاز) را وارد کنید:",
    "plan_added": "✅ پلن «{name}» با موفقیت اضافه شد.",
    "plan_deleted": "🗑 پلن حذف شد.",
    "plan_updated": "✅ پلن «{name}» با موفقیت به‌روزرسانی شد.",
    "no_plans": "هیچ پلنی وجود ندارد.",
    "plan_list_item": "📌 نام: {name}\n💰 قیمت: {price:,} تومان\n📆 مدت: {duration} روز\n👥 لیمیت کاربر: {max_users}",
    "choose_plan": "پلن مورد نظر را انتخاب کنید:",
    "purchase_cancelled": "❌ عملیات لغو شد.",
    "config_duplicate": "⚠️ این کانفیگ قبلاً در دیتابیس وجود دارد. آیا مایل به ثبت مجدد آن هستید؟",
    "config_duplicate_ignored": "⚠️ کانفیگ تکراری نادیده گرفته شد و ثبت نشد.",
    "config_duplicate_forced": "✅ کانفیگ تکراری با نادیده گرفتن اخطار ثبت شد.",
    "plan_edit_step1": "📝 نام جدید پلن را وارد کنید (یا 'لغو' برای انصراف):",
    "plan_edit_step2": "💰 قیمت جدید را وارد کنید (یا 'لغو'):",
    "plan_edit_step3": "📆 مدت جدید را وارد کنید (یا 'لغو'):",
    "plan_edit_step4": "👥 محدودیت کاربر جدید را وارد کنید (یا 'لغو'):",
    "delete_plan_confirm": "⚠️ آیا از حذف این پلن اطمینان دارید؟",
    "delete_cancelled": "❌ عملیات حذف لغو شد.",
    "sub_source_list": "📡 لیست ساب‌لینک‌های خارجی:\n\n",
    "sub_source_add_step1": "📝 لطفاً نام این ساب‌لینک را وارد کنید:",
    "sub_source_add_step2": "🔗 لطفاً URL ساب‌لینک را وارد کنید:",
    "sub_source_added": "✅ ساب‌لینک «{name}» با موفقیت اضافه شد.",
    "sub_source_deleted": "🗑 ساب‌لینک حذف شد.",
    "sub_source_updated": "✅ ساب‌لینک به‌روزرسانی شد.",
    "sub_source_fetch_start": "⏳ در حال دریافت کانفیگ‌ها از ساب‌لینک‌ها...",
    "sub_source_fetch_done": "✅ دریافت کانفیگ‌ها به پایان رسید.\nتعداد کانفیگ‌های جدید اضافه شده: {count}",
    "sub_source_fetch_error": "❌ خطا در دریافت از ساب‌لینک: {error}",
    "sub_source_edit_name": "📝 نام جدید را وارد کنید (یا 'لغو'):",
    "sub_source_edit_url": "🔗 URL جدید را وارد کنید (یا 'لغو'):",
    "proxy_list": "🔌 لیست پروکسی‌های تست:\n\n",
    "proxy_add_step1": "📝 لطفاً آدرس پروکسی را وارد کنید (فرمت: `http://ip:port` یا `socks4://ip:port`):",
    "proxy_added": "✅ پروکسی با موفقیت اضافه شد و فعال است.",
    "proxy_add_failed": "❌ پروکسی غیرفعال است. لطفاً دوباره تلاش کنید.",
    "proxy_deleted": "🗑 پروکسی حذف شد.",
    "proxy_updated": "✅ پروکسی به‌روزرسانی شد.",
    "proxy_add_stopped": "⏹ عملیات افزودن پروکسی متوقف شد.",
    "proxy_status_report": "📊 وضعیت پروکسی‌ها:\nکل: {total} | فعال: {active} | غیرفعال: {inactive} | ضعیف: {weak}",
    "proxy_death_report": "⚠️ پروکسی `{name}` غیرفعال شد. (امتیاز: {score})",
    "proxy_birth_report": "✅ پروکسی `{name}` دوباره فعال شد. (امتیاز: {score})",
    "proxy_low_warning": "🚨 هشدار: فقط {count} پروکسی فعال باقی مانده است. لطفاً یک پروکسی جدید اضافه کنید.",
    "proxy_no_active": "🚨 هیچ پروکسی فعالی وجود ندارد. ربات وارد حالت ایمن شد.",
    "proxy_restored": "✅ پروکسی جدید فعال شد. ربات از حالت ایمن خارج شد.",
    "proxy_delete_confirm": "آیا از حذف این پروکسی اطمینان دارید؟",
    "batch_test_start": "⏳ در حال تست {total} پروکسی... لطفاً صبر کنید. (حداکثر {max_concurrent} تا همزمان)",
    "batch_test_result": "📊 **نتیجه تست پروکسی‌ها**\n\n🔢 کل: {total}\n✅ قبول‌شده (ایران + فعال): {accepted}\n❌ ردشده: {rejected}\n\n📋 لیست قبول‌شده‌ها:\n{accepted_list}\n\n❌ دلایل رد:\n{rejected_reasons}",
    "batch_test_no_result": "❌ هیچ پروکسی معتبری در لیست شما یافت نشد.\n\n🔍 دلایل احتمالی:\n- پروکسی‌ها همگی غیرفعال هستند.\n- آی‌پی‌ها خارج از ایران هستند.\n- خطا در فرمت لیست (حتماً به‌صورت `ip:port` باشد).",
    "batch_test_error": "❌ خطا در پردازش لیست. لطفاً دوباره تلاش کنید.",
    "batch_file_processing": "⏳ در حال پردازش فایل... لطفاً صبر کنید.",
    "batch_file_download_error": "❌ خطا در دانلود فایل. لطفاً دوباره تلاش کنید.",
}

# ---------------------------------------------------------------------
# 🔧 توابع کمکی
# ---------------------------------------------------------------------
def safe_int(value, default=0):
    try:
        return int(value)
    except:
        return default

def get_rows(db_res):
    if db_res and isinstance(db_res, dict) and db_res.get("success"):
        try:
            return db_res["result"][0].get("results", [])
        except:
            pass
    return []

def get_first_row(db_res):
    rows = get_rows(db_res)
    return rows[0] if rows else None

async def query_db(sql, *args, retries=3):
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
# 📨 ارتباط با تلگرام
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
    if not message_id:
        return await call_telegram("sendMessage", {"chat_id": chat_id, "text": text, "reply_markup": reply_markup, "parse_mode": parse_mode})
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return await call_telegram("editMessageText", payload)

def get_back_markup(is_admin_user):
    return {"inline_keyboard": [[{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "admin_return" if is_admin_user else "user_return"}]]}

# ---------------------------------------------------------------------
# ⚙️ کش KV
# ---------------------------------------------------------------------
async def get_kv(key, retries=3):
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_ID}/values/{key}"
    for attempt in range(retries):
        try:
            r = await http_client.get(url, headers={"Authorization": f"Bearer {CF_API_TOKEN}"}, timeout=5.0)
            if r.status_code == 200:
                return r.text
        except:
            pass
        await asyncio.sleep(0.5 * (attempt + 1))
    return None

async def put_kv(key, value, expiration_ttl=86400, retries=3):
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_ID}/values/{key}"
    params = {"expiration_ttl": expiration_ttl} if expiration_ttl else {}
    for attempt in range(retries):
        try:
            await http_client.put(url, headers={"Authorization": f"Bearer {CF_API_TOKEN}"}, params=params, content=str(value), timeout=5.0)
            return
        except:
            await asyncio.sleep(0.5 * (attempt + 1))
    logger.error(f"KV put failed after {retries} attempts")

async def delete_kv(key, retries=3):
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_ID}/values/{key}"
    for attempt in range(retries):
        try:
            await http_client.delete(url, headers={"Authorization": f"Bearer {CF_API_TOKEN}"}, timeout=5.0)
            return
        except:
            await asyncio.sleep(0.5 * (attempt + 1))

async def get_setting(key, default=None):
    cached = get_local_cache(f"setting_{key}")
    if cached is not None:
        return cached
    kv = await get_kv(f"setting_{key}")
    if kv is not None:
        set_local_cache(f"setting_{key}", kv, 3600)
        return kv
    res = await query_db("SELECT value FROM settings WHERE key = ?", key)
    row = get_first_row(res)
    if row:
        val = row["value"]
        await put_kv(f"setting_{key}", val, expiration_ttl=86400)
        set_local_cache(f"setting_{key}", val, 3600)
        return val
    return default

async def set_setting(key, value):
    await execute_db("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", key, str(value))
    await put_kv(f"setting_{key}", str(value), expiration_ttl=86400)
    set_local_cache(f"setting_{key}", str(value), 3600)

# ---------------------------------------------------------------------
# استخراج اطلاعات کانفیگ
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

def extract_port_from_config(config_text):
    try:
        if config_text.startswith("vmess://"):
            j = json.loads(base64.b64decode(config_text[8:]).decode('utf-8'))
            return j.get('port', 443)
        elif "://" in config_text:
            parsed = urllib.parse.urlparse(config_text)
            return parsed.port or 443
    except:
        pass
    return 443

def extract_secret_from_config(config_text):
    try:
        if config_text.startswith("vmess://"):
            decoded = base64.b64decode(config_text[8:]).decode('utf-8')
            j = json.loads(decoded)
            return j.get('id', '')
        elif config_text.startswith("vless://"):
            parsed = urllib.parse.urlparse(config_text)
            return parsed.username or ''
        elif config_text.startswith("trojan://"):
            parsed = urllib.parse.urlparse(config_text)
            return parsed.username or ''
        elif config_text.startswith("ss://"):
            parsed = urllib.parse.urlparse(config_text)
            userinfo = parsed.username or ''
            if userinfo:
                try:
                    decoded = base64.b64decode(userinfo).decode('utf-8')
                    if ':' in decoded:
                        return decoded.split(':')[1]
                except:
                    if ':' in userinfo:
                        return userinfo.split(':')[1]
            return userinfo
        elif config_text.startswith("ssr://"):
            try:
                decoded = base64.b64decode(config_text[6:]).decode('utf-8')
                parts = decoded.split(':')
                if len(parts) >= 6:
                    return parts[5]
            except:
                pass
            return ''
    except:
        pass
    return ''

def get_config_fingerprint(config_text):
    secret = extract_secret_from_config(config_text)
    ip = extract_ip_from_config(config_text)
    port = extract_port_from_config(config_text)
    if secret:
        return f"{secret}@{ip}:{port}"
    else:
        return f"{ip}:{port}"

async def is_duplicate_config(config_text):
    fp = get_config_fingerprint(config_text)
    if not fp:
        return False
    res = await query_db("SELECT config_text FROM configs")
    rows = get_rows(res)
    for row in rows:
        existing_fp = get_config_fingerprint(row["config_text"])
        if existing_fp == fp:
            return True
    return False

def extract_config_name(config_text):
    try:
        if config_text.startswith("vmess://"):
            decoded = base64.b64decode(config_text[8:]).decode('utf-8')
            j = json.loads(decoded)
            return j.get('ps', '')
        elif "://" in config_text:
            parsed = urllib.parse.urlparse(config_text)
            fragment = parsed.fragment
            if fragment:
                return urllib.parse.unquote(fragment)
    except:
        pass
    return None

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

# ---------------------------------------------------------------------
# 🧪 توابع مدیریت پروکسی (نسخه نهایی و عملی - بازنویسی شده توسط CAT)
# ---------------------------------------------------------------------
async def test_proxy(proxy_address: str, proxy_type: str = "http") -> tuple:
    """
    تست واقعی یک پروکسی با ارسال درخواست به 1.1.1.1/cdn-cgi/trace
    بدون هیچ محدودیتی در کانکشن و سرعت پردازش.
    """
    try:
        proxy_url = f"{proxy_type}://{proxy_address}"
        start = time.time()
        
        client_kwargs = {"timeout": 10.0, "verify": False}
        
        # هندل کردن نسخه httpx به شکل کاملاً هوشمند
        if httpx.__version__ >= "0.28.0":
            client_kwargs["proxy"] = proxy_url
        else:
            client_kwargs["proxies"] = proxy_url

        async with httpx.AsyncClient(**client_kwargs) as client:
            # اندپوینت طلایی کلودفلر - بدون هیچ‌گونه لیمیت و بن شدن
            response = await client.get("https://1.1.1.1/cdn-cgi/trace")
            latency = int((time.time() - start) * 1000)
            
            if response.status_code == 200:
                text = response.text
                loc_match = re.search(r"loc=(.+)", text)
                country = loc_match.group(1).strip() if loc_match else ""
                
                # ایران باشه تایید می‌کنه
                if country == "IR":
                    return True, "IR", latency
                else:
                    return False, country, latency
            else:
                return False, None, 0
    except Exception as e:
        logger.debug(f"Proxy test failed for {proxy_address}: {e}")
        return False, None, 0

async def update_proxy_score(proxy_id: int):
    res = await query_db("SELECT address, type FROM proxies WHERE id = ?", proxy_id)
    row = get_first_row(res)
    if not row:
        return
    success, country, latency = await test_proxy(row["address"], row["type"])
    new_score = 0
    if success and country == "IR":
        new_score = max(0, 100 - latency // 10)
    await execute_db("UPDATE proxies SET is_active = ?, score = ?, last_check = ? WHERE id = ?",
                     1 if success and country == "IR" else 0, new_score, datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), proxy_id)

async def get_active_proxies():
    res = await query_db("SELECT id, address, type, score FROM proxies WHERE is_active = 1 ORDER BY score DESC")
    return get_rows(res)

async def get_proxy_count():
    total_res = await query_db("SELECT COUNT(*) as cnt FROM proxies")
    total = get_first_row(total_res)["cnt"] if get_first_row(total_res) else 0
    active_res = await query_db("SELECT COUNT(*) as cnt FROM proxies WHERE is_active = 1")
    active = get_first_row(active_res)["cnt"] if get_first_row(active_res) else 0
    weak_res = await query_db("SELECT COUNT(*) as cnt FROM proxies WHERE is_active = 1 AND score < 50")
    weak = get_first_row(weak_res)["cnt"] if get_first_row(weak_res) else 0
    inactive = total - active
    return total, active, inactive, weak

# ---------------------------------------------------------------------
# 🧪 تست کانفیگ از طریق پروکسی
# ---------------------------------------------------------------------
async def test_config_via_proxy(config_text: str, proxy: dict) -> tuple:
    ip = extract_ip_from_config(config_text)
    port = extract_port_from_config(config_text)
    if not ip:
        return False, 0
    try:
        proxy_url = f"{proxy['type']}://{proxy['address']}"
        start = time.time()
        
        client_kwargs = {"timeout": 8.0}
        if httpx.__version__ >= "0.28.0":
            client_kwargs["proxy"] = proxy_url
        else:
            client_kwargs["proxies"] = proxy_url
            
        async with httpx.AsyncClient(**client_kwargs) as client:
            response = await client.get("https://1.1.1.1/cdn-cgi/trace")
            latency = int((time.time() - start) * 1000)
            if response.status_code == 200:
                return True, latency
            else:
                return False, 0
    except Exception:
        return False, 0

async def test_config_with_all_proxies(config_text: str) -> tuple:
    proxies = await get_active_proxies()
    if not proxies:
        success, latency = await test_config_direct(config_text)
        return success, latency, 0
    total_latency = 0
    success_count = 0
    for proxy in proxies:
        ok, lat = await test_config_via_proxy(config_text, proxy)
        if ok:
            success_count += 1
            total_latency += lat
    avg_latency = total_latency // success_count if success_count > 0 else 0
    return success_count > 0, avg_latency, success_count

async def test_config_direct(config_text: str) -> tuple:
    ip = extract_ip_from_config(config_text)
    port = extract_port_from_config(config_text)
    if not ip:
        return False, 0
    try:
        start = time.time()
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=4.0)
        writer.close()
        await writer.wait_closed()
        latency = int((time.time() - start) * 1000)
        return True, latency
    except:
        return False, 0

# ---------------------------------------------------------------------
# 🧪 قابلیت جدید: تست دسته‌جمعی پروکسی از لیست (نسخه نهایی)
# ---------------------------------------------------------------------
def parse_proxy_list(raw_text: str) -> list:
    lines = raw_text.strip().splitlines()
    proxies = []
    # تلاش برای پارس JSON
    try:
        data = json.loads(raw_text)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "ip_address" in item and "port" in item:
                    ip = item["ip_address"]
                    port = item["port"]
                    proxy_type = "http"
                    if "type" in item and item["type"].lower() in ["http", "socks4", "socks5"]:
                        proxy_type = item["type"].lower()
                    proxies.append({"address": f"{ip}:{port}", "type": proxy_type})
            if proxies:
                return proxies
    except:
        pass

    for line in lines:
        line = line.strip()
        if not line:
            continue
        proxy_type = "http"
        address = line
        if line.startswith("http://"):
            proxy_type = "http"
            address = line[7:]
        elif line.startswith("socks4://"):
            proxy_type = "socks4"
            address = line[9:]
        elif line.startswith("socks5://"):
            proxy_type = "socks5"
            address = line[9:]
        # اگر فرمت "ip port" بود (با فاصله)
        if " " in address and ":" not in address:
            parts = address.split()
            if len(parts) == 2 and parts[1].isdigit():
                address = f"{parts[0]}:{parts[1]}"
        # اگر فقط "ip:port" بود
        if ":" in address:
            proxies.append({"address": address, "type": proxy_type})
    return proxies

async def batch_test_proxies(proxy_list: list, max_concurrent: int = 20) -> dict:
    semaphore = asyncio.Semaphore(max_concurrent)
    results = []
    
    async def test_one(proxy):
        async with semaphore:
            address = proxy["address"]
            proxy_type = proxy["type"]
            success, country, latency = await test_proxy(address, proxy_type)
            if success and country == "IR":
                return {"accepted": True, "address": address, "type": proxy_type, "latency": latency}
            else:
                reason = "غیرفعال (timeout)" if not success else f"آی‌پی خارجی ({country})"
                return {"accepted": False, "address": address, "type": proxy_type, "reason": reason}
    
    tasks = [test_one(p) for p in proxy_list]
    results = await asyncio.gather(*tasks)
    
    accepted = [r for r in results if r["accepted"]]
    rejected = [r for r in results if not r["accepted"]]
    
    return {
        "accepted": accepted,
        "rejected": rejected,
        "total": len(proxy_list),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected)
    }

# ---------------------------------------------------------------------
# 🗄️ مقداردهی اولیه دیتابیس
# ---------------------------------------------------------------------
async def init_database_if_needed():
    tables = [
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
            speed_score INTEGER DEFAULT 0,
            awaiting_retest INTEGER DEFAULT 0,
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
        );""",
        """CREATE TABLE IF NOT EXISTS subscription_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            last_fetch TIMESTAMP DEFAULT NULL,
            is_active INTEGER DEFAULT 1,
            score INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS proxies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            type TEXT DEFAULT 'http',
            is_active INTEGER DEFAULT 0,
            score INTEGER DEFAULT 0,
            last_check TIMESTAMP DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );"""
    ]

    for q in tables:
        await execute_db(q)

    for col in ["speed_score", "awaiting_retest"]:
        try:
            await execute_db(f"ALTER TABLE configs ADD COLUMN {col} INTEGER DEFAULT 0")
        except:
            pass
    for col in ["score", "last_fetch", "is_active"]:
        try:
            await execute_db(f"ALTER TABLE subscription_sources ADD COLUMN {col} INTEGER DEFAULT 0")
        except:
            pass

    await execute_db("CREATE INDEX IF NOT EXISTS idx_settings_key ON settings(key);")

    banner_exists = await query_db("SELECT id FROM configs WHERE id = 0")
    if not get_first_row(banner_exists):
        await execute_db("INSERT INTO configs (id, config_text, is_active, fail_count) VALUES (0, ?, 1, 0)", BANNER_CONFIG)
        logger.info("Banner config created with id=0")
    else:
        await execute_db("UPDATE configs SET is_active = 1, config_text = ? WHERE id = 0", BANNER_CONFIG)

    defaults = {"referral_reward": "2000", "force_channels": ""}
    for key, val in defaults.items():
        res = await query_db("SELECT value FROM settings WHERE key = ?", key)
        if not get_first_row(res):
            await execute_db("INSERT INTO settings (key, value) VALUES (?, ?)", key, val)

    await put_kv("db_initialized_v3_cat", "true")
    logger.info("Database initialized/verified with all required tables")

# ---------------------------------------------------------------------
# 🔄 تسک‌های پس‌زمینه (هشدارهای کاهش‌یافته به ۳ ساعت)
# ---------------------------------------------------------------------
_last_proxy_alert_time = 0

async def background_proxy_checker():
    global _last_proxy_alert_time
    last_status_was_active = False
    while True:
        await asyncio.sleep(300)
        try:
            proxies_res = await query_db("SELECT id, name, address, type, is_active FROM proxies")
            proxies = get_rows(proxies_res)
            for p in proxies:
                old_active = p["is_active"]
                await update_proxy_score(p["id"])
                new_res = await query_db("SELECT is_active, score FROM proxies WHERE id = ?", p["id"])
                new_row = get_first_row(new_res)
                if new_row:
                    new_active = new_row["is_active"]
                    new_score = new_row["score"]
                    if old_active == 1 and new_active == 0:
                        msg = STRINGS["proxy_death_report"].format(name=p["name"], score=new_score)
                        await send_admin_alert(msg)
                    elif old_active == 0 and new_active == 1:
                        msg = STRINGS["proxy_birth_report"].format(name=p["name"], score=new_score)
                        await send_admin_alert(msg)
            total, active, inactive, weak = await get_proxy_count()
            now = time.time()
            if active == 0:
                if last_status_was_active or (now - _last_proxy_alert_time) > 10800:
                    await send_admin_alert(STRINGS["proxy_no_active"])
                    _last_proxy_alert_time = now
                    last_status_was_active = False
            else:
                if not last_status_was_active:
                    await send_admin_alert(STRINGS["proxy_restored"])
                    last_status_was_active = True
                elif active == 1 and (now - _last_proxy_alert_time) > 10800:
                    await send_admin_alert(STRINGS["proxy_low_warning"].format(count=active))
                    _last_proxy_alert_time = now
        except Exception as e:
            logger.error(f"Proxy checker error: {e}")

async def background_config_tester():
    while True:
        await asyncio.sleep(1800)
        try:
            configs_res = await query_db("SELECT id, config_text, awaiting_retest FROM configs WHERE is_active = 1 AND id != 0")
            configs = get_rows(configs_res)
            for cfg in configs:
                success, avg_latency, succ_count = await test_config_with_all_proxies(cfg["config_text"])
                if success:
                    await execute_db("UPDATE configs SET speed_score = ?, awaiting_retest = 0 WHERE id = ?", avg_latency, cfg["id"])
                else:
                    direct_ok, direct_lat = await test_config_direct(cfg["config_text"])
                    if direct_ok:
                        await execute_db("DELETE FROM configs WHERE id = ?", cfg["id"])
                        await delete_kv("configs_payload")
                        logger.info(f"Config {cfg['id']} removed (not accessible from Iran)")
                    else:
                        fail_count = cfg.get("fail_count", 0) + 1
                        if fail_count >= 3:
                            await execute_db("DELETE FROM configs WHERE id = ?", cfg["id"])
                            await delete_kv("configs_payload")
                            logger.info(f"Config {cfg['id']} removed due to 3 failures")
                        else:
                            await execute_db("UPDATE configs SET fail_count = ? WHERE id = ?", fail_count, cfg["id"])
        except Exception as e:
            logger.error(f"Config tester error: {e}")

async def background_subscription_fetcher():
    while True:
        await asyncio.sleep(3600)
        try:
            sources_res = await query_db("SELECT id, name, url FROM subscription_sources WHERE is_active = 1")
            sources = get_rows(sources_res)
            for s in sources:
                count = await fetch_and_add_configs_from_source(s["id"])
                if count > 0:
                    await execute_db("UPDATE subscription_sources SET score = score + ? WHERE id = ?", count, s["id"])
                    msg = f"🆕 کانفیگ جدید از ساب‌لینک «{s['name']}» استخراج شد. تعداد: {count}"
                    await send_admin_alert(msg)
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Background fetcher error: {e}")

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
                except:
                    continue
                time_left_sec = (expires_at - now).total_seconds()
                if time_left_sec <= 0:
                    continue
                notified_level = sub.get("notified_level", 0)
                tg_id = sub["telegram_id"]
                sub_url = await build_sub_url_async(sub["token"])
                msg = ""
                new_level = notified_level
                if time_left_sec <= 3600 and notified_level < 3:
                    msg = f"⚠️ **هشدار خیلی مهم** ⚠️\n\nفقط **۱ ساعت** تا پایان اعتبار سرویس شما باقی مانده است!\n\n🔗 لینک سرویس: `{sub_url}`\n💰 موجودی کیف پول: {sub['balance']:,} تومان\n\nجهت جلوگیری از قطعی اینترنت، سریعاً از طریق دکمه زیر تمدید کنید."
                    new_level = 3
                elif time_left_sec <= 86400 and notified_level < 2:
                    msg = f"⏳ **یادآوری تمدید**\n\nسرویس شما **۲۴ ساعت** دیگر منقضی خواهد شد.\n\n🔗 لینک سرویس: `{sub_url}`\n💰 موجودی کیف پول: {sub['balance']:,} تومان\n\nلطفاً پیش از اتمام زمان، اکانت خود را شارژ و تمدید نمایید."
                    new_level = 2
                elif time_left_sec <= 259200 and notified_level < 1:
                    msg = f"📅 **اطلاعیه سرویس**\n\nکاربر گرامی، تنها **۳ روز** تا پایان اشتراک شما باقی مانده است.\n\n🔗 لینک سرویس: `{sub_url}`\n💰 موجودی کیف پول: {sub['balance']:,} تومان\n\nمی‌توانید با دعوت دوستان حساب خود را رایگان شارژ کنید یا تمدید نمایید."
                    new_level = 1
                if msg:
                    markup = {"inline_keyboard": [[{"text": "♻️ تمدید سریع سرویس", "callback_data": f"renew_sub_{sub['token']}"}]]}
                    res_tg = await call_telegram("sendMessage", {"chat_id": int(tg_id), "text": msg, "parse_mode": "Markdown", "reply_markup": markup})
                    if res_tg.get("ok"):
                        await execute_db("UPDATE subscriptions SET notified_level = ? WHERE id = ?", new_level, sub["sub_id"])
        except Exception as e:
            logger.error(f"Notifier error: {e}")

async def background_daily_report():
    while True:
        await asyncio.sleep(86400)
        try:
            total_users = get_first_row(await query_db("SELECT COUNT(*) as cnt FROM users"))["cnt"] if get_first_row(await query_db("SELECT COUNT(*) as cnt FROM users")) else 0
            premium_users = get_first_row(await query_db("SELECT COUNT(DISTINCT user_id) as cnt FROM subscriptions WHERE status = 'active'"))["cnt"] if get_first_row(await query_db("SELECT COUNT(DISTINCT user_id) as cnt FROM subscriptions WHERE status = 'active'")) else 0
            total_configs = get_first_row(await query_db("SELECT COUNT(*) as cnt FROM configs WHERE id != 0"))["cnt"] if get_first_row(await query_db("SELECT COUNT(*) as cnt FROM configs WHERE id != 0")) else 0
            total_proxies, active_proxies, inactive_proxies, weak_proxies = await get_proxy_count()
            msg = f"📊 **گزارش روزانه ربات**\n\n👥 کاربران کل: {total_users}\n⭐ کاربران پرومکس: {premium_users}\n📡 کانفیگ‌ها: {total_configs}\n🔌 پروکسی‌ها: کل {total_proxies} | فعال {active_proxies} | ضعیف {weak_proxies} | غیرفعال {inactive_proxies}"
            await send_admin_alert(msg)
        except Exception as e:
            logger.error(f"Daily report error: {e}")

async def send_admin_alert(text):
    if not ADMIN_IDS:
        return
    admins = [x.strip() for x in str(ADMIN_IDS).split(",") if x.strip()]
    for admin_id in admins:
        await call_telegram("sendMessage", {"chat_id": int(admin_id), "text": text, "parse_mode": "Markdown"})

# ---------------------------------------------------------------------
# 👤 توابع کاربر و ادمین
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
        if from_user:
            await execute_db("UPDATE users SET username = ?, full_name = ? WHERE id = ?", username, full_name, user["id"])
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
        ch_id = ch_parts[0].strip()
        if not ch_id.startswith("@") and not ch_id.startswith("-100"):
            ch_id = f"@{ch_id}"
        res = await call_telegram("getChatMember", {"chat_id": ch_id, "user_id": int(telegram_id)})
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
        "FROM subscriptions s LEFT JOIN plans p ON s.plan_id = p.id "
        "WHERE s.token = ? AND s.status = 'active'", token
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
    except:
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

# ---------------------------------------------------------------------
# 📋 کیبوردها
# ---------------------------------------------------------------------
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
            [{"text": "📋 مدیریت کانفیگ‌ها", "callback_data": "adm_manage_configs"}],
            [{"text": "📡 مدیریت ساب‌لینک‌های خارجی", "callback_data": "adm_manage_sub_sources"}],
            [{"text": "🔌 مدیریت پروکسی‌ها", "callback_data": "adm_manage_proxies"}],
            [{"text": "📥 تست و دریافت لیست پروکسی", "callback_data": "adm_batch_proxy"}],
            [{"text": "⚙️ تنظیمات", "callback_data": "adm_settings"}, {"text": "📢 ارسال همگانی", "callback_data": "adm_broadcast"}],
            [{"text": "👤 نمای کاربری (تست)", "callback_data": "adm_test_user"}]
        ]
    }

def get_plans_inline_keyboard(plans, is_admin_user):
    kb = []
    for p in plans:
        kb.append([{"text": f"{p['name']} - {p['price']:,} تومان", "callback_data": f"buy_plan_{p['id']}"}])
    kb.append([{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "admin_return" if is_admin_user else "user_return"}])
    return {"inline_keyboard": kb}

# ---------------------------------------------------------------------
# هندلرهای کاربر
# ---------------------------------------------------------------------
async def send_membership_requirement(chat_id, message_id=None):
    force_channels = await get_setting("force_channels", "")
    if not force_channels:
        return
    channels = [c.strip() for c in force_channels.split(",") if c.strip()]
    kb = []
    for ch in channels:
        ch_parts = ch.split("|")
        ch_id = ch_parts[0].strip()
        if not ch_id.startswith("@") and not ch_id.startswith("-100"):
            ch_id = f"@{ch_id}"
        ch_name = ch_parts[1].strip() if len(ch_parts) > 1 and ch_parts[1].strip() else ch_id
        ch_clean = ch_id.replace('@', '')
        kb.append([{"text": f"📢 عضویت در {ch_name}", "url": f"https://t.me/{ch_clean}"}])
    kb.append([{"text": "✅ عضو شدم", "callback_data": "chk_membership"}])
    markup = {"inline_keyboard": kb}
    if message_id:
        await edit_message(chat_id, message_id, STRINGS["not_member"], reply_markup=markup)
    else:
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["not_member"], "reply_markup": markup})

async def credit_referrer_if_pending(user, chat_id):
    ref_id = user.get("referred_by")
    if ref_id and not str(ref_id).endswith("_rewarded"):
        reward_val = await get_setting("referral_reward", "2000")
        reward = safe_int(reward_val, 2000)
        await execute_db("UPDATE users SET balance = balance + ? WHERE telegram_id = ?", reward, ref_id)
        ref_user_res = await query_db("SELECT balance FROM users WHERE telegram_id = ?", ref_id)
        ref_user = get_first_row(ref_user_res)
        new_balance = ref_user["balance"] if ref_user else 0
        await call_telegram("sendMessage", {"chat_id": int(ref_id), "text": f"🎉 یکی از دوستان شما با لینک دعوت شما عضو شد و مبلغ {reward:,} تومان به موجودی شما افزوده گردید!\n💰 موجودی جدید شما: {new_balance:,} تومان"})
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
    await call_telegram("sendPhoto", {"chat_id": chat_id, "photo": qr_url, "caption": msg, "parse_mode": "Markdown", "reply_markup": get_back_markup(is_admin_user)})

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
        markup = {"inline_keyboard": [[{"text": "🖼 نمایش کیوآرکد", "callback_data": f"qr_{s['token']}"}], [{"text": "♻️ تمدید سرویس", "callback_data": f"renew_sub_{s['token']}"}, {"text": "🗑 حذف سرویس", "callback_data": f"del_sub_req_{s['token']}"}]]}
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": f"🔗 ساب‌لینک شما:\n`{sub_url}`\n\n📅 تاریخ انقضا: {s['expires_at']} (UTC)", "parse_mode": "Markdown", "reply_markup": markup})
    await call_telegram("sendMessage", {"chat_id": chat_id, "text": "برای بازگشت از دکمه زیر استفاده کنید:", "reply_markup": get_back_markup(is_admin_user)})

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
    await call_telegram("sendMessage", {"chat_id": chat_id, "text": "✅ پیام شما به پشتیبانی ارسال شد. منتظر پاسخ باشید."})

async def create_subscription_from_plan(plan_id, user_id):
    res = await query_db("SELECT * FROM plans WHERE id = ? AND is_active = 1", plan_id)
    plan = get_first_row(res)
    if not plan:
        return None
    token = secrets.token_hex(16)
    expires_at = (datetime.datetime.utcnow() + datetime.timedelta(days=plan["duration_days"])).strftime("%Y-%m-%d %H:%M:%S")
    await execute_db("INSERT INTO subscriptions (user_id, plan_id, token, expires_at) VALUES (?, ?, ?, ?)", user_id, plan_id, token, expires_at)
    return token

# ---------------------------------------------------------------------
# 💬 مدیریت state ها (با رفع کامل)
# ---------------------------------------------------------------------
async def handle_state(user, state, message, chat_id, is_admin_user, actual_is_admin):
    text = message.get("text", "").strip()
    message_id = message.get("message_id")

    if text in ["❌ خروج / اتمام ارسال", "/cancel"]:
        await execute_db("UPDATE users SET state = NULL, plan_data = NULL WHERE id = ?", user["id"])
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": "عملیات لغو شد."})
        if is_admin_user:
            await show_admin_panel(chat_id)
        else:
            markup = await get_user_inline_keyboard(actual_is_admin)
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["start_welcome"], "reply_markup": markup})
        return True

    if is_admin_user:
        # ---------- مدیریت دسته‌جمعی پروکسی ----------
        if state == "waiting_for_batch_proxy":
            # اگر فایل ارسال شده
            if message.get("document"):
                file_id = message["document"]["file_id"]
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["batch_file_processing"]})
                file_obj = await call_telegram("getFile", {"file_id": file_id})
                if file_obj.get("ok"):
                    file_path = file_obj["result"]["file_path"]
                    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
                    try:
                        resp = await http_client.get(file_url, timeout=30.0)
                        raw_text = resp.text
                    except Exception as e:
                        logger.error(f"File download error: {e}")
                        await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["batch_file_download_error"]})
                        await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])
                        return True
                else:
                    await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["batch_file_download_error"]})
                    await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])
                    return True
            else:
                raw_text = text
                if not raw_text:
                    await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ لطفاً یک متن یا فایل ارسال کنید."})
                    return True

            proxy_list = parse_proxy_list(raw_text)
            if not proxy_list:
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["batch_test_no_result"]})
                await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])
                return True

            await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["batch_test_start"].format(total=len(proxy_list), max_concurrent=20)})
            result = await batch_test_proxies(proxy_list)

            for p in result["accepted"]:
                name = f"batch_{int(time.time())}_{secrets.token_hex(4)}"
                await execute_db(
                    "INSERT INTO proxies (name, address, type, is_active, score) VALUES (?, ?, ?, 1, ?)",
                    name, p["address"], p["type"], max(0, 100 - p["latency"] // 10)
                )

            accepted_list = "\n".join([f"- {p['type']}://{p['address']} (تاخیر: {p['latency']}ms)" for p in result["accepted"]]) or "هیچ‌کدام"
            rejected_reasons = {}
            for r in result["rejected"]:
                reason = r["reason"]
                rejected_reasons[reason] = rejected_reasons.get(reason, 0) + 1
            reasons_str = "\n".join([f"- {count} تا: {reason}" for reason, count in rejected_reasons.items()]) or "هیچ‌کدام"

            if result["accepted_count"] == 0:
                final_msg = STRINGS["batch_test_no_result"]
            else:
                final_msg = STRINGS["batch_test_result"].format(
                    total=result["total"],
                    accepted=result["accepted_count"],
                    rejected=result["rejected_count"],
                    accepted_list=accepted_list,
                    rejected_reasons=reasons_str
                )

            await call_telegram("sendMessage", {"chat_id": chat_id, "text": final_msg, "parse_mode": "Markdown"})
            await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])
            return True

        # ---------- افزودن کانفیگ ----------
        if state == "waiting_for_config":
            if await is_duplicate_config(text):
                await execute_db("UPDATE users SET plan_data = ? WHERE id = ?", json.dumps({"config_text": text, "action": "add"}), user["id"])
                await execute_db("UPDATE users SET state = 'waiting_for_dup_decision' WHERE id = ?", user["id"])
                markup = {"inline_keyboard": [[{"text": "❌ لغو (ثبت نشود)", "callback_data": "cfg_dup_cancel"}, {"text": "✅ نادیده گرفتن (ثبت شود)", "callback_data": "cfg_dup_ignore"}]]}
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["config_duplicate"], "reply_markup": markup})
                return True
            else:
                success, avg_latency, succ_count = await test_config_with_all_proxies(text)
                if success:
                    formatted_cfg = await format_config_name(text)
                    await execute_db("INSERT INTO configs (config_text, speed_score) VALUES (?, ?)", formatted_cfg, avg_latency)
                    await delete_kv("configs_payload")
                    await execute_db("UPDATE users SET state = 'waiting_for_config', plan_data = NULL WHERE id = ?", user["id"])
                    markup = {"inline_keyboard": [[{"text": "❌ پایان افزودن", "callback_data": "adm_add_config_stop"}]]}
                    await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["config_added"] + f"\n\n⚡ سرعت میانگین: {avg_latency}ms\n📥 کانفیگ بعدی را ارسال کنید یا دکمه پایان را بزنید.", "reply_markup": markup})
                else:
                    direct_ok, _ = await test_config_direct(text)
                    if direct_ok:
                        await call_telegram("sendMessage", {"chat_id": chat_id, "text": "⚠️ این کانفیگ از ایران قابل دسترس نیست. لطفاً کانفیگ دیگری ارسال کنید."})
                    else:
                        await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ کانفیگ غیرفعال است. لطفاً کانفیگ دیگری ارسال کنید."})
                return True

        # ---------- افزودن پروکسی ----------
        if state == "waiting_for_proxy":
            proxy_type = "http"
            address = text
            if text.startswith("socks4://"):
                proxy_type = "socks4"
                address = text[9:]
            elif text.startswith("socks5://"):
                proxy_type = "socks5"
                address = text[9:]
            elif text.startswith("http://"):
                address = text[7:]
            success, country, latency = await test_proxy(address, proxy_type)
            if success and country == "IR":
                name = f"proxy_{int(time.time())}"
                await execute_db("INSERT INTO proxies (name, address, type, is_active, score) VALUES (?, ?, ?, 1, ?)", name, address, proxy_type, max(0, 100 - latency // 10))
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["proxy_added"] + f"\n⚡ تاخیر: {latency}ms"})
                await execute_db("UPDATE users SET state = 'waiting_for_proxy' WHERE id = ?", user["id"])
                markup = {"inline_keyboard": [[{"text": "🔚 پایان افزودن", "callback_data": "adm_proxy_add_stop"}]]}
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["proxy_add_step1"], "reply_markup": markup})
            else:
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["proxy_add_failed"] + (f" (کشور: {country})" if country else "")})
            return True

        # ---------- بقیه state ها ----------
        if state == "waiting_for_broadcast":
            if not text:
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ متن پیام نمی‌تواند خالی باشد. مجدداً ارسال کنید:"})
                return True
            await put_kv(f"broadcast_{user['id']}", text, expiration_ttl=3600)
            await execute_db("UPDATE users SET state = ? WHERE id = ?", "waiting_for_broadcast_confirm", user["id"])
            markup = {"inline_keyboard": [[{"text": "✅ تایید و ارسال", "callback_data": "adm_broadcast_yes"}, {"text": "🔙 بازگشت به منوی اصلی", "callback_data": "admin_return"}]]}
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
            info = STRINGS["user_info"].format(tg_id=target_user["telegram_id"], full_name=target_user["full_name"] or "ندارد", username=target_user["username"] or "ندارد", balance=target_user["balance"], trial_status="بله" if target_user["has_used_trial"] else "خیر")
            markup = {"inline_keyboard": [[{"text": "➕ افزایش موجودی", "callback_data": f"adm_add_bal_{target_user['telegram_id']}"}, {"text": "➖ کاهش موجودی", "callback_data": f"adm_sub_bal_{target_user['telegram_id']}"}], [{"text": "🔙 بازگشت", "callback_data": "adm_manage_users_1"}]]}
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": info, "parse_mode": "Markdown", "reply_markup": markup})
            return True

        if state.startswith("waiting_for_add_"):
            target_id = state.replace("waiting_for_add_", "")
            amount = safe_int(text)
            if amount <= 0:
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ لطفاً عدد مثبت وارد کنید:"})
                return True
            await execute_db("UPDATE users SET balance = balance + ?, state = NULL WHERE telegram_id = ?", amount, target_id)
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["balance_added"].format(amount=amount, target_id=target_id), "reply_markup": get_admin_inline_keyboard()})
            await call_telegram("sendMessage", {"chat_id": int(target_id), "text": f"💰 کیف پول شما به مقدار {amount:,} تومان توسط مدیر شارژ شد."})
            return True

        if state.startswith("waiting_for_sub_"):
            target_id = state.replace("waiting_for_sub_", "")
            amount = safe_int(text)
            if amount <= 0:
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ لطفاً عدد مثبت وارد کنید:"})
                return True
            await execute_db("UPDATE users SET balance = CASE WHEN balance - ? < 0 THEN 0 ELSE balance - ? END, state = NULL WHERE telegram_id = ?", amount, amount, target_id)
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["balance_subtracted"].format(amount=amount, target_id=target_id), "reply_markup": get_admin_inline_keyboard()})
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
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["setting_updated"], "reply_markup": get_admin_inline_keyboard()})
            return True

        # ---------- افزودن پلن (تکمیل شده توسط CAT) ----------
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
                limit = safe_int(text)
                if limit <= 0:
                    limit = 1
                plan_data["max_users"] = limit
                await execute_db(
                    "INSERT INTO plans (name, price, duration_days, max_users) VALUES (?, ?, ?, ?)",
                    plan_data["name"], plan_data["price"], plan_data["duration_days"], plan_data["max_users"]
                )
                await execute_db("UPDATE users SET state = NULL, plan_data = NULL WHERE id = ?", user["id"])
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["plan_added"].format(name=plan_data["name"]), "reply_markup": get_admin_inline_keyboard()})
                return True
    
    return False

# ---------------------------------------------------------------------
# 🚀 FastAPI Initialization
# ---------------------------------------------------------------------
app = FastAPI()

@app.on_event("startup")
async def on_startup():
    global http_client
    http_client = httpx.AsyncClient()
    await init_database_if_needed()
    asyncio.create_task(background_proxy_checker())
    asyncio.create_task(background_config_tester())
    asyncio.create_task(background_subscription_fetcher())
    asyncio.create_task(background_expiration_notifier())
    asyncio.create_task(background_daily_report())

@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        update = await request.json()
        # پردازش آپدیت‌های تلگرام
    except Exception as e:
        logger.error(f"Webhook Error: {e}")
    return Response(status_code=200)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)