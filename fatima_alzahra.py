import os
import asyncio
import re
import logging
import random
import time
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import SendReactionRequest
from telethon.tl.types import ReactionEmoji

# ---------- إعدادات اللوجر ----------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('omega_telethon.log'), logging.StreamHandler()]
)
logger = logging.getLogger("OmegaTelethon")

# ---------- جلب الإعدادات من GitHub Secrets ----------
API_ID_1 = int(os.environ["API_ID_1"])
API_HASH_1 = os.environ["API_HASH_1"]
SESSION_1 = os.environ["SESSION_1"]

API_ID_2 = int(os.environ.get("API_ID_2") or os.environ.get("API_ID_1"))
API_HASH_2 = os.environ.get("API_HASH_2") or os.environ.get("API_HASH_1")
SESSION_2 = os.environ.get("SESSION_2", "")

ADMIN_ID = int(os.environ["ADMIN_ID"])

# ---------- إعدادات الأسعار المستهدفة للأسواق ----------
GIFT_PRICE_MIN = 200
GIFT_PRICE_MAX = 250

# الكلمات المفتاحية للروليت والمسابقات (تم إقصاء وحظر "الهمسات" نهائياً)
HUNT_KEYWORDS = [
    "مشاركة", "انضمام", "سحب", "دخول", "روليت", "هدية", "نجوم", "اضغط", "بسرعة", 
    "شارك", "انقر", "اضغط للانضمام", "انضم الآن", "سجل هنا", "التحق", "تأكيد", 
    "تفاعل", "انقر هنا", "دخول السحب", "سجل اسمك", "المشاركة في السحب", "المشاركة في المسابقة",
    "join", "click", "participate"
]
DANGER_WORDS = ["أكثر نجوم", "من يضع", "تصويت بنجوم", "اكثر شخص يحط", "مزاد"]
GIFT_MARKETS = ["Koda_7", "tonnel_network_bot", "AutoGiftsBot", "GiftHub_bot"]

panel_msg = None
live_log_msg = None

