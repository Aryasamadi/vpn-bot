import json
import base64
import uuid
import datetime
import js
from js import Response, Headers, fetch
from pyodide.ffi import to_js

# =====================================================================
# ⚙️ تنظیمات اصلی سیستم - حتماً این دو خط را با مقادیر خودت پر کن
# =====================================================================
FALLBACK_BOT_TOKEN = "8816894724:AAGqVWwWmWkP5KrbtEEa8S7VhIhxY92aXRc"
FALLBACK_ADMIN_IDS = "813473008"
# =====================================================================

# ---------------------------------------------------------------------
# متدهای کمکی جهت اجرای کوئری‌های دیتابیس D1
# ---------------------------------------------------------------------
async def query_db(db, sql, *args):
    try:
        stmt = db.prepare(sql)
        if args:
            stmt = stmt.bind(*args)
        res = await stmt.all()
        return res.to_py()
    except Exception as e:
        print(f"D1 Query Error: {str(e)}")
        return {"results": [], "success": False, "error": str(e)}

async def execute_db(db, sql, *args):
    try:
        stmt = db.prepare(sql)
        if args:
            stmt = stmt.bind(*args)
        res = await stmt.run()
        return res.to_py()
    except Exception as e:
        print(f"D1 Execute Error: {str(e)}")
        return {"success": False, "error": str(e)}

def get_rows(db_res):
    if db_res and isinstance(db_res, dict) and db_res.get("success") and "results" in db_res:
        return db_res["results"]
    return []

def get_first_row(db_res):
    rows = get_rows(db_res)
    return rows[0] if rows else None

# ---------------------------------------------------------------------
# خودکارسازی ساخت جداول دیتابیس در اولین اجرا (Auto Installer)
# ---------------------------------------------------------------------
async def init_database_if_needed(env):
    try:
        if hasattr(env, "KV") and env.KV:
            initialized = await env.KV.get("db_initialized")
            if initialized == "true":
                return
    except Exception:
        pass
        
    queries = [
        """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id TEXT UNIQUE NOT NULL,
            balance INTEGER DEFAULT 0,
            referred_by TEXT DEFAULT NULL,
            has_used_trial BOOLEAN DEFAULT 0,
            state TEXT DEFAULT NULL,
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
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );""",
        "INSERT OR IGNORE INTO settings (key, value) VALUES ('referral_reward', '2000');",
        "INSERT OR IGNORE INTO settings (key, value) VALUES ('service_price', '50000');",
        "INSERT OR IGNORE INTO settings (key, value) VALUES ('force_channel', '');",
        "INSERT OR IGNORE INTO settings (key, value) VALUES ('support_contact', '@support_v2ray');"
    ]
    
    if hasattr(env, "DB") and env.DB:
        for q in queries:
            await execute_db(env.DB, q)
            
    try:
        if hasattr(env, "KV") and env.KV:
            await env.KV.put("db_initialized", "true")
    except Exception:
        pass

# ---------------------------------------------------------------------
# توابع ارتباط با تلگرام
# ---------------------------------------------------------------------
async def call_telegram(token, method, payload):
    url = f"https://api.telegram.org/bot{token}/{method}"
    headers = Headers.new()
    headers.set("Content-Type", "application/json")
    
    options = {
        "method": "POST",
        "headers": headers,
        "body": json.dumps(payload)
    }
    js_options = to_js(options, dict_converter=js.Object.fromEntries)
    try:
        response = await fetch(url, js_options)
        res_text = await response.text()
        return json.loads(res_text)
    except Exception as e:
        return {"ok": False, "description": str(e)}

def is_admin(telegram_id, env):
    admin_str = getattr(env, "ADMIN_IDS", FALLBACK_ADMIN_IDS)
    if not admin_str:
        admin_str = FALLBACK_ADMIN_IDS
    admins = [x.strip() for x in str(admin_str).split(",") if x.strip()]
    return str(telegram_id) in admins

async def get_or_create_user(telegram_id, env, referred_by=None):
    res = await query_db(env.DB, "SELECT * FROM users WHERE telegram_id = ?", str(telegram_id))
    user = get_first_row(res)
    
    if not user:
        ref_id = None
        if referred_by and str(referred_by) != str(telegram_id):
            ref_res = await query_db(env.DB, "SELECT id FROM users WHERE telegram_id = ?", str(referred_by))
            if get_first_row(ref_res):
                ref_id = str(referred_by)
                
        if ref_id is not None:
            await execute_db(env.DB, "INSERT INTO users (telegram_id, referred_by) VALUES (?, ?)", str(telegram_id), ref_id)
        else:
            await execute_db(env.DB, "INSERT INTO users (telegram_id) VALUES (?)", str(telegram_id))
            
        res = await query_db(env.DB, "SELECT * FROM users WHERE telegram_id = ?", str(telegram_id))
        user = get_first_row(res)
    return user

