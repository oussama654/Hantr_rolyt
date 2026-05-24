#!/usr/bin/env python3
"""
███████████████████████████████████████████████████████████████████████████████
Omega Flawless v5 – الإصدار النهائي (3 حسابات، بدون همسات، تأخير كبير، صيد VPS)
- دعم 3 حسابات مع اتصال دائم
- تجنب الهمسات والبوتات تماماً
- تأخير عشوائي بين 30 ثانية ودقيقتين
- صيد VPS من قنوات محددة وتغيير كلمة المرور
- أوامر تحكم شاملة (.start, .stop, .stats, .config, .restart)
███████████████████████████████████████████████████████████████████████████████
"""

import os
import asyncio
import random
import re
import time
import logging
import json
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button, functions
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.account import UpdateStatusRequest
from telethon.errors import (
    FloodWaitError, UserBannedInChannelError, UserChannelsTooMuchError,
    ChannelsTooMuchError, AuthKeyDuplicatedError
)

# paramiko لتغيير كلمة مرور VPS (اختياري)
try:
    import paramiko
    from paramiko import SSHClient, AutoAddPolicy
    SSH_AVAILABLE = True
except ImportError:
    SSH_AVAILABLE = False

# إعدادات التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('flawless_v5.log'), logging.StreamHandler()]
)
logger = logging.getLogger("FlawlessV5")

# ========== قراءة متغيرات البيئة ==========
# الحسابات (حتى 3)
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

# إعدادات التأخير (بالثواني)
DELAY_MIN = int(os.environ.get("DELAY_MIN", 30))
DELAY_MAX = int(os.environ.get("DELAY_MAX", 120))

# ========== الكلمات المفتاحية للأزرار ==========
PARTICIPATE_BUTTONS = [
    "مشاركة", "انضمام", "سحب", "تدوير", "دخول", "تأكيد", "اضغط هنا",
    "المشاركة", "اشترك", "join", "participate", "spin", "شارك"
]

# كلمات تدل على مسابقات خطيرة (نتجنبها)
DANGER_WORDS = ["أكثر نجوم", "من يضع", "تصويت بنجوم", "اكثر شخص يحط", "يحط يربح", "مزاد نجوم"]

# كلمات الهمسات التي يجب تجاهلها
WHISPER_WORDS = ["همسة", "صارخني", "ililbot", "همس", "سرية", "بوت صارخني", "همسة سرية", "همسات"]

# ========== أنماط الكابتشا ==========
MATH_PATTERNS = [
    r'ناتج\s*:\s*(\d+)\s*\+\s*(\d+)',
    r'(\d+)\s*\+\s*(\d+)\s*\?',
    r'كم\s*ناتج\s*(\d+)\s*\+\s*(\d+)',
    r'(\d+)\s*\+\s*(\d+)',
    r'(\d+)\s*\-\s*(\d+)',
    r'(\d+)\s*\*\s*(\d+)',
]

EMOJI_PATTERN = r'يشبه هذا الإيموجي\s*([\U00010000-\U0010FFFF])|اضغط على الزر الذي يحتوي على\s*([\U00010000-\U0010FFFF])'

COMMENT_PATTERNS = [
    r'هل يستحق\s*(.*?)\?',
    r'اكتب\s*"([^"]+)"',
    r'علق\s*بـ\s*([^\s]+)',
    r'يقول\s*"([^"]+)"'
]

CHANNEL_PATTERNS = [
    r'(?:@|t\.me/)([a-zA-Z0-9_]{5,})',
    r'الاشتراك في\s*([@a-zA-Z0-9_]+)',
    r'قنوات التالية:\s*(?:[0-9]+\.\s*)?(@[a-zA-Z0-9_]+)',
    r'(?:انضم|اشترك)\s*إلى\s*([@a-zA-Z0-9_]+)'
]