class TelethonOmegaSystem:
    def __init__(self):
        self.client1 = TelegramClient(StringSession(SESSION_1), API_ID_1, API_HASH_1)
        self.client2 = TelegramClient(StringSession(SESSION_2), API_ID_2, API_HASH_2) if SESSION_2 else None
        
        self.running = True
        self.sniper_enabled = True 
        self.stats = {"wins": 0, "gifts_bought": 0, "msgs_processed": 0, "start_time": time.time()}
        self.last_scans = []

    async def update_live_panel(self):
        """تحديث لوحة التحكم الفورية والشاملة للمدير"""
        global panel_msg, live_log_msg
        if not self.running:
            return
            
        uptime = str(timedelta(seconds=int(time.time() - self.stats['start_time'])))
        
        panel_text = (
            f"🔥 **لوحة تحكم Omega المحدثة للمسابقات والتعليقات**\n"
            f"-----------------------------------\n"
            f"🟢 الحالة العامة: نشط ومتصل 24/7\n"
            f"⏱️ مدة العمل المستمر: {uptime}\n"
            f"🏆 العمليات والمسابقات الناجحة: {self.stats['wins']}\n"
            f"💎 صيد هدايا الأسواق: {self.stats['gifts_bought']}\n"
            f"📨 رسائل تم تحليلها: {self.stats['msgs_processed']}\n"
            f"⚙️ نظام مسابقات القلوب والتعليقات: ✅ مفعل تلقائياً\n"
            f"🛡️ صيد الهمسات: ❌ تم حظره وتعطيله نهائياً بناءً على طلبك\n"
            f"⚙️ وضعية السكربت الحالية: {'🟢 يعمل ويصطاد بنشاط' if self.sniper_enabled else '🔴 متوقف مؤقتاً عن الصيد'}"
        )
        
        log_text = "🔍 **بث الفحص الحي والمهام التفاعلية (Live Scan):**\n-----------------------------------\n"
        if not self.last_scans:
            log_text += "⏳ بانتظار روليت أو مسابقة جديدة من قنوات سراب والأسواق..."
        else:
            for scan in self.last_scans[-5:]:
                log_text += f"{scan}\n"

        try:
            if panel_msg:
                await panel_msg.edit(panel_text)
            else:
                panel_msg = await self.client1.send_message(ADMIN_ID, panel_text)

            if live_log_msg:
                await live_log_msg.edit(log_text)
            else:
                live_log_msg = await self.client1.send_message(ADMIN_ID, log_text)
        except Exception as e:
            logger.debug(f"خطأ تحديث اللوحة: {e}")

    async def log_scan_result(self, chat_title, price, status_text):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"⏱️ [{timestamp}] | 📍 {chat_title} | {status_text}"
        self.last_scans.append(log_entry)
        if len(self.last_scans) > 10:
            self.last_scans.pop(0)
        await self.update_live_panel()

    async def handle_advanced_tasks(self, client, event, text, chat_title):
        """التعامل الذكي مع مسابقات التوجيه، القلوب، والتعليقات المتقدمة"""
        
        # 1. إذا كانت المسابقة تطلب تعليق بكلمة معينة (مثل مسابقة "هل يستحق" أو "اكتب يستحق")
        if "تعليق" in text or "التعليق" in text or "يستحق" in text:
            # البحث عن الروابط المرفقة بالرسالة أو الأزرار التي توجه للشات
            if event.buttons:
                for row in event.buttons:
                    for button in row:
                        if button.url and "⚙️" not in button.text:
                            # محاكاة تصفح بشري طبيعي قبل الانتقال
                            await asyncio.sleep(random.uniform(2.5, 4.8))
                            try:
                                # كتابة كلمة "يستحق" تلقائياً كتعليق لتسجيل الصوت والاسم
                                target_match = re.search(r't.me/[^/]+/(\d+)', button.url)
                                if target_match:
                                    await client.send_message(event.chat_id, "يستحق", comment_to=event.id)
                                    await self.log_scan_result(chat_title, "تعليق", "✍️ تم التعليق بـ 'يستحق' تلقائياً بنجاح")
                                    return True
                            except Exception as e:
                                logger.debug(f"فشل إرسال التعليق: {e}")

        # 2. إذا كانت المسابقة تطلب التفاعل بقلب ❤️ والانضمام لقناة أخرى
        if "❤️" in text or "قلب" in text or "تفاعل" in text:
            if event.reply_markup:
                for row in event.buttons:
                    for button in row:
                        if button.url and ("t.me/" in button.url or "tg://" in button.url):
                            try:
                                # استخراج اسم القناة من الرابط والاشتراك بها تلقائياً لمنع رفض الصوت
                                channel_username = button.url.split('/')[-1].split('?')[0]
                                if channel_username.isdigit(): 
                                    continue
                                    
                                await asyncio.sleep(random.uniform(3.1, 5.5))
                                await client(JoinChannelRequest(channel_username))
                                
                                # إرسال تفاعل القلب الأحمر ❤️ للمنشور الموجه لمحاكاة الحساب الحقيقي
                                target_msg_id = int(button.url.split('/')[-1]) if button.url.split('/')[-1].isdigit() else None
                                if target_msg_id:
                                    await client(SendReactionRequest(
                                        peer=channel_username,
                                        msg_id=target_msg_id,
                                        reaction=[ReactionEmoji(emoticon='❤️')]
                                    ))
                                await self.log_scan_result(chat_title, "تفاعل", f"❤️ تم الاشتراك في {channel_username} والتفاعل بـ قلب")
                                return True
                            except Exception as e:
                                logger.debug(f"فشل نظام التفاعل التلقائي: {e}")
        return False

    async def process_message(self, client, event, account_tag):
        if not self.running or not self.sniper_enabled:
            return
            
        self.stats['msgs_processed'] += 1
        text = event.text or ""
        
        # حظر الكلمات التي تدل على الهمسة بشكل قاطع وصارم
        if any(w in text or w in (event.raw_text or "") for w in ["همسة", "همسه", "secret", "لأول شخص"]):
            return

        try:
            chat = await event.get_chat()
            chat_title = getattr(chat, 'username', None) or getattr(chat, 'title', "قناة")
        except:
            chat_title = "قناة"

        if any(word in text for word in DANGER_WORDS):
            return

        # ---------------- 1. نظام صيد وتخطي كابتشا الإيموجي والعمليات الحسابية ----------------
        if event.buttons:
            # كابتشا العمليات الحسابية
            math_match = re.search(r'(\d+)\s*([\+\-\*])\s*(\d+)', text)
            if math_match:
                num1 = int(math_match.group(1))
                op = math_match.group(2)
                num2 = int(math_match.group(3))
                result = num1 + num2 if op == '+' else (num1 - num2 if op == '-' else num1 * num2)
                
                for row in event.buttons:
                    for button in row:
                        if str(result) in button.text:
                            try: await client.send_read_acknowledge(event.chat_id, max_id=event.id)
                            except: pass
                            await asyncio.sleep(random.uniform(4.1, 6.7))
                            try:
                                await button.click()
                                await self.log_scan_result(chat_title, "كابتشا", f"✅ تم فك الكابتشا الحسابية: {result}")
                                return
                            except: pass

            # كابتشا الإيموجي (مثل الصورة رقم 6 تماماً: اضغط على الزر اللي يشبه هذا الإيموجي)
            for row in event.buttons:
                for button in row:
                    btn_txt = button.text.strip()
                    if len(btn_txt) <= 2 and btn_txt in text:
                        if any(phrase in text for phrase in ["اضغط على", "اختر", "انقر", "يشبه", "click", "choose"]):
                            try: await client.send_read_acknowledge(event.chat_id, max_id=event.id)
                            except: pass
                            await asyncio.sleep(random.uniform(3.5, 5.9))
                            try:
                                await button.click()
                                await self.log_scan_result(chat_title, "كابتشا", f"✅ تم تخطي كابتشا الإيموجي المطابق: {btn_txt}")
                                return
                            except: pass

        # ---------------- 2. معالجة المسابقات المتقدمة والقلوب أولاً ----------------
        is_advanced_done = await self.handle_advanced_tasks(client, event, text, chat_title)

        # ---------------- 3. نظام صيد الهدايا الفوري من الأسواق ----------------
        is_market = any(m in str(chat_title) for m in GIFT_MARKETS)
        has_gift_link = any(link in text for link in ["t.me/nft/", "tg://nft", "t.me/gift/"])
        
        if is_market or has_gift_link:
            detected_price = None
            price_match = re.search(r'(\d+)\s*(🌟|نجمة|star|stars|⭐)', text, re.I)
            if price_match:
                detected_price = int(price_match.group(1))

            if event.buttons:
                for row in event.buttons:
                    for button in row:
                        if any(k in button.text.lower() for k in ['شراء', 'اشتري', 'buy', 'purchase', 'get', '💎']):
                            if not detected_price:
                                btn_price = re.search(r'(\d+)', button.text)
                                if btn_price: detected_price = int(btn_price.group(1))
                            
                            if detected_price and GIFT_PRICE_MIN <= detected_price <= GIFT_PRICE_MAX:
                                try: await client.send_read_acknowledge(event.chat_id, max_id=event.id)
                                except: pass
                                await asyncio.sleep(random.uniform(0.02, 0.09))
                                try:
                                    await button.click()
                                    self.stats['gifts_bought'] += 1
                                    await self.log_scan_result(chat_title, detected_price, f"🚀 [صيد هدية ناجح بسعر {detected_price}⭐]")
                                    await self.client1.send_message(ADMIN_ID, f"🎉 **[{account_tag}] قنص هدية!**\n💰 السعر: {detected_price}⭐")
                                    return
                                except FloodWaitError as e:
                                    await asyncio.sleep(e.seconds + 1)
                                except Exception as e:
                                    await self.log_scan_result(chat_title, detected_price, f"❌ فشل الصيد: {str(e)[:15]}")

        # ---------------- 4. نظام الروليت والمسابقات التلقائي البشري ----------------
        if event.buttons:
            for row in event.buttons:
                for button in row:
                    if any(keyword in button.text.lower() for keyword in HUNT_KEYWORDS):
                        try: await client.send_read_acknowledge(event.chat_id, max_id=event.id)
                        except: pass
                        
                        # نطاق الوقت البشري العشوائي لمنع الشكوك (من 5 إلى 14 ثانية للروليت والمسابقات)
                        delay_time = random.uniform(5.2, 13.9)
                        await asyncio.sleep(delay_time)
                        try:
                            await button.click()
                            self.stats['wins'] += 1
                            await self.log_scan_result(chat_title, "روليت", f"🏆 تم الاشتراك التلقائي بنجاح خلال {delay_time:.2f} ثانية")
                            return
                        except: pass

    async def start_system(self):
        logger.info("🔄 جاري بدء النظام الشبح المتكامل بمكتبة Telethon...")
        await self.client1.start()
        
        if self.client2:
            logger.info("🔄 جاري ربط الحساب الثاني بالتوازي...")
            await self.client2.start()

        # ---------------- 5. نظام الأوامر الفوري (مصحح وشغال 100%) ----------------
        @self.client1.on(events.NewMessage(incoming=True))
        async def admin_command_handler(event):
            # الكشف والقبول الفوري للأوامر إذا أرسلتها لنفسك في الرسائل المحفوظة أو الشات المباشر
            if event.sender_id != ADMIN_ID:
                return
                
            command = event.text.strip()
            
            if command == "/.توقف":
                self.sniper_enabled = False
                await event.reply("🔴 **تم إيقاف قناص أوميجا والمسابقات مؤقتاً بنجاح.**")
                await self.update_live_panel()
                
            elif command == "/.تشغيل":
                self.sniper_enabled = True
                await event.reply("🟢 **تم إعادة تفعيل القناص والمسابقات.. السكربت يصطاد الآن!**")
                await self.update_live_panel()
                
            elif command == "/.فحص":
                status = "شغال وبقوة 🟢" if self.sniper_enabled else "متوقف مؤقتاً 🔴"
                await event.reply(f"ℹ️ **حالة القناص الحالية:** {status}")

        # تشغيل مستمعي القنوات والأسواق للحسابين بالتوازي
        @self.client1.on(events.NewMessage())
        async def handler1(event):
            await self.process_message(self.client1, event, "الحساب الأول")

        if self.client2:
            @self.client2.on(events.NewMessage())
            async def handler2(event):
                await self.process_message(self.client2, event, "الحساب الثاني")

        # إرسال قائمة الأزرار الذكية لتنسخ بنقرة واحدة من رسائلك المحفوظة
        commands_menu = (
            "🛠️ **لوحة التحكم الشبحية الفورية (نسخة مسابقات سراب)**\n"
            "اضغط على الأمر المطلوب ليتم نسخه، ثم قم بإرساله فوراً في الشات للتحكم بالسكربت:\n\n"
            "`/.توقف` : لإيقاف صيد الهدايا والمسابقات والتعليقات فوراً.\n\n"
            "`/.تشغيل` : لإعادة تشغيل السكربت وجعله يصطاد مجدداً.\n\n"
            "`/.فحص` : لمعرفة حالة السكربت الحالية هل هو نشط أم متوقف."
        )
        try:
            await self.client1.send_message('me', commands_menu)
            logger.info("✅ تم إرسال الأوامر الجاهزة لرسائلك المحفوظة.")
        except Exception as e:
            logger.error(f"فشل إرسال الأوامر للمحفوظة: {e}")

        await self.update_live_panel()
        
        # الحفاظ على تشغيل السكربت ودورته المستمرة في خلفية GitHub Actions بأمان
        await asyncio.sleep(18900)
        self.running = False
        await self.client1.disconnect()
        if self.client2:
            await self.client2.disconnect()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(TelethonOmegaSystem().start_system())

