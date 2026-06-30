import os
import time
import random
import string
import threading
import requests
import telebot
from flask import Flask, request
from telebot.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from pymongo import MongoClient
from bson.objectid import ObjectId

import functions

# ==================== TOKEN & SETTINGS ====================
TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME")
ADMIN_ID = 7797502113

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
functions.set_bot_username(BOT_USERNAME)

# ==================== MONGO DB CONNECTION ====================
# TO'G'RILANGAN MONGO_URI - protokol va format tuzatildi
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    # Agar environment variable bo'sh bo'lsa, to'g'ridan-to'g'ri yozing
    MONGO_URI = "mongodb+srv://ShadowUzDev:ShadowUzDevAnimeshnik@cluster0.vudnhub.mongodb.net/?retryWrites=true&w=majority&appName=AniComplex"

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    # Ulanishni tekshirish
    client.admin.command('ping')
    print("✅ MongoDB ga muvaffaqiyatli ulandi!")
except Exception as e:
    print(f"❌ MongoDB ulanish xatosi: {e}")
    # Agar ulana olmasa, bot ishlamasligi uchun xatoni ko'taramiz
    raise

# Database nomi - lotin harflarida, "AniComplex" deb nomlandi
db = client["AniComplex"]

# Kolleksiyalar
contents = db["contents"]
required_channels_collection = db["required_channels"]
optional_channels_collection = db["optional_channels"]
users_collection = db["users"]
referrals_collection = db["referrals"]
user_referrals_collection = db["user_referrals"]
bot_settings_collection = db["bot_settings"]
required_bots_collection = db["required_bots"]
join_requests_collection = db["join_requests"]
ads_collection = db["ads"]

# Kolleksiyalarni tekshirish
print(f"📊 Kolleksiyalar soni: {len(db.list_collection_names())}")
print(f"📋 Mavjud kolleksiyalar: {db.list_collection_names()}")

# ==================== FLASK SERVER ====================
app = Flask(__name__)

@app.route('/')
def home():
    try:
        # MongoDB ulanishini tekshirish
        client.admin.command('ping')
        db_status = "✅ MongoDB ulangan"
    except:
        db_status = "❌ MongoDB ulanmagan"
    return f"AniComplex Bot is running! | DB: {db_status}"

@app.route('/webhook', methods=['POST'])
def webhook():
    json_data = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return "OK", 200

def keep_alive():
    while True:
        try:
            requests.get("https://anicomplex.onrender.com")
        except:
            pass
        time.sleep(60)

threading.Thread(target=keep_alive, daemon=True).start()

def generate_code(length=12):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))

admin_state = {}
admin_data = {}
add_button_state = {}
broadcast_state = {}
zayavka_state = {}
last_prompt_msg = {}

# ==================== ADMIN PANEL ====================
def admin_panel():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("Cantent Qo'shish"), KeyboardButton("Majburi Obuna"))
    markup.row(KeyboardButton("Habar Yuborish"), KeyboardButton("Rasm Sozlash"))
    markup.row(KeyboardButton("2-Bo'lim"), KeyboardButton("🔙 Chiqish"))
    return markup

def second_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("Referal"), KeyboardButton("Zayavka sozlamari"))
    markup.row(KeyboardButton("Cantnetga tugma qoshish"), KeyboardButton("Reklama"))
    markup.row(KeyboardButton("1-Bo'lim"))
    return markup

def required_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("➕ Majburiy kanal", callback_data="req_add"),
           InlineKeyboardButton("➕ Ixtiyoriy kanal", callback_data="opt_add"))
    kb.add(InlineKeyboardButton("🤖 Majburiy bot", callback_data="bot_add_menu"),
           InlineKeyboardButton("✏️ Tahrirlash", callback_data="req_edit"))
    kb.add(InlineKeyboardButton("🗑 O'chirish", callback_data="req_delete"),
           InlineKeyboardButton("🔙 Orqaga", callback_data="req_back"))
    return kb

def required_bots_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("➕ Bot qo'shish", callback_data="bot_add"),
           InlineKeyboardButton("✏️ Tahrirlash", callback_data="bot_edit"))
    kb.add(InlineKeyboardButton("🗑 O'chirish", callback_data="bot_delete"),
           InlineKeyboardButton("🔙 Orqaga", callback_data="bot_back"))
    return kb

# ==================== /admin ====================
@bot.message_handler(commands=['admin'])
def admin_start(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Siz admin emassiz!")
        return
    # MongoDB ga saqlashda xatolik bo'lsa ham davom etish
    try:
        users_collection.update_one(
            {"user_id": message.from_user.id},
            {"$set": {"user_id": message.from_user.id}},
            upsert=True
        )
    except Exception as e:
        print(f"⚠️ Foydalanuvchini saqlashda xatolik: {e}")
    
    sent = bot.reply_to(message, "⚙️ Admin panelga xush kelibsiz!", reply_markup=admin_panel())
    try:
        functions.add_premium_reaction(bot, sent.chat.id, sent.message_id, "👑")
    except:
        pass

@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.text in [
    "Cantent Qo'shish", "Majburi Obuna", "Habar Yuborish", "Referal",
    "Rasm Sozlash", "🔙 Chiqish", "2-Bo'lim", "1-Bo'lim",
    "Cantnetga tugma qoshish", "Zayavka sozlamari", "Reklama"
])
def admin_buttons(message):
    uid = message.from_user.id
    text = message.text

    if text == "Cantent Qo'shish":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("1 - 1", callback_data="multi_mode_single"),
               InlineKeyboardButton("♾️ - 1", callback_data="multi_mode_batch"))
        admin_state[uid] = None
        bot.reply_to(message, "Qaysi tarzda kontent qo'shmoqchisiz?", reply_markup=kb)

    elif text == "Habar Yuborish":
        broadcast_state[uid] = {"step": "choose_mode"}
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Forward", callback_data="broadcast_forward"),
               InlineKeyboardButton("Oddiy", callback_data="broadcast_normal"))
        bot.reply_to(message, "Qaysi tarzda foydalanuvchilarga habar yubormoqchisiz?", reply_markup=kb)

    elif text == "Majburi Obuna":
        bot.send_message(uid, "📌 Majburiy obuna bo'limi:", reply_markup=required_menu())

    elif text == "Referal":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("➕ Yangi qo'shish", callback_data="referral_add"),
               InlineKeyboardButton("📊 Statistika", callback_data="referral_stats"))
        bot.send_message(uid, "Salom Admin bugun nima qilamiz?", reply_markup=kb)

    elif text == "Rasm Sozlash":
        admin_state[uid] = "set_main_image"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🗑 Rasmni o'chirish", callback_data="delete_main_image"))
        bot.reply_to(message, "🖼 Majburiy obuna xabari uchun rasm yuboring:", reply_markup=kb)

    elif text == "2-Bo'lim":
        bot.send_message(uid, "🔽 2-Bo'lim menyusi:", reply_markup=second_menu())

    elif text == "1-Bo'lim":
        bot.send_message(uid, "🔽 Asosiy menyu:", reply_markup=admin_panel())

    elif text == "Cantnetga tugma qoshish":
        add_button_state[uid] = {"step": "waiting_code"}
        bot.reply_to(message,
            "📎 Iltimos, kontent havolasini yoki start kodini yuboring:\n\n"
            f"Masalan: <code>https://t.me/{BOT_USERNAME}?start=abc123</code>\nyoki <code>abc123</code>")

    elif text == "Zayavka sozlamari":
        zayavka_state[uid] = {"step": "waiting_channel_id"}
        bot.reply_to(
            message,
            "Zayavka qabul qilinishi kerak bo'lgan kanal ID raqamini kiriting.\n\n"
            "<b>Eslatma:</b> Bot kanalda admin bo'lishi va a'zolik so'rovlarini tasdiqlash huquqiga ega bo'lishi kerak.",
            parse_mode="HTML"
        )

    elif text == "Reklama":
        admin_state[uid] = "add_advertisement"
        bot.reply_to(message, "📢 Reklama sifatida saqlash uchun xabarni forward qiling yoki yuboring.")

    elif text == "🔙 Chiqish":
        admin_state.pop(uid, None)
        admin_data.pop(uid, None)
        add_button_state.pop(uid, None)
        broadcast_state.pop(uid, None)
        zayavka_state.pop(uid, None)
        bot.send_message(uid, "<b>Admin paneldan chiqdingiz.</b>",
                         reply_markup=telebot.types.ReplyKeyboardRemove())

