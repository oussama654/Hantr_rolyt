#!/usr/bin/env python3
"""
■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
Omega Flawless v2 – صائد الـ VPS والروليت
يعالج FloodWait السابق بذكاء | استخراج VPS من تنسيقات متعددة
■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
"""
import os, asyncio, random, re, time, logging, json
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button, functions
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.account import UpdateStatusRequest
from telethon.errors import (
    FloodWaitError, UserBannedInChannelError, UserChannelsTooMuchError,
    ChannelsTooMuchError, AuthKeyDuplicatedError
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('flawless_v2.log'), logging.StreamHandler()]
)
logger = logging.getLogger("FlawlessV2")

# ---------- الإعدادات ----------
API_ID_1 = int(os.environ["API_ID_1"]); API_HASH_1 = os.environ["API_HASH_1"]; SESSION_1 = os.environ["SESSION_1"]
API_ID_2 = int(os.environ.get("API_ID_2", 0)); API_HASH_2 = os.environ.get("API_HASH_2", ""); SESSION_2 = os.environ.get("SESSION_2", "")
ADMIN_ID = int(os.environ["ADMIN_ID"])
NOTIFY_USER = os.environ.get("NOTIFY_USER", "me")
VPS_CHANNEL_ID = int(os.environ.get("VPS_CHANNEL_ID", 0))

HUNT_BUTTONS = ["مشاركة", "انضمام", "سحب", "تدوير", "دخول", "تأكيد", "اضغط هنا"]
DANGER_WORDS = ["أكثر نجوم", "من يضع", "تصويت بنجوم", "اكثر شخص يحط", "يحط يربح", "مزاد نجوم"]
SAFE_CONTEST_REGEX = r'أول\s*(شخص|واحد|من)\s*(ي|يلي)?\s*(كتب|يكتب|قال|يقول|رد|يرد|علق|يعلق)\s*[({\[].*?[)}\]]'

SPEED_FILE = "flawless_speed.json"
STATS_MSG_ID = None

