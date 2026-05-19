#!/usr/bin/env python3
"""
■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
Omega Roulette Hunter – صائد الروليت الصامت
بدون ذكاء اصطناعي | يتعلم من الأخطاء | أوامر .stop / .start
■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
"""
import os, asyncio, random, re, time, logging, json
from datetime import datetime, timedelta
from telethon import TelegramClient, events, functions, types
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.errors import (
    FloodWaitError, UserBannedInChannelError, PeerFloodError,
    AuthKeyDuplicatedError
)

# ---------- تسجيل ----------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('roulette_hunter.log'), logging.StreamHandler()]
)
logger = logging.getLogger("RouletteHunter")

# ---------- الإعدادات ----------
API_ID_1 = int(os.environ["API_ID_1"]); API_HASH_1 = os.environ["API_HASH_1"]; SESSION_1 = os.environ["SESSION_1"]
API_ID_2 = int(os.environ.get("API_ID_2", 0)); API_HASH_2 = os.environ.get("API_HASH_2", ""); SESSION_2 = os.environ.get("SESSION_2", "")
ADMIN_ID = int(os.environ["ADMIN_ID"])

# كلمات الصيد
HUNT_KEYWORDS = [
    "مشاركة", "انضمام", "سحب", "دخول", "روليت", "هدية", "نجوم",
    "يلا", "سجل", "اضغط", "بسرعة", "التحق", "تأكيد", "شارك", "انقر"
]
# مسابقات خطيرة (لا نشارك فيها)
DANGER_WORDS = ["أكثر نجوم", "من يضع", "تصويت بنجوم", "اكثر شخص يحط", "يحط يربح", "مزاد نجوم"]
# مسابقة "أول شخص يكتب" (آمنة)
SAFE_CONTEST_REGEX = r'أول\s*(شخص|واحد|من)\s*(ي|يلي)?\s*(كتب|يكتب|قال|يقول|رد|يرد|علق|يعلق)\s*[({\[].*?[)}\]]'

# ملف التعلم
LEARNING_FILE = "hunter_memory.json"