# ==================== REKLAMA QABUL QILISH ====================
@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'sticker', 'audio', 'voice', 'video_note'],
                    func=lambda m: admin_state.get(m.from_user.id) == "add_advertisement")
def receive_advertisement(message):
    uid = message.from_user.id
    ad_data = {
        "chat_id": message.chat.id,
        "message_id": message.message_id,
        "impressions": 0,
        "buttons": []
    }
    if message.forward_from_chat:
        ad_data["chat_id"] = message.forward_from_chat.id
        ad_data["message_id"] = message.forward_from_message_id

    try:
        ads_collection.insert_one(ad_data)
        bot.reply_to(message, "✅ Reklama muvaffaqiyatli saqlandi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Saqlashda xatolik: {e}")
    admin_state.pop(uid, None)

# ==================== DELETE MAIN IMAGE ====================
@bot.callback_query_handler(func=lambda c: c.data == "delete_main_image")
def delete_main_image(call):
    try:
        bot_settings_collection.delete_one({"setting": "main_image"})
        bot.edit_message_text("✅ Rasm o'chirildi! Endi majburiy obuna xabari rasm bilan chiqmaydi.",
                              call.message.chat.id, call.message.message_id)
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Xatolik: {e}")

# ==================== MAIN IMAGE SETUP ====================
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    uid = message.from_user.id
    if uid != ADMIN_ID:
        return
    if admin_state.get(uid) == "set_main_image":
        save_main_image(message)
        return

def save_main_image(message):
    uid = message.from_user.id
    file_id = message.photo[-1].file_id
    try:
        bot_settings_collection.update_one(
            {"setting": "main_image"},
            {"$set": {"image_id": file_id}},
            upsert=True
        )
        sent = bot.reply_to(message, "✅ Rasm saqlandi! Endi majburiy obuna xabari rasm bilan chiqadi.")
        functions.add_premium_reaction(bot, sent.chat.id, sent.message_id, "✅")
    except Exception as e:
        bot.reply_to(message, f"❌ Rasm saqlashda xatolik: {e}")
    admin_state[uid] = None

# ==================== REFERRAL SYSTEM ====================
@bot.callback_query_handler(func=lambda c: c.data == "referral_add")
def referral_add(call):
    uid = call.from_user.id
    admin_state[uid] = "referral_add_name"
    bot.edit_message_text(
        "📛 Yangi referal uchun nom kiriting:\n\n<i>Faqat lotin harflari, raqamlar va pastki chiziq (_) ishlatilishi mumkin.</i>",
        call.message.chat.id, call.message.message_id, parse_mode="HTML"
    )

@bot.callback_query_handler(func=lambda c: c.data == "referral_stats")
def referral_stats(call):
    try:
        referrals = list(referrals_collection.find({}))
    except Exception as e:
        bot.edit_message_text(f"❌ Ma'lumot olishda xatolik: {e}",
                              call.message.chat.id, call.message.message_id)
        return
    
    if not referrals:
        bot.edit_message_text("📊 Referallar mavjud emas.",
                              call.message.chat.id, call.message.message_id)
        return
    
    text = "📊 <b>Referallar statistikasi</b>\n\n"
    kb = InlineKeyboardMarkup()
    for ref in referrals:
        try:
            count = user_referrals_collection.count_documents({"referral_name": ref["name"]})
        except:
            count = 0
        text += f"• <b>{ref['name']}</b>: {count} ta foydalanuvchi\n"
        kb.add(InlineKeyboardButton(f"🗑 {ref['name']}", callback_data=f"del_ref:{ref['name']}"))
    kb.add(InlineKeyboardButton("🔙 Orqaga", callback_data="referral_back"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                          reply_markup=kb, parse_mode="HTML")

@bot.message_handler(func=lambda m: admin_state.get(m.from_user.id) == "referral_add_name")
def referral_save_name(message):
    uid = message.from_user.id
    name = message.text.strip()
    if not all(c.isalnum() or c == '_' for c in name):
        bot.reply_to(message, "❌ Nom faqat lotin harflari, raqamlar va pastki chiziq (_) dan iborat bo'lishi kerak!")
        return
    if len(name) < 3 or len(name) > 20:
        bot.reply_to(message, "❌ Nom 3-20 belgi orasida bo'lishi kerak!")
        return
    
    try:
        if referrals_collection.find_one({"name": name}):
            bot.reply_to(message, "❌ Bunday nomli referal allaqachon mavjud!")
            return
        referrals_collection.insert_one({"name": name, "created_at": time.time()})
        sent = bot.reply_to(message,
            f"✅ <b>{name}</b> referali yaratildi!\n\n"
            f"Havola: <code>https://t.me/{BOT_USERNAME}?start=ref_{name}</code>",
            parse_mode="HTML")
        functions.add_premium_reaction(bot, sent.chat.id, sent.message_id, "✅")
    except Exception as e:
        bot.reply_to(message, f"❌ Saqlashda xatolik: {e}")
    admin_state[uid] = None

@bot.callback_query_handler(func=lambda c: c.data.startswith("del_ref:"))
def delete_referral_confirm(call):
    ref_name = call.data.split(":")[1]
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Ha", callback_data=f"del_ref_yes:{ref_name}"),
           InlineKeyboardButton("❌ Yo'q", callback_data="referral_stats"))
    bot.edit_message_text(f"⚠️ Haqiqatdan ham <b>{ref_name}</b> havolasini o'chirmoqchimisiz?",
                          call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("del_ref_yes:"))
def delete_referral_yes(call):
    ref_name = call.data.split(":")[1]
    try:
        referrals_collection.delete_one({"name": ref_name})
        user_referrals_collection.delete_many({"referral_name": ref_name})
        bot.edit_message_text(f"✅ <b>{ref_name}</b> referali o'chirildi!",
                              call.message.chat.id, call.message.message_id, parse_mode="HTML")
    except Exception as e:
        bot.edit_message_text(f"❌ O'chirishda xatolik: {e}",
                              call.message.chat.id, call.message.message_id)
    referral_stats(call)

@bot.callback_query_handler(func=lambda c: c.data == "referral_back")
def referral_back(call):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ Yangi qo'shish", callback_data="referral_add"),
           InlineKeyboardButton("📊 Statistika", callback_data="referral_stats"))
    bot.edit_message_text("Salom Admin bugun nima qilamiz?",
                          call.message.chat.id, call.message.message_id, reply_markup=kb)

# ==================== BROADCAST ====================
@bot.callback_query_handler(func=lambda c: c.data in ["broadcast_forward", "broadcast_normal"])
def broadcast_mode_selected(call):
    uid = call.from_user.id
    if uid != ADMIN_ID:
        return
    mode = "forward" if call.data == "broadcast_forward" else "normal"
    broadcast_state[uid] = {"step": "waiting_message", "mode": mode}
    text = "📨 Forward xabaringizni yuboring." if mode == "forward" else "📝 Yaxshi, habaringizni yuboring (media, stiker va boshqalar)."
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id)

@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'sticker', 'audio', 'voice', 'video_note'],
                    func=lambda m: broadcast_state.get(m.from_user.id, {}).get("step") == "waiting_message")
