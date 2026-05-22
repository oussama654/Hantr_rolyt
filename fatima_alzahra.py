#!/usr/bin/env python3
"""
■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
Omega Ultimate X – VPS Hunter + روليت متكامل (مُحسَّن)
يعالج FloodWait الذكي | يقلل طلبات ResolveUsername | 24/7
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
    handlers=[logging.FileHandler('omega_ultimate_x.log'), logging.StreamHandler()]
)
logger = logging.getLogger("OmegaUX")

# ---------- الإعدادات ----------
API_ID_1 = int(os.environ["API_ID_1"]); API_HASH_1 = os.environ["API_HASH_1"]; SESSION_1 = os.environ["SESSION_1"]
API_ID_2 = int(os.environ.get("API_ID_2", 0)); API_HASH_2 = os.environ.get("API_HASH_2", ""); SESSION_2 = os.environ.get("SESSION_2", "")
ADMIN_ID = int(os.environ["ADMIN_ID"])
TARGET_VPS_CHANNEL = "FreeinternetTM"
NOTIFY_USER = "KOA_7"
HUNT_BUTTONS = ["مشاركة", "انضمام", "سحب", "تدوير", "دخول", "تأكيد", "اضغط هنا", "سجل"]
VOTE_BUTTONS = ["❤️", "👍", "تصويت", "يستحق", "صوت"]
DANGER_WORDS = ["أكثر نجوم", "من يضع", "تصويت بنجوم", "اكثر شخص يحط", "يحط يربح", "مزاد نجوم"]
SAFE_CONTEST_REGEX = r'أول\s*(شخص|واحد|من)\s*(ي|يلي)?\s*(كتب|يكتب|قال|يقول|رد|يرد|علق|يعلق)\s*[({\[].*?[)}\]]'

LEARNING_FILE = "omega_memory.json"
STATS_MSG_ID = None

class OmegaUltimateX:
    def __init__(self):
        self.c1 = TelegramClient(StringSession(SESSION_1), API_ID_1, API_HASH_1)
        self.c2 = TelegramClient(StringSession(SESSION_2), API_ID_2, API_HASH_2) if SESSION_2 else None
        self.running = True
        self.stats = {"vps":0, "pwds":0, "wins":0, "left":0, "start":time.time()}
        self.cache = set()
        self.active = set()
        self.memory = self.load_mem()
        self.main_client = None
        self.vps_entity = None  # سنخزن معرف القناة بعد تحويله مرة واحدة

    def load_mem(self):
        try: return json.load(open(LEARNING_FILE, 'r'))
        except: return {"delay":1.0, "bad":[]}
    def save_mem(self): json.dump(self.memory, open(LEARNING_FILE,'w'), indent=2)

    async def safe_resolve(self, username):
        """يحاول جلب الكيان مع التعامل مع FloodWait"""
        try:
            return await self.c1.get_entity(username)
        except FloodWaitError as e:
            logger.warning(f"⏳ FloodWait أثناء جلب {username}: {e.seconds} ثانية")
            await asyncio.sleep(e.seconds + 1)
            return await self.c1.get_entity(username)
        except: return None

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
                msg = (f"📊 **OmegaUX**\n🕒 {datetime.now():%H:%M:%S}\n⏱️ {uptime}\n"
                       f"🌐 VPS:{self.stats['vps']} 🔑 مغير:{self.stats['pwds']}\n"
                       f"🏆 روليت:{self.stats['wins']} 🚪 مغادرة:{self.stats['left']}\n"
                       f"🟢 {'يعمل' if self.running else 'متوقف'}")
                try:
                    if STATS_MSG_ID: await self.main_client.edit_message('me', STATS_MSG_ID, msg)
                    else: sent = await self.main_client.send_message('me', msg); STATS_MSG_ID = sent.id
                except: pass
            await asyncio.sleep(5)

    # ---------- VPS ----------
    async def vps_watcher(self, event):
        text = event.raw_text or ""
        ip = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', text)
        user = re.search(r'(?:User[:\s]*|👤\s*User[:\s]*)(\S+)', text, re.I)
        pwd = re.search(r'(?:password[:\s]*|🔐\s*New password[:\s]*)(\S+)', text, re.I)
        if ip and pwd:
            ip_val, user_val, pwd_val = ip.group(1), (user.group(1) if user else "root"), pwd.group(1)
            self.stats['vps'] += 1
            msg = (f"🔥 **VPS جديد!**\n▪️ IP: `{ip_val}`\n▪️ User: `{user_val}`\n▪️ Pass: `{pwd_val}`")
            try: await self.main_client.send_message(NOTIFY_USER, msg)
            except: pass

    # ---------- روليت ----------
    async def process_roulette(self, event, client):
        if event.id in self.active: return
        self.active.add(event.id)
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

        # روابط توجيه
        redirect = []
        for r,row in enumerate(event.reply_markup.rows):
            for b,btn in enumerate(row.buttons):
                if btn.url and 't.me' in btn.url:
                    redirect.append((btn, r, b))

        for btn, r_idx, b_idx in redirect:
            if any(k in btn.text for k in HUNT_BUTTONS) or 'هنا' in btn.text:
                match = re.search(r't\.me/([\w_]+)/(\d+)', btn.url)
                if match:
                    ch, msg_id = match.group(1), int(match.group(2))
                    try:
                        entity = await self.safe_resolve(ch)
                        if entity:
                            await client(JoinChannelRequest(entity))
                            await asyncio.sleep(random.uniform(3,5))
                            vote_msg = await client.get_messages(entity, ids=msg_id)
                            if vote_msg and vote_msg.reply_markup:
                                for vr,vrow in enumerate(vote_msg.reply_markup.rows):
                                    for vb,vbtn in enumerate(vrow.buttons):
                                        if any(vk in vbtn.text for vk in VOTE_BUTTONS):
                                            await vote_msg.click(vr,vb)
                                            await asyncio.sleep(2)
                    except FloodWaitError as e:
                        logger.warning(f"FloodWait {e.seconds}s"); await asyncio.sleep(e.seconds)
                    except: pass
                    # العودة للروليت
                    try:
                        orig = await client.get_messages(event.chat_id, ids=event.id)
                        await orig.click(r_idx, b_idx)
                        self.stats['wins'] += 1
                    except: pass
                    return

        # روليت عادي
        if event.id in self.cache: return
        if any(k in (text + " ".join([b.text for r in event.reply_markup.rows for b in r.buttons])).lower() for k in HUNT_BUTTONS):
            self.cache.add(event.id)
            links = set(re.findall(r't\.me/[\w\d_]+|@[\w\d_]+', text))
            for l in links:
                name = l.split('/')[-1].replace('@','')
                try:
                    entity = await self.safe_resolve(name)
                    if entity:
                        await client(JoinChannelRequest(entity))
                        await asyncio.sleep(random.uniform(5,10))
                except: pass
            await asyncio.sleep(self.memory.get('delay',1.0))
            await self.click_hunt(event, client)

    async def click_hunt(self, event, client):
        if not event.reply_markup: return
        for r,row in enumerate(event.reply_markup.rows):
            for b,btn in enumerate(row.buttons):
                if any(k in btn.text for k in HUNT_BUTTONS) or "مشاركة" in btn.text:
                    try:
                        await event.click(r,b)
                        self.stats['wins'] += 1
                        return
                    except FloodWaitError as e: await asyncio.sleep(e.seconds)
                    except: pass
        try: await event.click(0,0); self.stats['wins']+=1
        except: pass

    # ---------- أوامر ----------
    async def handle_command(self, event, parts):
        cmd = parts[0][1:].lower()
        if cmd=="stop": self.running=False; await event.reply("🛑")
        elif cmd=="start": self.running=True; await event.reply("✅")
        elif cmd=="stats": await event.reply("📊 اللوحة تُحدث نفسها تلقائياً")
        elif cmd=="leavedead":
            c=0
            async for d in self.c1.iter_dialogs():
                if d.is_channel:
                    try:
                        m = await self.c1.get_messages(d.entity, limit=1)
                        if not m or not m[0].date: await self.c1(LeaveChannelRequest(d.entity)); c+=1
                    except: pass
            self.stats['left']+=c; await event.reply(f"🧹 غادرت {c}")
        elif cmd=="panel":
            await event.respond("🔥 **Omega UX**", buttons=[[Button.inline(".stats",b"copy_stats")]])

    # ---------- تشغيل ----------
    async def main(self):
        if not await self.connect(self.c1, "ح1"): return
        self.main_client = self.c1
        if self.c2 and not await self.connect(self.c2, "ح2"): self.c2 = None

        # جلب كيان قناة VPS مرة واحدة فقط
        self.vps_entity = await self.safe_resolve(TARGET_VPS_CHANNEL)
        if self.vps_entity:
            logger.info(f"🎯 تم جلب قناة VPS: {self.vps_entity.id}")
            @self.c1.on(events.NewMessage(chats=self.vps_entity))
            async def vps_handler(event): await self.vps_watcher(event)
        else:
            logger.warning("⚠️ تعذر جلب قناة VPS، سيتم تجاهل مراقبتها")

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

        asyncio.create_task(self.keep_alive(self.c1,"ح1"))
        if self.c2: asyncio.create_task(self.keep_alive(self.c2,"ح2"))
        asyncio.create_task(self.live_stats())

        # تنظيف القنوات الميتة كل 6 ساعات
        async def periodic():
            while self.running:
                await asyncio.sleep(21600)
                c=0
                async for d in self.c1.iter_dialogs():
                    if d.is_channel:
                        try:
                            m = await self.c1.get_messages(d.entity, limit=1)
                            if not m or not m[0].date: await self.c1(LeaveChannelRequest(d.entity)); c+=1
                        except: pass
                self.stats['left']+=c
        asyncio.create_task(periodic())

        await self.c1(UpdateStatusRequest(offline=False))
        logger.info("🚀 Omega UX يعمل")
        await self.c1.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(OmegaUltimateX().main())
