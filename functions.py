import time

BOT_USERNAME = None

def set_bot_username(username):
    global BOT_USERNAME
    BOT_USERNAME = username

def add_premium_reaction(bot, chat_id, message_id, emoji="🎉"):
    try:
        time.sleep(0.3)
        bot.set_message_reaction(chat_id=chat_id, message_id=message_id,
                                 reaction=[{"type": "emoji", "emoji": emoji}], is_big=True)
        return True
    except:
        return False
