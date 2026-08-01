            print(f"Error parse update: {str(e)}")
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
from urllib.parse import urlparse
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
        "⚠️ برای فعال‌سازی کامل امکانات ربات، ابتدا در کانال زیر عضو شوید و سپس روی دکمه «عضو شدم» کلیک کنید."
    ),
    "membership_confirmed": "✅ عضویت شما تأیید شد! اکنون می‌توانید از ربات استفاده کنید.",
    "trial_already_used": "⚠️ شما قبلاً از تست رایگان ۱ روزه استفاده کرده‌اید.",
    "trial_activated": "🎁 اشتراک تست ۱ روزه شما با موفقیت فعال شد!",
    "wallet_info": "👛 جزئیات کیف پول شما:\n\n💰 موجودی فعلی: {balance:,} تومان\n👥 تعداد زیرمجموعه‌ها: {ref_count} نفر\n\n🛒 هزینه خرید اشتراک: {price:,} تومان",
    "insufficient_balance": (
        "❌ موجودی حساب شما کافی نیست.\n\n"
        "💰 موجودی شما: {balance:,} تومان\n"
        "💵 قیمت اشتراک {duration} روزه: {price:,} تومان"
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
    "support_contact": "🎧 بخش ارتباط با پشتیبانی:\n\nجهت افزایش دستی موجودی، ارسال انتقاد و یا حل مشکلات فنی پیام دهید:\n\n💬 آیدی پشتیبانی: {support}",
    "support_session_started": "💬 پشتیبانی: پیام خود را ارسال کنید. (برای پایان، /end یا دکمه پایان را بزنید)",
    "support_session_ended": "🔚 جلسه پشتیبانی پایان یافت.",
    "support_forwarded": "پیام از کاربر {user_id}:\n\n{text}",
    "admin_only": "⛔ این بخش فقط برای مدیران در دسترس است.",
    "admin_panel": "🛠 به بخش ادمین خوش آمدید. دستورات مدیریتی را انتخاب کنید:",
    "config_added": "✅ کانفیگ ثبت شد. منتظر کانفیگ بعدی هستیم (یا دکمه خروج را بزنید):",
    "config_add_stopped": "⏹ عملیات افزودن کانفیگ متوقف شد.",
    "broadcast_start": "📢 متن پیام همگانی خود را ارسال کنید (برای لغو، «لغو» را بنویسید):",
    "broadcast_sending": "⏳ در حال ارسال همگانی...",
    "broadcast_done": "✅ پیام همگانی ارسال شد.\nتعداد کل: {success} از {total}",
    "settings_show": (
        "⚙️ تنظیمات داینامیک:\n\n"
        "💰 قیمت سرویس: {price:,} تومان\n"
        "🎁 پاداش دعوت: {reward:,} تومان\n"
        "📢 کانال‌های اجباری: `{channels}`\n"
        "🎧 آیدی پشتیبانی: `{support}`\n"
        "🌐 دامنه ساب‌لینک: `{domain}`"
    ),
    "user_not_found": "❌ کاربر یافت نشد.",
    "user_info": (
        "👤 جزئیات حساب کاربر:\n\n"
        "🆔 آیدی تلگرام: `{tg_id}`\n"
        "💰 موجودی کیف پول: {balance:,} تومان\n"
        "🎁 استفاده از تست رایگان: {trial_status}"
    ),
    "balance_added": "✅ مبلغ {amount:,} تومان به حساب کاربر {target_id} اضافه گردید.",
    "balance_subtracted": "✅ مبلغ {amount:,} تومان از موجودی کاربر {target_id} کسر شد.",
    "setting_updated": "✅ فیلد تنظیمات `{key}` با موفقیت آپدیت شد.",
    "plan_add_step1": "📝 نام پلن را وارد کنید:",
    "plan_add_step2": "💰 قیمت (به تومان) را وارد کنید:",
    "plan_add_step3": "📆 مدت زمان (تعداد روز) را وارد کنید:",
    "plan_add_step4": "👥 حداکثر تعداد کاربر (max_users) را وارد کنید:",
    "plan_add_step5": "📦 تعداد موجود (available_count) را وارد کنید:",
    "plan_added": "✅ پلن «{name}» با موفقیت اضافه شد.",
    "plan_deleted": "🗑 پلن حذف شد.",
    "plan_toggled": "✅ وضعیت پلن تغییر کرد.",
    "no_plans": "هیچ پلنی وجود ندارد.",
    "plan_list_item": "🆔 {id}\n📌 نام: {name}\n💰 قیمت: {price:,} تومان\n📆 مدت: {duration} روز\n👥 max_users: {max_users}\n📦 موجود: {available_count}\n🟢 وضعیت: {status}",
    "choose_plan": "پلن مورد نظر را انتخاب کنید:",
    "purchase_cancelled": "❌ خرید لغو شد.",
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
# 🗄️ مقداردهی اولیه دیتابیس
# ---------------------------------------------------------------------
async def init_database_if_needed():
    initialized = await get_kv("db_initialized")
    if initialized == "true":
        return

    queries = [
        """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id TEXT UNIQUE NOT NULL,
            balance INTEGER DEFAULT 0,
            referred_by TEXT DEFAULT NULL,
            has_used_trial INTEGER DEFAULT 0,
            state TEXT DEFAULT NULL,
            plan_data TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
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
            available_count INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS subscription_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subscription_token TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(subscription_token) REFERENCES subscriptions(token),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );"""
    ]
    
    for q in queries:
        await execute_db(q)

    defaults = {
        "referral_reward": "2000",
        "service_price": "50000",
        "force_channels": "",
        "support_contact": "@support_v2ray",
        "sub_domain": "your-railway-app.up.railway.app",
    }
    for key, val in defaults.items():
        res = await query_db("SELECT value FROM settings WHERE key = ?", key)
        if not get_first_row(res):
            await execute_db("INSERT INTO settings (key, value) VALUES (?, ?)", key, val)

    await put_kv("db_initialized", "true")

# ---------------------------------------------------------------------
# 🧑‍💼 توابع کاربر و ادمین
# ---------------------------------------------------------------------
def is_admin(telegram_id):
    if not ADMIN_IDS:
        return False
    admins = [x.strip() for x in str(ADMIN_IDS).split(",") if x.strip()]
    return str(telegram_id) in admins

async def get_or_create_user(telegram_id, referred_by=None):
    res = await query_db("SELECT * FROM users WHERE telegram_id = ?", str(telegram_id))
    user = get_first_row(res)
    if not user:
        ref_id = None
        if referred_by and str(referred_by) != str(telegram_id):
            ref_res = await query_db("SELECT id FROM users WHERE telegram_id = ?", str(referred_by))
            if get_first_row(ref_res):
                ref_id = str(referred_by)
        if ref_id:
            await execute_db("INSERT INTO users (telegram_id, referred_by) VALUES (?, ?)", str(telegram_id), ref_id)
        else:
            await execute_db("INSERT INTO users (telegram_id) VALUES (?)", str(telegram_id))
        res = await query_db("SELECT * FROM users WHERE telegram_id = ?", str(telegram_id))
        user = get_first_row(res)
    return user

async def check_channel_membership(telegram_id):
    force_channels = await get_setting("force_channels", "")
    if not force_channels:
        return True
    channel = force_channels.split(",")[0].strip()
    if not channel:
        return True
    if not channel.startswith("@") and not channel.startswith("-100"):
        channel = f"@{channel}"
    
    res = await call_telegram("getChatMember", {
        "chat_id": channel,
        "user_id": int(telegram_id)
    })
    if res.get("ok"):
        status = res["result"].get("status")
        if status in ["creator", "administrator", "member"]:
            return True
    return False

async def build_sub_url_async(token):
    domain = await get_setting("sub_domain", "your-railway-app.up.railway.app")
    domain = domain.replace("https://", "").replace("http://", "")
    return f"https://{domain}/sub/{token}"

# ---------------------------------------------------------------------
# 📋 کیبوردهای اینلاین
# ---------------------------------------------------------------------
def get_user_inline_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🎁 تست رایگان", "callback_data": "free_trial"}],
            [{"text": "🛒 خرید سرویس", "callback_data": "buy_service"}],
            [{"text": "👛 کیف پول", "callback_data": "wallet"}],
            [{"text": "📱 سرویس‌های من", "callback_data": "my_services"}],
            [{"text": "👥 دعوت دوستان", "callback_data": "referral"}],
            [{"text": "🎧 پشتیبانی", "callback_data": "support"}],
        ]
    }

