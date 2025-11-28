import os
import logging
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Instagram uchun
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ChallengeRequired

# Sozlamalarni yuklash
load_dotenv()

# Tokens
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")
ADMIN_ID = os.getenv("ADMIN_ID")

# Log sozlash
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Instagram client
cl = Client()

class InstagramBot:
    def __init__(self):
        self.is_logged_in = False
    
    def login(self):
        """Instagramga login qilish"""
        try:
            cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            self.is_logged_in = True
            logger.info("✅ Instagramga muvaffaqiyatli login qilindi")
            return True
        except Exception as e:
            logger.error(f"❌ Instagram login xatosi: {e}")
            return False
    
    def get_profile_info(self):
        """Profil ma'lumotlarini olish"""
        try:
            if not self.is_logged_in:
                self.login()
            
            user_info = cl.account_info()
            return {
                'username': user_info.username,
                'full_name': user_info.full_name,
                'followers': user_info.follower_count,
                'following': user_info.following_count,
                'posts': user_info.media_count,
                'bio': user_info.biography
            }
        except Exception as e:
            logger.error(f"Profil ma'lumotlarini olishda xato: {e}")
            return None
    
    def get_followers(self):
        """Followerlar ro'yxatini olish"""
        try:
            if not self.is_logged_in:
                self.login()
            
            followers = cl.user_followers(cl.user_id)
            return [user.username for user in followers.values()][:50]  # Faqat 50 tasi
        except Exception as e:
            logger.error(f"Followerlarni olishda xato: {e}")
            return []
    
    def upload_post(self, image_path, caption):
        """Post yuklash"""
        try:
            if not self.is_logged_in:
                self.login()
            
            cl.photo_upload(image_path, caption)
            return True
        except Exception as e:
            logger.error(f"Post yuklashda xato: {e}")
            return False
    
    def send_dm(self, username, message):
        """Direct message yuborish"""
        try:
            if not self.is_logged_in:
                self.login()
            
            user_id = cl.user_id_from_username(username)
            cl.direct_send(message, [user_id])
            return True
        except Exception as e:
            logger.error(f"DM yuborishda xato: {e}")
            return False

# Botni yaratish
instagram_bot = InstagramBot()

# Telegram bot handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    keyboard = [
        ["📊 Profil ma'lumotlari", "👥 Followerlar"],
        ["📤 Post yuklash", "📩 DM yuborish"],
        ["🔄 Instagramga ulanish"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "🤖 Instagram Botiga xush kelibsiz!\n"
        "Quyidagi menyudan kerakli amalni tanlang:",
        reply_markup=reply_markup
    )

async def profile_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Profil ma'lumotlarini ko'rsatish"""
    await update.message.reply_text("⏳ Profil ma'lumotlari olinmoqda...")
    
    info = instagram_bot.get_profile_info()
    if info:
        message = (
            f"📊 **Profil Ma'lumotlari:**\n\n"
            f"👤 **Username:** @{info['username']}\n"
            f"📛 **Ism:** {info['full_name']}\n"
            f"📈 **Followerlar:** {info['followers']:,}\n"
            f"📉 **Following:** {info['following']:,}\n"
            f"📷 **Postlar:** {info['posts']:,}\n"
            f"📝 **Bio:** {info['bio'][:100]}..."
        )
    else:
        message = "❌ Profil ma'lumotlarini olishda xatolik!"
    
    await update.message.reply_text(message)

async def show_followers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Followerlarni ko'rsatish"""
    await update.message.reply_text("⏳ Followerlar ro'yxati olinmoqda...")
    
    followers = instagram_bot.get_followers()
    if followers:
        followers_list = "\n".join([f"👤 @{user}" for user in followers[:20]])  # Faqat 20 tasi
        message = f"👥 **So'ngi 20 follower:**\n\n{followers_list}"
        if len(followers) > 20:
            message += f"\n\n... va yana {len(followers) - 20} ta"
    else:
        message = "❌ Followerlarni olishda xatolik!"
    
    await update.message.reply_text(message)