async def check_channel_membership(env, telegram_id):
    force_channel = None
    if hasattr(env, "KV") and env.KV:
        try:
            force_channel = await env.KV.get("setting_force_channel")
        except Exception:
            pass

    if force_channel is None:
        res = await query_db(env.DB, "SELECT value FROM settings WHERE key = 'force_channel'")
        row = get_first_row(res)
        force_channel = row["value"] if row else ""
        if hasattr(env, "KV") and env.KV:
            try:
                await env.KV.put("setting_force_channel", force_channel, expirationTtl=300)
            except Exception:
                pass
        
    if not force_channel or force_channel.strip() == "":
        return True
        
    channel = force_channel.strip()
    if not channel.startswith("@") and not channel.startswith("-100"):
        channel = f"@{channel}"
        
    bot_token = getattr(env, "BOT_TOKEN", FALLBACK_BOT_TOKEN)
    res = await call_telegram(bot_token, "getChatMember", {
        "chat_id": channel,
        "user_id": int(telegram_id)
    })
    
    if res.get("ok"):
        status = res["result"].get("status")
        if status in ["creator", "administrator", "member"]:
            return True
    return False

# ---------------------------------------------------------------------
# تعریف کیبوردها
# ---------------------------------------------------------------------
def get_user_keyboard(is_admin_user=False):
    keyboard = [
        [{"text": "🎁 تست رایگان (Free Trial)"}, {"text": "🛒 خرید سرویس (Buy Service)"}],
        [{"text": "👛 کیف پول (Wallet)"}, {"text": "📱 سرویس‌های من (My Services)"}],
        [{"text": "👥 دعوت دوستان (Referral)"}, {"text": "🎧 پشتیبانی"}],
    ]
    if is_admin_user:
        keyboard.append([{"text": "🔑 پنل مدیریت (Admin Panel)"}])
    return {"keyboard": keyboard, "resize_keyboard": True}

def get_admin_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "➕ افزودن کانفیگ جدید", "callback_data": "adm_add_config"}, {"text": "📋 مدیریت کانفیگ‌ها", "callback_data": "adm_manage_configs"}],
            [{"text": "📢 همه‌فرستی (Broadcast)", "callback_data": "adm_broadcast"}, {"text": "⚙️ تنظیمات سیستم", "callback_data": "adm_settings"}],
            [{"text": "👤 مدیریت کاربران", "callback_data": "adm_manage_users"}]
        ]
    }

# ---------------------------------------------------------------------
# موتور پردازش منطق ربات (Webhook Processor)
# ---------------------------------------------------------------------
async def process_update(update, env):
    bot_token = getattr(env, "BOT_TOKEN", FALLBACK_BOT_TOKEN)
    
    if "message" in update:
        message = update["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "").strip()
        from_user = message.get("from", {})
        telegram_id = str(from_user.get("id", ""))
        
        if not telegram_id:
            return
            
        referred_by = None
        if text.startswith("/start ") and len(text.split()) > 1:
            referred_by = text.split()[1]
            
        user = await get_or_create_user(telegram_id, env, referred_by)
        is_admin_user = is_admin(telegram_id, env)
        
        is_member = await check_channel_membership(env, telegram_id)
        if not is_member and text != "✅ عضو شدم (تایید)":
            await send_membership_requirement(env, chat_id)
            return
            
        state = user.get("state")
        if state:
            if await handle_user_state(env, user, text, chat_id, is_admin_user):
                return
                
        if text.startswith("/start"):
            welcome_msg = (
                "👋 به ربات هوشمند مدیریت ساب‌لینک خوش آمدید!\n\n"
                "با استفاده از گزینه‌های زیر می‌توانید حساب خود را مدیریت کرده و ساب‌لینک‌های پرسرعت دریافت کنید."
            )
            await call_telegram(bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": welcome_msg,
                "reply_markup": get_user_keyboard(is_admin_user)
            })
            
        elif text == "🎁 تست رایگان (Free Trial)":
            await handle_free_trial_request(env, user, chat_id)
            
        elif text == "👛 کیف پول (Wallet)":
            await handle_wallet_request(env, user, chat_id)
            
        elif text == "🛒 خرید سرویس (Buy Service)":
            await handle_buy_service_request(env, user, chat_id)
            
        elif text == "📱 سرویس‌های من (My Services)":
            await handle_my_services_request(env, user, chat_id)
            
        elif text == "👥 دعوت دوستان (Referral)":
            await handle_referral_request(env, user, chat_id)
            
        elif text == "🎧 پشتیبانی":
            await handle_support_request(env, chat_id)
            
        elif text == "🔑 پنل مدیریت (Admin Panel)" and is_admin_user:
            await call_telegram(bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": "🛠 به بخش ادمین خوش آمدید. دستورات مدیریتی را انتخاب کنید:",
                "reply_markup": get_admin_keyboard()
            })
            
    elif "callback_query" in update:
        callback_query = update["callback_query"]
        cq_id = callback_query["id"]
        chat_id = callback_query["message"]["chat"]["id"]
        data = callback_query.get("data", "")
        from_user = callback_query.get("from", {})
        telegram_id = str(from_user.get("id", ""))
        
        user = await get_or_create_user(telegram_id, env)
        is_admin_user = is_admin(telegram_id, env)
        
        await handle_callback(env, user, cq_id, chat_id, data, is_admin_user)

