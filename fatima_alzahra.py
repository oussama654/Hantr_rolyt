#!/usr/bin/env python3
import os, asyncio, random, re, time, logging
from datetime import datetime
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.errors import (
    FloodWaitError, UserBannedInChannelError, UserChannelsTooMuchError, ChannelsTooMuchError
)

# ---------- الإعدادات ----------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ZsewwiHunter")

API_ID = int(os.environ.get("API_ID_1", 0))
API_HASH = os.environ.get("API_HASH_1", "")
SESSION = os.environ.get("SESSION_1", "")

TARGET_VPS_CHANNEL = "FreeinternetTM"
NOTIFY_USER = "@KOA_7" # أو @Pro

HUNT_BUTTONS = ["مشاركة", "انضمام", "سحب", "تدوير", "دخول", "تأكيد", "اضغط هنا"]
VOTE_BUTTONS = ["❤️", "👍", "تصويت", "يستحق", "صوت"]

class ZsewwiBot:
    def __init__(self):
        self.client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)
        self.active_tasks = set()

    async def leave_oldest_channels(self):
        """مغادرة أقدم 5 قنوات غير نشطة لتفريغ مساحة"""
        logger.info("⚠️ الحساب ممتلئ! جاري البحث عن قنوات ميتة لمغادرتها...")
        dialogs = await self.client.get_dialogs()
        channels = [d for d in dialogs if d.is_channel]
        
        # ترتيب القنوات حسب أقدم رسالة
        channels.sort(key=lambda d: d.date or datetime.min)
        
        left_count = 0
        for d in channels[:5]:
            try:
                await self.client(LeaveChannelRequest(d.entity))
                logger.info(f"🧹 تم مغادرة: {d.name}")
                left_count += 1
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"فشل المغادرة: {e}")
        return left_count > 0

    async def safe_join_channel(self, channel_entity):
        """الانضمام الآمن مع التعامل مع امتلاء الحساب والتأخير"""
        delay = random.randint(6, 15)
        logger.info(f"⏳ انتظار {delay} ثوانٍ قبل الانضمام...")
        await asyncio.sleep(delay)
        
        try:
            await self.client(JoinChannelRequest(channel_entity))
            logger.info("✅ تم الانضمام للقناة.")
            return True
        except (UserChannelsTooMuchError, ChannelsTooMuchError):
            if await self.leave_oldest_channels():
                await asyncio.sleep(3)
                try:
                    await self.client(JoinChannelRequest(channel_entity))
                    return True
                except: pass
        except Exception as e:
            logger.error(f"خطأ الانضمام: {e}")
        return False

    async def handle_captcha_bot(self, bot_username):
        """التعامل مع بوت التحقق (الكابتشا)"""
        logger.info(f"🤖 توجيه لبوت الكابتشا: {bot_username}")
        try:
            await self.client.send_message(bot_username, "/start")
            await asyncio.sleep(3)
            # البوت عادة يرسل رسالة كابتشا، ننتظرها
            messages = await self.client.get_messages(bot_username, limit=2)
            for msg in messages:
                if msg.reply_markup:
                    text = msg.text or ""
                    # استخراج الإيموجي أو الرقم
                    emoji_match = re.search(r'\((.*?)\)', text)
                    if emoji_match:
                        target = emoji_match.group(1).strip()
                        for r, row in enumerate(msg.reply_markup.rows):
                            for b, btn in enumerate(row.buttons):
                                if target in btn.text:
                                    await msg.click(r, b)
                                    logger.info("✅ تم حل الكابتشا بنجاح.")
                                    return True
                    # إذا كان زر التحقق العادي
                    else:
                        await msg.click(0, 0)
                        return True
        except Exception as e:
            logger.error(f"خطأ في بوت الكابتشا: {e}")
        return False

    async def process_complex_roulette(self, event):
        """مسار الروليت المعقد (توجيه -> اشتراك -> تصويت -> بوت -> عودة)"""
        if event.id in self.active_tasks: return
        self.active_tasks.add(event.id)

        original_chat = event.chat_id
        original_msg_id = event.id

        if not event.reply_markup: return

        # 1. الضغط على زر الروليت الأساسي
        for r, row in enumerate(event.reply_markup.rows):
            for b, btn in enumerate(row.buttons):
                if any(k in btn.text for k in HUNT_BUTTONS):
                    if btn.url and 't.me' in btn.url:
                        # توجيه لقناة أخرى (مثل التصويت)
                        match = re.search(r't\.me/([\w_]+)/(\d+)', btn.url)
                        if match:
                            target_channel = match.group(1)
                            target_msg_id = int(match.group(2))
                            
                            logger.info(f"🔄 مسار معقد: توجيه إلى {target_channel}")
                            await self.safe_join_channel(target_channel)
                            
                            # 2. جلب رسالة التصويت
                            try:
                                vote_msg = await self.client.get_messages(target_channel, ids=target_msg_id)
                                if vote_msg and vote_msg.reply_markup:
                                    # 3. الضغط على زر التصويت (القلب الشفاف)
                                    for vr, vrow in enumerate(vote_msg.reply_markup.rows):
                                        for vb, vbtn in enumerate(vrow.buttons):
                                            if any(vk in vbtn.text for vk in VOTE_BUTTONS) or not vbtn.text: # قد يكون بدون نص
                                                await vote_msg.click(vr, vb)
                                                logger.info("تم ضغط زر التصويت.")
                                                await asyncio.sleep(3)
                                                
                                                # هل يوجد توجيه لبوت التحقق بعد التصويت؟
                                                if vbtn.url and 't.me' in vbtn.url and 'bot' in vbtn.url.lower():
                                                    bot_match = re.search(r't\.me/([\w_]+bot)', vbtn.url, re.I)
                                                    if bot_match:
                                                        await self.handle_captcha_bot(bot_match.group(1))
                                                        await asyncio.sleep(2)
                                                        
                            except Exception as e:
                                logger.error(f"خطأ في رسالة التصويت: {e}")
                            
                            # 4. العودة للروليت الأصلية وتأكيد الانضمام
                            logger.info("🔙 العودة للروليت الأصلية للتأكيد...")
                            try:
                                original_msg = await self.client.get_messages(original_chat, ids=original_msg_id)
                                await original_msg.click(r, b)
                            except: pass
                    else:
                        # روليت مباشر بدون توجيه
                        try:
                            # استخراج روابط الانضمام الإجبارية أولاً
                            links = re.findall(r'(?:t\.me/|@)([\w_]+)', event.text or "")
                            for link in set(links):
                                await self.safe_join_channel(link)
                            
                            await asyncio.sleep(random.uniform(2, 5))
                            await event.click(r, b)
                            logger.info("✅ تم المشاركة في الروليت المباشر.")
                        except: pass

    async def start(self):
        await self.client.start()
        logger.info("🚀 Zsewwi Hunter يعمل بكفاءة...")

        # --- مستمع الـ VPS (سحب وإرسال فقط) ---
        @self.client.on(events.NewMessage(chats=TARGET_VPS_CHANNEL))
        async def vps_watcher(event):
            text = event.raw_text or ""
            ip = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', text)
            user = re.search(r'(?:User[:\s]*|👤\s*User[:\s]*)(\S+)', text, re.I)
            pwd = re.search(r'(?:password[:\s]*|🔐\s*New password[:\s]*|password[:\s]*)(\S+)', text, re.I)

            if ip and pwd:
                ip_val = ip.group(1)
                pwd_val = pwd.group(1)
                user_val = user.group(1) if user else "root"
                
                msg = f"🔥 **VPS جديد تم اصطياده بسرعة!**\n`{ip_val}`\n`{user_val}`\n`{pwd_val}`"
                await self.client.send_message(NOTIFY_USER, msg)
                logger.info(f"⚡ تم إرسال بيانات VPS إلى {NOTIFY_USER}")

        # --- مستمع الروليت والمسابقات ---
        @self.client.on(events.NewMessage())
        async def roulette_handler(event):
            text = event.text or ""
            
            # التعليق الإجباري
            if "يستحق" in text or "التعليق" in text:
                try:
                    await asyncio.sleep(random.uniform(3, 7))
                    await self.client.send_message(event.chat_id, "يستحق", comment_to=event.id)
                except: pass
            
            # إذا كان هناك أزرار، نقوم بمعالجتها
            if event.reply_markup:
                await self.process_complex_roulette(event)

        await self.client.run_until_disconnected()

if __name__ == "__main__":
    bot = ZsewwiBot()
    asyncio.run(bot.start())
                                