def broadcast_receive_message(message):
    uid = message.from_user.id
    broadcast_state[uid]["message"] = message
    broadcast_state[uid]["step"] = "ask_buttons"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ Tugma qo'shish", callback_data="broadcast_add_btn"),
           InlineKeyboardButton("⏭ O'tkazib yuborish", callback_data="broadcast_skip_btn"))
    bot.reply_to(message, "Tugma qo'shishni xohlaysizmi?", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "broadcast_add_btn")
def broadcast_add_buttons_start(call):
    uid = call.from_user.id
    broadcast_state[uid]["step"] = "waiting_buttons"
    bot.edit_message_text(
        "🔘 Tugmalarni quyidagi formatda yuboring:\n\n"
        "<code>Tugma nomi - URL</code>\n"
        "Bir qatorda bir nechta: <code>Tugma1 - url1 | Tugma2 - url2</code>",
        call.message.chat.id, call.message.message_id, parse_mode="HTML")

@bot.message_handler(func=lambda m: broadcast_state.get(m.from_user.id, {}).get("step") == "waiting_buttons")
def broadcast_save_buttons(message):
    uid = message.from_user.id
    text = message.text.strip()
    buttons = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        row_buttons = []
        for part in line.split("|"):
            part = part.strip()
            if " - " in part:
                name, url = part.split(" - ", 1)
                name = name.strip()
                url = url.strip()
                if name and url:
                    row_buttons.append(InlineKeyboardButton(name, url=url))
        if row_buttons:
            buttons.append(row_buttons)
    if not buttons:
        bot.reply_to(message, "❌ Hech qanday tugma topilmadi. Qaytadan urinib ko'ring yoki /skip bosing.")
        return
    broadcast_state[uid]["buttons"] = buttons
    broadcast_state[uid]["step"] = "confirm"
    show_broadcast_confirm(message.chat.id, uid, message)

@bot.message_handler(commands=['skip'])
def broadcast_skip_buttons_cmd(message):
    uid = message.from_user.id
    if broadcast_state.get(uid, {}).get("step") == "waiting_buttons":
        broadcast_state[uid].pop("buttons", None)
        broadcast_state[uid]["step"] = "confirm"
        show_broadcast_confirm(message.chat.id, uid, message)

def show_broadcast_confirm(chat_id, uid, reply_to=None):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Tasdiqlash", callback_data="broadcast_final_confirm"),
           InlineKeyboardButton("❌ Bekor qilish", callback_data="broadcast_cancel"))
    text = "⚠️ Haqiqatdan ham shu xabarni barcha foydalanuvchilarga yubormoqchimisiz?"
    if reply_to:
        bot.reply_to(reply_to, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "broadcast_final_confirm")
def broadcast_final_confirm(call):
    uid = call.from_user.id
    data = broadcast_state.get(uid, {})
    msg = data.get("message")
    if not msg:
        bot.answer_callback_query(call.id, "❌ Xabar topilmadi!")
        return
    buttons = data.get("buttons")
    markup = InlineKeyboardMarkup(buttons) if buttons else None

    try:
        users = list(users_collection.find({}))
    except Exception as e:
        bot.edit_message_text(f"❌ Foydalanuvchilarni olishda xatolik: {e}",
                              call.message.chat.id, call.message.message_id)
        return

    success = 0
    fail = 0
    status_msg = bot.edit_message_text("⏳ Xabar yuborilmoqda...",
                                       call.message.chat.id, call.message.message_id)
    for u in users:
        try:
            if data["mode"] == "forward":
                bot.copy_message(u["user_id"], msg.chat.id, msg.message_id, reply_markup=markup)
            else:
                if msg.content_type == "text":
                    bot.send_message(u["user_id"], msg.text, reply_markup=markup, parse_mode="HTML")
                elif msg.content_type == "photo":
                    bot.send_photo(u["user_id"], msg.photo[-1].file_id, caption=msg.caption, reply_markup=markup)
                elif msg.content_type == "video":
                    bot.send_video(u["user_id"], msg.video.file_id, caption=msg.caption, reply_markup=markup)
                elif msg.content_type == "document":
                    bot.send_document(u["user_id"], msg.document.file_id, caption=msg.caption, reply_markup=markup)
                elif msg.content_type == "sticker":
                    bot.send_sticker(u["user_id"], msg.sticker.file_id, reply_markup=markup)
                elif msg.content_type == "audio":
                    bot.send_audio(u["user_id"], msg.audio.file_id, caption=msg.caption, reply_markup=markup)
                elif msg.content_type == "voice":
                    bot.send_voice(u["user_id"], msg.voice.file_id, reply_markup=markup)
                elif msg.content_type == "video_note":
                    bot.send_video_note(u["user_id"], msg.video_note.file_id, reply_markup=markup)
                else:
                    bot.copy_message(u["user_id"], msg.chat.id, msg.message_id, reply_markup=markup)
            success += 1
            time.sleep(0.05)
        except Exception as e:
            fail += 1
            print(f"Broadcast xatolik {u.get('user_id')}: {e}")
    
    bot.edit_message_text(
        f"✅ Xabar yuborildi!\n\n✅ Muvaffaqiyatli: {success}\n❌ Xatolik: {fail}",
        call.message.chat.id, call.message.message_id)
    try:
        functions.add_premium_reaction(bot, call.message.chat.id, call.message.message_id, "📨")
    except:
        pass
    broadcast_state.pop(uid, None)

@bot.callback_query_handler(func=lambda c: c.data == "broadcast_cancel")
def broadcast_cancel(call):
    uid = call.from_user.id
    bot.edit_message_text("❌ Xabar yuborish bekor qilindi.",
                          call.message.chat.id, call.message.message_id)
    broadcast_state.pop(uid, None)

# ==================== CONTENTGA TUGMA QO'SHISH ====================
@bot.message_handler(func=lambda m: add_button_state.get(m.from_user.id, {}).get("step") == "waiting_code")
def button_add_code(message):
    uid = message.from_user.id
    text = message.text.strip()
    if "?start=" in text:
        code = text.split("?start=")[-1].split()[0].split("&")[0]
    else:
        code = text
    
    try:
        items = list(contents.find({"code": code}))
    except Exception as e:
        bot.reply_to(message, f"❌ Ma'lumot olishda xatolik: {e}")
        add_button_state.pop(uid, None)
        return
    
    if not items:
        bot.reply_to(message, "❌ Bunday kodli kontent topilmadi!")
        add_button_state.pop(uid, None)
        return
    
    add_button_state[uid] = {"step": "waiting_buttons", "code": code}
    bot.reply_to(message,
        "✅ Kod qabul qilindi!\n\nEndi tugmalarni quyidagi formatda yuboring:\n\n"
        "<b>Oddiy tugma:</b>\n<code>Kanal - https://t.me/kanal</code>\n\n"
        "<b>Bir qatorda bir nechta:</b>\n<code>Tugma1 - url1 | Tugma2 - url2</code>\n\n"
        "<b>Rangli qilish (ixtiyoriy, lekin rang qo'llanilmaydi):</b>\n"
        "<code>Tugma - url - rang:yashil</code>\n\n"
        "Har bir qator yangi qatordan boshlansin.", parse_mode="HTML")