# ---------------------------------------------------------------------
# منطق توابع ربات
# ---------------------------------------------------------------------
async def send_membership_requirement(env, chat_id):
    force_channel = ""
    if hasattr(env, "KV") and env.KV:
        try:
            force_channel = await env.KV.get("setting_force_channel")
        except Exception:
            pass

    if not force_channel:
        res = await query_db(env.DB, "SELECT value FROM settings WHERE key = 'force_channel'")
        row = get_first_row(res)
        force_channel = row["value"] if row else ""
        if hasattr(env, "KV") and env.KV:
            try:
                await env.KV.put("setting_force_channel", force_channel, expirationTtl=300)
            except Exception:
                pass
        
    channel_url = f"https://t.me/{force_channel.replace('@', '')}"
    markup = {
        "inline_keyboard": [
            [{"text": "📢 عضویت در کانال", "url": channel_url}],
            [{"text": "✅ عضو شدم (تایید)", "callback_data": "chk_membership"}]
        ]
    }
    bot_token = getattr(env, "BOT_TOKEN", FALLBACK_BOT_TOKEN)
    await call_telegram(bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": "⚠️ برای فعال‌سازی کامل امکانات ربات، ابتدا وارد کانال زیر شوید و سپس روی دکمه عضو شدم کلیک کنید.",
        "reply_markup": markup
    })

async def credit_referrer_if_pending(env, user, chat_id):
    ref_id = user.get("referred_by")
    if ref_id and not str(ref_id).endswith("_rewarded"):
        reward_val = None
        if hasattr(env, "KV") and env.KV:
            try:
                reward_val = await env.KV.get("setting_referral_reward")
            except Exception:
                pass

        if reward_val is None:
            res = await query_db(env.DB, "SELECT value FROM settings WHERE key = 'referral_reward'")
            row = get_first_row(res)
            reward_val = row["value"] if row else "2000"
            if hasattr(env, "KV") and env.KV:
                try:
                    await env.KV.put("setting_referral_reward", reward_val, expirationTtl=300)
                except Exception:
                    pass
            
        try:
            reward = int(reward_val)
        except ValueError:
            reward = 2000
            
        await execute_db(env.DB, "UPDATE users SET balance = balance + ? WHERE telegram_id = ?", reward, ref_id)
        
        bot_token = getattr(env, "BOT_TOKEN", FALLBACK_BOT_TOKEN)
        await call_telegram(bot_token, "sendMessage", {
            "chat_id": int(ref_id),
            "text": f"🎉 یکی از کاربران با لینک دعوت شما عضو شد و مبلغ {reward:,} تومان به موجودی شما افزوده گردید!"
        })
        
        new_ref_status = f"{ref_id}_rewarded"
        await execute_db(env.DB, "UPDATE users SET referred_by = ? WHERE id = ?", new_ref_status, user["id"])

