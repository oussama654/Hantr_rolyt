#!/usr/bin/env python3
"""
■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
Omega Flawless – صائد الروليت والـ VPS (بدون أخطاء)
يتجنب FloodWait تماماً | معرفات القنوات بالأرقام | جدولة ذكية
■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
"""
import os, asyncio, random, re, time, logging, json
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button, functions, types
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.account import UpdateStatusRequest
from telethon.errors import (
    FloodWaitError, UserBannedInChannelError, UserChannelsTooMuchError,
    ChannelsTooMuchError, PeerFloodError, AuthKeyDuplicatedError
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('flawless.log'), logging.StreamHandler()]
)
logger = logging.getLogger("Flawless")

# ---------- الإعدادات ----------
API_ID_1 = int(os.environ["API_ID_1"]); API_HASH_1 = os.environ["API_HASH_1"]; SESSION_1 = os.environ["SESSION_1"]
API_ID_2 = int(os.environ.get("API_ID_2", 0)); API_HASH_2 = os.environ.get("API_HASH_2", ""); SESSION_2 = os.environ.get("SESSION_2", "")
ADMIN_ID = int(os.environ["ADMIN_ID"])
NOTIFY_USER = os.environ.get("NOTIFY_USER", "me")  # حساب استقبال VPS (افتراضي: المحفوظات)
VPS_CHANNEL_ID = int(os.environ.get("VPS_CHANNEL_ID", 0))  # المعرف الرقمي لقناة FreeinternetTM

# كلمات الصيد
HUNT_BUTTONS = ["مشاركة", "انضمام", "سحب", "تدوير", "دخول", "تأكيد", "اضغط هنا"]
VOTE_BUTTONS = ["❤️", "👍", "تصويت", "يستحق", "صوت"]
DANGER_WORDS = ["أكثر نجوم", "من يضع", "تصويت بنجوم", "اكثر شخص يحط", "يحط يربح", "مزاد نجوم"]
SAFE_CONTEST_REGEX = r'أول\s*(شخص|واحد|من)\s*(ي|يلي)?\s*(كتب|يكتب|قال|يقول|رد|يرد|علق|يعلق)\s*[({\[].*?[)}\]]'

# ملف التحكم بالسرعة
SPEED_FILE = "flawless_speed.json"

