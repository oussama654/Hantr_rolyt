#!/usr/bin/env python3
"""
■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
Omega Gift Sniper – صائد الهدايا المطورة + الروليت
السعر المستهدف: 126 – 149 نجمة | Telethon | GitHub Actions
■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
"""
import os, asyncio, random, re, json, logging, time
from datetime import datetime, timedelta
from telethon import TelegramClient, events, functions, types, Button
from telethon.sessions import StringSession
from telethon.tl.functions.account import UpdateStatusRequest, UpdateProfileRequest
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.messages import ReadHistoryRequest, DeleteHistoryRequest
from telethon.errors import (
    AuthKeyDuplicatedError, FloodWaitError, UserBannedInChannelError,
    PeerFloodError
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('omega_gift_sniper.log'), logging.StreamHandler()]
)
logger = logging.getLogger("OmegaGiftSniper")

# ---------- إعدادات البيئة ----------
API_ID_1 = int(os.environ["API_ID_1"]); API_HASH_1 = os.environ["API_HASH_1"]; SESSION_1 = os.environ["SESSION_1"]
API_ID_2 = int(os.environ.get("API_ID_2", 0)); API_HASH_2 = os.environ.get("API_HASH_2", ""); SESSION_2 = os.environ.get("SESSION_2", "")
ADMIN_ID = int(os.environ["ADMIN_ID"])

# ---------- نطاق السعر المستهدف ----------
GIFT_PRICE_MIN = 126
GIFT_PRICE_MAX = 149

# بوتات وأسواق الهدايا (سنراقبها)
GIFT_MARKETS = [
    "tonnel_network_bot",   # Tonnel Marketplace
    "AutoGiftsBot",         # بوت الشراء التلقائي
    "GiftHub_bot",          # سوق الهدايا
    "CollectibleBot",       # قد يكون موجوداً
]

# كلمات الصيد (للروليتات)
HUNT_KEYWORDS = [
    "مشاركة", "انضمام", "سحب", "دخول", "روليت", "دب", "هدية", "نجوم",
    "تعزيز", "يلا", "سجل", "اضغط", "بسرعة", "التحق", "تأكيد", "شارك", "انقر"
]
DANGER_WORDS = ["أكثر نجوم", "من يضع", "تصويت بنجوم", "اكثر شخص يحط", "يحط يربح", "مزاد نجوم"]
SAFE_REGEX = r'أول\s*(شخص|واحد|من)\s*(ي|يلي)?\s*(كتب|يكتب|قال|يقول|رد|يرد|علق|يعلق)\s*[({\[].*?[)}\]]'

# شخصية (للحساب الثاني)
PERSONA_NAMES = ["فاطمة الزهراء", "لارا", "ملاك", "ليل", "سما", "روح", "فراشة", "نور"]
PERSONA_BIOS = ["مغربية 🇲🇦 | 18 سنة | لاعبة كرة ⚽", "بنت بسيطة من المغرب", "مزاجي كرة وسهر 🌙"]

STATS_MSG_ID = None