def get_admin_inline_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "➕ افزودن کانفیگ", "callback_data": "adm_add_config"}],
            [{"text": "📋 مدیریت کانفیگ‌ها", "callback_data": "adm_manage_configs"}],
            [{"text": "📢 همه‌فرستی", "callback_data": "adm_broadcast"}],
            [{"text": "⚙️ تنظیمات", "callback_data": "adm_settings"}],
            [{"text": "👤 مدیریت کاربران", "callback_data": "adm_manage_users"}],
            [{"text": "📦 مدیریت پلن‌ها", "callback_data": "adm_manage_plans"}],
        ]
    }

def get_plans_inline_keyboard(plans):
    kb = []
    for p in plans:
        kb.append([{"text": f"{p['name']} - {p['price']:,} تومان", "callback_data": f"buy_plan_{p['id']}"}])
    kb.append([{"text": "❌ لغو", "callback_data": "cancel_purchase"}])
    return {"inline_keyboard": kb}

# ---------------------------------------------------------------------
# 🧠 توابع اصلی
# ---------------------------------------------------------------------
async def send_membership_requirement(chat_id):
    force_channels = await get_setting("force_channels", "")
    channel = force_channels.split(",")[0].strip() if force_channels else ""
    if not channel:
        return
    if not channel.startswith("@") and not channel.startswith("-100"):
        channel = f"@{channel}"
    channel_url = f"https://t.me/{channel.replace('@', '')}"
    markup = {
        "inline_keyboard": [
            [{"text": "📢 عضویت در کانال", "url": channel_url}],
            [{"text": "✅ عضو شدم (تایید)", "callback_data": "chk_membership"}]
        ]
    }
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
    price = safe_int(await get_setting("service_price", "50000"))
    msg = STRINGS["wallet_info"].format(balance=user["balance"], ref_count=ref_count, price=price)
    await call_telegram("sendMessage", {"chat_id": chat_id, "text": msg})

