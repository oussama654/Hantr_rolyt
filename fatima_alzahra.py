#!/usr/bin/env python3
import os
import asyncio
import random
import re
import time
import logging
import json
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.account import UpdateStatusRequest
from telethon.errors import FloodWaitError, AuthKeyDuplicatedError

# paramiko اختياري لـ VPS
try:
    import paramiko
    from paramiko import SSHClient, AutoAddPolicy
    SSH_AVAILABLE = True
except ImportError:
    SSH_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('flawless_v5.log'), logging.StreamHandler()]
)
logger = logging.getLogger("FlawlessV5")

# قراءة المتغيرات
API_ID_1 = int(os.environ["API_ID_1"])
API_HASH_1 = os.environ["API_HASH_1"]
SESSION_1 = os.environ["SESSION_1"]

API_ID_2 = int(os.environ.get("API_ID_2", 0))
API_HASH_2 = os.environ.get("API_HASH_2", "")
SESSION_2 = os.environ.get("SESSION_2", "")

API_ID_3 = int(os.environ.get("API_ID_3", 0))
API_HASH_3 = os.environ.get("API_HASH_3", "")
SESSION_3 = os.environ.get("SESSION_3", "")

ADMIN_ID = int(os.environ["ADMIN_ID"])
NOTIFY_USER = os.environ.get("NOTIFY_USER", "me")
VPS_CHANNEL_ID = int(os.environ.get("VPS_CHANNEL_ID", 0))
AUTO_CHANGE_VPS_PASS = os.environ.get("AUTO_CHANGE_VPS_PASS", "false").lower() == "true"

DELAY_MIN = int(os.environ.get("DELAY_MIN", 45))
DELAY_MAX = int(os.environ.get("DELAY_MAX", 180))

# كلمات الهمسات
WHISPER_KEYWORDS = ["همسة", "الهمسات", "همسة...", "صارخني", "ililbot", "همس", "سرية", "بوت صارخني", "همسة سرية"]

PARTICIPATE_BUTTONS = ["مشاركة", "انضمام", "سحب", "تدوير", "دخول", "تأكيد", "اضغط هنا", "المشاركة", "اشترك", "join", "participate", "spin"]
DANGER_WORDS = ["أكثر نجوم", "من يضع", "تصويت بنجوم", "اكثر شخص يحط", "يحط يربح", "مزاد نجوم"]

MATH_PATTERNS = [
    r'ناتج\s*:\s*(\d+)\s*\+\s*(\d+)',
    r'(\d+)\s*\+\s*(\d+)\s*\?',
    r'كم\s*ناتج\s*(\d+)\s*\+\s*(\d+)',
    r'(\d+)\s*\+\s*(\d+)',
]
EMOJI_PATTERN = r'يشبه هذا الإيموجي\s*([\U00010000-\U0010FFFF])|اضغط على الزر الذي يحتوي على\s*([\U00010000-\U0010FFFF])'
COMMENT_PATTERNS = [
    r'هل يستحق\s*(.*?)\?',
    r'اكتب\s*"([^"]+)"',
    r'علق\s*بـ\s*([^\s]+)',
]
CHANNEL_PATTERNS = [
    r'(?:@|t\.me/)([a-zA-Z0-9_]{5,})',
    r'الاشتراك في\s*([@a-zA-Z0-9_]+)',
    r'قنوات التالية:\s*(?:[0-9]+\.\s*)?(@[a-zA-Z0-9_]+)',
]

# ملفات الحظر
BLOCKLIST_FILE = "blocked_channels.json"
def load_blocklist():
    try:
        with open(BLOCKLIST_FILE, 'r') as f:
            return set(json.load(f))
    except:
        return set()
def save_blocklist(blocked):
    with open(BLOCKLIST_FILE, 'w') as f:
        json.dump(list(blocked), f)

