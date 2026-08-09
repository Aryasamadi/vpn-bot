# -*- coding: utf-8 -*-
"""
ربات مدیریت ساب‌لینک – نسخه CAT FINAL (با رفع کامل دکمه تست لیست)
- مدیریت پروکسی‌های HTTP/SOCKS4/SOCKS5 با صفحه‌بندی و نام‌گذاری ساده
- تست کانفیگ‌ها از طریق پروکسی‌های ایران (اتصال TCP از طریق پروکسی)
- دریافت ساب‌لینک فقط از طریق پروکسی‌های ایران
- هشدارهای هوشمند با دکمه‌های حذف/نادیده گرفتن (با حذف خودکار پیام پس از کلیک)
- شمارش قطع/وصل شدن و حذف خودکار در بار ششم
- ادغام مدیریت پروکسی و تست دسته‌جمعی
- ارسال همگانی در تنظیمات
- حذف دکمه‌های اضافی و ساده‌سازی عناوین
- حالت کاربری با دستور «تست»
- تشخیص تکراری پروکسی و کانفیگ
- تست حجم با درخواست HTTP واقعی از طریق پروکسی
- چینش ۲-۲ در کیبوردها
- حذف تکی کانفیگ‌ها در مدیریت کانفیگ
- دکمه دریافت اختصاصی برای هر ساب‌لینک (به‌جای وضعیت)
- رفع کامل دکمه تست و دریافت لیست
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
    "admin_panel": "🛠 پنل مدیریت – گزینه‌های خود را انتخاب کنید:",
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
    "proxy_list": "🔌 لیست پروکسی‌ها (صفحه {page} از {total_pages}):\n\n",
    "proxy_add_step1": "📝 لطفاً آدرس پروکسی را وارد کنید (فرمت: `http://ip:port` یا `socks4://ip:port`):",
    "proxy_added": "✅ پروکسی با موفقیت اضافه شد و فعال است.",
    "proxy_add_failed": "❌ پروکسی غیرفعال است. لطفاً دوباره تلاش کنید.",
    "proxy_deleted": "🗑 پروکسی حذف شد.",
    "proxy_updated": "✅ پروکسی به‌روزرسانی شد.",
    "proxy_add_stopped": "⏹ عملیات افزودن پروکسی متوقف شد.",
    "proxy_status_report": "📊 وضعیت پروکسی‌ها:\nکل: {total} | فعال: {active} | غیرفعال: {inactive} | ضعیف: {weak}",
    "proxy_death_report": "⚠️ پروکسی `{name}` غیرفعال شد. (پینگ: {ping}ms)",
    "proxy_birth_report": "✅ پروکسی `{name}` دوباره فعال شد. (پینگ: {ping}ms)",
    "proxy_low_warning": "🚨 هشدار: فقط {count} پروکسی فعال باقی مانده است. لطفاً یک پروکسی جدید اضافه کنید.",
    "proxy_no_active": "🚨 هیچ پروکسی فعالی وجود ندارد. ربات وارد حالت ایمن شد.",
    "proxy_restored": "✅ پروکسی جدید فعال شد. ربات از حالت ایمن خارج شد.",
    "proxy_delete_confirm": "آیا از حذف این پروکسی اطمینان دارید؟",
    "proxy_delete_inactive_confirm": "آیا از حذف تمام پروکسی‌های غیرفعال اطمینان دارید؟",
    "proxy_delete_inactive_done": "🧹 تمام پروکسی‌های غیرفعال حذف شدند.",
    "proxy_duplicate": "⚠️ پروکسی `{address}` با پروتکل `{type}` قبلاً ثبت شده است.",
    "proxy_flap_warning": "⚠️ پروکسی `{name}` برای بار {count} قطع و وصل شد. در بار ششم خودکار حذف می‌شود.",
    "proxy_flap_deleted": "🗑 پروکسی `{name}` به‌دلیل ۶ بار قطع/وصل شدن متوالی خودکار حذف شد.",
    "config_deleted_alert": "🗑 کانفیگ [ {code} ] به‌دلیل عدم دسترسی از ایران حذف شد.",
    "config_delete_all_confirm": "⚠️ آیا از حذف همه کانفیگ‌ها (به جز بنر) اطمینان دارید؟",
    "config_delete_all_done": "🗑 همه کانفیگ‌ها حذف شدند.",
    "batch_test_start": "⏳ در حال تست {total} پروکسی... لطفاً صبر کنید. (حداکثر {max_concurrent} تا همزمان)",
    "batch_test_result": "📊 **نتیجه تست پروکسی‌ها**\n\n🔢 کل: {total}\n✅ قبول‌شده (ایران + فعال): {accepted}\n❌ ردشده: {rejected}\n\n📋 لیست قبول‌شده‌ها:\n{accepted_list}\n\n❌ دلایل رد:\n{rejected_reasons}",
    "batch_test_no_result": "❌ هیچ پروکسی معتبری در لیست شما یافت نشد.",
    "batch_test_error": "❌ خطا در پردازش لیست. لطفاً دوباره تلاش کنید.",
    "batch_file_processing": "⏳ در حال پردازش فایل... لطفاً صبر کنید.",
    "batch_file_download_error": "❌ خطا در دانلود فایل. لطفاً دوباره تلاش کنید.",
    "batch_continue": "📥 لیست بعدی را ارسال کنید یا دکمه پایان را بزنید.",
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
# 🔌 توابع مدیریت پروکسی (نسخه نهایی)
# ---------------------------------------------------------------------
async def test_proxy(proxy_address: str, proxy_type: str = "http") -> tuple:
    try:
        proxy_url = f"{proxy_type}://{proxy_address}"
        start = time.time()
        try:
            client = httpx.AsyncClient(proxy=proxy_url, timeout=10.0)
        except Exception:
            client = httpx.AsyncClient(proxies={"all://": proxy_url}, timeout=10.0)
        async with client:
            response = await client.get("http://ip-api.com/json/", timeout=10.0)
            latency = int((time.time() - start) * 1000)
            if response.status_code == 200:
                data = response.json()
                country = data.get("countryCode", "")
                if country == "IR":
                    return True, "IR", latency
                else:
                    return False, country, latency
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
    await execute_db("UPDATE proxies SET is_active = ?, score = ?, last_check = ?, last_latency = ? WHERE id = ?",
                     1 if success and country == "IR" else 0, new_score,
                     datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                     latency if success else 0, proxy_id)

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

async def generate_proxy_name():
    counter = await get_setting("proxy_name_counter", "0")
    num = int(counter) + 1
    await set_setting("proxy_name_counter", str(num))
    letter_index = (num - 1) // 26
    letter = chr(ord('A') + letter_index)
    number = (num - 1) % 26 + 1
    return f"{letter}{number}"

async def is_duplicate_proxy(address: str, proxy_type: str):
    res = await query_db("SELECT id FROM proxies WHERE address = ? AND type = ?", address, proxy_type)
    return get_first_row(res) is not None

# ---------------------------------------------------------------------
# 🧪 تست کانفیگ از طریق پروکسی (ورژن جدید)
# ---------------------------------------------------------------------
async def test_config_via_proxy(config_text: str, proxy: dict) -> tuple:
    ip = extract_ip_from_config(config_text)
    port = extract_port_from_config(config_text)
    if not ip:
        return False, 0
    try:
        proxy_url = f"{proxy['type']}://{proxy['address']}"
        start = time.time()
        try:
            client = httpx.AsyncClient(proxy=proxy_url, timeout=8.0)
        except Exception:
            client = httpx.AsyncClient(proxies={"all://": proxy_url}, timeout=8.0)
        async with client:
            response = await client.get(f"http://{ip}:{port}/", timeout=8.0)
            latency = int((time.time() - start) * 1000)
            return True, latency
    except Exception as e:
        logger.debug(f"Config test via proxy failed: {e}")
        return False, 0

async def test_config_with_all_proxies(config_text: str) -> tuple:
    proxies = await get_active_proxies()
    if not proxies:
        return False, 0, 0
    total_latency = 0
    success_count = 0
    for proxy in proxies:
        ok, lat = await test_config_via_proxy(config_text, proxy)
        if ok:
            success_count += 1
            total_latency += lat
    if success_count > 0:
        avg_latency = total_latency // success_count
        return True, avg_latency, success_count
    else:
        return False, 0, 0

# ---------------------------------------------------------------------
# 🧪 تست دسته‌جمعی پروکسی از لیست
# ---------------------------------------------------------------------
def parse_proxy_list(raw_text: str) -> list:
    lines = raw_text.strip().splitlines()
    proxies = []
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
        if " " in address and ":" not in address:
            parts = address.split()
            if len(parts) == 2 and parts[1].isdigit():
                address = f"{parts[0]}:{parts[1]}"
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
            last_latency INTEGER DEFAULT 0,
            flap_count INTEGER DEFAULT 0,
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
    for col in ["last_latency", "flap_count"]:
        try:
            await execute_db(f"ALTER TABLE proxies ADD COLUMN {col} INTEGER DEFAULT 0")
        except:
            pass

    await execute_db("CREATE INDEX IF NOT EXISTS idx_settings_key ON settings(key);")

    banner_exists = await query_db("SELECT id FROM configs WHERE id = 0")
    if not get_first_row(banner_exists):
        await execute_db("INSERT INTO configs (id, config_text, is_active, fail_count) VALUES (0, ?, 1, 0)", BANNER_CONFIG)
        logger.info("Banner config created with id=0")
    else:
        await execute_db("UPDATE configs SET is_active = 1, config_text = ? WHERE id = 0", BANNER_CONFIG)

    defaults = {"referral_reward": "2000", "force_channels": "", "proxy_name_counter": "0"}
    for key, val in defaults.items():
        res = await query_db("SELECT value FROM settings WHERE key = ?", key)
        if not get_first_row(res):
            await execute_db("INSERT INTO settings (key, value) VALUES (?, ?)", key, val)

    await put_kv("db_initialized_v3_cat", "true")
    logger.info("Database initialized/verified with all required tables")

# ---------------------------------------------------------------------
# 🔄 تسک‌های پس‌زمینه
# ---------------------------------------------------------------------
_last_proxy_alert_time = 0

async def background_proxy_checker():
    global _last_proxy_alert_time
    last_status_was_active = False
    while True:
        await asyncio.sleep(300)
        try:
            proxies_res = await query_db("SELECT id, name, address, type, is_active, flap_count FROM proxies")
            proxies = get_rows(proxies_res)
            for p in proxies:
                old_active = p["is_active"]
                await update_proxy_score(p["id"])
                new_res = await query_db("SELECT is_active, score, last_latency, flap_count FROM proxies WHERE id = ?", p["id"])
                new_row = get_first_row(new_res)
                if new_row:
                    new_active = new_row["is_active"]
                    new_latency = new_row["last_latency"]
                    flap_count = new_row.get("flap_count", 0)
                    if old_active == 1 and new_active == 0:
                        flap_count += 1
                        await execute_db("UPDATE proxies SET flap_count = ? WHERE id = ?", flap_count, p["id"])
                        msg = STRINGS["proxy_death_report"].format(name=p["name"], ping=new_latency)
                        if flap_count >= 6:
                            await execute_db("DELETE FROM proxies WHERE id = ?", p["id"])
                            msg += "\n" + STRINGS["proxy_flap_deleted"].format(name=p["name"])
                            await send_admin_alert(msg)
                        else:
                            await send_proxy_flap_alert(p["id"], p["name"], flap_count, msg)
                    elif old_active == 0 and new_active == 1:
                        flap_count = 0
                        await execute_db("UPDATE proxies SET flap_count = 0 WHERE id = ?", p["id"])
                        msg = STRINGS["proxy_birth_report"].format(name=p["name"], ping=new_latency)
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

async def send_proxy_flap_alert(proxy_id, name, flap_count, alert_text):
    if flap_count >= 6:
        return
    markup = {
        "inline_keyboard": [
            [{"text": "🗑 حذف", "callback_data": f"proxy_del_{proxy_id}"},
             {"text": "⏳ نادیده بگیر", "callback_data": f"proxy_ignore_{proxy_id}"}]
        ]
    }
    await send_admin_alert(alert_text, reply_markup=markup)

async def send_admin_alert(text, reply_markup=None, parse_mode="Markdown"):
    if not ADMIN_IDS:
        return
    admins = [x.strip() for x in str(ADMIN_IDS).split(",") if x.strip()]
    for admin_id in admins:
        await call_telegram("sendMessage", {"chat_id": int(admin_id), "text": text, "reply_markup": reply_markup, "parse_mode": parse_mode})

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

async def background_config_tester():
    while True:
        await asyncio.sleep(1800)
        try:
            configs_res = await query_db("SELECT id, config_text FROM configs WHERE is_active = 1 AND id != 0")
            configs = get_rows(configs_res)
            for cfg in configs:
                success, avg_latency, succ_count = await test_config_with_all_proxies(cfg["config_text"])
                if success:
                    await execute_db("UPDATE configs SET speed_score = ?, fail_count = 0 WHERE id = ?", avg_latency, cfg["id"])
                else:
                    code = extract_config_name(cfg["config_text"]) or cfg["id"]
                    await execute_db("DELETE FROM configs WHERE id = ?", cfg["id"])
                    await delete_kv("configs_payload")
                    msg = STRINGS["config_deleted_alert"].format(code=code)
                    await send_admin_alert(msg)
        except Exception as e:
            logger.error(f"Config tester error: {e}")

async def background_subscription_fetcher():
    while True:
        await asyncio.sleep(3600)
        try:
            active_proxies = await get_active_proxies()
            if not active_proxies:
                await send_admin_alert("⚠️ هیچ پروکسی فعالی برای دریافت ساب‌لینک وجود ندارد. عملیات متوقف شد.")
                continue
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

# ---------------------------------------------------------------------
# 📥 دریافت کانفیگ از ساب‌لینک (فقط از طریق پروکسی)
# ---------------------------------------------------------------------
async def fetch_and_add_configs_from_source(source_id):
    res = await query_db("SELECT url FROM subscription_sources WHERE id = ?", source_id)
    row = get_first_row(res)
    if not row:
        return 0
    url = row["url"]

    proxies = await get_active_proxies()
    if not proxies:
        await send_admin_alert(f"⚠️ برای دریافت ساب‌لینک {url} هیچ پروکسی فعالی وجود ندارد.")
        return 0

    proxy = proxies[0]
    proxy_url = f"{proxy['type']}://{proxy['address']}"
    try:
        try:
            client = httpx.AsyncClient(proxy=proxy_url, timeout=20.0)
        except Exception:
            client = httpx.AsyncClient(proxies={"all://": proxy_url}, timeout=20.0)
        async with client:
            response = await client.get(url, timeout=20.0)
            if response.status_code != 200:
                logger.error(f"Failed to fetch {url}: status {response.status_code}")
                return 0
            content = response.text
            try:
                decoded = base64.b64decode(content).decode('utf-8')
            except:
                decoded = content
            lines = [line.strip() for line in decoded.splitlines() if line.strip()]
            count = 0
            for line in lines:
                if any(line.startswith(p) for p in ["vmess://", "vless://", "trojan://", "ss://", "ssr://"]):
                    if await is_duplicate_config(line):
                        continue
                    success, avg_latency, _ = await test_config_with_all_proxies(line)
                    if success:
                        formatted = await format_config_name(line)
                        await execute_db("INSERT INTO configs (config_text, speed_score) VALUES (?, ?)", formatted, avg_latency)
                        count += 1
            now_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            await execute_db("UPDATE subscription_sources SET last_fetch = ? WHERE id = ?", now_str, source_id)
            await delete_kv("configs_payload")
            return count
    except Exception as e:
        logger.error(f"Error fetching from {url}: {e}")
        return 0

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
# 📋 کیبوردها (چینش ۲-۲)
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
        kb.append([{"text": "👑 پنل مدیریت", "callback_data": "admin_return"}])
    return {"inline_keyboard": kb}

def get_admin_inline_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "📦 پلن‌ها", "callback_data": "adm_manage_plans"}, {"text": "👤 کاربران", "callback_data": "adm_manage_users_1"}],
            [{"text": "📋 کانفیگ‌ها", "callback_data": "adm_manage_configs"}, {"text": "📡 ساب‌لینک‌ها", "callback_data": "adm_manage_sub_sources"}],
            [{"text": "🔌 پروکسی‌ها", "callback_data": "adm_manage_proxies"}, {"text": "⚙️ تنظیمات", "callback_data": "adm_settings"}]
        ]
    }

def get_plans_inline_keyboard(plans, is_admin_user):
    kb = []
    for p in plans:
        kb.append([{"text": f"{p['name']} - {p['price']:,} تومان", "callback_data": f"buy_plan_{p['id']}"}])
    kb.append([{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "admin_return" if is_admin_user else "user_return"}])
    return {"inline_keyboard": kb}

# ---------------------------------------------------------------------
# هندلرهای کاربر (بدون تغییر)
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
# 💬 مدیریت state ها
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
                        return True
                else:
                    await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["batch_file_download_error"]})
                    return True
            else:
                raw_text = text
                if not raw_text:
                    await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ لطفاً یک متن یا فایل ارسال کنید."})
                    return True

            proxy_list = parse_proxy_list(raw_text)
            if not proxy_list:
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["batch_test_no_result"]})
                return True

            await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["batch_test_start"].format(total=len(proxy_list), max_concurrent=20)})
            result = await batch_test_proxies(proxy_list)

            for p in result["accepted"]:
                if await is_duplicate_proxy(p["address"], p["type"]):
                    await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["proxy_duplicate"].format(address=p["address"], type=p["type"])})
                    continue
                name = await generate_proxy_name()
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

            markup = {"inline_keyboard": [[{"text": "🔚 پایان و بازگشت", "callback_data": "adm_batch_proxy_finish"}]]}
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": final_msg + "\n\n" + STRINGS["batch_continue"], "parse_mode": "Markdown", "reply_markup": markup})
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
                    await call_telegram("sendMessage", {"chat_id": chat_id, "text": "⚠️ کانفیگ از ایران قابل دسترس نیست. لطفاً کانفیگ دیگری ارسال کنید."})
                return True

        # ---------- افزودن پروکسی (دستی) ----------
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
            if await is_duplicate_proxy(address, proxy_type):
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["proxy_duplicate"].format(address=address, type=proxy_type)})
                return True
            success, country, latency = await test_proxy(address, proxy_type)
            if success and country == "IR":
                name = await generate_proxy_name()
                await execute_db("INSERT INTO proxies (name, address, type, is_active, score) VALUES (?, ?, ?, 1, ?)", name, address, proxy_type, max(0, 100 - latency // 10))
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["proxy_added"] + f"\n⚡ تاخیر: {latency}ms"})
                await execute_db("UPDATE users SET state = 'waiting_for_proxy' WHERE id = ?", user["id"])
                markup = {"inline_keyboard": [[{"text": "🔚 پایان افزودن", "callback_data": "adm_proxy_add_stop"}]]}
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["proxy_add_step1"], "reply_markup": markup})
            else:
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["proxy_add_failed"] + (f" (کشور: {country})" if country else "")})
            return True

        # ---------- بقیه state ها (فشرده) ----------
        if state == "waiting_for_broadcast":
            if not text:
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ متن پیام نمی‌تواند خالی باشد. مجدداً ارسال کنید:"})
                return True
            await put_kv(f"broadcast_{user['id']}", text, expiration_ttl=3600)
            await execute_db("UPDATE users SET state = ? WHERE id = ?", "waiting_for_broadcast_confirm", user["id"])
            markup = {"inline_keyboard": [[{"text": "✅ تایید و ارسال", "callback_data": "adm_broadcast_yes"}, {"text": "🔙 بازگشت", "callback_data": "admin_return"}]]}
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

        # ---------- افزودن پلن ----------
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
                await execute_db("INSERT INTO plans (name, price, duration_days, max_users, is_active) VALUES (?, ?, ?, ?, 1)", name, price, duration, max_users)
                await execute_db("UPDATE users SET state = NULL, plan_data = NULL WHERE id = ?", user["id"])
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["plan_added"].format(name=name), "reply_markup": get_admin_inline_keyboard()})
                return True

        # ---------- محتوای راهنما ----------
        if state == "waiting_for_help_content":
            help_data = {}
            if text:
                parse_mode = "Markdown" if any(m in text for m in ['*', '_', '`', '#']) else None
                help_data = {"type": "text", "content": text, "parse_mode": parse_mode}
            elif message.get("photo"):
                help_data = {"type": "photo", "file_id": message["photo"][-1]["file_id"], "caption": message.get("caption", ""), "parse_mode": "Markdown" if message.get("caption") else None}
            elif message.get("video"):
                help_data = {"type": "video", "file_id": message["video"]["file_id"], "caption": message.get("caption", ""), "parse_mode": "Markdown" if message.get("caption") else None}
            elif message.get("document"):
                help_data = {"type": "document", "file_id": message["document"]["file_id"], "caption": message.get("caption", ""), "parse_mode": "Markdown" if message.get("caption") else None}
            if help_data:
                await set_setting("help_content", json.dumps(help_data))
                await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": "✅ محتوای راهنما با موفقیت ثبت شد.", "reply_markup": get_admin_inline_keyboard()})
            return True

        # ---------- دکمه داینامیک ----------
        if state == "waiting_dyn_title":
            await set_setting("dyn_btn_title", text.strip())
            await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": "✅ عنوان دکمه در منوی کاربری ذخیره شد.", "reply_markup": get_admin_inline_keyboard()})
            return True

        if state == "waiting_dyn_content":
            dyn_data = {}
            if text:
                parse_mode = "Markdown" if any(m in text for m in ['*', '_', '`', '#']) else None
                dyn_data = {"type": "text", "content": text, "parse_mode": parse_mode}
            elif message.get("photo"):
                dyn_data = {"type": "photo", "file_id": message["photo"][-1]["file_id"], "caption": message.get("caption", ""), "parse_mode": "Markdown" if message.get("caption") else None}
            elif message.get("video"):
                dyn_data = {"type": "video", "file_id": message["video"]["file_id"], "caption": message.get("caption", ""), "parse_mode": "Markdown" if message.get("caption") else None}
            elif message.get("document"):
                dyn_data = {"type": "document", "file_id": message["document"]["file_id"], "caption": message.get("caption", ""), "parse_mode": "Markdown" if message.get("caption") else None}
            if dyn_data:
                await set_setting("dyn_btn_content", json.dumps(dyn_data))
                await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": "✅ محتوای دکمه داینامیک ثبت شد.", "reply_markup": get_admin_inline_keyboard()})
            return True

        # ---------- مدیریت ساب‌لینک خارجی ----------
        if state == "waiting_sub_source_name":
            if text == "لغو":
                await execute_db("UPDATE users SET state = NULL, plan_data = NULL WHERE id = ?", user["id"])
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ افزودن ساب‌لینک لغو شد.", "reply_markup": get_admin_inline_keyboard()})
                return True
            await execute_db("UPDATE users SET plan_data = ? WHERE id = ?", json.dumps({"name": text}), user["id"])
            await execute_db("UPDATE users SET state = 'waiting_sub_source_url' WHERE id = ?", user["id"])
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["sub_source_add_step2"]})
            return True

        if state == "waiting_sub_source_url":
            if text == "لغو":
                await execute_db("UPDATE users SET state = NULL, plan_data = NULL WHERE id = ?", user["id"])
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ افزودن ساب‌لینک لغو شد.", "reply_markup": get_admin_inline_keyboard()})
                return True
            plan_data = user.get("plan_data")
            if plan_data:
                try:
                    data = json.loads(plan_data)
                    name = data.get("name", "بدون نام")
                except:
                    name = "بدون نام"
            else:
                name = "بدون نام"
            url = text.strip()
            if not url.startswith("http"):
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ لطفاً یک URL معتبر وارد کنید (با http یا https شروع شود):"})
                return True
            check_res = await query_db("SELECT id FROM subscription_sources WHERE name = ? OR url = ?", name, url)
            if get_first_row(check_res):
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": "⚠️ یک ساب‌لینک با همین نام یا URL قبلاً ثبت شده است.", "reply_markup": get_admin_inline_keyboard()})
                await execute_db("UPDATE users SET state = NULL, plan_data = NULL WHERE id = ?", user["id"])
                return True
            insert_result = await execute_db("INSERT INTO subscription_sources (name, url, is_active, last_fetch) VALUES (?, ?, 1, NULL)", name, url)
            if insert_result.get("success") is False:
                error_msg = insert_result.get("error") or insert_result.get("errors") or "خطای ناشناخته"
                logger.error(f"Insert failed: {insert_result}")
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": f"❌ خطا در ثبت ساب‌لینک:\n{error_msg}", "reply_markup": get_admin_inline_keyboard()})
                await execute_db("UPDATE users SET state = NULL, plan_data = NULL WHERE id = ?", user["id"])
                return True
            await execute_db("UPDATE users SET state = NULL, plan_data = NULL WHERE id = ?", user["id"])
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["sub_source_added"].format(name=name), "reply_markup": get_admin_inline_keyboard()})
            await show_sub_source_management(chat_id, None)
            return True

        if state.startswith("waiting_sub_source_edit_name_"):
            source_id = state.replace("waiting_sub_source_edit_name_", "")
            new_name = text.strip()
            if new_name and new_name.lower() != "لغو":
                await execute_db("UPDATE subscription_sources SET name = ? WHERE id = ?", new_name, source_id)
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["sub_source_updated"], "reply_markup": get_admin_inline_keyboard()})
            else:
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ ویرایش لغو شد.", "reply_markup": get_admin_inline_keyboard()})
            await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])
            return True

        if state.startswith("waiting_sub_source_edit_url_"):
            source_id = state.replace("waiting_sub_source_edit_url_", "")
            new_url = text.strip()
            if new_url and new_url.lower() != "لغو" and new_url.startswith("http"):
                await execute_db("UPDATE subscription_sources SET url = ? WHERE id = ?", new_url, source_id)
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["sub_source_updated"], "reply_markup": get_admin_inline_keyboard()})
            else:
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ ویرایش لغو شد یا URL نامعتبر.", "reply_markup": get_admin_inline_keyboard()})
            await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])
            return True

        # ---------- ویرایش پلن ----------
        if state.startswith("waiting_plan_edit_"):
            pass

    # ---------- حالت پشتیبانی ----------
    if state and state.startswith("support_session_"):
        await forward_support_message(user, message, chat_id)
        return True

    return False

# ---------------------------------------------------------------------
# 📞 پردازش Callback
# ---------------------------------------------------------------------
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

    defer_answer = data.startswith("confirm_buy_") or data == "chk_membership" or data.startswith("qr_") or data.startswith("confirm_renew_") or data.startswith("cfg_dup") or data.startswith("proxy_")
    if not defer_answer and data != "end_support":
        await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id})

    # ---------- پایان پشتیبانی ----------
    if data == "end_support":
        await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])
        await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "✅ نشست پشتیبانی پایان یافت.", "show_alert": True})
        await call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
        markup = await get_user_inline_keyboard(actual_is_admin)
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["start_welcome"], "reply_markup": markup})
        return

    # ---------- بازگشت به منو ----------
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
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["start_welcome"], "reply_markup": markup})
        return

    # ---------- بررسی عضویت ----------
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
            await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "❌ هنوز در کانال‌های اجباری عضو نشده‌اید!\nبعد از عضویت دوباره تلاش کنید.", "show_alert": True})
        return

    # ---------- دکمه‌های کاربر ----------
    if data == "free_trial": return await handle_free_trial(user, chat_id, message_id, is_admin_user)
    if data == "wallet": return await handle_wallet(user, chat_id, message_id, is_admin_user)
    if data == "buy_service": return await handle_buy_service(user, chat_id, message_id, is_admin_user)
    if data == "my_services": return await handle_my_services(user, chat_id, message_id, is_admin_user)
    if data == "referral": return await handle_referral(user, chat_id, message_id, is_admin_user)
    if data == "support": return await handle_support_start(user, chat_id, message_id, is_admin_user)

    # ---------- راهنما ----------
    if data == "help_btn":
        help_val = await get_setting("help_content")
        if not help_val:
            await edit_message(chat_id, message_id, "محتوای راهنما هنوز تنظیم نشده است.", reply_markup=get_back_markup(is_admin_user))
            return
        try:
            help_data = json.loads(help_val)
            parse_mode = help_data.get("parse_mode", None)
            if help_data["type"] == "text":
                await edit_message(chat_id, message_id, help_data["content"], reply_markup=get_back_markup(is_admin_user), parse_mode=parse_mode)
            else:
                await call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
                if help_data["type"] == "photo":
                    await call_telegram("sendPhoto", {"chat_id": chat_id, "photo": help_data["file_id"], "caption": help_data.get("caption", ""), "reply_markup": get_back_markup(is_admin_user), "parse_mode": parse_mode})
                elif help_data["type"] == "video":
                    await call_telegram("sendVideo", {"chat_id": chat_id, "video": help_data["file_id"], "caption": help_data.get("caption", ""), "reply_markup": get_back_markup(is_admin_user), "parse_mode": parse_mode})
                elif help_data["type"] == "document":
                    await call_telegram("sendDocument", {"chat_id": chat_id, "document": help_data["file_id"], "caption": help_data.get("caption", ""), "reply_markup": get_back_markup(is_admin_user), "parse_mode": parse_mode})
        except:
            pass
        return

    # ---------- دکمه داینامیک ----------
    if data == "dyn_btn_click":
        content_val = await get_setting("dyn_btn_content")
        if not content_val:
            await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "محتوایی تنظیم نشده است.", "show_alert": True})
            return
        markup = {"inline_keyboard": [[{"text": "🔙 بازگشت", "callback_data": "user_return"}]]}
        try:
            dyn_data = json.loads(content_val)
            parse_mode = dyn_data.get("parse_mode", None)
            if dyn_data["type"] == "text":
                await edit_message(chat_id, message_id, dyn_data["content"], reply_markup=markup, parse_mode=parse_mode)
            else:
                await call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
                if dyn_data["type"] == "photo":
                    await call_telegram("sendPhoto", {"chat_id": chat_id, "photo": dyn_data["file_id"], "caption": dyn_data.get("caption", ""), "reply_markup": markup, "parse_mode": parse_mode})
                elif dyn_data["type"] == "video":
                    await call_telegram("sendVideo", {"chat_id": chat_id, "video": dyn_data["file_id"], "caption": dyn_data.get("caption", ""), "reply_markup": markup, "parse_mode": parse_mode})
                elif dyn_data["type"] == "document":
                    await call_telegram("sendDocument", {"chat_id": chat_id, "document": dyn_data["file_id"], "caption": dyn_data.get("caption", ""), "reply_markup": markup, "parse_mode": parse_mode})
        except:
            pass
        return

    # ---------- QR و تمدید و حذف سرویس ----------
    if data.startswith("qr_"):
        token = data.replace("qr_", "")
        sub_res = await query_db("SELECT * FROM subscriptions WHERE token = ? AND status = 'active'", token)
        if not get_first_row(sub_res):
            await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "❌ اشتراک یافت نشد.", "show_alert": True})
            return
        await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id})
        sub_url = await build_sub_url_async(token)
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={sub_url}"
        await call_telegram("sendPhoto", {"chat_id": chat_id, "photo": qr_url, "caption": f"📱 کیوآرکد اتصال شما:\n\n`{sub_url}`", "parse_mode": "Markdown", "reply_markup": {"inline_keyboard": [[{"text": "🔙 بازگشت", "callback_data": "my_services"}]]}})
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

    # ---------- خرید پلن ----------
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
        await call_telegram("sendPhoto", {"chat_id": chat_id, "photo": qr_url, "caption": msg, "parse_mode": "Markdown", "reply_markup": get_back_markup(is_admin_user)})
        return

    # ---------- فقط مدیران ----------
    if not is_admin_user:
        await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": STRINGS["admin_only"], "show_alert": True})
        return

    # =============================================================
    # ---------- بخش‌های مدیریتی ----------
    # =============================================================

    # ----- مدیریت پروکسی (ادغام شده) -----
    if data == "adm_manage_proxies":
        await show_proxy_management(chat_id, message_id, page=1)
        return

    if data.startswith("adm_manage_proxies_page_"):
        page = safe_int(data.replace("adm_manage_proxies_page_", ""), 1)
        await show_proxy_management(chat_id, message_id, page=page)
        return

    if data == "adm_add_proxy":
        await execute_db("UPDATE users SET state = 'waiting_for_proxy' WHERE id = ?", user["id"])
        markup = {"inline_keyboard": [[{"text": "🔚 پایان افزودن", "callback_data": "adm_proxy_add_stop"}]]}
        await edit_message(chat_id, message_id, STRINGS["proxy_add_step1"], reply_markup=markup)
        return

    if data == "adm_proxy_add_stop":
        await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])
        await edit_message(chat_id, message_id, STRINGS["proxy_add_stopped"], reply_markup=get_admin_inline_keyboard())
        return

    # دکمه حذف پروکسی
    if data.startswith("adm_proxy_del_"):
        proxy_id = data.replace("adm_proxy_del_", "")
        markup = {"inline_keyboard": [[{"text": "✅ بله، حذف کن", "callback_data": f"adm_proxy_del_yes_{proxy_id}"}, {"text": "❌ لغو", "callback_data": "adm_manage_proxies"}]]}
        await edit_message(chat_id, message_id, STRINGS["proxy_delete_confirm"], reply_markup=markup)
        return

    if data.startswith("adm_proxy_del_yes_"):
        proxy_id = data.replace("adm_proxy_del_yes_", "")
        await execute_db("DELETE FROM proxies WHERE id = ?", proxy_id)
        await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": STRINGS["proxy_deleted"]})
        await show_proxy_management(chat_id, message_id, page=1)
        return

    # حذف غیرفعال‌ها
    if data == "adm_proxy_delete_inactive":
        markup = {"inline_keyboard": [[{"text": "✅ بله، حذف کن", "callback_data": "adm_proxy_delete_inactive_yes"}, {"text": "❌ لغو", "callback_data": "adm_manage_proxies"}]]}
        await edit_message(chat_id, message_id, STRINGS["proxy_delete_inactive_confirm"], reply_markup=markup)
        return

    if data == "adm_proxy_delete_inactive_yes":
        await execute_db("DELETE FROM proxies WHERE is_active = 0")
        await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": STRINGS["proxy_delete_inactive_done"]})
        await show_proxy_management(chat_id, message_id, page=1)
        return

    # دکمه‌های حذف/نادیده‌گرفتن پروکسی (با حذف پیام پس از کلیک)
    if data.startswith("proxy_del_"):
        proxy_id = int(data.replace("proxy_del_", ""))
        await execute_db("DELETE FROM proxies WHERE id = ?", proxy_id)
        await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "🗑 پروکسی حذف شد."})
        await call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
        return

    if data.startswith("proxy_ignore_"):
        await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "⏳ پروکسی نادیده گرفته شد."})
        await call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
        return

    # پایان حالت دسته‌جمعی
    if data == "adm_batch_proxy_finish":
        await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])
        await edit_message(chat_id, message_id, "🔚 عملیات تست لیست پایان یافت.", reply_markup=get_admin_inline_keyboard())
        return

    # =============================================================
    # ✅ دکمه تست و دریافت لیست (رفع کامل)
    # =============================================================
    if data == "adm_batch_proxy":
        await execute_db("UPDATE users SET state = 'waiting_for_batch_proxy' WHERE id = ?", user["id"])
        await call_telegram("sendMessage", {
            "chat_id": chat_id,
            "text": "📥 لطفاً لیست پروکسی‌ها را به‌صورت **متن** (هر خط یک آدرس) یا **فایل** (TXT/JSON) ارسال کنید.\n\nفرمت‌های پشتیبانی:\n- `ip:port` (پیش‌فرض HTTP)\n- `http://ip:port`\n- `socks4://ip:port`\n- `socks5://ip:port`\n- JSON با کلیدهای `ip_address` و `port`\n\nربات همه را تست می‌کند و فقط پروکسی‌های فعال ایرانی را اضافه می‌کند.",
            "reply_markup": {"inline_keyboard": [[{"text": "🔙 لغو", "callback_data": "admin_return"}]]},
            "parse_mode": "Markdown"
        })
        # پیام قبلی را حذف نمی‌کنیم تا کاربر گیج نشود
        return

    # ----- مدیریت کانفیگ‌ها (با حذف تکی) -----
    if data == "adm_manage_configs":
        await show_config_management(chat_id, message_id, page=1)
        return

    if data.startswith("adm_configs_page_"):
        page = safe_int(data.replace("adm_configs_page_", ""), 1)
        await show_config_management(chat_id, message_id, page=page)
        return

    if data == "adm_config_delete_all":
        markup = {"inline_keyboard": [[{"text": "✅ بله، حذف کن", "callback_data": "adm_config_delete_all_yes"}, {"text": "❌ لغو", "callback_data": "adm_manage_configs"}]]}
        await edit_message(chat_id, message_id, STRINGS["config_delete_all_confirm"], reply_markup=markup)
        return

    if data == "adm_config_delete_all_yes":
        await execute_db("DELETE FROM configs WHERE id != 0")
        await delete_kv("configs_payload")
        await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": STRINGS["config_delete_all_done"]})
        await show_config_management(chat_id, message_id, page=1)
        return

    # حذف تکی کانفیگ
    if data.startswith("adm_cfg_del_immediate_"):
        parts = data.split("_")
        if len(parts) >= 5:
            cfg_id = parts[4]
            page = safe_int(parts[5], 1)
        else:
            cfg_id = data.replace("adm_cfg_del_immediate_", "")
            page = 1
        if int(cfg_id) == 0:
            await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "❌ بنر دائمی قابل حذف نیست!", "show_alert": True})
            return
        await execute_db("DELETE FROM configs WHERE id = ?", cfg_id)
        await delete_kv("configs_payload")
        await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "✅ کانفیگ با موفقیت حذف شد."})
        await show_config_management(chat_id, message_id, page=page)
        return

    if data == "adm_add_config_stop":
        await execute_db("UPDATE users SET state = NULL, plan_data = NULL WHERE id = ?", user["id"])
        await edit_message(chat_id, message_id, STRINGS["config_add_stopped"], reply_markup=get_admin_inline_keyboard())
        await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id})
        return

    if data == "cfg_dup_cancel":
        await execute_db("UPDATE users SET state = NULL, plan_data = NULL WHERE id = ?", user["id"])
        await edit_message(chat_id, message_id, STRINGS["config_duplicate_ignored"], reply_markup=get_back_markup(True))
        await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id})
        return

    if data == "cfg_dup_ignore":
        plan_data = user.get("plan_data")
        if plan_data:
            try:
                data_obj = json.loads(plan_data)
                config_text = data_obj.get("config_text")
                if config_text:
                    formatted_cfg = await format_config_name(config_text)
                    await execute_db("INSERT INTO configs (config_text) VALUES (?)", formatted_cfg)
                    await delete_kv("configs_payload")
                    await execute_db("UPDATE users SET state = 'waiting_for_config', plan_data = NULL WHERE id = ?", user["id"])
                    markup = {"inline_keyboard": [[{"text": "❌ پایان افزودن", "callback_data": "adm_add_config_stop"}]]}
                    await edit_message(chat_id, message_id, STRINGS["config_duplicate_forced"] + "\n\n📥 کانفیگ بعدی را ارسال کنید یا دکمه پایان را بزنید.", reply_markup=markup)
                else:
                    await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ خطا: کانفیگ یافت نشد."})
            except Exception as e:
                logger.error(f"Error in cfg_dup_ignore: {e}")
        await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id})
        return

    if data == "adm_add_config":
        await execute_db("UPDATE users SET state = 'waiting_for_config', plan_data = NULL WHERE id = ?", user["id"])
        await edit_message(chat_id, message_id, "📥 لطفا کانفیگ خود را ارسال کنید.\nبرای پایان، دکمه زیر را بزنید:", reply_markup={"inline_keyboard": [[{"text": "❌ پایان افزودن", "callback_data": "adm_add_config_stop"}]]})
        return

    # ----- مدیریت پلن‌ها -----
    if data == "adm_manage_plans":
        await show_plan_management(chat_id, message_id)
        return

    if data == "adm_add_plan":
        await execute_db("UPDATE users SET state = 'waiting_plan_name', plan_data = '{}' WHERE id = ?", user["id"])
        await edit_message(chat_id, message_id, STRINGS["plan_add_step1"], reply_markup={"inline_keyboard": [[{"text": "🔙 لغو", "callback_data": "adm_manage_plans"}]]})
        return

    if data.startswith("adm_plan_edit_"):
        plan_id = data.replace("adm_plan_edit_", "")
        await execute_db("UPDATE users SET state = ?, plan_data = ? WHERE id = ?", f"waiting_plan_edit_{plan_id}", json.dumps({"step": "name"}), user["id"])
        await edit_message(chat_id, message_id, STRINGS["plan_edit_step1"], reply_markup={"inline_keyboard": [[{"text": "🔙 لغو", "callback_data": "adm_manage_plans"}]]})
        return

    if data.startswith("adm_plan_del_req_"):
        plan_id = data.replace("adm_plan_del_req_", "")
        markup = {"inline_keyboard": [[{"text": "✅ بله، حذف کن", "callback_data": f"adm_plan_del_yes_{plan_id}"}, {"text": "❌ لغو", "callback_data": "adm_manage_plans"}]]}
        await edit_message(chat_id, message_id, STRINGS["delete_plan_confirm"], reply_markup=markup)
        return

    if data.startswith("adm_plan_del_yes_"):
        plan_id = data.replace("adm_plan_del_yes_", "")
        await execute_db("DELETE FROM plans WHERE id = ?", plan_id)
        await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "✅ پلن حذف شد."})
        await show_plan_management(chat_id, message_id)
        return

    # ----- دکمه‌های قبلی برای broadcast و تنظیمات -----
    if data == "adm_broadcast":
        await execute_db("UPDATE users SET state = 'waiting_for_broadcast' WHERE id = ?", user["id"])
        await edit_message(chat_id, message_id, STRINGS["broadcast_start"], reply_markup=get_back_markup(True))
        return

    if data == "adm_broadcast_yes":
        if user.get("state") != "waiting_for_broadcast_confirm":
            await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "❌ وضعیت نامعتبر.", "show_alert": True})
            return
        msg_text = await get_kv(f"broadcast_{user['id']}")
        if not msg_text:
            await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "❌ متن پیام یافت نشد.", "show_alert": True})
            return
        await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])
        await delete_kv(f"broadcast_{user['id']}")
        all_users_res = await query_db("SELECT telegram_id FROM users")
        all_users = get_rows(all_users_res)
        await edit_message(chat_id, message_id, STRINGS["broadcast_sending"])
        success = 0
        for u in all_users:
            res = await call_telegram("sendMessage", {"chat_id": int(u["telegram_id"]), "text": msg_text})
            if res.get("ok"):
                success += 1
            await asyncio.sleep(0.05)
        await edit_message(chat_id, message_id, STRINGS["broadcast_done"].format(success=success, total=len(all_users)), reply_markup=get_admin_inline_keyboard())
        return

    if data == "adm_settings":
        reward = await get_setting("referral_reward", "2000")
        channels = await get_setting("force_channels", "غیرفعال")
        settings_text = STRINGS["settings_show"].format(reward=safe_int(reward), channels=channels)
        markup = {"inline_keyboard": [
            [{"text": "✏️ ویرایش کانال‌های اجباری", "callback_data": "adm_set_channels"},
             {"text": "✏️ ویرایش پاداش دعوت", "callback_data": "adm_set_referral_reward"}],
            [{"text": "📖 تنظیم راهنما", "callback_data": "adm_set_help"},
             {"text": "🔘 تنظیم دکمه داینامیک", "callback_data": "adm_dyn_btn"}],
            [{"text": "📢 ارسال همگانی", "callback_data": "adm_broadcast"}],
            [{"text": "🔙 بازگشت", "callback_data": "admin_return"}]
        ]}
        await edit_message(chat_id, message_id, settings_text, reply_markup=markup, parse_mode="Markdown")
        return

    # بقیه تنظیمات (کانال، راهنما، داینامیک)
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
            await process_callback({"id": cq_id, "message": message, "data": "adm_set_channels", "from": from_user})
        return

    if data == "adm_set_referral_reward":
        await execute_db("UPDATE users SET state = 'waiting_setting_referral_reward' WHERE id = ?", user["id"])
        await edit_message(chat_id, message_id, "✏️ لطفاً مقدار جدید پاداش دعوت را بفرستید:", reply_markup={"inline_keyboard": [[{"text": "🔙 بازگشت", "callback_data": "adm_settings"}]]})
        return

    if data == "adm_set_help":
        await execute_db("UPDATE users SET state = 'waiting_for_help_content' WHERE id = ?", user["id"])
        await edit_message(chat_id, message_id, "محتوای دکمه راهنما را ارسال کنید (پشتیبانی از متن، عکس، ویدیو و فایل):\n\n💡 برای استفاده از مارک‌داون، متن را با *، _، ` یا # قالب‌بندی کنید.", reply_markup={"inline_keyboard": [[{"text": "🔙 بازگشت", "callback_data": "adm_settings"}]]})
        return

    if data == "adm_dyn_btn":
        markup = {"inline_keyboard": [[{"text": "✏️ عنوان دکمه در منو", "callback_data": "adm_dyn_title"}], [{"text": "✏️ محتوای دکمه (پیام اصلی)", "callback_data": "adm_dyn_content"}], [{"text": "🔙 بازگشت", "callback_data": "adm_settings"}]]}
        await edit_message(chat_id, message_id, "تنظیمات دکمه داینامیک:", reply_markup=markup)
        return

    if data == "adm_dyn_title":
        await execute_db("UPDATE users SET state = 'waiting_dyn_title' WHERE id = ?", user["id"])
        await edit_message(chat_id, message_id, "لطفاً عنوانی که می‌خواهید برای دکمه در منوی کاربری نمایش داده شود را ارسال کنید:", reply_markup={"inline_keyboard": [[{"text": "🔙 بازگشت", "callback_data": "adm_dyn_btn"}]]})
        return

    if data == "adm_dyn_content":
        await execute_db("UPDATE users SET state = 'waiting_dyn_content' WHERE id = ?", user["id"])
        await edit_message(chat_id, message_id, "محتوای دکمه داینامیک را ارسال کنید (پشتیبانی کامل از عکس، متن، ویدیو و فایل):\n\n💡 برای استفاده از مارک‌داون، متن را با *، _، ` یا # قالب‌بندی کنید.", reply_markup={"inline_keyboard": [[{"text": "🔙 بازگشت", "callback_data": "adm_dyn_btn"}]]})
        return

    # ----- مدیریت کاربران -----
    if data.startswith("adm_manage_users_"):
        page = safe_int(data.replace("adm_manage_users_", ""), 1)
        limit = 5
        offset = (page - 1) * limit
        total_res = await query_db("SELECT COUNT(*) as cnt FROM users")
        total_row = get_first_row(total_res)
        total_users = total_row["cnt"] if total_row else 0
        res = await query_db("SELECT * FROM users ORDER BY id DESC LIMIT ? OFFSET ?", limit, offset)
        users = get_rows(res)
        txt = f"👤 لیست کاربران (صفحه {page}) – **تعداد کل: {total_users}**\n\n"
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
        kb.append([{"text": "🔙 بازگشت", "callback_data": "admin_return"}])
        await edit_message(chat_id, message_id, txt, reply_markup={"inline_keyboard": kb}, parse_mode="HTML")
        return

    if data == "adm_search_user":
        await execute_db("UPDATE users SET state = 'waiting_for_user_search' WHERE id = ?", user["id"])
        await edit_message(chat_id, message_id, "🔍 شناسه عددی تلگرام کاربر مورد نظر را بفرستید:", reply_markup={"inline_keyboard": [[{"text": "🔙 بازگشت", "callback_data": "adm_manage_users_1"}]]})
        return

    if data.startswith("adm_add_bal_") or data.startswith("adm_sub_bal_"):
        is_addition = "add" in data
        target_tg_id = data.replace("adm_add_bal_", "").replace("adm_sub_bal_", "")
        state_val = f"waiting_for