class RouletteHunter:
    def __init__(self):
        self.c1 = TelegramClient(StringSession(SESSION_1), API_ID_1, API_HASH_1)
        self.c2 = TelegramClient(StringSession(SESSION_2), API_ID_2, API_HASH_2) if SESSION_2 else None
        self.running = True
        self.stats = {"wins": 0, "channels_left": 0, "start": time.time()}
        self.cache = set()
        self.memory = self.load_memory()

    # ========== ذاكرة التعلم ==========
    def load_memory(self):
        try:
            with open(LEARNING_FILE, 'r') as f:
                return json.load(f)
        except:
            return {
                "slow_mode_channels": {},
                "bad_channels": [],
                "delay_multiplier": 1.0
            }

    def save_memory(self):
        with open(LEARNING_FILE, 'w') as f:
            json.dump(self.memory, f, indent=2)

    async def learn_from_error(self, error, channel_id=None):
        if isinstance(error, FloodWaitError):
            self.memory['delay_multiplier'] = min(3.0, self.memory['delay_multiplier'] + 0.1)
            self.save_memory()
        elif isinstance(error, (UserBannedInChannelError, PeerFloodError)):
            if channel_id:
                self.memory['bad_channels'].append(channel_id)
                self.save_memory()

    def get_delay(self):
        mult = self.memory['delay_multiplier']
        return random.uniform(1.5 * mult, 4.0 * mult)

    def is_bad_channel(self, channel_id):
        return channel_id in self.memory['bad_channels']

    # ========== اتصال ==========
    async def connect(self, client, name):
        try:
            await client.connect()
            if await client.is_user_authorized():
                logger.info(f"✅ {name}")
                return True
        except AuthKeyDuplicatedError:
            logger.critical(f"🔑 {name} الجلسة مكررة!")
        except Exception as e:
            logger.error(f"❌ {name}: {e}")
        return False

    async def keep_alive(self, client, name):
        while self.running:
            try:
                if not client.is_connected():
                    await client.connect()
                await client(functions.PingRequest(ping_id=random.randint(0, 2**31)))
            except:
                pass
            await asyncio.sleep(120)

    # ========== معالج القنوات ==========
    async def handle_message(self, event, client):
        if not self.running:
            return
        chat = await event.get_chat()
        chat_id = chat.id

        if self.is_bad_channel(chat_id):
            return

        text = event.raw_text or ""

        if any(w in text for w in DANGER_WORDS):
            return

        safe = re.search(SAFE_CONTEST_REGEX, text, re.I)
        if safe:
            match = re.search(r'[({\[].*?[)}\]]', text)
            reply_text = match.group(0).strip('(){}[]') if match else "تم"
            try:
                await event.reply(reply_text)
            except:
                pass
            if event.reply_markup:
                await self.click_buttons(event, client, chat_id)
            return

        if event.reply_markup and event.id not in self.cache:
            btn_text = " ".join(b.text for row in event.reply_markup.rows for b in row.buttons)
            if any(k in (text + " " + btn_text).lower() for k in HUNT_KEYWORDS):
                self.cache.add(event.id)
                await self.join_required(event, client)
                delay = self.get_delay()
                await asyncio.sleep(delay)
                await self.click_buttons(event, client, chat_id)

    async def click_buttons(self, event, client, chat_id):
        if not event.reply_markup:
            return
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
                        try:
                            await client(LeaveChannelRequest(chat_id))
                        except:
                            pass
                        self.stats['channels_left'] += 1
                    except:
                        pass

    async def join_required(self, event, client):
        links = set()
        if event.entities:
            for e in event.entities:
                if hasattr(e, 'url') and 't.me' in (e.url or ''):
                    links.add(e.url)
        links.update(re.findall(r'(?:t\.me/[\w\d_]+|@[\w\d_]+)', event.raw_text))
        for link in links:
            name = link.split('/')[-1].replace('@', '')
            try:
                await client(JoinChannelRequest(name))
            except:
                pass

    async def leave_dead_channels(self):
        count = 0
        for client in [self.c1, self.c2] if self.c2 else [self.c1]:
            async for dialog in client.iter_dialogs():
                if not dialog.is_channel:
                    continue
                try:
                    msgs = await client.get_messages(dialog.entity, limit=1)
                    if not msgs or not msgs[0].date:
                        await client(LeaveChannelRequest(dialog.entity))
                        count += 1
                except:
                    pass
        self.stats['channels_left'] += count
        if count:
            logger.info(f"🧹 غادرت {count} قناة ميتة")

    # ========== أوامر ==========
    async def handle_command(self, event):
        cmd = event.raw_text[1:].lower()
        if cmd == "stop":
            self.running = False
            await event.reply("🛑 تم إيقاف المحرك")
        elif cmd == "start":
            self.running = True
            await event.reply("✅ تم تشغيل المحرك")
        elif cmd == "stats":
            uptime = str(timedelta(seconds=int(time.time() - self.stats['start'])))
            await event.reply(
                f"📊 **صائد الروليت**\n"
                f"🏆 صيد: {self.stats['wins']}\n"
                f"⏱️ مدة: {uptime}\n"
                f"🚪 قنوات مغادرة: {self.stats['channels_left']}\n"
                f"🐌 مضاعف التأخير: {self.memory['delay_multiplier']:.2f}"
            )

    # ========== تشغيل ==========
    async def main(self):
        if not await self.connect(self.c1, "حساب 1"):
            return
        if self.c2 and not await self.connect(self.c2, "حساب 2"):
            self.c2 = None

        @self.c1.on(events.NewMessage)
        async def handler1(e):
            if e.sender_id == ADMIN_ID and e.raw_text.startswith("."):
                await self.handle_command(e)
            elif e.is_channel or e.is_group:
                await self.handle_message(e, self.c1)

        if self.c2:
            @self.c2.on(events.NewMessage)
            async def handler2(e):
                if e.is_channel or e.is_group:
                    await self.handle_message(e, self.c2)

        asyncio.create_task(self.keep_alive(self.c1, "ح1"))
        if self.c2:
            asyncio.create_task(self.keep_alive(self.c2, "ح2"))

        async def periodic():
            while self.running:
                await asyncio.sleep(21600)
                await self.leave_dead_channels()
        asyncio.create_task(periodic())

        logger.info("🚀 صائد الروليت انطلق")
        await self.c1.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(RouletteHunter().main())