# ========== كلاس الحساب ==========
class AccountHandler:
    def __init__(self, client, name, account_id, parent):
        self.client = client
        self.name = name
        self.account_id = account_id
        self.parent = parent
        self.running = True
        self.cache = set()

    async def delay(self):
        wait = random.uniform(DELAY_MIN, DELAY_MAX)
        logger.info(f"[{self.name}] انتظار {wait:.1f} ثانية")
        await asyncio.sleep(wait)

    async def is_whisper(self, event):
        text = event.raw_text or ""
        for kw in WHISPER_KEYWORDS:
            if kw in text:
                return True
        if event.sender_id:
            try:
                sender = await event.get_sender()
                if sender and sender.bot:
                    return True
            except:
                pass
        return False

    async def solve_math(self, text, buttons):
        for pat in MATH_PATTERNS:
            m = re.search(pat, text)
            if m:
                a = int(m.group(1)); b = int(m.group(2))
                res = a + b
                logger.info(f"[{self.name}] مسألة: {a}+{b}={res}")
                for i,row in enumerate(buttons):
                    for j,btn in enumerate(row):
                        if btn.text.strip() == str(res):
                            return i,j
        return None

    async def solve_emoji(self, text, buttons):
        m = re.search(EMOJI_PATTERN, text)
        if m:
            em = m.group(1) or m.group(2)
            if em:
                for i,row in enumerate(buttons):
                    for j,btn in enumerate(row):
                        if em in btn.text:
                            return i,j
        return None

    async def extract_comment(self, text):
        for pat in COMMENT_PATTERNS:
            m = re.search(pat, text, re.I)
            if m:
                return m.group(1).strip('"\'')
        if re.search(r'هل يستحق', text):
            return "يستحق"
        return None

    async def reply_comment(self, event, comment):
        try:
            if event.message.fwd_from and event.message.fwd_from.from_id:
                cid = event.message.fwd_from.from_id.channel_id
                if cid:
                    chat = await self.client.get_entity(cid)
                    await self.client.send_message(chat, comment, reply_to=event.message.id)
                    logger.info(f"[{self.name}] رد على منشور محول: {comment}")
                    self.parent.stats['captcha_solved'] += 1
                    return True
            await event.reply(comment)
            logger.info(f"[{self.name}] تعليق: {comment}")
            self.parent.stats['captcha_solved'] += 1
            return True
        except Exception as e:
            logger.error(f"[{self.name}] فشل التعليق: {e}")
            return False

    async def click_participate(self, event):
        if not event.reply_markup:
            return False
        # أول زر
        try:
            btn = event.reply_markup.rows[0].buttons[0]
            if btn.text not in ["إلغاء","Cancel","لا"]:
                await event.click(0,0)
                logger.info(f"[{self.name}] ضغط أول زر: {btn.text}")
                self.parent.stats['wins'] += 1
                return True
        except:
            pass
        # أزرار بها كلمات مشاركة
        for i,row in enumerate(event.reply_markup.rows):
            for j,btn in enumerate(row.buttons):
                if any(k in btn.text for k in PARTICIPATE_BUTTONS):
                    await event.click(i,j)
                    logger.info(f"[{self.name}] ضغط زر: {btn.text}")
                    self.parent.stats['wins'] += 1
                    return True
        return False

    async def join_channels(self, text):
        if not self.running:
            return
        channels = set()
        for pat in CHANNEL_PATTERNS:
            for m in re.findall(pat, text):
                uname = m.strip('@')
                if len(uname) > 3 and uname.lower() not in ['bot','c','me','telegram']:
                    channels.add(uname)
        blocked = load_blocklist()
        for uname in channels:
            if uname in blocked:
                logger.info(f"[{self.name}] قناة {uname} محظورة، تخطي")
                continue
            try:
                entity = await self.client.get_entity(uname)
                await self.delay()
                await self.client(JoinChannelRequest(entity))
                logger.info(f"[{self.name}] انضم إلى {uname}")
                self.parent.stats['joined_channels'] += 1
            except FloodWaitError as e:
                logger.warning(f"[{self.name}] FloodWait {e.seconds}s")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"[{self.name}] فشل الانضمام {uname}: {e}")

    async def process(self, event):
        if not self.running:
            return
        if event.id in self.cache:
            return
        # تجاهل الهمسات فوراً
        if await self.is_whisper(event):
            logger.info(f"[{self.name}] تجاهل همسة: {event.raw_text[:50]}")
            return
        text = event.raw_text or ""
        if any(w in text for w in DANGER_WORDS):
            return

        # انضمام للقنوات
        await self.join_channels(text)

        # حل الكابتشا
        if event.reply_markup:
            buttons = [[b for b in row.buttons] for row in event.reply_markup.rows]
            pos = await self.solve_math(text, buttons)
            if not pos:
                pos = await self.solve_emoji(text, buttons)
            if pos:
                try:
                    await event.click(pos[0], pos[1])
                    logger.info(f"[{self.name}] تم حل كابتشا")
                    self.parent.stats['captcha_solved'] += 1
                    await self.delay()
                except Exception as e:
                    logger.error(f"[{self.name}] خطأ في الضغط: {e}")

        # تعليق
        cmt = await self.extract_comment(text)
        if cmt:
            await self.reply_comment(event, cmt)
            await self.delay()

        # زر المشاركة
        if await self.click_participate(event):
            self.cache.add(event.id)
            return

        # ضغط عام (آخر زر)
        if event.reply_markup and event.id not in self.cache:
            try:
                btn = event.reply_markup.rows[0].buttons[0]
                if btn.text not in ["إلغاء","Cancel","لا"]:
                    await event.click(0,0)
                    logger.info(f"[{self.name}] ضغط عام: {btn.text}")
                    self.parent.stats['wins'] += 1
                    self.cache.add(event.id)
            except:
                pass

    async def keep_alive(self):
        while True:
            try:
                if not self.client.is_connected():
                    await self.client.connect()
                await self.client(UpdateStatusRequest(offline=False))
            except:
                pass
            await asyncio.sleep(120)

    async def run(self):
        @self.client.on(events.NewMessage)
        async def handler(event):
            if event.sender_id == ADMIN_ID and event.raw_text.startswith("."):
                return
            if event.is_channel or event.is_group:
                await self.process(event)
        asyncio.create_task(self.keep_alive())
        logger.info(f"[{self.name}] بدأ العمل (تأخير {DELAY_MIN}-{DELAY_MAX} ثانية)")
        await self.client.run_until_disconnected()