async def handle_user_state(env, user, text, chat_id, is_admin_user):
    state = user["state"]
    bot_token = getattr(env, "BOT_TOKEN", FALLBACK_BOT_TOKEN)
    
    if text in ["❌ خروج / اتمام ارسال", "لغو"]:
        await execute_db(env.DB, "UPDATE users SET state = NULL WHERE id = ?", user["id"])
        await call_telegram(bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "عملیات لغو شد.",
            "reply_markup": get_user_keyboard(is_admin_user)
        })
        return True

    if is_admin_user:
        if state == "waiting_for_config":
            await execute_db(env.DB, "INSERT INTO configs (config_text) VALUES (?)", text)
            if hasattr(env, "KV") and env.KV:
                try:
                    await env.KV.delete("cached_configs_payload")
                except Exception:
                    pass
            
            markup = {
                "inline_keyboard": [[{"text": "❌ خروج / اتمام ارسال", "callback_data": "adm_stop_config"}]]
            }
            await call_telegram(bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": "✅ کانفیگ ثبت شد. منتظر کانفیگ بعدی هستیم (یا دکمه خروج را بزنید):",
                "reply_markup": markup
            })
            return True
            
        elif state == "waiting_for_broadcast":
            await execute_db(env.DB, "UPDATE users SET state = NULL WHERE id = ?", user["id"])
            all_users_res = await query_db(env.DB, "SELECT telegram_id FROM users")
            all_users = get_rows(all_users_res)
            
            await call_telegram(bot_token, "sendMessage", {"chat_id": chat_id, "text": "⏳ در حال ارسال همگانی..."})
            
            success = 0
            for u in all_users:
                res = await call_telegram(bot_token, "sendMessage", {
                    "chat_id": int(u["telegram_id"]),
                    "text": text
                })
                if res.get("ok"):
                    success += 1
            
            await call_telegram(bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": f"✅ پیام همگانی ارسال شد.\nتعداد کل: {success} از {len(all_users)}",
                "reply_markup": get_user_keyboard(is_admin_user)
            })
            return True
            
        elif state == "waiting_for_user_search":
            res = await query_db(env.DB, "SELECT * FROM users WHERE telegram_id = ?", text.strip())
            target_user = get_first_row(res)
            if not target_user:
                await call_telegram(bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "❌ کاربر یافت نشد. مجدداً تلاش کنید یا بنویسید: لغو"
                })
                return True
                
            await execute_db(env.DB, "UPDATE users SET state = NULL WHERE id = ?", user["id"])
            
            user_info = (
                f"👤 جزئیات حساب کاربر:\n\n"
                f"🆔 آیدی تلگرام: `{target_user['telegram_id']}`\n"
                f"💰 موجودی کیف پول: {target_user['balance']:,} تومان\n"
                f"🎁 از تست رایگان استفاده کرده؟ {'بله' if target_user['has_used_trial'] else 'خیر'}\n"
            )
            markup = {
                "inline_keyboard": [
                    [
                        {"text": "➕ افزایش موجودی", "callback_data": f"adm_add_bal_{target_user['telegram_id']}"},
                        {"text": "➖ کاهش موجودی", "callback_data": f"adm_sub_bal_{target_user['telegram_id']}"}
                    ]
                ]
            }
            await call_telegram(bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": user_info,
                "parse_mode": "Markdown",
                "reply_markup": markup
            })
            return True
            
        elif state.startswith("waiting_for_add_"):
            target_id = state.replace("waiting_for_add_", "")
            try:
                amount = int(text.strip())
            except ValueError:
                await call_telegram(bot_token, "sendMessage", {"chat_id": chat_id, "text": "❌ لطفاً فقط عدد وارد کنید:"})
                return True
                
            await execute_db(env.DB, "UPDATE users SET balance = balance + ?, state = NULL WHERE telegram_id = ?", amount, target_id)
            await call_telegram(bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": f"✅ مبلغ {amount:,} تومان به حساب کاربر {target_id} اضافه گردید.",
                "reply_markup": get_user_keyboard(is_admin_user)
            })
            await call_telegram(bot_token, "sendMessage", {
                "chat_id": int(target_id),
                "text": f"💰 کیف پول شما به مقدار {amount:,} تومان توسط مدیر شارژ شد."
            })
            return True
            
        elif state.startswith("waiting_for_sub_"):
            target_id = state.replace("waiting_for_sub_", "")
            try:
                amount = int(text.strip())
            except ValueError:
                await call_telegram(bot_token, "sendMessage", {"chat_id": chat_id, "text": "❌ لطفاً فقط عدد وارد کنید:"})
                return True
                
            await execute_db(env.DB, "UPDATE users SET balance = CASE WHEN balance - ? < 0 THEN 0 ELSE balance - ? END, state = NULL WHERE telegram_id = ?", amount, amount, target_id)
            await call_telegram(bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": f"✅ مبلغ {amount:,} تومان از موجودی کاربر کسر شد.",
                "reply_markup": get_user_keyboard(is_admin_user)
            })
            return True
            
        elif state.startswith("waiting_setting_"):
            setting_key = state.replace("waiting_setting_", "")
            await execute_db(env.DB, "UPDATE users SET state = NULL WHERE id = ?", user["id"])
            await execute_db(env.DB, "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", setting_key, text.strip())
            if hasattr(env, "KV") and env.KV:
                try:
                    await env.KV.put(f"setting_{setting_key}", text.strip(), expirationTtl=300)
                except Exception:
                    pass
            
            await call_telegram(bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": f"✅ فیلد تنظیمات `{setting_key}` با موفقیت آپدیت شد.",
                "parse_mode": "Markdown",
                "reply_markup": get_user_keyboard(is_admin_user)
            })
            return True
            
    return False