class OmegaFlawlessV2:
    def __init__(self):
        self.c1 = TelegramClient(StringSession(SESSION_1), API_ID_1, API_HASH_1)
        self.c2 = TelegramClient(StringSession(SESSION_2), API_ID_2, API_HASH_2) if SESSION_2 else None
        self.running = True
        self.stats = {"vps":0, "wins":0, "left":0, "start":time.time()}
        self.cache = set()
        self.speed = self.load_speed()
        self.join_queue = asyncio.Queue()
        self.main_client = None

    def load_speed(self):
        try: return json.load(open(SPEED_FILE, 'r'))
        except: return {"delay": 60, "fails": 0}
    def save_speed(self):
        json.dump(self.speed, open(SPEED_FILE,'w'), indent=2)

    async def dynamic_delay(self):
        base = self.speed["delay"] * (1 + 0.2 * self.speed["fails"])
        await asyncio.sleep(random.uniform(base * 0.8, base * 1.2))

    async def handle_flood(self, e):
        if isinstance(e, FloodWaitError):
            logger.warning(f"⏳ FloodWait {e.seconds}s")
            self.speed["delay"] = min(600, self.speed["delay"] * 2)
            self.speed["fails"] += 1
            self.save_speed()
            await asyncio.sleep(e.seconds)
            return True
        return False

    async def success_action(self):
        self.speed["fails"] = max(0, self.speed["fails"] - 1)
        if self.speed["delay"] > 60:
            self.speed["delay"] = max(60, self.speed["delay"] * 0.9)
        self.save_speed()

    async def connect(self, client, name):
        for _ in range(3):
            try:
                await client.connect()
                if await client.is_user_authorized():
                    logger.info(f"✅ {name}")
                    return True
            except AuthKeyDuplicatedError:
                logger.critical(f"🔑 {name} جلسة مكررة!"); break
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

    async def live_stats(self):
        global STATS_MSG_ID
        while self.running:
            if self.main_client:
                uptime = str(timedelta(seconds=int(time.time()-self.stats['start'])))
                msg = (f"📊 **Flawless V2**\n🕒 {datetime.now():%H:%M:%S}\n⏱️ {uptime}\n"
                       f"🌐 VPS:{self.stats['vps']}\n🏆 روليت:{self.stats['wins']}\n"
                       f"🚪 مغادرة:{self.stats['left']}\n🐌 تأخير:{self.speed['delay']}s")
                try:
                    if STATS_MSG_ID: await self.main_client.edit_message('me', STATS_MSG_ID, msg)
                    else: sent = await self.main_client.send_message('me', msg); STATS_MSG_ID = sent.id
                except: pass
            await asyncio.sleep(5)

    # ---------- استخراج VPS من تنسيقات متعددة ----------
    def extract_vps(self, text):
        """محاولة استخراج IP, User, Password من النص بمختلف التنسيقات"""
        ip = user = pwd = None

        # تنسيق 1: "🌐 IP: 94.72.120.108" مع "👤 User: r00t" و "🔐 New password: sinko@"
        ip1 = re.search(r'(?:IP[:\s]*|🌐\s*IP[:\s]*)(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', text)
        if ip1:
            ip = ip1.group(1)
            user1 = re.search(r'(?:User[:\s]*|👤\s*User[:\s]*)(\S+)', text)
            if user1: user = user1.group(1)
            pwd1 = re.search(r'(?:New password[:\s]*|🔐\s*New password[:\s]*|password[:\s]*)(\S+)', text)
            if pwd1: pwd = pwd1.group(1)

        # تنسيق 2: "VPS 🇫🇷" ثم "37.60.235.208" في سطر جديد
        if not ip:
            ip2 = re.search(r'(?:^|\n)\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*(?:\n|$)', text, re.MULTILINE)
            if ip2:
                ip = ip2.group(1).strip()
                # غالباً user هو "root"
                user = "root"
                # كلمة المرور قد تكون في سطر يحتوي على "@" مثل "ACON@VPS"
                pwd2 = re.search(r'(?:^|\n)\s*([^\s]+@[^\s]+)\s*(?:\n|$)', text, re.MULTILINE)
                if pwd2: pwd = pwd2.group(1).strip()
                else:
                    # قد تكون كلمة مرور بدون @: "ACON@VPS" (احتوى @) أو كلمة عادية مثل "sinko@"
                    pwd3 = re.search(r'(?:^|\n)\s*([A-Za-z0-9@]+)\s*(?:\n|$)', text, re.MULTILINE)
                    if pwd3: pwd = pwd3.group(1).strip()

        if ip and pwd:
            if not user: user = "root"
            return ip, user, pwd
        return None, None, None

    async def vps_watcher(self, event):
        text = event.raw_text or ""
        ip, user, pwd = self.extract_vps(text)
        if ip and pwd:
            self.stats['vps'] += 1
            msg = (f"🔥 **VPS جديد**\n▪️ IP: `{ip}`\n▪️ User: `{user}`\n▪️ Pass: `{pwd}`")
            try: await self.main_client.send_message(NOTIFY_USER, msg)
            except: pass
            logger.info(f"✅ VPS مُرسَل: {ip}")

    # ---------- طابور الانضمام ----------
    async def join_worker(self):
        while self.running:
            channel_id = await self.join_queue.get()
            try:
                await self.dynamic_delay()
                await self.c1(JoinChannelRequest(channel_id))
                await self.success_action()
                logger.info(f"✅ انضم للقناة {channel_id}")
            except (UserChannelsTooMuchError, ChannelsTooMuchError):
                logger.warning("⚠️ الحساب ممتلئ، مغادرة أقدم 3 قنوات")
                await self.leave_oldest(3)
                await asyncio.sleep(10)
                try: await self.c1(JoinChannelRequest(channel_id))
                except: pass
            except FloodWaitError as e:
                await self.handle_flood(e)
            except: pass
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

    # ---------- روليت (بدون تغيير عن السابق) ----------
    async def process_roulette(self, event, client):
        if event.id in self.cache: return
        text = event.raw_text or ""
        if any(w in text for w in DANGER_WORDS): return

        safe = re.search(SAFE_CONTEST_REGEX, text, re.I)
        if safe:
            reply = re.search(r'[({\[].*?[)}\]]', text)
            reply_text = reply.group(0).strip('(){}[]') if reply else "تم"
            try: await event.reply(reply_text)
            except: pass
            if event.reply_markup: await self.click_hunt(event, client)
            return

        if not event.reply_markup: return

        # استخراج أسماء القنوات وإضافتها للطابور
        links = set(re.findall(r'(?:t\.me/|@)([\w_]+)', text))
        for username in links:
            if username.lower() in ['bot', 'c', 'me']: continue
            try:
                entity = await client.get_entity(username)
                await self.join_queue.put(entity.id)
            except FloodWaitError as e: await self.handle_flood(e)
            except: pass

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
            await event.respond("🔥 **Flawless V2**", buttons=[[Button.inline(".stats",b"copy_stats")]])

    # ---------- تشغيل ----------
    async def main(self):
        if not await self.connect(self.c1, "ح1"): return
        self.main_client = self.c1
        if self.c2 and not await self.connect(self.c2, "ح2"): self.c2 = None

        if VPS_CHANNEL_ID:
            @self.c1.on(events.NewMessage(chats=VPS_CHANNEL_ID))
            async def vps_handler(event): await self.vps_watcher(event)
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

        @self.c1.on(events.CallbackQuery)
        async def cb(event):
            if event.data.decode().startswith("copy_"): await event.answer("✅")

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
        logger.info("🚀 Flawless V2 يعمل بدون أخطاء")
        await self.c1.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(OmegaFlawlessV2().main())