@bot.message_handler(func=lambda m: add_button_state.get(m.from_user.id, {}).get("step") == "waiting_buttons")
def button_add_buttons(message):
    uid = message.from_user.id
    code = add_button_state[uid]["code"]
    text = message.text.strip()
    buttons = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        row_buttons = []
        for part in line.split("|"):
            part = part.strip()
            if " - rang:" in part:
                part = part.split(" - rang:")[0].strip()
            if " - " in part:
                name, url = part.split(" - ", 1)
                name = name.strip()
                url = url.strip()
                if name and url:
                    row_buttons.append(InlineKeyboardButton(name, url=url))
        if row_buttons:
            buttons.append(row_buttons)
    if not buttons:
        bot.reply_to(message, "❌ Hech qanday to'g'ri formatdagi tugma topilmadi!")
        return
    
    serializable_buttons = []
    for row in buttons:
        serializable_buttons.append([{"text": btn.text, "url": btn.url} for btn in row])
    
    try:
        contents.update_many({"code": code}, {"$set": {"buttons": serializable_buttons}})
        kb = InlineKeyboardMarkup(buttons)
        sent = bot.reply_to(message,
            f"✅ Tugmalar muvaffaqiyatli qo'shildi!\n\n"
            f"Kod: <code>{code}</code>\nJami kontentlar soni: {contents.count_documents({'code': code})}",
            reply_markup=kb, parse_mode="HTML")
        functions.add_premium_reaction(bot, sent.chat.id, sent.message_id, "✅")
    except Exception as e:
        bot.reply_to(message, f"❌ Tugmalarni saqlashda xatolik: {e}")
    add_button_state.pop(uid, None)

# ==================== MULTI MODE TANLASH ====================
@bot.callback_query_handler(func=lambda c: c.data in ["multi_mode_single", "multi_mode_batch"])
def multi_mode_select(call):
    uid = call.from_user.id
    if uid != ADMIN_ID:
        return
    if call.data == "multi_mode_single":
        admin_state[uid] = "multi_add_single"
        bot.edit_message_text(
            "📥 Kontentlarni tashlang.\n\nHar bir kontent uchun alohida havola beriladi.\n"
            "Tugagach /stop deb yozing.",
            call.message.chat.id, call.message.message_id)
    else:
        admin_state[uid] = "multi_add_batch"
        admin_data[uid] = {"batch": []}
        bot.edit_message_text(
            "📥 Barcha kontentlarni yuboring va oxirida /stop bosing.\n\n"
            "Barchasi uchun bitta havola beriladi.",
            call.message.chat.id, call.message.message_id)

@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'sticker', 'audio', 'voice', 'video_note'],
                    func=lambda m: admin_state.get(m.from_user.id) in ["multi_add_single", "multi_add_batch"]
                    and not (hasattr(m, 'text') and m.text == "/stop"))
def save_multi(message):
    uid = message.from_user.id
    state = admin_state.get(uid)
    if state == "multi_add_single":
        time.sleep(0.1)
    elif state == "multi_add_batch":
        time.sleep(1.0)
    content_type = message.content_type
    item = {"type": content_type, "order": 1}
    if content_type == "video":
        item["file_id"] = message.video.file_id
        item["caption"] = message.caption
    elif content_type == "photo":
        item["file_id"] = message.photo[-1].file_id
        item["caption"] = message.caption
    elif content_type == "document":
        item["file_id"] = message.document.file_id
        item["caption"] = message.caption
    elif content_type == "sticker":
        item["file_id"] = message.sticker.file_id
    elif content_type == "audio":
        item["file_id"] = message.audio.file_id
        item["caption"] = message.caption
    elif content_type == "voice":
        item["file_id"] = message.voice.file_id
    elif content_type == "video_note":
        item["file_id"] = message.video_note.file_id
    else:
        item["text"] = message.text
    
    try:
        if state == "multi_add_single":
            code = generate_code()
            item["code"] = code
            contents.insert_one(item)
            link = f"https://t.me/{BOT_USERNAME}?start={code}"
            sent = bot.reply_to(message, link)
            functions.add_premium_reaction(bot, sent.chat.id, sent.message_id, "✅")
        else:
            batch = admin_data[uid].get("batch", [])
            item["order"] = len(batch) + 1
            batch.append(item)
            admin_data[uid]["batch"] = batch
            sent = bot.reply_to(message, f"✅ {len(batch)}-kontent qabul qilindi.")
            functions.add_premium_reaction(bot, sent.chat.id, sent.message_id, "✅")
    except Exception as e:
        bot.reply_to(message, f"❌ Saqlashda xatolik: {e}")

@bot.message_handler(commands=['stop'])
def stop(message):
    uid = message.from_user.id
    state = admin_state.get(uid)
    if state == "multi_add_batch":
        batch = admin_data.get(uid, {}).get("batch", [])
        if not batch:
            bot.reply_to(message, "❌ Hech qanday kontent yuborilmadi.")
            admin_state[uid] = None
            admin_data[uid] = {}
            return
        code = generate_code()
        docs = []
        for item in batch:
            doc = {"type": item["type"], "code": code, "order": item["order"]}
            if item["type"] in ["video", "photo", "document", "sticker", "audio", "voice", "video_note"]:
                doc["file_id"] = item.get("file_id")
                if "caption" in item:
                    doc["caption"] = item["caption"]
            else:
                doc["text"] = item.get("text")
            docs.append(doc)
        try:
            contents.insert_many(docs)
            link = f"https://t.me/{BOT_USERNAME}?start={code}"
            sent = bot.reply_to(message, link)
            functions.add_premium_reaction(bot, sent.chat.id, sent.message_id, "✅")
        except Exception as e:
            bot.reply_to(message, f"❌ Kontentlarni saqlashda xatolik: {e}")
        admin_state[uid] = None
        admin_data[uid] = {}
        return
    if state == "multi_add_single":
        admin_state[uid] = None
        sent = bot.reply_to(message, "<b>✅ Barcha kontentlar qabul qilindi.</b>",
                            reply_markup=admin_panel())
        functions.add_premium_reaction(bot, sent.chat.id, sent.message_id, "✅")
        return
    bot.reply_to(message, "❌ Hech qanday faol jarayon yo'q.")

# ==================== MAJBURIY KANAL QO'SHISH ====================
@bot.callback_query_handler(func=lambda c: c.data == "req_add")
def start_required_add(call):
    uid = call.from_user.id
    admin_state[uid] = "req_add_id"
    admin_data[uid] = {}
    bot.edit_message_text(
        "➕ Majburiy kanal qo'shish boshlandi.\n\nIltimos kanal ID raqamini yuboring:",
        call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda m: admin_state.get(m.from_user.id) == "req_add_id")
def req_get_id(message):
    uid = message.from_user.id
    try:
        channel_id = int(message.text)
    except:
        bot.reply_to(message, "❌ ID faqat raqam bo'lishi kerak.")
        return
    admin_data[uid]["channel_id"] = channel_id
    admin_state[uid] = "req_add_url"
    bot.reply_to(message, "🔗 Endi kanal havolasini yuboring:")

@bot.message_handler(func=lambda m: admin_state.get(m.from_user.id) == "req_add_url")
def req_get_url(message):
    uid = message.from_user.id
    url = message.text.strip()
    channel_id = admin_data[uid]["channel_id"]
    try:
        member = bot.get_chat_member(channel_id, bot.get_me().id)
        if member.status not in ["administrator", "creator"]:
            bot.reply_to(message, "❌ Bot kanalda admin emas.")
            return
    except Exception as e:
        bot.reply_to(message, f"❌ Kanalga ulanib bo'lmadi: {e}")
        return
    admin_data[uid]["url"] = url
    admin_state[uid] = "req_add_count"
    bot.reply_to(message, "👥 Ushbu kanalga qancha obunachi qo'shmoqchisiz?")