# ---------------------------------------------------------------------
# پردازش دکمه‌های شیشه‌ای (Callbacks)
# ---------------------------------------------------------------------
async def handle_callback(env, user, cq_id, chat_id, data, is_admin_user):
    bot_token = getattr(env, "BOT_TOKEN", FALLBACK_BOT_TOKEN)
    telegram_id = user["telegram_id"]
    
    if data == "chk_membership":
        is_member = await check_channel_membership(env, telegram_id)
        if is_member:
            await credit_referrer_if_pending(env, user, chat_id)
            await call_telegram(bot_token, "answerCallbackQuery", {"callback_query_id": cq_id, "text": "✅ عضویت تایید شد!"})
            await call_telegram(bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": "🎉 به ربات خوش آمدید! هم اکنون دسترسی فعال است.",
                "reply_markup": get_user_keyboard(is_admin_user)
            })
        else:
            await call_telegram(bot_token, "answerCallbackQuery", {
                "callback_query_id": cq_id,
                "text": "❌ شما هنوز عضو کانال نشده‌اید!",
                "show_alert": True
            })
            
    elif data.startswith("qr_"):
        token = data.replace("qr_", "")
        sub_res = await query_db(env.DB, "SELECT * FROM subscriptions WHERE token = ?", token)
        sub = get_first_row(sub_res)
        if sub:
            domain_res = await query_db(env.DB, "SELECT value FROM settings WHERE key = 'sub_domain'")
            domain_row = get_first_row(domain_res)
            domain = domain_row["value"] if domain_row else "your-worker.workers.dev"
            
            sub_url = f"https://{domain}/sub/{token}"
            qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={sub_url}"
            
            await call_telegram(bot_token, "answerCallbackQuery", {"callback_query_id": cq_id})
            await call_telegram(bot_token, "sendPhoto", {
                "chat_id": chat_id,
                "photo": qr_url,
                "caption": f"📱 کیوآرکد اتصال شما:\n\n`{sub_url}`",
                "parse_mode": "Markdown"
            })
        else:
            await call_telegram(bot_token, "answerCallbackQuery", {"callback_query_id": cq_id, "text": "❌ اشتراک یافت نشد.", "show_alert": True})

    elif is_admin_user:
        if data == "adm_add_config":
            await execute_db(env.DB, "UPDATE users SET state = 'waiting_for_config' WHERE id = ?", user["id"])
            await call_telegram(bot_token, "answerCallbackQuery", {"callback_query_id": cq_id})
            await call_telegram(bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": "📥 لطفا اولین کانفیگ خود را ارسال کنید.\nبرای پایان حالت ارسال دسته جمعی، روی دکمه زیر کلیک کنید:",
                "reply_markup": {
                    "inline_keyboard": [[{"text": "❌ خروج / اتمام ارسال", "callback_data": "adm_stop_config"}]]
                }
            })
            
        elif data == "adm_stop_config":
            await execute_db(env.DB, "UPDATE users SET state = NULL WHERE id = ?", user["id"])
            await call_telegram(bot_token, "answerCallbackQuery", {"callback_query_id": cq_id, "text": "عملیات متوقف شد."})
            await call_telegram(bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": "⚙️ پنل اصلی مدیریت فعال شد:",
                "reply_markup": get_user_keyboard(is_admin_user)
            })
            
        elif data == "adm_manage_configs":
            cfg_res = await query_db(env.DB, "SELECT id, config_text, is_active FROM configs ORDER BY id DESC LIMIT 10")
            configs = get_rows(cfg_res)
            
            if not configs:
                await call_telegram(bot_token, "answerCallbackQuery", {"callback_query_id": cq_id, "text": "هیچ کانفیگی موجود نیست.", "show_alert": True})
                return
                
            await call_telegram(bot_token, "answerCallbackQuery", {"callback_query_id": cq_id})
            for c in configs:
                status_emoji = "🟢 فعال" if c["is_active"] else "🔴 غیرفعال"
                preview = c["config_text"][:40] + "..."
                markup = {
                    "inline_keyboard": [
                        [
                            {"text": f"تغییر وضعیت ({status_emoji})", "callback_data": f"adm_cfg_toggle_{c['id']}"},
                            {"text": "❌ حذف", "callback_data": f"adm_cfg_del_{c['id']}"}
                        ]
                    ]
                }
                await call_telegram(bot_token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": f"شناسه کانفیگ: {c['id']}\n`{preview}`",
                    "parse_mode": "Markdown",
                    "reply_markup": markup
                })
                
        elif data.startswith("adm_cfg_toggle_"):
            cfg_id = data.replace("adm_cfg_toggle_", "")
            cfg_res = await query_db(env.DB, "SELECT is_active FROM configs WHERE id = ?", cfg_id)
            cfg = get_first_row(cfg_res)
            if cfg:
                new_state = 0 if cfg["is_active"] else 1
                await execute_db(env.DB, "UPDATE configs SET is_active = ? WHERE id = ?", new_state, cfg_id)
                if hasattr(env, "KV") and env.KV:
                    try:
                        await env.KV.delete("cached_configs_payload")
                    except Exception:
                        pass
                await call_telegram(bot_token, "answerCallbackQuery", {"callback_query_id": cq_id, "text": "✅ تغییر وضعیت انجام شد."})
                
        elif data.startswith("adm_cfg_del_"):
            cfg_id = data.replace("adm_cfg_del_", "")
            await execute_db(env.DB, "DELETE FROM configs WHERE id = ?", cfg_id)
            if hasattr(env, "KV") and env.KV:
                try:
                    await env.KV.delete("cached_configs_payload")
                except Exception:
                    pass
            await call_telegram(bot_token, "answerCallbackQuery", {"callback_query_id": cq_id, "text": "🗑 کانفیگ حذف شد."})
            
        elif data == "adm_broadcast":
            await execute_db(env.DB, "UPDATE users SET state = 'waiting_for_broadcast' WHERE id = ?", user["id"])
            await call_telegram(bot_token, "answerCallbackQuery", {"callback_query_id": cq_id})
            await call_telegram(bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": "📢 متن پیام خود را ارسال کنید (برای لغو بنویسید: لغو):"
            })
            
        elif data == "adm_settings":
            await call_telegram(bot_token, "answerCallbackQuery", {"callback_query_id": cq_id})
            price = "50000"
            reward = "2000"
            channel = "غیرفعال"
            support = "ثبت نشده"
            
            if hasattr(env, "KV") and env.KV:
                try:
                    price = await env.KV.get("setting_service_price") or "50000"
                    reward = await env.KV.get("setting_referral_reward") or "2000"
                    channel = await env.KV.get("setting_force_channel") or "غیرفعال"
                    support = await env.KV.get("setting_support_contact") or "ثبت نشده"
                except Exception:
                    pass
            
            settings_text = (
                f"⚙️ تنظیمات داینامیک کلودفلر:\n\n"
                f"💰 قیمت سرویس: {int(price):,} تومان\n"
                f"🎁 پاداش دعوت: {int(reward):,} تومان\n"
                f"📢 کانال اجباری: `{channel}`\n"
                f"🎧 آیدی پشتیبانی: `{support}`"
            )
            markup = {
                "inline_keyboard": [
                    [{"text": "✏️ ویرایش قیمت سرویس", "callback_data": "adm_set_service_price"}, {"text": "✏️ ویرایش پاداش دعوت", "callback_data": "adm_set_referral_reward"}],
                    [{"text": "✏️ ویرایش کانال اجباری", "callback_data": "adm_set_force_channel"}, {"text": "✏️ ویرایش آیدی پشتیبانی", "callback_data": "adm_set_support_contact"}],
                ]
            }
            await call_telegram(bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": settings_text,
                "parse_mode": "Markdown",
                "reply_markup": markup
            })
            
        elif data.startswith("adm_set_"):
            setting_key = data.replace("adm_set_", "")
            await execute_db(env.DB, "UPDATE users SET state = ? WHERE id = ?", f"waiting_setting_{setting_key}", user["id"])
            await call_telegram(bot_token, "answerCallbackQuery", {"callback_query_id": cq_id})
            await call_telegram(bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": f"✏️ لطفاً مقدار جدید برای فیلد `{setting_key}` را بفرستید:\n(یا بنویسید: لغو)",
                "parse_mode": "Markdown"
            })
            
        elif data == "adm_manage_users":
            await execute_db(env.DB, "UPDATE users SET state = 'waiting_for_user_search' WHERE id = ?", user["id"])
            await call_telegram(bot_token, "answerCallbackQuery", {"callback_query_id": cq_id})
            await call_telegram(bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": "🔍 شناسه عددی تلگرام کاربر مورد نظر را بفرستید:"
            })
            
        elif data.startswith("adm_add_bal_") or data.startswith("adm_sub_bal_"):
            is_addition = "add" in data
            target_tg_id = data.replace("adm_add_bal_", "").replace("adm_sub_bal_", "")
            state_val = f"waiting_for_add_{target_tg_id}" if is_addition else f"waiting_for_sub_{target_tg_id}"
            
            await execute_db(env.DB, "UPDATE users SET state = ? WHERE id = ?", state_val, user["id"])
            await call_telegram(bot_token, "answerCallbackQuery", {"callback_query_id": cq_id})
            
            action_text = "افزایش" if is_addition else "کاهش"
            await call_telegram(bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": f"💵 میزان شارژ مایل به {action_text} (به تومان) را بفرستید:"
            })

