#!/usr/bin/env python3
"""
■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
Omega VPS Hunter – صائد الـ VPS + روليت 24/7
يراقب قناة FreeinternetTM ويسحب بيانات VPS بسرعة البرق
يدير حسابين | لوحة تحكم حية | أوامر تحكم كاملة
■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
"""
import os, asyncio, random, re, time, logging, json
from datetime import datetime, timedelta
from telethon import TelegramClient, events, functions, types, Button
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.account import UpdateStatusRequest, UpdateProfileRequest
from telethon.errors import (
    FloodWaitError, UserBannedInChannelError, PeerFloodError,
    AuthKeyDuplicatedError
)

# ---------- إعداد السجلات ----------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('omega_vps_hunter.log'), logging.StreamHandler()]
)
logger = logging.getLogger("OmegaVPS")

# ---------- متغيرات البيئة ----------
API_ID_1 = int(os.environ["API_ID_1"]); API_HASH_1 = os.environ["API_HASH_1"]; SESSION_1 = os.environ["SESSION_1"]
API_ID_2 = int(os.environ.get("API_ID_2", 0)); API_HASH_2 = os.environ.get("API_HASH_2", ""); SESSION_2 = os.environ.get("SESSION_2", "")
ADMIN_ID = int(os.environ["ADMIN_ID"])
TARGET_CHANNEL = "FreeinternetTM"      # القناة التي نراقبها
NOTIFY_USER = "KOA_7"                  # الحساب الذي تصل إليه بيانات VPS (يمكن تغييره إلى @Pro)

# كلمات الصيد
HUNT_KEYWORDS = [
    "مشاركة", "انضمام", "سحب", "دخول", "روليت", "هدية", "نجوم",
    "يلا", "سجل", "اضغط", "بسرعة", "التحق", "تأكيد", "شارك", "انقر"
]
DANGER_WORDS = ["أكثر نجوم", "من يضع", "تصويت بنجوم", "اكثر شخص يحط", "يحط يربح", "مزاد نجوم"]
SAFE_CONTEST_REGEX = r'أول\s*(شخص|واحد|من)\s*(ي|يلي)?\s*(كتب|يكتب|قال|يقول|رد|يرد|علق|يعلق)\s*[({\[].*?[)}\]]'

# ملف التعلم
LEARNING_FILE = "omega_vps_memory.json"
STATS_MSG_ID = None   # رسالة الإحصائيات الحية في المحفوظات