@bot.message_handler(func=lambda m: admin_state.get(m.from_user.id) == "req_add_count")
def req_get_count(message):
    uid = message.from_user.id
    try:
        count = int(message.text)
    except:
        bot.reply_to(message, "❌ Miqdor faqat raqam bo'lishi kerak.")
        return
    admin_data[uid]["count"] = count
    admin_state[uid] = "req_add_name"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🤖 Avto nomlash", callback_data="req_auto_name"))
    bot.reply_to(message, "📛 Kanal uchun nom kiriting yoki pastdagi tugmani bosing:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "req_auto_name")
def req_auto_name(call):
    uid = call.from_user.id
    if admin_state.get(uid) != "req_add_name":
        return
    try:
        auto_channels = list(required_channels_collection.find({"auto": True}))
        auto_channels.sort(key=lambda x: x.get("name", ""))
        auto_name = f"{len(auto_channels) + 1}-Kanal"
        data = admin_data[uid]
        new_channel = {
            "name": auto_name,
            "channel_id": data["channel_id"],
            "url": data["url"],
            "count": data["count"],
            "auto": True
        }
        required_channels_collection.insert_one(new_channel)
        bot.edit_message_text(f"✅ <b>{auto_name}</b> muvaffaqiyatli qo'shildi!",
                              call.message.chat.id, call.message.message_id, parse_mode="HTML")
    except Exception as e:
        bot.edit_message_text(f"❌ Saqlashda xatolik: {e}",
                              call.message.chat.id, call.message.message_id)
    admin_state[uid] = None
    admin_data[uid] = {}

@bot.message_handler(func=lambda m: admin_state.get(m.from_user.id) == "req_add_name")
def req_custom_name(message):
    uid = message.from_user.id
    name = message.text.strip()
    data = admin_data[uid]
    new_channel = {
        "name": name,
        "channel_id": data["channel_id"],
        "url": data["url"],
        "count": data["count"],
        "auto": False
    }
    try:
        required_channels_collection.insert_one(new_channel)
        sent = bot.reply_to(message, f"✅ <b>{name}</b> muvaffaqiyatli qo'shildi!", parse_mode="HTML")
        functions.add_premium_reaction(bot, sent.chat.id, sent.message_id, "➕")
    except Exception as e:
        bot.reply_to(message, f"❌ Saqlashda xatolik: {e}")
    admin_state[uid] = None
    admin_data[uid] = {}

# ==================== IXTIYORIY KANAL QO'SHISH ====================
@bot.callback_query_handler(func=lambda c: c.data == "opt_add")
def start_optional_add(call):
    uid = call.from_user.id
    admin_state[uid] = "opt_add_name"
    admin_data[uid] = {}
    bot.edit_message_text(
        "➕ Ixtiyoriy kanal qo'shish boshlandi.\n\nIltimos tugma uchun nom kiriting:",
        call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda m: admin_state.get(m.from_user.id) == "opt_add_name")
def opt_get_name(message):
    uid = message.from_user.id
    admin_data[uid]["name"] = message.text.strip()
    admin_state[uid] = "opt_add_url"
    bot.reply_to(message, "🔗 Endi kanal havolasini yuboring:")

@bot.message_handler(func=lambda m: admin_state.get(m.from_user.id) == "opt_add_url")
def opt_get_url(message):
    uid = message.from_user.id
    name = admin_data[uid]["name"]
    url = message.text.strip()
    try:
        optional_channels_collection.insert_one({"name": name, "url": url})
        sent = bot.reply_to(message, f"✅ Ixtiyoriy kanal <b>{name}</b> qo'shildi!", parse_mode="HTML")
        functions.add_premium_reaction(bot, sent.chat.id, sent.message_id, "➕")
    except Exception as e:
        bot.reply_to(message, f"❌ Saqlashda xatolik: {e}")
    admin_state[uid] = None
    admin_data[uid] = {}

# ==================== MAJBURIY BOT QO'SHISH ====================
@bot.callback_query_handler(func=lambda c: c.data == "bot_add_menu")
def bot_add_menu(call):
    bot.edit_message_text("🤖 Majburiy botlar bo'limi:",
                          call.message.chat.id, call.message.message_id,
                          reply_markup=required_bots_menu())

@bot.callback_query_handler(func=lambda c: c.data == "bot_add")
def start_bot_add(call):
    uid = call.from_user.id
    admin_state[uid] = "bot_add_username"
    admin_data[uid] = {}
    bot.edit_message_text(
        "➕ Majburiy bot qo'shish boshlandi.\n\nIltimos bot username ni yuboring (masalan: @example_bot):",
        call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda m: admin_state.get(m.from_user.id) == "bot_add_username")
def bot_add_username(message):
    uid = message.from_user.id
    username = message.text.strip().replace("@", "")
    if not username:
        bot.reply_to(message, "❌ Noto'g'ri username formati!")
        return
    admin_data[uid]["bot_username"] = username
    admin_state[uid] = "bot_add_count"
    bot.reply_to(message, "👥 Ushbu botga qancha foydalanuvchi start bosgan?")

@bot.message_handler(func=lambda m: admin_state.get(m.from_user.id) == "bot_add_count")
def bot_add_count(message):
    uid = message.from_user.id
    try:
        count = int(message.text)
    except:
        bot.reply_to(message, "❌ Miqdor faqat raqam bo'lishi kerak.")
        return
    admin_data[uid]["count"] = count
    admin_state[uid] = "bot_add_name_final"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🤖 Avto nomlash", callback_data="bot_auto_name"))
    bot.reply_to(message, "📛 Bot uchun nom kiriting yoki pastdagi tugmani bosing:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "bot_auto_name")
def bot_auto_name(call):
    uid = call.from_user.id
    if admin_state.get(uid) != "bot_add_name_final":
        return
    try:
        auto_bots = list(required_bots_collection.find({}))
        auto_name = f"{len(auto_bots) + 1}-Bot"
        data = admin_data[uid]
        new_bot = {
            "name": auto_name,
            "bot_username": data["bot_username"],
            "count": data["count"],
            "auto": True
        }
        required_bots_collection.insert_one(new_bot)
        bot.edit_message_text(f"✅ <b>{auto_name}</b> muvaffaqiyatli qo'shildi!",
                              call.message.chat.id, call.message.message_id, parse_mode="HTML")
    except Exception as e:
        bot.edit_message_text(f"❌ Saqlashda xatolik: {e}",
                              call.message.chat.id, call.message.message_id)
    admin_state[uid] = None
    admin_data[uid] = {}

@bot.message_handler(func=lambda m: admin_state.get(m.from_user.id) == "bot_add_name_final")
def bot_custom_name(message):
    uid = message.from_user.id
    name = message.text.strip()
    data = admin_data[uid]
    new_bot = {
        "name": name,
        "bot_username": data["bot_username"],
        "count": data["count"],
        "auto": False
    }
    try:
        required_bots_collection.insert_one(new_bot)
        sent = bot.reply_to(message, f"✅ <b>{name}</b> muvaffaqiyatli qo'shildi!", parse_mode="HTML")
        functions.add_premium_reaction(bot, sent.chat.id, sent.message_id, "🤖")
    except Exception as e:
        bot.reply_to(message, f"❌ Saqlashda xatolik: {e}")
    admin_state[uid] = None
    admin_data[uid] = {}

# ==================== TAHRIRLASH VA O'CHIRISH ====================
@bot.callback_query_handler(func=lambda c: c.data == "req_edit")
def start_required_edit(call):
    try:
        channels = list(required_channels_collection.find({}))
    except Exception as e:
        bot.edit_message_text(f"❌ Ma'lumot olishda xatolik: {e}",
                              call.message.chat.id, call.message.message_id)
        return
    
    if not channels:
        bot.edit_message_text("❌ Majburiy kanallar yo'q.",
                              call.message.chat.id, call.message.message_id)
        return
    kb = InlineKeyboardMarkup()
    for ch in channels:
        kb.add(InlineKeyboardButton(ch["name"], callback_data=f"edit_req:{ch['_id']}"))
    kb.add(InlineKeyboardButton("🔙 Orqaga", callback_data="req_back"))
    bot.edit_message_text("✏️ Tahrirlash uchun kanalni tanlang:",
                          call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("edit_req:"))
def edit_required_menu(call):
    ch_id = call.data.split(":")[1]
    try:
        channel = required_channels_collection.find_one({"_id": ObjectId(ch_id)})
    except:
        bot.answer_callback_query(call.id, "❌ Kanal topilmadi.")
        return
    
    if not channel:
        bot.answer_callback_query(call.id, "❌ Kanal topilmadi.")
        return
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📛 Nomni o'zgartirish", callback_data=f"edit_name:{ch_id}"))
    kb.add(InlineKeyboardButton("🔗 Havolani o'zgartirish", callback_data=f"edit_url:{ch_id}"))
    kb.add(InlineKeyboardButton("👥 Miqdorni o'zgartirish", callback_data=f"edit_count:{ch_id}"))
    kb.add(InlineKeyboardButton("🔙 Orqaga", callback_data="req_edit"))
    bot.edit_message_text(f"✏️ <b>{channel['name']}</b> kanalini tahrirlash:",
                          call.message.chat.id, call.message.message_id,
                          reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data == "req_delete")
def start_required_delete(call):
    try:
        req = list(required_channels_collection.find({}))
        opt = list(optional_channels_collection.find({}))
    except Exception as e:
        bot.edit_message_text(f"❌ Ma'lumot olishda xatolik: {e}",
                              call.message.chat.id, call.message.message_id)
        return
    
    kb = InlineKeyboardMarkup()
    if req:
        kb.add(InlineKeyboardButton("📛 Majburiy kanallar", callback_data="del_req_list"))
    if opt:
        kb.add(InlineKeyboardButton("📛 Ixtiyoriy kanallar", callback_data="del_opt_list"))
    kb.add(InlineKeyboardButton("🔙 Orqaga", callback_data="req_back"))
    bot.edit_message_text("🗑 O'chirish bo'limi:\nQaysi turdagi kanallarni o'chirmoqchisiz?",
                          call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "del_req_list")
def delete_required_list(call):
    try:
        channels = list(required_channels_collection.find({}))
    except Exception as e:
        bot.edit_message_text(f"❌ Ma'lumot olishda xatolik: {e}",
                              call.message.chat.id, call.message.message_id)
        return
    
    if not channels:
        bot.edit_message_text("❌ Majburiy kanallar yo'q.",
                              call.message.chat.id, call.message.message_id)
        return
    kb = InlineKeyboardMarkup()
    for ch in channels:
        kb.add(InlineKeyboardButton(f"🗑 {ch['name']}", callback_data=f"del_req_confirm:{ch['_id']}"))
    kb.add(InlineKeyboardButton("🔙 Orqaga", callback_data="req_delete"))
    bot.edit_message_text("🗑 O'chirish uchun kanalni tanlang:",
                          call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("del_req_confirm:"))
def delete_required_confirm(call):
    ch_id = call.data.split(":")[1]
    try:
        ch = required_channels_collection.find_one({"_id": ObjectId(ch_id)})
    except:
        bot.answer_callback_query(call.id, "❌ Kanal topilmadi.")
        return
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Ha, o'chirish", callback_data=f"del_req_yes:{ch_id}"),
           InlineKeyboardButton("❌ Yo'q", callback_data="del_req_list"))
    bot.edit_message_text(f"⚠️ <b>{ch['name']}</b> kanalini o'chirmoqchimisiz?",
                          call.message.chat.id, call.message.message_id,
                          reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("del_req_yes:"))
def delete_required_yes(call):
    ch_id = call.data.split(":")[1]
    try:
        required_channels_collection.delete_one({"_id": ObjectId(ch_id)})
        # Avto nomlangan kanallarni qayta raqamlash
        auto_channels = list(required_channels_collection.find({"auto": True}))
        auto_channels.sort(key=lambda x: x.get("name", ""))
        for i, ch in enumerate(auto_channels):
            required_channels_collection.update_one(
                {"_id": ch["_id"]},
                {"$set": {"name": f"{i+1}-Kanal"}}
            )
        bot.edit_message_text("✅ Kanal o'chirildi!",
                              call.message.chat.id, call.message.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ O'chirishda xatolik: {e}",
                              call.message.chat.id, call.message.message_id)
    delete_required_list(call)

@bot.callback_query_handler(func=lambda c: c.data == "del_opt_list")
def delete_optional_list(call):
    try:
        channels = list(optional_channels_collection.find({}))
    except Exception as e:
        bot.edit_message_text(f"❌ Ma'lumot olishda xatolik: {e}",
                              call.message.chat.id, call.message.message_id)
        return
    
    if not channels:
        bot.edit_message_text("❌ Ixtiyoriy kanallar yo'q.",
                              call.message.chat.id, call.message.message_id)
        return
    kb = InlineKeyboardMarkup()
    for ch in channels:
        kb.add(InlineKeyboardButton(f"🗑 {ch['name']}", callback_data=f"del_opt_confirm:{ch['_id']}"))
    kb.add(InlineKeyboardButton("🔙 Orqaga", callback_data="req_delete"))
    bot.edit_message_text("🗑 O'chirish uchun kanalni tanlang:",
                          call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("del_opt_confirm:"))
def delete_optional_confirm(call):
    ch_id = call.data.split(":")[1]
    try:
        ch = optional_channels_collection.find_one({"_id": ObjectId(ch_id)})
    except:
        bot.answer_callback_query(call.id, "❌ Kanal topilmadi.")
        return
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Ha, o'chirish", callback_data=f"del_opt_yes:{ch_id}"),
           InlineKeyboardButton("❌ Yo'q", callback_data="del_opt_list"))
    bot.edit_message_text(f"⚠️ <b>{ch['name']}</b> kanalini o'chirmoqchimisiz?",
                          call.message.chat.id, call.message.message_id,
                          reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("del_opt_yes:"))