# ---------------------------------------------------------------------
# فرآیندهای مربوط به منوی کاربران
# ---------------------------------------------------------------------
async def handle_free_trial_request(env, user, chat_id):
    if user["has_used_trial"]:
        bot_token = getattr(env, "BOT_TOKEN", FALLBACK_BOT_TOKEN)
        await call_telegram(bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "⚠️ شما قبلاً از تست رایگان ۱ روزه استفاده کرده‌اید."
        })
        return
        
    token = str(uuid.uuid4())
    expires_at = (datetime.datetime.utcnow() + datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    
    await execute_db(env.DB, "INSERT INTO subscriptions (user_id, token, expires_at) VALUES (?, ?, ?)", user["id"], token, expires_at)
    await execute_db(env.DB, "UPDATE users SET has_used_trial = 1 WHERE id = ?", user["id"])
    
    domain_res = await query_db(env.DB, "SELECT value FROM settings WHERE key = 'sub_domain'")
    domain_row = get_first_row(domain_res)
    domain = domain_row["value"] if domain_row else "your-worker.workers.dev"
    
    sublink = f"https://{domain}/sub/{token}"
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={sublink}"
    
    msg = (
        f"🎁 اشتراک تست ۱ روزه شما با موفقیت فعال شد!\n\n"
        f"🔗 آدرس ساب‌لینک شما:\n"
        f"`{sublink}`\n\n"
        f"📅 تاریخ انقضا: {expires_at} (UTC)"
    )
    
    bot_token = getattr(env, "BOT_TOKEN", FALLBACK_BOT_TOKEN)
    await call_telegram(bot_token, "sendPhoto", {
        "chat_id": chat_id,
        "photo": qr_url,
        "caption": msg,
        "parse_mode": "Markdown"
    })

async def handle_wallet_request(env, user, chat_id):
    telegram_id = user["telegram_id"]
    ref_count_res = await query_db(env.DB, "SELECT COUNT(*) as count FROM users WHERE referred_by LIKE ?", f"{telegram_id}%")
    ref_count_row = get_first_row(ref_count_res)
    ref_count = ref_count_row["count"] if ref_count_row else 0
    
    price_res = await query_db(env.DB, "SELECT value FROM settings WHERE key = 'service_price'")
    price_row = get_first_row(price_res)
    price = int(price_row["value"]) if price_row else 50000
    
    msg = (
        f"👛 جزئیات کیف پول شما:\n\n"
        f"💰 موجودی فعلی: {user['balance']:,} تومان\n"
        f"👥 تعداد زیرمجموعه‌ها: {ref_count} نفر\n\n"
        f"🛒 هزینه خرید اشتراک: {price:,} تومان\n\n"
        f"💡 می‌توانید با دعوت از دوستانتان با لینک اختصاصی خود موجودی دریافت کنید."
    )
    bot_token = getattr(env, "BOT_TOKEN", FALLBACK_BOT_TOKEN)
    await call_telegram(bot_token, "sendMessage", {"chat_id": chat_id, "text": msg})

async def handle_buy_service_request(env, user, chat_id):
    price_res = await query_db(env.DB, "SELECT value FROM settings WHERE key = 'service_price'")
    price_row = get_first_row(price_res)
    price = int(price_row["value"]) if price_row else 50000
    
    bot_token = getattr(env, "BOT_TOKEN", FALLBACK_BOT_TOKEN)
    if user["balance"] < price:
        msg = (
            f"❌ موجودی حساب شما کافی نیست.\n\n"
            f"💰 موجودی شما: {user['balance']:,} تومان\n"
            f"💵 قیمت اشتراک ۳۰ روزه: {price:,} تومان\n"
        )
        await call_telegram(bot_token, "sendMessage", {"chat_id": chat_id, "text": msg})
        return
        
    await execute_db(env.DB, "UPDATE users SET balance = balance - ? WHERE id = ?", price, user["id"])
    
    token = str(uuid.uuid4())
    expires_at = (datetime.datetime.utcnow() + datetime.timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    await execute_db(env.DB, "INSERT INTO subscriptions (user_id, token, expires_at) VALUES (?, ?, ?)", user["id"], token, expires_at)
    
    domain_res = await query_db(env.DB, "SELECT value FROM settings WHERE key = 'sub_domain'")
    domain_row = get_first_row(domain_res)
    domain = domain_row["value"] if domain_row else "your-worker.workers.dev"
    
    sublink = f"https://{domain}/sub/{token}"
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={sublink}"
    
    msg = (
        f"✅ اشتراک ۳۰ روزه شما با موفقیت ساخته شد:\n\n"
        f"`{sublink}`\n\n"
        f"📅 تاریخ انقضا: {expires_at} (UTC)"
    )
    
    await call_telegram(bot_token, "sendPhoto", {
        "chat_id": chat_id,
        "photo": qr_url,
        "caption": msg,
        "parse_mode": "Markdown"
    })

async def handle_my_services_request(env, user, chat_id):
    sub_res = await query_db(env.DB, "SELECT * FROM subscriptions WHERE user_id = ? AND status = 'active' ORDER BY id DESC", user["id"])
    subs = get_rows(sub_res)
    
    bot_token = getattr(env, "BOT_TOKEN", FALLBACK_BOT_TOKEN)
    if not subs:
        await call_telegram(bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "⚠️ شما اشتراک فعالی در حال حاضر ندارید."
        })
        return
        
    domain_res = await query_db(env.DB, "SELECT value FROM settings WHERE key = 'sub_domain'")
    domain_row = get_first_row(domain_res)
    domain = domain_row["value"] if domain_row else "your-worker.workers.dev"
    
    await call_telegram(bot_token, "sendMessage", {"chat_id": chat_id, "text": f"📋 لیست سرویس‌های فعال شما ({len(subs)} مورد):"})
    for s in subs:
        sub_url = f"https://{domain}/sub/{s['token']}"
        markup = {
            "inline_keyboard": [[{"text": "🖼 نمایش کیوآرکد (QR Code)", "callback_data": f"qr_{s['token']}"}]]
        }
        await call_telegram(bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": f"🔗 ساب‌لینک شما:\n`{sub_url}`\n\n📅 تاریخ انقضا: {s['expires_at']} (UTC)",
            "parse_mode": "Markdown",
            "reply_markup": markup
        })