# ========== الفئة الرئيسية لكل حساب ==========
class AccountHandler:
    def __init__(self, client, name, account_id, parent):
        self.client = client
        self.name = name
        self.account_id = account_id
        self.parent = parent
        self.running = True
        self.cache = set()

    async def dynamic_delay(self):
        """تأخير عشوائي بين DELAY_MIN و DELAY_MAX (افتراضي 30-120 ثانية)"""
        delay = random.uniform(DELAY_MIN, DELAY_MAX)
        logger.info(f"[{self.name}] انتظار {delay:.1f} ثانية (تجنب الاكتشاف)")
        await asyncio.sleep(delay)

    async def is_whisper(self, event):
        """التحقق مما إذا كانت الرسالة همسة أو من بوت همسات"""
        text = event.raw_text or ""
        # كلمات الهمسات
        for w in WHISPER_WORDS:
            if w in text:
                return True
        # إذا كان المرسل بوتاً معروفاً للهمسات
        if event.sender_id:
            try:
                sender = await event.get_sender()
                if hasattr(sender, 'bot') and sender.bot:
                    return True
            except:
                pass
        # التحقق من وجود كلمة "همسة" في أي مكان
        if "همسة" in text:
            return True
        return False

    async def solve_math_captcha(self, text, buttons):
        for pattern in MATH_PATTERNS:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    try:
                        a = int(groups[0])
                        b = int(groups[1])
                        if '+' in match.group(0) or 'جمع' in text:
                            result = a + b
                        elif '-' in match.group(0):
                            result = a - b
                        elif '*' in match.group(0):
                            result = a * b
                        else:
                            result = a + b
                        logger.info(f"[{self.name}] 🧮 مسألة: {a} + {b} = {result}")
                        for row_idx, row in enumerate(buttons):
                            for col_idx, btn in enumerate(row):
                                if btn.text.strip() == str(result):
                                    return row_idx, col_idx
                    except:
                        continue
        return None

    async def solve_emoji_captcha(self, text, buttons):
        match = re.search(EMOJI_PATTERN, text)
        if match:
            target_emoji = match.group(1) or match.group(2)
            if target_emoji:
                logger.info(f"[{self.name}] 😀 إيموجي: {target_emoji}")
                for row_idx, row in enumerate(buttons):
                    for col_idx, btn in enumerate(row):
                        if target_emoji in btn.text:
                            return row_idx, col_idx
        return None

    async def extract_comment_text(self, text):
        for pattern in COMMENT_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                comment = match.group(1).strip().strip('"\'')
                return comment
        if re.search(r'هل يستحق', text, re.IGNORECASE):
            return "يستحق"
        return None

    async def reply_comment(self, event, comment):
        try:
            if event.message.fwd_from and event.message.fwd_from.from_id:
                original_chat_id = event.message.fwd_from.from_id.channel_id
                if original_chat_id:
                    original_chat = await self.client.get_entity(original_chat_id)
                    await self.client.send_message(original_chat, comment, reply_to=event.message.id)
                    logger.info(f"[{self.name}] ✅ رد على منشور محول: {comment}")
                    self.parent.stats['captcha_solved'] += 1
                    return True
            await event.reply(comment)
            logger.info(f"[{self.name}] ✅ تعليق: {comment}")
            self.parent.stats['captcha_solved'] += 1
            return True
        except Exception as e:
            logger.error(f"[{self.name}] فشل التعليق: {e}")
            return False

    async def click_participate_button(self, event):
        if not event.reply_markup:
            return False
        try:
            first_btn = event.reply_markup.rows[0].buttons[0]
            if first_btn.text not in ["إلغاء", "Cancel", "لا", "غلق"]:
                await event.click(0, 0)
                logger.info(f"[{self.name}] ✅ ضغط على أول زر: {first_btn.text}")
                self.parent.stats['wins'] += 1
                return True
        except:
            pass
        for row_idx, row in enumerate(event.reply_markup.rows):
            for col_idx, btn in enumerate(row.buttons):
                if any(k in btn.text for k in PARTICIPATE_BUTTONS):
                    try:
                        await event.click(row_idx, col_idx)
                        logger.info(f"[{self.name}] ✅ ضغط على زر: {btn.text}")
                        self.parent.stats['wins'] += 1
                        return True
                    except:
                        pass
        return False

    async def extract_and_join_channels(self, text):
        channels = set()
        for pattern in CHANNEL_PATTERNS:
            matches = re.findall(pattern, text)
            for m in matches:
                username = m.strip('@')
                if username and len(username) > 3 and username.lower() not in ['bot', 'c', 'me', 'telegram']:
                    channels.add(username)
        if not channels:
            return 0
        for username in channels:
            try:
                entity = await self.client.get_entity(username)
                await self.dynamic_delay()
                await self.client(JoinChannelRequest(entity))
                logger.info(f"[{self.name}] ✅ انضم للقناة: {username}")
                self.parent.stats['joined_channels'] += 1
            except FloodWaitError as e:
                logger.warning(f"[{self.name}] FloodWait {e.seconds}s")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"[{self.name}] فشل الانضمام {username}: {e}")
        return len(channels)

    async def process_message(self, event):
        if event.id in self.cache:
            return

        # تجاهل الهمسات تماماً
        if await self.is_whisper(event):
            logger.info(f"[{self.name}] ⚠️ تجاهل همسة: {event.raw_text[:50]}")
            return

        text = event.raw_text or ""

        # تجنب المسابقات الخطيرة
        if any(word in text for word in DANGER_WORDS):
            return

        # 1. الانضمام للقنوات
        await self.extract_and_join_channels(text)

        # 2. حل الكابتشا
        if event.reply_markup:
            buttons = [[btn for btn in row.buttons] for row in event.reply_markup.rows]
            math_pos = await self.solve_math_captcha(text, buttons)
            if math_pos:
                row, col = math_pos
                try:
                    await event.click(row, col)
                    logger.info(f"[{self.name}] 🧠 حل كابتشا حسابي")
                    self.parent.stats['captcha_solved'] += 1
                    await self.dynamic_delay()
                except Exception as e:
                    logger.error(f"[{self.name}] فشل حل المسألة: {e}")
            else:
                emoji_pos = await self.solve_emoji_captcha(text, buttons)
                if emoji_pos:
                    row, col = emoji_pos
                    try:
                        await event.click(row, col)
                        logger.info(f"[{self.name}] 😀 حل كابتشا إيموجي")
                        self.parent.stats['captcha_solved'] += 1
                        await self.dynamic_delay()
                    except Exception as e:
                        logger.error(f"[{self.name}] فشل الإيموجي: {e}")

        # 3. التعليق المطلوب
        comment = await self.extract_comment_text(text)
        if comment:
            await self.reply_comment(event, comment)
            await self.dynamic_delay()

        # 4. زر المشاركة
        if await self.click_participate_button(event):
            self.cache.add(event.id)
            return

        # 5. ضغط عام على أول زر
        if event.reply_markup and event.id not in self.cache:
            try:
                first_btn = event.reply_markup.rows[0].buttons[0]
                if first_btn.text not in ["إلغاء", "Cancel", "لا"]:
                    await event.click(0, 0)
                    logger.info(f"[{self.name}] ⚠️ ضغط عام: {first_btn.text}")
                    self.parent.stats['wins'] += 1
                    self.cache.add(event.id)
            except:
                pass

    async def keep_alive(self):
        while self.running:
            try:
                if not self.client.is_connected():
                    await self.client.connect()
                await self.client(UpdateStatusRequest(offline=False))
            except Exception as e:
                logger.error(f"[{self.name}] Keep-alive: {e}")
            await asyncio.sleep(120)

    async def run(self):
        @self.client.on(events.NewMessage)
        async def handler(event):
            # تجاهل أوامر الأدمن (تعالج عالمياً)
            if event.sender_id == ADMIN_ID and event.raw_text.startswith("."):
                return
            if event.is_channel or event.is_group:
                await self.process_message(event)
        asyncio.create_task(self.keep_alive())
        logger.info(f"[{self.name}] جاهز (تأخير {DELAY_MIN}-{DELAY_MAX} ثانية)")
        await self.client.run_until_disconnected()