def delete_optional_yes(call):
    ch_id = call.data.split(":")[1]
    try:
        optional_channels_collection.delete_one({"_id": ObjectId(ch_id)})
        bot.edit_message_text("✅ Kanal o'chirildi!",
                              call.message.chat.id, call.message.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ O'chirishda xatolik: {e}",
                              call.message.chat.id, call.message.message_id)
    delete_optional_list(call)

@bot.callback_query_handler(func=lambda c: c.data == "req_back")
def back_to_required_menu(call):
    bot.edit_message_text("📌 Majburiy obuna bo'limi:",
                          call.message.chat.id, call.message.message_id,
                          reply_markup=required_menu())

# ==================== ZAYAVKA QAYD ETISH ====================
@bot.chat_join_request_handler()
def handle_join_request(update: telebot.types.ChatJoinRequest):
    try:
        chat_id = update.chat.id
        user_id = update.from_user.id
        channel = required_channels_collection.find_one({"channel_id": chat_id})
        if channel:
            join_requests_collection.update_one(
                {"user_id": user_id, "channel_id": chat_id},
                {"$set": {"timestamp": time.time()}}, upsert=True)
            users_collection.update_one({"user_id": user_id}, {"$set": {"user_id": user_id}}, upsert=True)
    except Exception as e:
        print(f"Zayavka xatolik: {e}")