async def handle_referral_request(env, user, chat_id):
    reward_val = "2000"
    if hasattr(env, "KV") and env.KV:
        try:
            reward_val = await env.KV.get("setting_referral_reward") or "2000"
        except Exception:
            pass
            
    bot_token = getattr(env, "BOT_TOKEN", FALLBACK_BOT_TOKEN)
    bot_info = await call_telegram(bot_token, "getMe", {})
    bot_username = bot_info.get("result", {}).get("username", "V2rayBot")
    
    ref_link = f"https://t.me/{bot_username}?start={user['telegram_id']}"
    
    msg = (
        f"👥 سیستم زیرمجموعه گیری و دعوت دوستان:\n\n"
        f"با دعوت از دوستانتان کیف پولتان را شارژ کنید و رایگان خرید کنید!\n\n"
        f"🎁 پاداش دعوت هر کاربر: {int(reward_val):,} تومان\n\n"
        f"🔗 لینک اختصاصی شما برای دعوت:\n"
        f"`{ref_link}`"
    )
    await call_telegram(bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": msg,
        "parse_mode": "Markdown"
    })

async def handle_support_request(env, chat_id):
    support_contact = "@support_v2ray"
    if hasattr(env, "KV") and env.KV:
        try:
            support_contact = await env.KV.get("setting_support_contact") or "@support_v2ray"
        except Exception:
            pass
            
    msg = (
        f"🎧 بخش ارتباط با پشتیبانی:\n\n"
        f"جهت افزایش دستی موجودی، ارسال انتقاد و یا حل مشکلات فنی پیام دهید:\n\n"
        f"💬 آیدی پشتیبانی: {support_contact}"
    )
    bot_token = getattr(env, "BOT_TOKEN", FALLBACK_BOT_TOKEN)
    await call_telegram(bot_token, "sendMessage", {"chat_id": chat_id, "text": msg})