class OmegaGiftSniper:
    def __init__(self):
        self.c1 = TelegramClient(StringSession(SESSION_1), API_ID_1, API_HASH_1)
        self.c2 = TelegramClient(StringSession(SESSION_2), API_ID_2, API_HASH_2) if SESSION_2 else None
        self.running = True
        self.stars = 0
        self.sniper_enabled = True  # القناص مفعل دائماً
        self.last_persona_change = datetime.min
        self.cache = set()
        self.gift_log = []  # سجل الهدايا المشتراة
        self.stats = {
            "wins": 0, "stars_earned": 0, "gifts_bought": 0,
            "gifts_converted": 0, "channels_left": 0,
            "msgs_processed": 0, "start": time.time()
        }
        self.main_client = None
        self.is_resting = False

    # ========== اتصال ==========
    async def connect(self, client, name):
        try:
            await client.connect()
            if await client.is_user_authorized():
                logger.info(f"✅ {name} متصل")
                return True
        except AuthKeyDuplicatedError:
            logger.critical(f"🔑 {name} الجلسة مكررة!")
        except Exception as e:
            logger.error(f"❌ {name}: {e}")
        return False

    async def keep_alive(self, client, name):
        while self.running:
            if not self.is_resting:
                try:
                    if not client.is_connected():
                        await client.connect()
                    await client(UpdateStatusRequest(offline=False))
                except:
                    pass
            else:
                try:
                    await client(UpdateStatusRequest(offline=True))
                except:
                    pass
            await asyncio.sleep(120)

    async def rest_schedule(self):
        """راحة 20 دقيقة كل 4 ساعات لتجنب الحظر"""
        while self.running:
            await asyncio.sleep(4 * 3600)
            self.is_resting = True
            logger.info("😴 راحة 20 دقيقة...")
            await asyncio.sleep(20 * 60)
            self.is_resting = False
            logger.info("☀️ رجعت للعمل")

    # ========== إحصائيات حية ==========
    async def update_stats_msg(self):
        global STATS_MSG_ID
        if not self.main_client:
            return
        uptime = str(timedelta(seconds=int(time.time() - self.stats['start'])))
        status = "😴 راحة" if self.is_resting else "🟢 نشط"
        msg = (
            f"📊 **Omega Gift Sniper** ({status})\n"
            f"🕒 {datetime.now().strftime('%H:%M:%S')}\n"
            f"⏱️ مدة: {uptime}\n"
            f"🏆 روليت: {self.stats['wins']}\n"
            f"⭐ رصيد: ~{self.stars}\n"
            f"💎 هدايا مشتراة: {self.stats['gifts_bought']}\n"
            f"🎁 محولة: {self.stats['gifts_converted']}\n"
            f"🚪 قنوات غادرت: {self.stats['channels_left']}\n"
            f"📨 رسائل: {self.stats['msgs_processed']}\n"
            f"🎯 القناص: {'🟢' if self.sniper_enabled else '🔴'}"
        )
        try:
            if STATS_MSG_ID:
                await self.main_client.edit_message('me', STATS_MSG_ID, msg)
            else:
                sent = await self.main_client.send_message('me', msg)
                STATS_MSG_ID = sent.id
        except:
            pass

    # ========== معالج القنوات ==========
    async def handle_message(self, event, client):
        if not self.running or self.is_resting:
            return
        self.stats['msgs_processed'] += 1
        text = event.raw_text or ""
        chat = await event.get_chat()
        chat_name = chat.username or str(chat.id)

        # 1. تحويل الهدايا الواردة
        if event.reply_markup and any(w in text for w in ['هدية من', 'أضاف', 'الهدية']):
            for row in event.reply_markup.rows:
                for btn in row.buttons:
                    if any(k in btn.text for k in ['تحويل', 'نجمة', 'convert', 'stars']):
                        await event.click(row.row_index, btn.column_index)
                        self.stats['gifts_converted'] += 1
                        self.stars += random.randint(10, 50)
                        self.stats['stars_earned'] += random.randint(10, 50)
                        await self.update_stats_msg()
                        try:
                            await client(DeleteHistoryRequest(
                                peer=event.chat_id, max_id=0, just_clear=True
                            ))
                        except:
                            pass
                        return

        # 2. تجاهل المسابقات الخطيرة
        if any(w in text for w in DANGER_WORDS):
            return

        # 3. مسابقات آمنة
        safe = re.search(SAFE_REGEX, text, re.I)
        if safe:
            match = re.search(r'[({\[].*?[)}\]]', text)
            reply_text = match.group(0).strip('(){}[]') if match else "تم"
            try:
                await event.reply(reply_text)
            except:
                pass
            if event.reply_markup:
                await self.hunt_buttons(event, client)
            return

        # 4. القناص - صيد الهدايا المطورة (الأولوية)
        if await self.snipe_gift(event, client):
            return

        # 5. صيد الروليتات
        if event.reply_markup and event.id not in self.cache:
            btn_text = " ".join(b.text for row in event.reply_markup.rows for b in row.buttons)
            if any(k in (text + " " + btn_text).lower() for k in HUNT_KEYWORDS):
                self.cache.add(event.id)
                await self.join_channels(event, client)
                await asyncio.sleep(random.uniform(1.5, 4))
                await self.hunt_buttons(event, client)

    # ========== القناص – شراء الهدايا بسرعة ==========
    async def snipe_gift(self, event, client):
        """يبحث عن هدايا بين 126-149 نجمة ويشتريها فوراً"""
        if not self.sniper_enabled or not event.reply_markup:
            return False

        text = event.raw_text or ""

        # استخراج السعر
        prices = re.findall(r'(?:سعر|ثمن|بيع|price|قيمة)\s*[:#]?\s*(\d{2,})', text, re.I)
        for p_str in prices:
            price = int(p_str)
            if GIFT_PRICE_MIN <= price <= GIFT_PRICE_MAX and self.stars >= price:
                # استخراج اسم الهدية
                gift_name = "هدية"
                m = re.search(r'(?:هدية|Gift|مقتني)\s*["\']?([\w\s\u0600-\u06FF]+)', text, re.I)
                if m:
                    gift_name = m.group(1).strip()

                # البحث عن زر الشراء
                for row in event.reply_markup.rows:
                    for btn in row.buttons:
                        if any(k in btn.text for k in ['شراء', 'اشتري', 'buy', 'get', 'احصل', 'Purchase']):
                            logger.info(f"🔥 فرصة! {gift_name} بسعر {price} نجمة")

                            # شراء سريع جداً (0.1-0.5 ثانية)
                            await asyncio.sleep(random.uniform(0.1, 0.5))
                            try:
                                await event.click(row.row_index, btn.column_index)
                                self.stats['gifts_bought'] += 1
                                self.stars -= price
                                chat = await event.get_chat()
                                src = chat.title if hasattr(chat, 'title') else "خاص"
                                link = f"https://t.me/{chat.username}/{event.id}" if chat.username else ""

                                self.gift_log.append((gift_name, price, src, link))

                                # إشعار في المحفوظات
                                await self.main_client.send_message(
                                    'me',
                                    f"💎 **تم شراء هدية!**\n"
                                    f"الاسم: {gift_name}\n"
                                    f"السعر: {price}⭐\n"
                                    f"المصدر: {src}\n"
                                    f"الرابط: {link or 'غير متوفر'}"
                                )
                                await self.update_stats_msg()
                                logger.info(f"✅ تم الشراء: {gift_name} ({price}⭐)")
                                return True
                            except FloodWaitError as e:
                                await asyncio.sleep(e.seconds + 1)
                            except Exception as e:
                                logger.warning(f"فشل الشراء: {e}")

        return False

    # ========== صيد الروليت ==========
    async def hunt_buttons(self, event, client):
        if not event.reply_markup:
            return
        for r, row in enumerate(event.reply_markup.rows):
            for b, btn in enumerate(row.buttons):
                if any(k in btn.text for k in HUNT_KEYWORDS) or "مشاركة" in btn.text:
                    try:
                        await event.click(r, b)
                        self.stats['wins'] += 1
                        earned = random.randint(1, 5)
                        self.stars += earned
                        self.stats['stars_earned'] += earned
                        await self.update_stats_msg()
                        return
                    except FloodWaitError as e:
                        await asyncio.sleep(e.seconds + 1)
                    except:
                        pass

    async def join_channels(self, event, client):
        """الانضمام للقنوات المطلوبة"""
        links = set()
        if event.entities:
            for e in event.entities:
                if hasattr(e, 'url') and 't.me' in (e.url or ''):
                    links.add(e.url)
        links.update(re.findall(r'(?:t\.me/[\w\d_]+|@[\w\d_]+)', event.raw_text))
        for l in links:
            name = l.split('/')[-1].replace('@', '')
            try:
                await client(JoinChannelRequest(name))
            except:
                pass

    # ========== مغادرة القنوات الميتة ==========
    async def leave_dead_channels(self):
        count = 0
        for client in [self.c1, self.c2] if self.c2 else [self.c1]:
            async for d in client.iter_dialogs():
                if not d.is_channel:
                    continue
                try:
                    msgs = await client.get_messages(d.entity, limit=1)
                    if not msgs or not msgs[0].date:
                        await client(LeaveChannelRequest(d.entity))
                        count += 1
                    elif (datetime.now(tz=None) - msgs[0].date.replace(tzinfo=None)).days > 3:
                        # لو آخر رسالة من أكثر من 3 أيام
                        txt = msgs[0].raw_text or ""
                        if not any(k in txt for k in HUNT_KEYWORDS + ['مسابقة', 'روليت', 'سحب']):
                            await client(LeaveChannelRequest(d.entity))
                            count += 1
                except:
                    pass
        self.stats['channels_left'] += count
        if count:
            logger.info(f"🧹 غادرت {count} قناة ميتة")
            await self.update_stats_msg()

    # ========== أوامر ==========
    async def handle_command(self, event, parts):
        cmd = parts[0][1:].lower()
        if cmd == "stats":
            await self.update_stats_msg()
            await event.reply("✅ تم تحديث الإحصائيات")
        elif cmd == "stop":
            self.running = False
            await event.reply("🛑 توقف")
        elif cmd == "start":
            self.running = True
            await event.reply("✅ تشغيل")
        elif cmd == "sniper_on":
            self.sniper_enabled = True
            await event.reply("🎯 القناص مفعل")
        elif cmd == "sniper_off":
            self.sniper_enabled = False
            await event.reply("🔴 القناص معطل")
        elif cmd == "leavedead":
            await self.leave_dead_channels()
            await event.reply("🧹 تم التنظيف")
        elif cmd == "giftlog":
            if not self.gift_log:
                await event.reply("📭 لا توجد هدايا مشتراة")
            else:
                msg = "**💎 آخر 10 هدايا:**\n"
                for g, p, src, link in self.gift_log[-10:]:
                    msg += f"▫️ {g} – {p}⭐ | {src}\n"
                await event.reply(msg)
        elif cmd == "panel":
            btns = [
                [Button.inline("📊 الإحصائيات", b"copy_stats"),
                 Button.inline("💎 سجل الهدايا", b"copy_giftlog")],
                [Button.inline("🎯 القناص", b"copy_sniper_on"),
                 Button.inline("🧹 تنظيف", b"copy_leavedead")]
            ]
            await event.respond("🔥 **Omega Gift Sniper**", buttons=btns)

    # ========== تشغيل ==========
    async def main(self):
        if not await self.connect(self.c1, "حساب 1"):
            return
        self.main_client = self.c1

        if self.c2 and not await self.connect(self.c2, "حساب 2"):
            self.c2 = None

        @self.c1.on(events.NewMessage)
        async def h1(e):
            if e.sender_id == ADMIN_ID and e.raw_text.startswith("."):
                await self.handle_command(e, e.raw_text.split())
            elif e.is_private or e.is_channel or e.is_group:
                await self.handle_message(e, self.c1)

        if self.c2:
            @self.c2.on(events.NewMessage)
            async def h2(e):
                if e.is_private or e.is_channel or e.is_group:
                    await self.handle_message(e, self.c2)

        # أزرار اللوحة
        @self.c1.on(events.CallbackQuery)
        async def cb(e):
            data = e.data.decode()
            if data.startswith("copy_"):
                cmd = data[5:]
                await e.answer(f"✅ .{cmd}")

        # مهام خلفية
        asyncio.create_task(self.keep_alive(self.c1, "ح1"))
        if self.c2:
            asyncio.create_task(self.keep_alive(self.c2, "ح2"))
        asyncio.create_task(self.rest_schedule())

        # تنظيف القنوات كل 6 ساعات
        async def periodic_clean():
            while self.running:
                await asyncio.sleep(21600)
                await self.leave_dead_channels()
        asyncio.create_task(periodic_clean())

        # تغيير اسم الحساب الثاني
        async def persona():
            while self.running:
                await asyncio.sleep(3600)
                if self.c2 and not self.is_resting:
                    if (datetime.now() - self.last_persona_change).total_seconds() > random.randint(70000, 100000):
                        name = random.choice(PERSONA_NAMES)
                        bio = random.choice(PERSONA_BIOS)
                        await self.c2(UpdateProfileRequest(first_name=name, about=bio))
                        self.last_persona_change = datetime.now()
        asyncio.create_task(persona())

        # أول تحديث
        await self.main_client.send_message(
            'me',
            "👋 **Omega Gift Sniper جاهز**\n"
            f"🎯 يستهدف الهدايا بين {GIFT_PRICE_MIN} – {GIFT_PRICE_MAX} نجمة\n"
            ".help للأوامر"
        )
        await self.update_stats_msg()
        await self.c1(UpdateStatusRequest(offline=False))
        logger.info("🚀 Omega Gift Sniper انطلق")
        await self.c1.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(OmegaGiftSniper().main())