# ==================== ZAYAVKA SOZLAMARI ====================
@bot.message_handler(func=lambda m: zayavka_state.get(m.from_user.id, {}).get("step") == "waiting_channel_id")
def zayavka_get_channel_id(message):
    uid = message.from_user.id
    try:
        channel_id = int(message.text.strip())
    except:
        bot.reply_to(message, "❌ ID faqat raqamlardan iborat bo'lishi kerak (masalan: -1001234567890).")
        return

    try:
        chat_info = bot.get_chat(channel_id)
        bot_member = bot.get_chat_member(channel_id, bot.get_me().id)
        if bot_member.status not in ["administrator", "creator"]:
            bot.reply_to(message, "❌ Bot bu kanalda admin emas yoki tasdiqlash huquqiga ega emas.")
            zayavka_state.pop(uid, None)
            return
    except Exception as e:
        bot.reply_to(message, f"❌ Kanal topilmadi yoki bot ulana olmadi: {e}")
        zayavka_state.pop(uid, None)
        return

    try:
        pending_count = join_requests_collection.count_documents({"channel_id": channel_id})
    except:
        pending_count = 0

    zayavka_state[uid] = {
        "step": "waiting_count",
        "channel_id": channel_id,
        "channel_title": chat_info.title
    }

    bot.reply_to(
        message,
        f"📢 <b>{chat_info.title}</b> kanali uchun qancha odamni qabul qilmoqchisiz?\n\n"
        f"👥 Mavjud zayavkalar soni: <b>{pending_count}</b> ta\n\n"
        f"Iltimos, miqdorni kiriting (maksimum <b>{pending_count}</b>):",
        parse_mode="HTML"
    )

@bot.message_handler(func=lambda m: zayavka_state.get(m.from_user.id, {}).get("step") == "waiting_count")
def zayavka_approve(message):
    uid = message.from_user.id
    try:
        count = int(message.text.strip())
    except:
        bot.reply_to(message, "❌ Iltimos, faqat raqam kiriting.")
        return

    data = zayavka_state[uid]
    channel_id = data["channel_id"]
    channel_title = data["channel_title"]

    try:
        pending = list(join_requests_collection.find(
            {"channel_id": channel_id}
        ).sort("timestamp", 1).limit(count))
    except Exception as e:
        bot.reply_to(message, f"❌ Zayavkalarni olishda xatolik: {e}")
        zayavka_state.pop(uid, None)
        return

    if not pending:
        bot.reply_to(message, "⚠️ Bu kanalda kutilayotgan zayavka qolmagan.")
        zayavka_state.pop(uid, None)
        return

    actual_count = len(pending)
    status_msg = bot.reply_to(message, f"⏳ Zayavkalar qabul qilinmoqda... 0/{actual_count}")

    approved = 0
    for idx, req in enumerate(pending):
        user_id = req["user_id"]
        try:
            bot.approve_chat_join_request(channel_id, user_id)
            approved += 1
            try:
                send_ad(user_id)
            except:
                pass
            if (idx + 1) % 5 == 0 or (idx + 1) == actual_count:
                try:
                    bot.edit_message_text(
                        f"⏳ Zayavkalar qabul qilinmoqda... {approved}/{actual_count}",
                        status_msg.chat.id, status_msg.message_id
                    )
                except:
                    pass
            time.sleep(0.05)
        except Exception as e:
            print(f"Zayavka qabul qilishda xatolik (user {user_id}): {e}")

    bot.edit_message_text(
        f"✅ Zayavkalar qabul qilindi!\n\n"
        f"📊 Jami: {approved}/{actual_count} ta\n"
        f"📢 Kanal: {channel_title}",
        status_msg.chat.id, status_msg.message_id
    )
    zayavka_state.pop(uid, None)

# ==================== MAJBURIY OBUNA TEKSHIRISH ====================
def check_required_subs(user_id):
    try:
        required = list(required_channels_collection.find({}))
    except:
        return True
    
    for ch in required:
        channel_id = ch["channel_id"]
        try:
            member = bot.get_chat_member(channel_id, user_id)
            if member.status in ["member", "administrator", "creator", "restricted"]:
                continue
        except:
            pass
        try:
            if join_requests_collection.find_one({"user_id": user_id, "channel_id": channel_id}):
                continue
        except:
            pass
        return False
    return True

def check_required_bots(user_id):
    try:
        required = list(required_bots_collection.find({}))
    except:
        return True
    
    for bot_info in required:
        try:
            member = bot.get_chat_member(f"@{bot_info['bot_username']}", user_id)
            if member.status != "member":
                return False
        except:
            return False
    return True

def get_required_keyboard(user_id, code):
    try:
        required = list(required_channels_collection.find({}))
        optional = list(optional_channels_collection.find({}))
    except:
        required = []
        optional = []

    unsubscribed = []
    for ch in required:
        channel_id = ch["channel_id"]
        is_member = False
        try:
            member = bot.get_chat_member(channel_id, user_id)
            if member.status in ["member", "administrator", "creator", "restricted"]:
                is_member = True
        except:
            pass
        if not is_member:
            try:
                if join_requests_collection.find_one({"user_id": user_id, "channel_id": channel_id}):
                    continue
            except:
                pass
            unsubscribed.append(ch)

    unsubscribed.sort(key=lambda x: x.get("name", ""))

    kb_buttons = []
    auto_count = 0
    for ch in unsubscribed:
        if ch.get("auto"):
            auto_count += 1
            display_name = f"{auto_count}-Kanal"
        else:
            display_name = ch["name"]
        kb_buttons.append(InlineKeyboardButton(display_name, url=ch["url"]))

    for ch in optional:
        kb_buttons.append(InlineKeyboardButton(ch["name"], url=ch["url"]))

    random.shuffle(kb_buttons)

    kb = InlineKeyboardMarkup(row_width=1)
    for btn in kb_buttons:
        kb.add(btn)
    kb.add(InlineKeyboardButton("Tekshirish ♻️", url=f"https://t.me/{BOT_USERNAME}?start={code}"))
    return kb

def get_required_bots_keyboard(user_id, code):
    try:
        required = list(required_bots_collection.find({}))
    except:
        required = []
    
    buttons = []
    for bot_info in required:
        try:
            member = bot.get_chat_member(f"@{bot_info['bot_username']}", user_id)
            if member.status == "member":
                continue
        except:
            pass
        buttons.append(InlineKeyboardButton(bot_info["name"],
                                            url=f"https://t.me/{bot_info['bot_username']}?start=from_{BOT_USERNAME}"))
    random.shuffle(buttons)
    kb = InlineKeyboardMarkup(row_width=1)
    for btn in buttons:
        kb.add(btn)
    kb.add(InlineKeyboardButton("✔️ Tekshirish", url=f"https://t.me/{BOT_USERNAME}?start={code}"))
    return kb

# ==================== REKLAMA ====================
def send_ad(chat_id):
    try:
        ads = list(ads_collection.find({}))
    except:
        return
    
    if not ads:
        return
    ad = random.choice(ads)
    try:
        ads_collection.update_one({"_id": ad["_id"]}, {"$inc": {"impressions": 1}})
    except:
        pass
    
    markup = None
    if ad.get("buttons"):
        rows = [[InlineKeyboardButton(b["text"], url=b["url"]) for b in row] for row in ad["buttons"]]
        markup = InlineKeyboardMarkup(rows)
    try:
        bot.copy_message(chat_id, ad["chat_id"], ad["message_id"], reply_markup=markup, protect_content=True)
    except:
        pass