# ---------------------------------------------------------------------
# تحویل خروجی کانفیگ با فرمت Base64 به کلاینت (Sublink Endpoint)
# ---------------------------------------------------------------------
async def handle_sublink(token, env):
    sub_res = await query_db(env.DB, "SELECT * FROM subscriptions WHERE token = ? AND status = 'active'", token)
    sub = get_first_row(sub_res)
    
    if not sub:
        return Response.new("", headers=to_js({"Content-Type": "text/plain; charset=utf-8"}))
        
    expires_str = sub["expires_at"]
    try:
        expires_at = datetime.datetime.strptime(expires_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        expires_at = datetime.datetime.strptime(expires_str.split(".")[0], "%Y-%m-%d %H:%M:%S")
        
    if expires_at < datetime.datetime.utcnow():
        await execute_db(env.DB, "UPDATE subscriptions SET status = 'expired' WHERE id = ?", sub["id"])
        return Response.new("", headers=to_js({"Content-Type": "text/plain; charset=utf-8"}))
        
    cached_payload = None
    if hasattr(env, "KV") and env.KV:
        try:
            cached_payload = await env.KV.get("cached_configs_payload")
        except Exception:
            pass

    if cached_payload is None:
        cfg_res = await query_db(env.DB, "SELECT config_text FROM configs WHERE is_active = 1")
        confs = get_rows(cfg_res)
        
        payload_lines = [c["config_text"].strip() for c in confs if c["config_text"].strip()]
        combined = "\n".join(payload_lines)
        
        b64_bytes = base64.b64encode(combined.encode("utf-8"))
        cached_payload = b64_bytes.decode("utf-8")
        
        if hasattr(env, "KV") and env.KV:
            try:
                await env.KV.put("cached_configs_payload", cached_payload, expirationTtl=300)
            except Exception:
                pass
        
    headers = Headers.new()
    headers.set("Content-Type", "text/plain; charset=utf-8")
    headers.set("Cache-Control", "public, max-age=120")
    
    return Response.new(cached_payload, headers=headers)

# ---------------------------------------------------------------------
# ورودی اصلی وب‌هوک و تحویل ساب‌لینک در کلودفلر (Fetch Handler)
# ---------------------------------------------------------------------
async def on_fetch(request, env, ctx):
    from urllib.parse import urlparse
    parsed = urlparse(request.url)
    path = parsed.path
    method = request.method
    
    # اجرای اتوماتیک پایگاه‌داده و ایجاد جدول‌ها
    await init_database_if_needed(env)
    
    # ذخیره خودکار دامنه
    if hasattr(env, "DB") and env.DB:
        domain_res = await query_db(env.DB, "SELECT value FROM settings WHERE key = 'sub_domain'")
        if not get_first_row(domain_res):
            await execute_db(env.DB, "INSERT OR REPLACE INTO settings (key, value) VALUES ('sub_domain', ?)", parsed.netloc)
    
    # روت سرویس تحویل اشتراک
    if path.startswith("/sub/"):
        token = path.split("/")[-1]
        return await handle_sublink(token, env)
        
    # روت دریافت وب‌هوک ربات تلگرام
    if (path == "/" or path == "/webhook") and method == "POST":
        try:
            body = await request.text()
            if body and body.strip():
                update = json.loads(body)
                # اجرای کاملاً همگام و مستقیم به جای ctx.waitUntil برای جلوگیری از کرش
                await process_update(update, env)
        except Exception as e:
            print(f"Error parse update: {str(e)}")
            
        return Response.new("OK", status=200)
        
    return Response.new("Not Found", status=404)