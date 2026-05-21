
#!/usr/bin/env python3
"""
■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
Omega Ultimate Hunter – صائد الروليت المتكامل
يتعامل مع الروليتات المتعددة الخطوات، الكابتشا، التوجيه، والأزرار الشفافة
■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
"""
import os, asyncio, random, re, time, logging, json
from datetime import datetime, timedelta
from telethon import TelegramClient, events, functions, types
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.messages import GetMessagesRequest
from telethon.errors import (
    FloodWaitError, UserBannedInChannelError, PeerFloodError,
    AuthKeyDuplicatedError, MessageDeleteForbiddenError
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('ultimate_hunter.log'), logging.StreamHandler()]
)
logger = logging.getLogger("UltimateHunter")

# ---------- متغيرات البيئة ----------
API_ID_1 = int(os.environ["API_ID_1"]); API_HASH_1 = os.environ["API_HASH_1"]; SESSION_1 = os.environ["SESSION_1"]
API_ID_2 = int(os.environ.get("API_ID_2", 0)); API_HASH_2 = os.environ.get("API_HASH_2", ""); SESSION_2 = os.environ.get("SESSION_2", "")
ADMIN_ID = int(os.environ["ADMIN_ID"])

HUNT_KEYWORDS = [
    "مشاركة", "انضمام", "سحب", "دخول", "روليت", "هدية", "نجوم",
    "يلا", "سجل", "اضغط", "بسرعة", "التحق", "تأكيد", "شارك", "انقر"
]
DANGER_WORDS = ["أكثر نجوم", "من يضع", "تصويت بنجوم", "اكثر شخص يحط", "يحط يربح", "مزاد نجوم"]
SAFE_CONTEST_REGEX = r'أول\s*(شخص|واحد|من)\s*(ي|يلي)?\s*(كتب|يكتب|قال|يقول|رد|يرد|علق|يعلق)\s*[({\[].*?[)}\]]'

LEARNING_FILE = "ultimate_memory.json"