def send_content(chat_id, items, is_batch=False):
    markup = None
    if items and "buttons" in items[0]:
        rows = [[InlineKeyboardButton(b["text"], url=b["url"]) for b in row] for row in items[0]["buttons"]]
        markup = InlineKeyboardMarkup(rows)

    for item in items:
        msg = None
        try:
            if item["type"] == "text":
                msg = bot.send_message(chat_id, item["text"], reply_markup=markup)
            elif item["type"] == "photo":
                msg = bot.send_photo(chat_id, item["file_id"], caption=item.get("caption"), reply_markup=markup)
            elif item["type"] == "video":
                msg = bot.send_video(chat_id, item["file_id"], caption=item.get("caption"), reply_markup=markup)
            elif item["type"] == "document":
                msg = bot.send_document(chat_id, item["file_id"], caption=item.get("caption"), reply_markup=markup)
            elif item["type"] == "sticker":
                msg = bot.send_sticker(chat_id, item["file_id"], reply_markup=markup)
            elif item["type"] == "audio":
                msg = bot.send_audio(chat_id, item["file_id"], caption=item.get("caption"), reply_markup=markup)
            elif item["type"] == "voice":
                msg = bot.send_voice(chat_id, item["file_id"], reply_markup=markup)
            elif item["type"] == "video_note":
                msg = bot.send_video_note(chat_id, item["file_id"], reply_markup=markup)
            if msg:
                schedule_delete(chat_id, msg.message_id, 1800)
        except Exception as e:
            print(f"Kontent yuborishda xatolik: {e}")

    try:
        warn = bot.send_message(chat_id,
            "<b>⚠️ ESLATMA ⚠️\n<blockquote>❗ Ushbu habarlar Mualiflik huquqi sababli 30 daqiqadan so'ng o'chiriladi.</blockquote></b>")
        schedule_delete(chat_id, warn.message_id, 1800)
    except:
        pass

    try:
        user = users_collection.find_one({"user_id": chat_id})
        count = user.get("content_count", 0) + (len(items) if is_batch else 1) if user else (len(items) if is_batch else 1)
        users_collection.update_one({"user_id": chat_id}, {"$set": {"content_count": count}}, upsert=True)
    except:
        return

    try:
        threshold_doc = bot_settings_collection.find_one({"setting": "ad_threshold"})
        threshold = threshold_doc["value"] if threshold_doc else 10
        if count >= threshold:
            send_ad(chat_id)
            users_collection.update_one({"user_id": chat_id}, {"$set": {"content_count": 0}})
    except:
        pass

def schedule_delete(chat_id, message_id, delay=300):
    def _delete():
        try:
            bot.delete_message(chat_id, message_id)
        except:
            pass
    threading.Timer(delay, _delete).start()

# ==================== /start ====================
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    try:
        users_collection.update_one({"user_id": uid}, {"$set": {"user_id": uid}}, upsert=True)
    except:
        pass
    
    args = message.text.split()
    if len(args) == 1:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📝 Bot Haqida", callback_data="about"),
                   InlineKeyboardButton("🔒 Yopish", callback_data=f"close:{message.message_id}"))
        sent = bot.reply_to(message,
            "<b>Bu bot orqali kanaldagi animelarni yuklab olishingiz mumkin.\n\n❗️Botga habar yozmang❗️</b>",
            reply_markup=markup)
        try:
            functions.add_premium_reaction(bot, sent.chat.id, sent.message_id, "🎉")
        except:
            pass
        return

    code = args[1]
    if code.startswith("ref_"):
        ref_name = code[4:]
        try:
            referral = referrals_collection.find_one({"name": ref_name})
            if referral:
                user = users_collection.find_one({"user_id": uid})
                if not user:
                    user_referrals_collection.update_one({"user_id": uid},
                        {"$set": {"referral_name": ref_name}}, upsert=True)
        except:
            pass
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📝 Bot Haqida", callback_data="about"),
                   InlineKeyboardButton("🔒 Yopish", callback_data=f"close:{message.message_id}"))
        sent = bot.reply_to(message,
            "<b>Bu bot orqali kanaldagi animelarni yuklab olishingiz mumkin.\n\n❗️Botga habar yozmang❗️</b>",
            reply_markup=markup)
        try:
            functions.add_premium_reaction(bot, sent.chat.id, sent.message_id, "🎉")
        except:
            pass
        return

    try:
        items = list(contents.find({"code": code}).sort("order", 1))
    except:
        items = []
    
    if not items:
        sent = bot.send_message(message.chat.id, "")
        try:
            functions.add_premium_reaction(bot, sent.chat.id, sent.message_id, "❌")
        except:
            pass
        return

    if not check_required_subs(uid):
        if uid in last_prompt_msg:
            try:
                bot.delete_message(message.chat.id, last_prompt_msg[uid])
            except:
                pass
            del last_prompt_msg[uid]

        try:
            settings = bot_settings_collection.find_one({"setting": "main_image"})
        except:
            settings = None
        
        kb = get_required_keyboard(uid, code)
        if settings and settings.get("image_id"):
            sent = bot.send_photo(message.chat.id, settings["image_id"],
                caption="📢 <b>Animeni yuklab olish uchun quyidagi kanallarga obuna bo'ling:</b>",
                reply_markup=kb)
        else:
            sent = bot.send_message(message.chat.id,
                "📢 <b>Animeni yuklab olish uchun quyidagi kanallarga obuna bo'ling:</b>",
                reply_markup=kb)
        last_prompt_msg[uid] = sent.message_id
        try:
            functions.add_premium_reaction(bot, sent.chat.id, sent.message_id, "🔔")
        except:
            pass
        return

    if uid in last_prompt_msg:
        try:
            bot.delete_message(message.chat.id, last_prompt_msg[uid])
        except:
            pass
        del last_prompt_msg[uid]

    if not check_required_bots(uid):
        try:
            settings = bot_settings_collection.find_one({"setting": "main_image"})
        except:
            settings = None
        
        kb = get_required_bots_keyboard(uid, code)
        if settings and settings.get("image_id"):
            sent = bot.send_photo(message.chat.id, settings["image_id"],
                caption="📢 <b>Kontentni ko'rish uchun quyidagi botlarga start bosing:</b>",
                reply_markup=kb)
        else:
            sent = bot.send_message(message.chat.id,
                "📢 <b>Kontentni ko'rish uchun quyidagi botlarga start bosing:</b>",
                reply_markup=kb)
        try:
            functions.add_premium_reaction(bot, sent.chat.id, sent.message_id, "🤖")
        except:
            pass
        return

    is_batch = len(items) > 1
    send_content(message.chat.id, items, is_batch)

# ==================== CALLBACK HANDLER ====================
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    data = call.data
    if data.startswith("close"):
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        return
    if data == "about":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("👨‍💻 Yaratuvchi", callback_data="creator"),
                   InlineKeyboardButton("🔒 Yopish", callback_data=f"close:{call.message.message_id}"))
        bot.edit_message_text(
            chat_id=call.message.chat.id, message_id=call.message.message_id,
            text=(
                "<b>Botni ishlatishni bilmaganlar uchun!\n\n"
                "❏ Botni ishlatish qo'llanmasi:\n"
                "1. Kanallarga obuna bo'ling!\n"
                "2. Tekshirish tugmasini bosing ✅\n"
                "3. Kanaldagi anime post past qismidagi yuklab olish tugmasini bosing\n\n"
                "📢 Kanal: <i>@AniGonUz</i></b>"
            ),
            reply_markup=markup, parse_mode="HTML"
        )
        try:
            functions.add_premium_reaction(bot, call.message.chat.id, call.message.message_id, "📖")
        except:
            pass
    if data == "creator":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📝 Bot Haqida", callback_data="about"),
                   InlineKeyboardButton("🔒 Yopish", callback_data=f"close:{call.message.message_id}"))
        bot.edit_message_text(
            chat_id=call.message.chat.id, message_id=call.message.message_id,
            text=(
                "<b>"
                "• Admin: <i>@Shadow_Sxi</i>\n"
                "• Asosiy Kanal: <i>@AniGonUz</i>\n"
                "• Reklama: <i>@AniReklamaUz</i>\n\n"
                "👨‍💻 Savollar Bo'lsa: <i>@AniManxwaBot</i>"
                "</b>"
            ),
            reply_markup=markup, parse_mode="HTML"
        )
        try:
            functions.add_premium_reaction(bot, call.message.chat.id, call.message.message_id, "👨‍💻")
        except:
            pass

# ==================== RUN SERVER ====================
if __name__ == "__main__":
    print("🚀 AniComplex bot ishga tushmoqda...")
    app.run(host="0.0.0.0", port=10000)