async def prepare_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Post yuklashga tayyorlash"""
    await update.message.reply_text(
        "📤 Post yuklash uchun rasm va matn yuboring:\n\n"
        "1. Avval rasmni yuboring\n"
        "2. Keyin caption (matn) yozing\n\n"
        "Yoki /cancel bilan bekor qiling."
    )
    context.user_data['waiting_for_photo'] = True

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rasm qabul qilish"""
    if context.user_data.get('waiting_for_photo'):
        photo = await update.message.photo[-1].get_file()
        photo_path = f"temp_photo_{update.update_id}.jpg"
        await photo.download_to_drive(photo_path)
        
        context.user_data['photo_path'] = photo_path
        context.user_data['waiting_for_photo'] = False
        context.user_data['waiting_for_caption'] = True
        
        await update.message.reply_text("✅ Rasm qabul qilindi. Endi caption (matn) yuboring:")

async def handle_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Caption qabul qilish va post yuklash"""
    if context.user_data.get('waiting_for_caption'):
        caption = update.message.text
        photo_path = context.user_data.get('photo_path')
        
        if photo_path and os.path.exists(photo_path):
            await update.message.reply_text("⏳ Post Instagramga yuklanmoqda...")
            
            success = instagram_bot.upload_post(photo_path, caption)
            
            # Vaqtincha faylni o'chirish
            try:
                os.remove(photo_path)
            except:
                pass
            
            if success:
                await update.message.reply_text("✅ Post muvaffaqiyatli yuklandi!")
            else:
                await update.message.reply_text("❌ Post yuklashda xatolik!")
        else:
            await update.message.reply_text("❌ Rasm topilmadi!")
        
        # User datani tozalash
        context.user_data.clear()

async def prepare_dm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """DM yuborishga tayyorlash"""
    await update.message.reply_text(
        "📩 DM yuborish uchun:\n\n"
        "Foydalanuvchi username va xabarni quyidagi formatda yuboring:\n"
        "`username:xabar matni`\n\n"
        "Misol: `john_doe:Salom! Qalaysiz?`"
    )

async def handle_dm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """DM yuborish"""
    text = update.message.text
    if ':' in text:
        username, message = text.split(':', 1)
        username = username.strip()
        message = message.strip()
        
        await update.message.reply_text(f"⏳ @{username} ga xabar yuborilmoqda...")
        
        success = instagram_bot.send_dm(username, message)
        
        if success:
            await update.message.reply_text(f"✅ @{username} ga xabar yuborildi!")
        else:
            await update.message.reply_text(f"❌ @{username} ga xabar yuborishda xatolik!")
    else:
        await update.message.reply_text("❌ Noto'g'ri format! username:xabar ko'rinishida yuboring")

async def connect_instagram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Instagramga ulanish"""
    await update.message.reply_text("⏳ Instagramga ulanmoqda...")
    
    success = instagram_bot.login()
    
    if success:
        await update.message.reply_text("✅ Instagramga muvaffaqiyatli ulandi!")
    else:
        await update.message.reply_text("❌ Instagramga ulanishda xatolik!")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bekor qilish"""
    context.user_data.clear()
    await update.message.reply_text("🚫 Amal bekor qilindi.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asosiy message handler"""
    text = update.message.text
    
    if text == "📊 Profil ma'lumotlari":
        await profile_info(update, context)
    elif text == "👥 Followerlar":
        await show_followers(update, context)
    elif text == "📤 Post yuklash":
        await prepare_upload(update, context)
    elif text == "📩 DM yuborish":
        await prepare_dm(update, context)
    elif text == "🔄 Instagramga ulanish":
        await connect_instagram(update, context)

def main():
    """Asosiy funksiya"""
    if not all([TELEGRAM_TOKEN, INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD]):
        logger.error("❌ .env faylda barcha sozlamalar to'ldirilmagan!")
        return
    
    # Telegram bot yaratish
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Handlerlar
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Maxsus handlerlar
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r".+:.+"), 
        handle_dm
    ))
    
    # Instagramga ulanish
    instagram_bot.login()
    
    print("🤖 Instagram Bot ishga tushdi...")
    application.run_polling()

if __name__ == "__main__":
    main()