async def handle_buy_service(user, chat_id):
    res = await query_db("SELECT * FROM plans WHERE is_active = 1 AND available_count > 0")
    plans = get_rows(res)
    if not plans:
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ هیچ پلن فعالی در حال حاضر موجود نیست."})
        return
    markup = get_plans_inline_keyboard(plans)
    await call_telegram("sendMessage", {
        "chat_id": chat_id,
        "text": "🛒 لطفاً پلن مورد نظر را انتخاب کنید:",
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
            "inline_keyboard": [[{"text": "🖼 نمایش کیوآرکد", "callback_data": f"qr_{s['token']}"}]]
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
    markup = {"inline_keyboard": [[{"text": "🔚 پایان پشتیبانی", "callback_data": "end_support"}]]}
    await call_telegram("sendMessage", {
        "chat_id": chat_id,
        "text": STRINGS["support_session_started"],
        "reply_markup": markup
    })

async def forward_support_message(user, text, chat_id):
    if not ADMIN_IDS:
        return
    admins = [x.strip() for x in str(ADMIN_IDS).split(",") if x.strip()]
    for admin_id in admins:
        await call_telegram("sendMessage", {
            "chat_id": int(admin_id),
            "text": STRINGS["support_forwarded"].format(user_id=user["telegram_id"], text=text)
        })
    await call_telegram("sendMessage", {
        "chat_id": chat_id,
        "text": "✅ پیام شما به پشتیبان‌ها ارسال شد. منتظر پاسخ باشید."
    })

async def create_subscription_from_plan(plan_id, user_id):
    res = await query_db("SELECT * FROM plans WHERE id = ? AND is_active = 1", plan_id)
    plan = get_first_row(res)
    if not plan or plan["available_count"] <= 0:
        return None
    token = uuid.uuid4().hex
    expires_at = (datetime.datetime.utcnow() + datetime.timedelta(days=plan["duration_days"])).strftime("%Y-%m-%d %H:%M:%S")
    await execute_db("INSERT INTO subscriptions (user_id, token, expires_at) VALUES (?, ?, ?)", user_id, token, expires_at)
    await execute_db("UPDATE plans SET available_count = available_count - 1 WHERE id = ?", plan_id)
    await execute_db("INSERT INTO subscription_usage (subscription_token, user_id) VALUES (?, ?)", token, user_id)
    return token

# ---------------------------------------------------------------------
# 💬 مدیریت state ها
# ---------------------------------------------------------------------
async def handle_state(user, state, text, chat_id, is_admin_user):
    if text in ["❌ خروج / اتمام ارسال", "لغو", "/cancel"]:
        await execute_db("UPDATE users SET state = NULL, plan_data = NULL WHERE id = ?", user["id"])
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": "عملیات لغو شد."})
        if is_admin_user:
            await show_admin_panel(chat_id)
        else:
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["start_welcome"], "reply_markup": get_user_inline_keyboard()})
        return True

    if is_admin_user:
        if state == "waiting_for_config":
            await execute_db("INSERT INTO configs (config_text) VALUES (?)", text)
            await delete_kv("cached_configs_payload")
            markup = {"inline_keyboard": [[{"text": "❌ خروج", "callback_data": "adm_stop_config"}]]}
            await call_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": STRINGS["config_added"],
                "reply_markup": markup
            })
            return True

        if state == "waiting_for_broadcast":
            await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])
            all_users_res = await query_db("SELECT telegram_id FROM users")
            all_users = get_rows(all_users_res)
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["broadcast_sending"]})
            success = 0
            for u in all_users:
                res = await call_telegram("sendMessage", {
                    "chat_id": int(u["telegram_id"]),
                    "text": text
                })
                if res.get("ok"):
                    success += 1
                await asyncio.sleep(0.05)
            await call_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": STRINGS["broadcast_done"].format(success=success, total=len(all_users)),
                "reply_markup": get_admin_inline_keyboard()
            })
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
                balance=target_user["balance"],
                trial_status="بله" if target_user["has_used_trial"] else "خیر"
            )
            markup = {
                "inline_keyboard": [
                    [{"text": "➕ افزایش موجودی", "callback_data": f"adm_add_bal_{target_user['telegram_id']}"},
                     {"text": "➖ کاهش موجودی", "callback_data": f"adm_sub_bal_{target_user['telegram_id']}"}]
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

        if state.startswith("waiting_setting_"):
            setting_key = state.replace("waiting_setting_", "")
            await set_setting(setting_key, text.strip())
            await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])
            await call_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": STRINGS["setting_updated"].format(key=setting_key),
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
                    await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ حداکثر کاربر باید عدد مثبت باشد:"})
                    return True
                plan_data["max_users"] = max_users
                await execute_db("UPDATE users SET state = 'waiting_plan_available', plan_data = ? WHERE id = ?", json.dumps(plan_data), user["id"])
                await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["plan_add_step5"]})
                return True
            elif step == "available":
                avail = safe_int(text)
                if avail <= 0:
                    await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ تعداد موجود باید عدد مثبت باشد:"})
                    return True
                plan_data["available_count"] = avail
                name = plan_data.get("name", "بدون نام")
                price = plan_data.get("price", 0)
                duration = plan_data.get("duration_days", 0)
                max_users = plan_data.get("max_users", 1)
                available_count = plan_data.get("available_count", 1)
                await execute_db("""
                    INSERT INTO plans (name, price, duration_days, max_users, available_count, is_active)
                    VALUES (?, ?, ?, ?, ?, 1)
                """, name, price, duration, max_users, available_count)
                await execute_db("UPDATE users SET state = NULL, plan_data = NULL WHERE id = ?", user["id"])
                await call_telegram("sendMessage", {
                    "chat_id": chat_id,
                    "text": STRINGS["plan_added"].format(name=name),
                    "reply_markup": get_admin_inline_keyboard()
                })
                return True

    if state and state.startswith("support_session_"):
        await forward_support_message(user, text, chat_id)
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

    user = await get_or_create_user(telegram_id)
    is_admin_user = is_admin(telegram_id)

    await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id})

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
                "reply_markup": get_admin_inline_keyboard() if is_admin_user else get_user_inline_keyboard()
            })
        else:
            await call_telegram("answerCallbackQuery", {
                "callback_query_id": cq_id,
                "text": "❌ شما هنوز عضو کانال نشده‌اید!",
                "show_alert": True
            })
        return

    if data == "free_trial": return await handle_free_trial(user, chat_id)
    if data == "wallet": return await handle_wallet(user, chat_id)
    if data == "buy_service": return await handle_buy_service(user, chat_id)
    if data == "my_services": return await handle_my_services(user, chat_id)
    if data == "referral": return await handle_referral(user, chat_id)
    if data == "support": return await handle_support_start(user, chat_id)
    
    if data == "end_support":
        await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["support_session_ended"]})
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

    if data.startswith("buy_plan_"):
        plan_id = int(data.replace("buy_plan_", ""))
        res = await query_db("SELECT * FROM plans WHERE id = ? AND is_active = 1", plan_id)
        plan = get_first_row(res)
        if not plan:
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": "❌ پلن مورد نظر فعال نیست یا موجودی تمام شده."})
            return
        price = plan["price"]
        if user["balance"] < price:
            msg = STRINGS["insufficient_balance"].format(balance=user["balance"], price=price, duration=plan["duration_days"])
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

    if data == "cancel_purchase":
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["purchase_cancelled"]})
        return

    if not is_admin_user:
        await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": STRINGS["admin_only"], "show_alert": True})
        return

    if data == "adm_add_config":
        await execute_db("UPDATE users SET state = 'waiting_for_config' WHERE id = ?", user["id"])
        await call_telegram("sendMessage", {
            "chat_id": chat_id,
            "text": "📥 لطفا اولین کانفیگ خود را ارسال کنید.\nبرای پایان، دکمه زیر را بزنید:",
            "reply_markup": {"inline_keyboard": [[{"text": "❌ خروج", "callback_data": "adm_stop_config"}]]}
        })
        return

    if data == "adm_stop_config":
        await execute_db("UPDATE users SET state = NULL WHERE id = ?", user["id"])
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["config_add_stopped"], "reply_markup": get_admin_inline_keyboard()})
        return

    if data == "adm_manage_configs":
        cfg_res = await query_db("SELECT id, config_text, is_active FROM configs ORDER BY id DESC LIMIT 10")
        configs = get_rows(cfg_res)
        if not configs:
            await call_telegram("sendMessage", {"chat_id": chat_id, "text": "هیچ کانفیگی موجود نیست."})
            return
        for c in configs:
            status_emoji = "🟢 فعال" if c["is_active"] else "🔴 غیرفعال"
            preview = c["config_text"][:40] + "..."
            markup = {
                "inline_keyboard": [
                    [{"text": f"تغییر وضعیت ({status_emoji})", "callback_data": f"adm_cfg_toggle_{c['id']}"},
                     {"text": "❌ حذف", "callback_data": f"adm_cfg_del_{c['id']}"}]
                ]
            }
            await call_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": f"شناسه کانفیگ: {c['id']}\n`{preview}`",
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

    if data.startswith("adm_cfg_del_"):
        cfg_id = data.replace("adm_cfg_del_", "")
        await execute_db("DELETE FROM configs WHERE id = ?", cfg_id)
        await delete_kv("cached_configs_payload")
        await call_telegram("answerCallbackQuery", {"callback_query_id": cq_id, "text": "🗑 کانفیگ حذف شد."})
        return

    if data == "adm_broadcast":
        await execute_db("UPDATE users SET state = 'waiting_for_broadcast' WHERE id = ?", user["id"])
        await call_telegram("sendMessage", {"chat_id": chat_id, "text": STRINGS["broadcast_start"]})
        return

    if data == "adm_settings":
        price = await get_setting("service_price", "50000")
        reward = await get_setting("referral_reward", "2000")
        channels = await get_setting("force_channels", "غیرفعال")
        support = await get_setting("support_contact", "ثبت نشده")
        domain = await get_setting("sub_domain", "your-railway-app.up.railway.app")
        settings_text = STRINGS["settings_show"].format(
            price=safe_int(price), reward=safe_int(reward), channels=channels, support=support, domain=domain
        )
        markup = {
            "inline_keyboard": [
                [{"text": "✏️ ویرایش قیمت سرویس", "callback_data": "adm_set_service_price"},
                 {"text": "✏️ ویرایش پاداش دعوت", "callback_data": "adm_set_referral_reward"}],
                [{"text": "✏️ ویرایش کانال‌های اجباری", "callback_data": "adm_set_force_channels"},
                 {"text": "✏️ ویرایش آیدی پشتیبانی", "callback_data": "adm_set_support_contact"}],
                [{"text": "✏️ ویرایش دامنه ساب‌لینک", "callback_data": "adm_set_sub_domain"}]
            ]
        }
        await call_telegram("sendMessage", {
            "chat_id": chat_id,
            "text": settings_text,
            "parse_mode": "Markdown",
            "reply_markup": markup
        })
        return

    if data.startswith("adm_set_"):
        setting_key = data.replace("adm_set_", "")
        await execute_db("UPDATE users SET state = ? WHERE id = ?", f"waiting_setting_{setting_key}", user["id"])
        await call_telegram("sendMessage", {
            "chat_id": chat_id,
            "text": f"✏️ لطفاً مقدار جدید برای فیلد `{setting_key}` را بفرستید:\n(یا بنویسید: لغو)",
            "parse_mode": "Markdown"
        })
        return

    if data == "adm_manage_users":
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
                id=p["id"], name=p["name"], price=p["price"], duration=p["duration_days"],
                max_users=p["max_users"], available_count=p["available_count"], status=status
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
        "reply_markup": {"inline_keyboard": [[{"text": "➕ افزودن پلن جدید", "callback_data": "adm_add_plan"}]]}
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

    user = await get_or_create_user(telegram_id, referred_by)
    is_admin_user = is_admin(telegram_id)

    if not await check_channel_membership(telegram_id) and text != "/start":
        await send_membership_requirement(chat_id)
        return

    state = user.get("state")
    if state:
        if await handle_state(user, state, text, chat_id, is_admin_user):
            return

    if text == "/start":
        await credit_referrer_if_pending(user, chat_id)
        if is_admin_user:
            await show_admin_panel(chat_id)
        else:
            await call_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": STRINGS["start_welcome"],
                "reply_markup": get_user_inline_keyboard()
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