# ========== الفئة الرئيسية (تدير الحسابات وأوامر الأدمن و VPS) ==========
class OmegaFlawlessV5:
    def __init__(self):
        self.accounts = []
        self.clients = []
        self.stats = {
            "vps": 0,
            "wins": 0,
            "joined_channels": 0,
            "captcha_solved": 0,
            "left": 0,
            "start": time.time()
        }
        self.running = True
        self.main_client = None
        self.config = {"delay_min": DELAY_MIN, "delay_max": DELAY_MAX}

    async def init_account(self, api_id, api_hash, session_str, name, account_id):
        if not api_id or not api_hash or not session_str:
            return None
        client = TelegramClient(StringSession(session_str), api_id, api_hash)
        try:
            await client.connect()
            if not await client.is_user_authorized():
                logger.error(f"{name} غير مصرح")
                return None
            handler = AccountHandler(client, name, account_id, self)
            self.accounts.append(handler)
            self.clients.append(client)
            if account_id == 1:
                self.main_client = client
            logger.info(f"✅ {name} تم تهيئته")
            return handler
        except Exception as e:
            logger.error(f"فشل تهيئة {name}: {e}")
            return None

    async def start_all(self):
        await self.init_account(API_ID_1, API_HASH_1, SESSION_1, "الحساب_الأول", 1)
        if API_ID_2 and SESSION_2:
            await self.init_account(API_ID_2, API_HASH_2, SESSION_2, "الحساب_الثاني", 2)
        if API_ID_3 and SESSION_3:
            await self.init_account(API_ID_3, API_HASH_3, SESSION_3, "الحساب_الثالث", 3)
        if not self.accounts:
            logger.critical("لا يوجد حسابات صالحة")
            return

        # مراقبة VPS (على الحساب الرئيسي)
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
        ip_match = re.search(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b', text)
        if not ip_match:
            return None, None, None
        ip = ip_match.group(1)
        user = "root"
        user_match = re.search(r'(?:User|Username|login)[\s:]*([a-zA-Z0-9_@.-]+)', text, re.I)
        if user_match:
            user = user_match.group(1)
        pwd_match = re.search(r'(?:Password|Pass|New password)[\s:]*([^\s]+)', text, re.I)
        pwd = pwd_match.group(1) if pwd_match else None
        if not pwd:
            pwd_match2 = re.search(r'(?:^|\n)\s*([^\s]+@[^\s]+|[A-Za-z0-9!@#%^&*]+)\s*(?:\n|$)', text, re.MULTILINE)
            if pwd_match2:
                pwd = pwd_match2.group(1)
        return ip, user, pwd

    async def change_vps_password(self, ip, user, old_pass):
        if not SSH_AVAILABLE:
            return
        new_pass = self.generate_strong_password()
        try:
            ssh = SSHClient()
            ssh.set_missing_host_key_policy(AutoAddPolicy())
            ssh.connect(ip, username=user, password=old_pass, timeout=10)
            command = f'echo "{user}:{new_pass}" | chpasswd'
            stdin, stdout, stderr = ssh.exec_command(command)
            err = stderr.read().decode()
            if err:
                logger.error(f"خطأ SSH {ip}: {err}")
                return
            ssh.close()
            logger.info(f"🔐 تم تغيير كلمة {ip}")
            msg = f"✅ **تم تغيير كلمة VPS**\n🌐 IP: `{ip}`\n👤 User: `{user}`\n🔑 New: `{new_pass}`"
            await self.main_client.send_message(NOTIFY_USER, msg)
        except Exception as e:
            logger.error(f"SSH فشل {ip}: {e}")

    def generate_strong_password(self, length=14):
        chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
        return ''.join(random.choice(chars) for _ in range(length))

    async def vps_watcher(self, event):
        text = event.raw_text or ""
        ip, user, pwd = self.extract_vps(text)
        if ip and pwd:
            self.stats['vps'] += 1
            msg = f"🔥 **VPS جديد**\n🌐 IP: `{ip}`\n👤 User: `{user}`\n🔑 Pass: `{pwd}`"
            await self.main_client.send_message(NOTIFY_USER, msg)
            logger.info(f"✅ VPS: {ip}")
            if AUTO_CHANGE_VPS_PASS and SSH_AVAILABLE:
                await self.change_vps_password(ip, user, pwd)

    # ---------- إحصائيات وأوامر ----------
    async def live_stats(self):
        msg_id = None
        while self.running:
            uptime = str(timedelta(seconds=int(time.time() - self.stats['start'])))
            msg = (
                f"📊 **Flawless V5**\n"
                f"🕒 {datetime.now():%H:%M:%S}\n"
                f"⏱️ {uptime}\n"
                f"🌐 VPS: {self.stats['vps']}\n"
                f"🏆 فوز: {self.stats['wins']}\n"
                f"📢 انضم: {self.stats['joined_channels']}\n"
                f"🧩 كابتشا: {self.stats['captcha_solved']}\n"
                f"🚪 مغادرة: {self.stats['left']}\n"
                f"👥 حسابات: {len(self.accounts)}\n"
                f"⏲️ تأخير: {DELAY_MIN}-{DELAY_MAX} ثانية"
            )
            if self.main_client:
                try:
                    if msg_id:
                        await self.main_client.edit_message(NOTIFY_USER, msg_id, msg)
                    else:
                        sent = await self.main_client.send_message(NOTIFY_USER, msg)
                        msg_id = sent.id
                except:
                    pass
            await asyncio.sleep(10)

    async def handle_command(self, event, parts):
        cmd = parts[0][1:].lower()
        if cmd == "stop":
            self.running = False
            for acc in self.accounts:
                acc.running = False
            await event.reply("🛑 تم إيقاف جميع الحسابات")
        elif cmd == "start":
            self.running = True
            for acc in self.accounts:
                acc.running = True
            await event.reply("✅ تم تشغيل جميع الحسابات")
        elif cmd == "stats":
            await event.reply("📊 الإحصائيات تُرسل إلى الخاص")
        elif cmd == "config":
            await event.reply(f"⚙️ الإعدادات:\nتأخير: {DELAY_MIN}-{DELAY_MAX} ثانية\nVPS: {'نشط' if VPS_CHANNEL_ID else 'غير نشط'}\nتغيير كلمة المرور: {AUTO_CHANGE_VPS_PASS}")
        else:
            await event.reply("أوامر متاحة:\n.start - تشغيل\n.stop - إيقاف\n.stats - إحصائيات\n.config - عرض الإعدادات")

    async def run(self):
        logger.info("🚀 تشغيل Flawless V5 (بدون همسات، تأخير كبير)")
        await self.start_all()

if __name__ == "__main__":
    bot = OmegaFlawlessV5()
    asyncio.run(bot.run())