class OmegaVPSHunter:
    def __init__(self):
        self.c1 = TelegramClient(StringSession(SESSION_1), API_ID_1, API_HASH_1)
        self.c2 = TelegramClient(StringSession(SESSION_2), API_ID_2, API_HASH_2) if SESSION_2 else None
        self.running = True
        self.stats = {
            "vps_captured": 0, "wins": 0, "channels_left": 0,
            "start": time.time()
        }
        self.cache = set()
        self.memory = self.load_memory()
        self.main_client = None  # يُستخدم للإحصائيات وإرسال التنبيهات

    # ---------- ذاكرة التعلم ----------
    def load_memory(self):
        try:
            with open(LEARNING_FILE, 'r') as f:
                return json.load(f)
        except:
            return {"delay_multiplier": 1.0, "bad_channels": []}

    def save_memory(self):
        with open(LEARNING_FILE, 'w') as f:
            json.dump(self.memory, f, indent=2)

    async def learn_from_error(self, error, channel_id=None):
        if isinstance(error, FloodWaitError):
            self.memory['delay_multiplier'] = min(3.0, self.memory['delay_multiplier'] + 0.1)
            self.save_memory()
        elif isinstance(error, (UserBannedInChannelError, PeerFloodError)) and channel_id:
            self.memory['bad_channels'].append(channel_id)
            self.save_memory()

    def is_bad(self, cid): return cid in self.memory['bad_channels']

    def get_delay(self):
        return random.uniform(1.5 * self.memory['delay_multiplier'], 4.0 * self.memory['delay_multiplier'])

    # ========== اتصال ==========
    async def connect(self, client, name):
        for _ in range(3):
            try:
                await client.connect()
                if await client.is_user_authorized():
                    logger.info(f"✅ {name}")
                    return True
            except AuthKeyDuplicatedError:
                logger.critical(f"🔑 {name} الجلسة مكررة! أوقف أي تشغيل آخر.")
                break
            except Exception as e:
                logger.error(f"❌ {name}: {e}")
            await asyncio.sleep(10)
        return False

    async def keep_alive(self, client, name):
        while self.running:
            try:
                if not client.is_connected():
                    await client.connect()
                await client(UpdateStatusRequest(offline=False))
            except:
                pass
            await asyncio.sleep(120)

    # ========== إحصائيات حية (رسالة واحدة في المحفوظات) ==========
    async def update_stats_msg(self):
        global STATS_MSG_ID
        if not self.main_client:
            return
        uptime = str(timedelta(seconds=int(time.time() - self.stats['start'])))
        msg = (
            f"📊 **Omega VPS Hunter**\n"
            f"🕒 {datetime.now().strftime('%H:%M:%S')}\n"
            f"⏱️ مدة: {uptime}\n"
            f"🌐 VPS تم اصطيادها: {self.stats['vps_captured']}\n"
            f"🏆 روليت: {self.stats['wins']}\n"
            f"🚪 قنوات غادرت: {self.stats['channels_left']}\n"
            f"🐌 مضاعف التأخير: {self.memory['delay_multiplier']:.2f}\n"
            f"🟢 الحالة: {'يعمل' if self.running else 'متوقف'}"
        )
        try:
            if STATS_MSG_ID:
                await self.main_client.edit_message('me', STATS_MSG_ID, msg)
            else:
                sent = await self.main_client.send_message('me', msg)
                STATS_MSG_ID = sent.id
        except:
            pass

    # ========== مراقبة قناة الـ VPS ==========
    async def vps_watcher(self, event):
        """استخراج بيانات VPS من رسالة وإرسالها إلى المستخدم"""
        text = event.raw_text or ""
        # نمط regex متسامح لاستخراج IP, User, Password
        ip = re.search(r'(?:IP[:\s]*|🌐\s*IP[:\s]*)(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', text)
        user = re.search(r'(?:User[:\s]*|👤\s*User[:\s]*)(\S+)', text)
        pwd = re.search(r'(?:New password[:\s]*|🔐\s*New password[:\s]*|password[:\s]*)(\S+)', text)

        if ip and user and pwd:
            ip_val = ip.group(1)
            user_val = user.group(1)
            pwd_val = pwd.group(1)
            # تجنب الإرسال إذا كانت البيانات مكررة (اختياري)
            self.stats['vps_captured'] += 1
            await self.update_stats_msg()

            # إرسال إلى المستخدم المحدد مع أزرار نسخ
            msg = (
                f"🌐 **VPS جديد تم اصطياده!**\n"
                f"▪️ IP: `{ip_val}`\n"
                f"▪️ User: `{user_val}`\n"
                f"▪️ Password: `{pwd_val}`"
            )
            try:
                await self.main_client.send_message(
                    NOTIFY_USER, msg,
                    buttons=[
                        [Button.inline("📋 نسخ IP", f"copy_{ip_val}"),
                         Button.inline("📋 نسخ كلمة السر", f"copy_{pwd_val}")]
                    ]
                )
                logger.info(f"✅ تم إرسال VPS {ip_val} إلى {NOTIFY_USER}")
            except Exception as e:
                logger.error(f"فشل إرسال VPS: {e}")

    # ========== حل الكابتشا ==========
    async def solve_captcha(self, event):
        if not event.reply_markup: return False
        text = event.raw_text or ""
        # رياضيات
        m = re.search(r'(\d+)\s*([+\-*/])\s*(\d+)', text)
        if m:
            res = str(eval(f"{m.group(1)}{m.group(2)}{m.group(3)}"))
            for r, row in enumerate(event.reply_markup.rows):
                for b, btn in enumerate(row.buttons):
                    if btn.text.strip() == res:
                        await event.click(r, b)
                        return True
        # إيموجي
        em = re.search(r'\((.*?)\)', text)
        if em:
            target = em.group(1).strip()
            for r, row in enumerate(event.reply_markup.rows):
                for b, btn in enumerate(row.buttons):
                    if target in btn.text:
                        await event.click(r, b)
                        return True
        return False

    # ========== تنفيذ إجراءات التوجيه (قنوات، تصويت، كتابة) ==========
    async def follow_redirects(self, event, client):
        """يتابع الأزرار التي توجه إلى قنوات أو تتطلب كتابة تعليق أو تصويت"""
        if not event.reply_markup: return
        for row in event.reply_markup.rows:
            for btn in row.buttons:
                # أزرار تحوي روابط
                if btn.url and 't.me' in btn.url:
                    await self.handle_redirect_link(btn.url, client)
                    return
                # أزرار مثل "هنا" أو "قناة" (callback قد يفتح توجيه)
                if any(w in btn.text for w in ['هنا', 'قناة', 'انضم', 'اضغط']):
                    try:
                        await event.click(row.row_index, btn.column_index)
                        await asyncio.sleep(2)
                        # بعد النقر قد نظهر رسالة جديدة، لا نستطيع متابعتها آلياً بسهولة
                        # لكن سنحاول العودة للرسالة الأصلية وننقر أزرارها
                        return
                    except: pass

    async def handle_redirect_link(self, url, client):
        """الانضمام لقناة وإجراء التصويت المطلوب"""
        match = re.match(r'(?:https?://)?t\.me/([\w\d_]+)/?(\d+)?', url)
        if not match: return
        username, msg_id = match.group(1), match.group(2)
        try:
            entity = await client.get_entity(username)
            await client(JoinChannelRequest(entity))
            if msg_id:
                target_msg = await client.get_messages(entity, ids=int(msg_id))
                if target_msg and target_msg.reply_markup:
                    # نبحث عن زر تصويت (قلب، 👍…)
                    for row in target_msg.reply_markup.rows:
                        for btn in row.buttons:
                            if any(k in btn.text for k in ['❤️','👍','👎','تصويت','vote']):
                                await target_msg.click(row.row_index, btn.column_index)
                                return
                    # وإلا نضغط أول زر
                    await target_msg.click(0, 0)
                elif target_msg:
                    # ربما نحتاج كتابة "يستحق"
                    try:
                        await target_msg.reply("يستحق")
                    except: pass
        except Exception as e:
            logger.warning(f"فشل في معالجة رابط التوجيه {url}: {e}")

    # ========== المعالج الرئيسي للروليت ==========
    async def handle_roulette(self, event, client):
        if not self.running: return
        chat = await event.get_chat()
        chat_id = chat.id
        if self.is_bad(chat_id): return

        text = event.raw_text or ""
        if any(w in text for w in DANGER_WORDS): return

        # مسابقة آمنة
        safe = re.search(SAFE_CONTEST_REGEX, text, re.I)
        if safe:
            reply_text = re.search(r'[({\[].*?[)}\]]', text)
            reply_text = reply_text.group(0).strip('(){}[]') if reply_text else "تم"
            try: await event.reply(reply_text)
            except: pass
            if event.reply_markup:
                await self.process_buttons(event, client, chat_id)
            return

        if event.id in self.cache: return

        if event.reply_markup:
            # حل كابتشا أولاً
            if await self.solve_captcha(event):
                self.cache.add(event.id)
                return

            # ابحث عن أزرار توجيه (ذات روابط)
            btn_texts = [btn.text for row in event.reply_markup.rows for btn in row.buttons]
            has_redirect = any('t.me' in (btn.url or '') for row in event.reply_markup.rows for btn in row.buttons)

            if has_redirect or any(w in btn_texts for w in ['هنا', 'قناة', 'تصويت', 'علق']):
                await self.follow_redirects(event, client)
                # بعد تنفيذ التوجيه، نعود ونضغط أزرار الصيد
                await asyncio.sleep(2)
                try:
                    # نعيد جلب الرسالة الأصلية
                    fresh = await client.get_messages(chat_id, ids=event.id)
                    if fresh and fresh.reply_markup:
                        await self.click_hunt(fresh, client, chat_id)
                except: pass
                return

            # روليت عادي
            if any(k in (text + " ".join(btn_texts)).lower() for k in HUNT_KEYWORDS):
                self.cache.add(event.id)
                await self.join_required(event, client)
                delay = self.get_delay()
                await asyncio.sleep(delay)
                await self.click_hunt(event, client, chat_id)

    async def click_hunt(self, event, client, chat_id):
        if not event.reply_markup: return
        for row in event.reply_markup.rows:
            for btn in row.buttons:
                if any(k in btn.text for k in HUNT_KEYWORDS) or "مشاركة" in btn.text:
                    try:
                        await event.click(row.row_index, btn.column_index)
                        self.stats['wins'] += 1
                        if self.stats['wins'] % 10 == 0:
                            self.memory['delay_multiplier'] = max(0.8, self.memory['delay_multiplier'] - 0.05)
                            self.save_memory()
                        return
                    except FloodWaitError as e:
                        await self.learn_from_error(e)
                        await asyncio.sleep(e.seconds + 1)
                    except (UserBannedInChannelError, PeerFloodError) as e:
                        await self.learn_from_error(e, chat_id)
                        try: await client(LeaveChannelRequest(chat_id))
                        except: pass
                        self.stats['channels_left'] += 1
                    except: pass
        # زر شفاف/أي زر متبقٍ
        try:
            await event.click(0, 0)
            self.stats['wins'] += 1
        except: pass

    async def join_required(self, event, client):
        links = set()
        if event.entities:
            for e in event.entities:
                if hasattr(e, 'url') and 't.me' in (e.url or ''):
                    links.add(e.url)
        links.update(re.findall(r'(?:t\.me/[\w\d_]+|@[\w\d_]+)', event.raw_text))
        for l in links:
            name = l.split('/')[-1].replace('@', '')
            try: await client(JoinChannelRequest(name))
            except: pass

    # ========== تنظيف القنوات الميتة ==========
    async def leave_dead_channels(self):
        count = 0
        clients = [self.c1] if not self.c2 else [self.c1, self.c2]
        for client in clients:
            async for d in client.iter_dialogs():
                if not d.is_channel: continue
                try:
                    msgs = await client.get_messages(d.entity, limit=1)
                    if not msgs or not msgs[0].date:
                        await client(LeaveChannelRequest(d.entity))
                        count += 1
                except: pass
        self.stats['channels_left'] += count
        if count: logger.info(f"🧹 غادرت {count} قناة ميتة")

    # ========== أوامر ==========
    async def handle_command(self, event, parts):
        cmd = parts[0][1:].lower()
        if cmd == "stop":
            self.running = False
            await event.reply("🛑 تم إيقاف المحرك")
        elif cmd == "start":
            self.running = True
            await event.reply("✅ تم تشغيل المحرك")
        elif cmd == "stats":
            await self.update_stats_msg()
            await event.reply("✅ تم تحديث الإحصائيات")
        elif cmd == "leavedead":
            await self.leave_dead_channels()
            await event.reply("🧹 تم تنظيف القنوات الميتة")
        elif cmd == "panel":
            btns = [
                [Button.inline("📊 إحصائيات", b"copy_stats"),
                 Button.inline("🛑 إيقاف", b"copy_stop"),
                 Button.inline("✅ تشغيل", b"copy_start")],
                [Button.inline("🧹 مغادرة الميتة", b"copy_leavedead")]
            ]
            await event.respond("🔥 **Omega VPS Hunter**", buttons=btns)

    # ========== تشغيل ==========
    async def main(self):
        if not await self.connect(self.c1, "حساب 1"): return
        self.main_client = self.c1
        if self.c2 and not await self.connect(self.c2, "حساب 2"): self.c2 = None

        # ---------- مستمعات ----------
        # 1. مراقبة قناة الـ VPS (حساب 1)
        @self.c1.on(events.NewMessage(chats=TARGET_CHANNEL))
        async def vps_handler(event):
            await self.vps_watcher(event)

        # 2. روليت – حساب 1
        @self.c1.on(events.NewMessage())
        async def r1(event):
            if event.sender_id == ADMIN_ID and event.raw_text.startswith("."):
                await self.handle_command(event, event.raw_text.split())
            elif event.is_channel or event.is_group:
                await self.handle_roulette(event, self.c1)

        # 3. حساب 2 (إن وجد) – روليت فقط
        if self.c2:
            @self.c2.on(events.NewMessage())
            async def r2(event):
                if event.is_channel or event.is_group:
                    await self.handle_roulette(event, self.c2)

        # ---------- أزرار اللوحة ----------
        @self.c1.on(events.CallbackQuery)
        async def cb(event):
            data = event.data.decode()
            if data.startswith("copy_"):
                cmd = data[5:]
                await event.answer(f"✅ تم نسخ .{cmd}")
            elif data.startswith("copy_shell_"):
                await event.answer("✅ تم نسخ النص")

        # ---------- مهام دورية ----------
        asyncio.create_task(self.keep_alive(self.c1, "ح1"))
        if self.c2: asyncio.create_task(self.keep_alive(self.c2, "ح2"))

        async def periodic():
            while self.running:
                await asyncio.sleep(21600)  # كل 6 ساعات
                await self.leave_dead_channels()
                await self.update_stats_msg()
        asyncio.create_task(periodic())

        # إظهار الحسابين متصلين دائمًا
        await self.c1(UpdateStatusRequest(offline=False))
        if self.c2: await self.c2(UpdateStatusRequest(offline=False))

        # رسالة بدء التشغيل
        await self.main_client.send_message(
            'me',
            "👋 **Omega VPS Hunter انطلق**\n"
            f"🎯 يراقب {TARGET_CHANNEL}\n"
            f"📨 يرسل VPS إلى {NOTIFY_USER}\n"
            ".panel للوحة التحكم"
        )
        await self.update_stats_msg()
        logger.info("🚀 Omega VPS Hunter يعمل الآن")
        await self.c1.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(OmegaVPSHunter().main())