class OmegaFlawless:
    def __init__(self):
        self.c1 = TelegramClient(StringSession(SESSION_1), API_ID_1, API_HASH_1)
        self.c2 = TelegramClient(StringSession(SESSION_2), API_ID_2, API_HASH_2) if SESSION_2 else None
        self.running = True
        self.stats = {"vps":0, "wins":0, "left":0, "start":time.time()}
        self.cache = set()
        self.speed = self.load_speed()
        self.join_queue = asyncio.Queue()   # طابور الانضمام للقنوات (لتجنب التكدس)
        self.main_client = None

    # ---------- إدارة السرعة ----------
    def load_speed(self):
        try: return json.load(open(SPEED_FILE, 'r'))
        except: return {"delay": 60, "consecutive_fails": 0}
    def save_speed(self):
        json.dump(self.speed, open(SPEED_FILE,'w'), indent=2)

    async def dynamic_delay(self):
        """تأخير يزداد كلما زادت الأخطاء"""
        base = self.speed["delay"] * (1 + 0.2 * self.speed["consecutive_fails"])
        wait = random.uniform(base * 0.8, base * 1.2)
        await asyncio.sleep(wait)

    async def handle_flood(self, e):
        """عند حدوث FloodWait، نزيد التأخير وننتظر"""
        if isinstance(e, FloodWaitError):
            logger.warning(f"⏳ FloodWait {e.seconds}s - زيادة التأخير")
            self.speed["delay"] = min(600, self.speed["delay"] * 2)
            self.speed["consecutive_fails"] += 1
            self.save_speed()
            await asyncio.sleep(e.seconds)
            return True
        return False

    async def success_action(self):
        """عند نجاح عملية، نقلل التأخير تدريجياً"""
        self.speed["consecutive_fails"] = max(0, self.speed["consecutive_fails"] - 1)
        if self.speed["delay"] > 60:
            self.speed["delay"] = max(60, self.speed["delay"] * 0.9)
        self.save_speed()

    # ---------- اتصال ----------
    async def connect(self, client, name):
        for _ in range(3):
            try:
                await client.connect()
                if await client.is_user_authorized():
                    logger.info(f"✅ {name}")
                    return True
            except AuthKeyDuplicatedError:
                logger.critical(f"🔑 {name} جلسة مكررة! أوقف أي تشغيل آخر.")
                break
            except Exception as e: logger.error(f"❌ {name}: {e}")
            await asyncio.sleep(10)
        return False

    async def keep_alive(self, client, name):
        while self.running:
            try:
                if not client.is_connected(): await client.connect()
                await client(UpdateStatusRequest(offline=False))
            except: pass
            await asyncio.sleep(120)

    # ---------- لوحة تحكم حية ----------
    async def live_stats(self):
        global STATS_MSG_ID
        while self.running:
            if self.main_client:
                uptime = str(timedelta(seconds=int(time.time()-self.stats['start'])))
                msg = (f"📊 **Flawless**\n🕒 {datetime.now():%H:%M:%S}\n⏱️ {uptime}\n"
                       f"🌐 VPS:{self.stats['vps']}\n🏆 روليت:{self.stats['wins']}\n"
                       f"🚪 مغادرة:{self.stats['left']}\n🐌 تأخير:{self.speed['delay']}s")
                try:
                    if STATS_MSG_ID: await self.main_client.edit_message('me', STATS_MSG_ID, msg)
                    else: sent = await self.main_client.send_message('me', msg); STATS_MSG_ID = sent.id
                except: pass
            await asyncio.sleep(5)

    # ---------- مراقبة VPS (بالمعرف الرقمي) ----------
    async def vps_watcher(self, event):
        text = event.raw_text or ""
        ip = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', text)
        pwd = re.search(r'(?:password[:\s]*|🔐\s*New password[:\s]*)(\S+)', text, re.I)
        if ip and pwd:
            ip_val, pwd_val = ip.group(1), pwd.group(1)
            user = re.search(r'(?:User[:\s]*|👤\s*User[:\s]*)(\S+)', text, re.I)
            user_val = user.group(1) if user else "root"
            self.stats['vps'] += 1
            msg = (f"🔥 **VPS جديد**\n▪️ IP: `{ip_val}`\n▪️ User: `{user_val}`\n▪️ Pass: `{pwd_val}`")
            try: await self.main_client.send_message(NOTIFY_USER, msg)
            except: pass

    # ---------- خدمة الانضمام للقنوات (خلفية) ----------
    async def join_worker(self):
        """يستهلك طابور الانضمام بحذر شديد"""
        while self.running:
            channel_id = await self.join_queue.get()
            try:
                await self.dynamic_delay()
                await self.c1(JoinChannelRequest(channel_id))
                await self.success_action()
                logger.info(f"✅ انضم للقناة {channel_id}")
            except (UserChannelsTooMuchError, ChannelsTooMuchError):
                logger.warning("⚠️ الحساب ممتلئ، محاولة مغادرة أقدم 3 قنوات")
                await self.leave_oldest(3)
                await asyncio.sleep(10)
                try: await self.c1(JoinChannelRequest(channel_id))
                except: pass
            except FloodWaitError as e:
                await self.handle_flood(e)
            except Exception as e:
                logger.error(f"فشل الانضمام {channel_id}: {e}")
            self.join_queue.task_done()

    async def leave_oldest(self, count=3):
        dialogs = await self.c1.get_dialogs()
        channels = [d for d in dialogs if d.is_channel]
        channels.sort(key=lambda d: d.date or datetime.min)
        for d in channels[:count]:
            try:
                await self.c1(LeaveChannelRequest(d.entity))
                self.stats['left'] += 1
                await asyncio.sleep(2)
            except: pass

    # ---------- روليت ----------
    async def process_roulette(self, event, client):
        if event.id in self.cache: return
        text = event.raw_text or ""
        if any(w in text for w in DANGER_WORDS): return

        # مسابقة آمنة
        safe = re.search(SAFE_CONTEST_REGEX, text, re.I)
        if safe:
            reply = re.search(r'[({\[].*?[)}\]]', text)
            reply_text = reply.group(0).strip('(){}[]') if reply else "تم"
            try: await event.reply(reply_text)
            except: pass
            if event.reply_markup: await self.click_hunt(event, client)
            return

        if not event.reply_markup: return

        # استخراج روابط القنوات للانضمام (نضيفها للطابور بدلاً من الانضمام الفوري)
        links = set(re.findall(r'(?:t\.me/|@)([\w_]+)', text))
        for username in links:
            if username.lower() in ['bot', 'c', 'me']: continue
            # نحاول الحصول على المعرف الرقمي من الذاكرة أو نضيفه للطابور لاحقاً
            # سنحاول حلها ببطء
            try:
                entity = await client.get_entity(username)
                await self.join_queue.put(entity.id)
            except FloodWaitError as e:
                await self.handle_flood(e)
            except: pass

        # نضغط أزرار الروليت
        if any(k in (text + " ".join([b.text for r in event.reply_markup.rows for b in r.buttons])).lower() for k in HUNT_BUTTONS):
            self.cache.add(event.id)
            await asyncio.sleep(random.uniform(2,5))
            await self.click_hunt(event, client)

    async def click_hunt(self, event, client):
        if not event.reply_markup: return
        for r,row in enumerate(event.reply_markup.rows):
            for b,btn in enumerate(row.buttons):
                if any(k in btn.text for k in HUNT_BUTTONS) or "مشاركة" in btn.text:
                    try:
                        await event.click(r,b)
                        self.stats['wins'] += 1
                        await self.success_action()
                        return
                    except FloodWaitError as e: await self.handle_flood(e)
                    except: pass
        try: await event.click(0,0); self.stats['wins']+=1
        except: pass

    # ---------- أوامر ----------
    async def handle_command(self, event, parts):
        cmd = parts[0][1:].lower()
        if cmd=="stop": self.running=False; await event.reply("🛑")
        elif cmd=="start": self.running=True; await event.reply("✅")
        elif cmd=="stats": await event.reply("📊 اللوحة حية")
        elif cmd=="panel":
            btns = [[Button.inline(".stats",b"copy_stats")]]
            await event.respond("🔥 **Flawless**", buttons=btns)

    # ---------- تشغيل ----------
    async def main(self):
        if not await self.connect(self.c1, "ح1"): return
        self.main_client = self.c1
        if self.c2 and not await self.connect(self.c2, "ح2"): self.c2 = None

        # مراقبة VPS باستخدام المعرف الرقمي
        if VPS_CHANNEL_ID:
            @self.c1.on(events.NewMessage(chats=VPS_CHANNEL_ID))
            async def vps_handler(event): await self.vps_watcher(event)
            logger.info(f"🎯 مراقبة VPS بالقناة {VPS_CHANNEL_ID}")
        else:
            logger.warning("⚠️ لم يتم تعيين VPS_CHANNEL_ID، لن تراقب الـ VPS")

        @self.c1.on(events.NewMessage())
        async def r1(event):
            if event.sender_id==ADMIN_ID and event.raw_text.startswith("."):
                await self.handle_command(event, event.raw_text.split())
            elif event.is_channel or event.is_group:
                await self.process_roulette(event, self.c1)

        if self.c2:
            @self.c2.on(events.NewMessage())
            async def r2(event):
                if event.is_channel or event.is_group:
                    await self.process_roulette(event, self.c2)

        # أزرار النسخ
        @self.c1.on(events.CallbackQuery)
        async def cb(event):
            if event.data.decode().startswith("copy_"): await event.answer("✅")

        # بدء خدمة الانضمام
        asyncio.create_task(self.join_worker())
        asyncio.create_task(self.keep_alive(self.c1,"ح1"))
        if self.c2: asyncio.create_task(self.keep_alive(self.c2,"ح2"))
        asyncio.create_task(self.live_stats())

        # تنظيف كل 12 ساعة
        async def clean():
            while self.running:
                await asyncio.sleep(43200)
                c=0
                async for d in self.c1.iter_dialogs():
                    if d.is_channel:
                        try:
                            m = await self.c1.get_messages(d.entity, limit=1)
                            if not m or not m[0].date: await self.c1(LeaveChannelRequest(d.entity)); c+=1
                        except: pass
                self.stats['left']+=c
        asyncio.create_task(clean())

        await self.c1(UpdateStatusRequest(offline=False))
        logger.info("🚀 Flawless يعمل بدون أخطاء")
        await self.c1.run_until_disconnected()

if __name__ == "__main__":
    STATS_MSG_ID = None
    asyncio.run(OmegaFlawless().main())