class UltimateHunter:
    def __init__(self):
        self.c1 = TelegramClient(StringSession(SESSION_1), API_ID_1, API_HASH_1)
        self.c2 = TelegramClient(StringSession(SESSION_2), API_ID_2, API_HASH_2) if SESSION_2 else None
        self.running = True
        self.stats = {"wins": 0, "tasks_done": 0, "channels_left": 0, "start": time.time()}
        self.cache = set()
        self.memory = self.load_memory()
        self.pending_tasks = {}  # {original_msg_id: asyncio.Task}

    def load_memory(self):
        try:
            with open(LEARNING_FILE, 'r') as f:
                return json.load(f)
        except:
            return {"delay_multiplier": 1.0, "bad_channels": []}

    def save_memory(self):
        with open(LEARNING_FILE, 'w') as f:
            json.dump(self.memory, f, indent=2)

    async def learn(self, error, channel_id=None):
        if isinstance(error, FloodWaitError):
            self.memory['delay_multiplier'] = min(3.0, self.memory['delay_multiplier'] + 0.1)
            self.save_memory()
        elif isinstance(error, (UserBannedInChannelError, PeerFloodError)) and channel_id:
            self.memory['bad_channels'].append(channel_id)
            self.save_memory()

    def is_bad(self, cid): return cid in self.memory['bad_channels']

    def get_delay(self): return random.uniform(1.5 * self.memory['delay_multiplier'], 4.0 * self.memory['delay_multiplier'])

    async def connect(self, client, name):
        try:
            await client.connect()
            if await client.is_user_authorized():
                logger.info(f"✅ {name}")
                return True
        except AuthKeyDuplicatedError:
            logger.critical(f"🔑 {name} جلسة مكررة")
        except Exception as e:
            logger.error(f"❌ {name}: {e}")
        return False

    async def keep_alive(self, client, name):
        while self.running:
            try:
                if not client.is_connected(): await client.connect()
                await client(functions.PingRequest(ping_id=random.randint(0, 2**31)))
            except: pass
            await asyncio.sleep(120)

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

    # ========== إجراءات التوجيه ==========
    async def follow_link(self, link, event, client):
        """ينضم للقناة/المجموعة وينفذ المهمة المطلوبة"""
        match = re.match(r'(?:https?://)?t\.me/([\w\d_]+)/?(\d+)?', link)
        if not match: return
        username, msg_id = match.group(1), match.group(2)
        try:
            entity = await client.get_entity(username)
            await client(JoinChannelRequest(entity))
        except: pass

        if msg_id:
            try:
                target_msg = await client.get_messages(entity, ids=int(msg_id))
                if target_msg and target_msg.reply_markup:
                    # ابحث عن زر تصويت أو قلب أو كتابة
                    for row in target_msg.reply_markup.rows:
                        for btn in row.buttons:
                            if any(k in btn.text for k in ['❤️','👍','👎','تصويت','قلب','vote']):
                                await target_msg.click(row.row_index, btn.column_index)
                                return
                    # إذا لم نجد زر، جرب النقر على أول زر
                    await target_msg.click(0, 0)
                elif target_msg and target_msg.is_reply:
                    # ربما نحتاج كتابة "يستحق"
                    try:
                        await target_msg.reply("يستحق")
                    except: pass
            except Exception as e:
                logger.warning(f"فشل تنفيذ مهمة في {username}: {e}")

    # ========== المعالج الرئيسي ==========
    async def handle_message(self, event, client):
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
            if event.reply_markup: await self.process_buttons(event, client, chat_id)
            return

        if event.id in self.cache: return

        # فحص الأزرار
        if event.reply_markup:
            # أولاً حل كابتشا إن وجد
            if await self.solve_captcha(event):
                self.cache.add(event.id)
                return

            # استخراج روابط التوجيه
            redirect_links = []
            for row in event.reply_markup.rows:
                for btn in row.buttons:
                    if btn.url and 't.me' in btn.url:
                        redirect_links.append(btn.url)
                    elif 'هنا' in btn.text or 'قناة' in btn.text or 'اذهب' in btn.text:
                        # زر توجيه بدون رابط واضح، قد يكون callback يفتح شيء
                        # نضغطه ونراقب النتيجة
                        try:
                            await event.click(row.row_index, btn.column_index)
                            await asyncio.sleep(2)
                            # بعد النقر قد تظهر رسالة جديدة أو ننتقل
                            # نعود للرسالة الأصلية بعد قليل
                        except: pass
                        return

            # إذا وجدنا روابط توجيه
            for link in redirect_links:
                await self.follow_link(link, event, client)
                await asyncio.sleep(2)
                # بعد تنفيذ المهمة، نعود للرسالة الأصلية ونضغط أزرارها
                try:
                    original = await client.get_messages(chat_id, ids=event.id)
                    if original and original.reply_markup:
                        await self.click_hunt_buttons(original, client, chat_id)
                except: pass
                return

            # روليت عادي
            if any(k in (text + " ".join(b.text for r in event.reply_markup.rows for b in r.buttons)).lower() for k in HUNT_KEYWORDS):
                self.cache.add(event.id)
                await self.join_channels(event, client)
                delay = self.get_delay()
                await asyncio.sleep(delay)
                await self.click_hunt_buttons(event, client, chat_id)

    async def click_hunt_buttons(self, event, client, chat_id):
        if not event.reply_markup: return
        for row in event.reply_markup.rows:
            for btn in row.buttons:
                if any(k in btn.text for k in HUNT_KEYWORDS) or "مشاركة" in btn.text or "انضم" in btn.text:
                    try:
                        await event.click(row.row_index, btn.column_index)
                        self.stats['wins'] += 1
                        return
                    except FloodWaitError as e:
                        await self.learn(e)
                        await asyncio.sleep(e.seconds + 1)
                    except (UserBannedInChannelError, PeerFloodError) as e:
                        await self.learn(e, chat_id)
                        try: await client(LeaveChannelRequest(chat_id))
                        except: pass
                        self.stats['channels_left'] += 1
                    except: pass
        # لو مافيش زر مناسب، نضغط أول زر (شفاف)
        try:
            await event.click(0, 0)
            self.stats['wins'] += 1
        except: pass

    async def join_channels(self, event, client):
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

    # ========== أوامر ==========
    async def handle_command(self, event):
        cmd = event.raw_text[1:].lower()
        if cmd == "stop": self.running = False; await event.reply("🛑 توقف")
        elif cmd == "start": self.running = True; await event.reply("✅ تشغيل")
        elif cmd == "stats":
            up = str(timedelta(seconds=int(time.time()-self.stats['start'])))
            await event.reply(f"📊 صيد: {self.stats['wins']}\n⏱️ {up}\n🐌 تأخير: {self.memory['delay_multiplier']:.2f}")

    # ========== تشغيل ==========
    async def main(self):
        if not await self.connect(self.c1, "ح1"): return
        if self.c2 and not await self.connect(self.c2, "ح2"): self.c2 = None

        @self.c1.on(events.NewMessage)
        async def h1(e):
            if e.sender_id == ADMIN_ID and e.raw_text.startswith("."):
                await self.handle_command(e)
            elif e.is_channel or e.is_group:
                await self.handle_message(e, self.c1)

        if self.c2:
            @self.c2.on(events.NewMessage)
            async def h2(e):
                if e.is_channel or e.is_group:
                    await self.handle_message(e, self.c2)

        asyncio.create_task(self.keep_alive(self.c1, "ح1"))
        if self.c2: asyncio.create_task(self.keep_alive(self.c2, "ح2"))

        logger.info("🚀 Ultimate Hunter انطلق")
        await self.c1.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(UltimateHunter().main())