# ========== الكلاس الرئيسي ==========
class OmegaFlawlessV5:
    def __init__(self):
        self.accounts = []
        self.main_client = None
        self.stats = {"vps":0, "wins":0, "joined_channels":0, "captcha_solved":0, "left":0, "start":time.time()}
        self.vps_active = True  # مراقبة VPS تعمل دائماً

    async def init_account(self, api_id, api_hash, sess, name, aid):
        if not api_id or not api_hash or not sess:
            return None
        client = TelegramClient(StringSession(sess), api_id, api_hash)
        try:
            await client.connect()
            if not await client.is_user_authorized():
                return None
            acc = AccountHandler(client, name, aid, self)
            self.accounts.append(acc)
            if aid == 1:
                self.main_client = client
            logger.info(f"✅ {name} جاهز")
            return acc
        except Exception as e:
            logger.error(f"فشل {name}: {e}")
            return None

    async def start_all(self):
        await self.init_account(API_ID_1, API_HASH_1, SESSION_1, "الحساب_الأول", 1)
        if API_ID_2:
            await self.init_account(API_ID_2, API_HASH_2, SESSION_2, "الحساب_الثاني", 2)
        if API_ID_3:
            await self.init_account(API_ID_3, API_HASH_3, SESSION_3, "الحساب_الثالث", 3)
        if not self.accounts:
            logger.critical("لا توجد حسابات صالحة")
            return

        # مراقبة VPS (دائماً نشطة)
        if VPS_CHANNEL_ID and self.main_client:
            @self.main_client.on(events.NewMessage(chats=VPS_CHANNEL_ID))
            async def vps_handler(event):
                await self.vps_watcher(event)

        # أوامر الأدمن
        if self.main_client:
            @self.main_client.on(events.NewMessage(from_users=ADMIN_ID))
            async def admin_cmd(event):
                if event.raw_text.startswith("."):
                    await self.handle_command(event, event.raw_text.split())

        asyncio.create_task(self.live_stats())
        tasks = [acc.run() for acc in self.accounts]
        await asyncio.gather(*tasks)

    # ---------- VPS ----------
    def extract_vps(self, text):
        ipm = re.search(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b', text)
        if not ipm:
            return None,None,None
        ip = ipm.group(1)
        user = "root"
        um = re.search(r'(?:User|Username|login)[\s:]*([a-zA-Z0-9_@.-]+)', text, re.I)
        if um: user = um.group(1)
        pm = re.search(r'(?:Password|Pass|New password)[\s:]*([^\s]+)', text, re.I)
        pwd = pm.group(1) if pm else None
        if not pwd:
            pm2 = re.search(r'(?:^|\n)\s*([^\s]+@[^\s]+|[A-Za-z0-9!@#%^&*]+)\s*(?:\n|$)', text, re.MULTILINE)
            if pm2: pwd = pm2.group(1)
        return ip, user, pwd

    async def change_vps_pass(self, ip, user, old):
        if not SSH_AVAILABLE or not AUTO_CHANGE_VPS_PASS:
            return
        new = ''.join(random.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*') for _ in range(14))
        try:
            ssh = SSHClient()
            ssh.set_missing_host_key_policy(AutoAddPolicy())
            ssh.connect(ip, username=user, password=old, timeout=10)
            ssh.exec_command(f'echo "{user}:{new}" | chpasswd')
            ssh.close()
            logger.info(f"🔐 تغيير كلمة {ip}")
            await self.main_client.send_message(NOTIFY_USER, f"✅ **تم تغيير كلمة VPS**\n🌐 IP: `{ip}`\n👤 User: `{user}`\n🔑 New: `{new}`")
        except Exception as e:
            logger.error(f"SSH فشل {ip}: {e}")

    async def vps_watcher(self, event):
        if not self.vps_active:
            return
        text = event.raw_text or ""
        ip,u,p = self.extract_vps(text)
        if ip and p:
            self.stats['vps'] += 1
            await self.main_client.send_message(NOTIFY_USER, f"🔥 **VPS جديد**\n🌐 IP: `{ip}`\n👤 User: `{u}`\n🔑 Pass: `{p}`")
            logger.info(f"✅ VPS: {ip}")
            await self.change_vps_pass(ip, u, p)

    # ---------- إحصائيات وأوامر ----------
    async def live_stats(self):
        msg_id = None
        while True:
            uptime = str(timedelta(seconds=int(time.time()-self.stats['start'])))
            msg = (f"📊 **Flawless V5**\n🕒 {datetime.now():%H:%M:%S}\n⏱️ {uptime}\n🌐 VPS: {self.stats['vps']}\n🏆 فوز: {self.stats['wins']}\n📢 انضم: {self.stats['joined_channels']}\n🧩 كابتشا: {self.stats['captcha_solved']}\n🚪 مغادرة: {self.stats['left']}\n👥 حسابات: {len(self.accounts)}\n⏲️ تأخير: {DELAY_MIN}-{DELAY_MAX} ثانية")
            if self.main_client:
                try:
                    if msg_id:
                        await self.main_client.edit_message(NOTIFY_USER, msg_id, msg)
                    else:
                        s = await self.main_client.send_message(NOTIFY_USER, msg)
                        msg_id = s.id
                except:
                    pass
            await asyncio.sleep(15)

    async def handle_command(self, event, parts):
        cmd = parts[0][1:].lower()
        # إيقاف كلي
        if cmd == "stop":
            for acc in self.accounts:
                acc.running = False
            await event.reply("🛑 تم إيقاف جميع الحسابات (مراقبة VPS ما زالت نشطة)")
        # تشغيل كلي
        elif cmd == "start":
            for acc in self.accounts:
                acc.running = True
            await event.reply("✅ تم تشغيل جميع الحسابات")
        # إيقاف حساب فردي
        elif cmd == "stop1":
            if len(self.accounts) >= 1:
                self.accounts[0].running = False
                await event.reply("🛑 توقف الحساب الأول")
            else:
                await event.reply("لا يوجد حساب أول")
        elif cmd == "stop2":
            if len(self.accounts) >= 2:
                self.accounts[1].running = False
                await event.reply("🛑 توقف الحساب الثاني")
            else:
                await event.reply("لا يوجد حساب ثان")
        elif cmd == "stop3":
            if len(self.accounts) >= 3:
                self.accounts[2].running = False
                await event.reply("🛑 توقف الحساب الثالث")
            else:
                await event.reply("لا يوجد حساب ثالث")
        # تشغيل فردي
        elif cmd == "start1":
            if len(self.accounts) >= 1:
                self.accounts[0].running = True
                await event.reply("✅ تشغيل الحساب الأول")
        elif cmd == "start2":
            if len(self.accounts) >= 2:
                self.accounts[1].running = True
                await event.reply("✅ تشغيل الحساب الثاني")
        elif cmd == "start3":
            if len(self.accounts) >= 3:
                self.accounts[2].running = True
                await event.reply("✅ تشغيل الحساب الثالث")
        # حظر قناة
        elif cmd == "block":
            if len(parts) < 2:
                await event.reply("الاستخدام: .block @username")
                return
            ch = parts[1].strip('@')
            blocked = load_blocklist()
            blocked.add(ch)
            save_blocklist(blocked)
            await event.reply(f"🚫 تم حظر القناة {ch} (لن يتم الانضمام إليها)")
        # إلغاء حظر قناة
        elif cmd == "unblock":
            if len(parts) < 2:
                await event.reply("الاستخدام: .unblock @username")
                return
            ch = parts[1].strip('@')
            blocked = load_blocklist()
            if ch in blocked:
                blocked.remove(ch)
                save_blocklist(blocked)
                await event.reply(f"✅ تم إلغاء حظر {ch}")
            else:
                await event.reply(f"⚠️ {ch} غير محظورة")
        # عرض القنوات المحظورة
        elif cmd == "blocklist":
            blocked = load_blocklist()
            if blocked:
                await event.reply(f"🚫 القنوات المحظورة:\n" + "\n".join(f"- @{b}" for b in blocked))
            else:
                await event.reply("لا توجد قنوات محظورة")
        # الانضمام اليدوي لقناة
        elif cmd == "join":
            if len(parts) < 2:
                await event.reply("الاستخدام: .join @username")
                return
            ch = parts[1].strip('@')
            for acc in self.accounts:
                try:
                    entity = await acc.client.get_entity(ch)
                    await acc.client(JoinChannelRequest(entity))
                    await event.reply(f"✅ {acc.name} انضم إلى @{ch}")
                    await asyncio.sleep(2)
                except Exception as e:
                    await event.reply(f"❌ {acc.name} فشل: {e}")
        # إحصائيات سريعة
        elif cmd == "stats":
            await event.reply("📊 الإحصائيات تُرسل إلى الخاص")
        # الإعدادات الحالية
        elif cmd == "config":
            await event.reply(f"⚙️ الإعدادات:\nتأخير: {DELAY_MIN}-{DELAY_MAX} ثانية\nVPS قناة: {VPS_CHANNEL_ID}\nتغيير كلمة المرور: {AUTO_CHANGE_VPS_PASS}\nعدد الحسابات: {len(self.accounts)}")
        else:
            await event.reply("أوامر متاحة:\n.start / .stop (كل الحسابات)\n.start1/stop1, .start2/stop2, .start3/stop3\n.block @channel / .unblock @channel / .blocklist\n.join @channel\n.stats\n.config")

    async def run(self):
        logger.info("بدء تشغيل Flawless V5 (بدون همسات، تأخير كبير، حظر القنوات)")
        await self.start_all()

if __name__ == "__main__":
    bot = OmegaFlawlessV5()
    asyncio.run(bot.run())
