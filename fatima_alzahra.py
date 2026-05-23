#!/usr/bin/env python3
"""
███████████████████████████████████████████████████████████████████████████████
Omega Flawless v4 – الإصدار المتكامل النهائي
- دعم 3 حسابات (أو أكثر) مع اتصال دائم
- حل جميع أنواع الكابتشا (حسابي، إيموجي، تعليق)
- انضمام تلقائي للقنوات الإجبارية (روابط، يوزرات، نصوص)
- تفاعل مع الأزرار: المشاركة، الانضمام، السحب، التدوير
- معالجة المنشورات المحولة (الرد في القناة الأصلية)
- تأخير عشوائي بين 6-25 ثانية لكل إجراء
- إدارة FloodWait بذكاء
- استخراج VPS وتغيير كلمة المرور عبر SSH
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
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.account import UpdateStatusRequest
from telethon.errors import (
    FloodWaitError, UserBannedInChannelError, UserChannelsTooMuchError,
    ChannelsTooMuchError, AuthKeyDuplicatedError
)

# paramiko اختياري لتغيير كلمة مرور VPS
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
    handlers=[logging.FileHandler('flawless_v4.log'), logging.StreamHandler()]
)
logger = logging.getLogger("FlawlessV4")

# ========== قراءة متغيرات البيئة ==========
# الحساب الأول (إجباري)
API_ID_1 = int(os.environ["API_ID_1"])
API_HASH_1 = os.environ["API_HASH_1"]
SESSION_1 = os.environ["SESSION_1"]

# الحساب الثاني (اختياري)
API_ID_2 = int(os.environ.get("API_ID_2", 0))
API_HASH_2 = os.environ.get("API_HASH_2", "")
SESSION_2 = os.environ.get("SESSION_2", "")

# الحساب الثالث (اختياري)
API_ID_3 = int(os.environ.get("API_ID_3", 0))
API_HASH_3 = os.environ.get("API_HASH_3", "")
SESSION_3 = os.environ.get("SESSION_3", "")

ADMIN_ID = int(os.environ["ADMIN_ID"])
NOTIFY_USER = os.environ.get("NOTIFY_USER", "me")
VPS_CHANNEL_ID = int(os.environ.get("VPS_CHANNEL_ID", 0))
AUTO_CHANGE_VPS_PASS = os.environ.get("AUTO_CHANGE_VPS_PASS", "false").lower() == "true"

# ========== الكلمات المفتاحية للأزرار ==========
PARTICIPATE_BUTTONS = [
    "مشاركة", "انضمام", "سحب", "تدوير", "دخول", "تأكيد", "اضغط هنا",
    "المشاركة", "اشترك", "join", "participate", "spin", "شارك"
]

# كلمات تدل على مسابقات خطيرة (نتجنبها)
DANGER_WORDS = ["أكثر نجوم", "من يضع", "تصويت بنجوم", "اكثر شخص يحط", "يحط يربح", "مزاد نجوم"]

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

# أنماط استخراج القنوات الإجبارية
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
        self.parent = parent  # مرجع للكائن الرئيسي
        self.running = True
        self.cache = set()  # لتجنب معالجة نفس الرسالة عدة مرات

    async def dynamic_delay(self):
        """تأخير عشوائي بين 6 و 25 ثانية"""
        delay = random.uniform(6, 25)
        logger.debug(f"[{self.name}] انتظار {delay:.1f} ثانية")
        await asyncio.sleep(delay)

    async def solve_math_captcha(self, text, buttons):
        """حل المسائل الحسابية والضغط على الزر المناسب"""
        for pattern in MATH_PATTERNS:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    try:
                        a = int(groups[0])
                        b = int(groups[1])
                        # تحديد العملية من النص
                        if '+' in match.group(0) or 'جمع' in text:
                            result = a + b
                        elif '-' in match.group(0):
                            result = a - b
                        elif '*' in match.group(0):
                            result = a * b
                        else:
                            result = a + b  # افتراضي جمع
                        logger.info(f"[{self.name}] 🧮 حل مسألة: {a} + {b} = {result}")
                        # البحث عن زر بنفس الرقم
                        for row_idx, row in enumerate(buttons):
                            for col_idx, btn in enumerate(row):
                                if btn.text.strip() == str(result):
                                    return row_idx, col_idx
                    except:
                        continue
        return None

    async def solve_emoji_captcha(self, text, buttons):
        """حل كابتشا الإيموجي"""
        match = re.search(EMOJI_PATTERN, text)
        if match:
            target_emoji = match.group(1) or match.group(2)
            if target_emoji:
                logger.info(f"[{self.name}] 😀 إيموجي مطلوب: {target_emoji}")
                for row_idx, row in enumerate(buttons):
                    for col_idx, btn in enumerate(row):
                        if target_emoji in btn.text:
                            return row_idx, col_idx
        return None

    async def extract_comment_text(self, text):
        """استخراج النص المطلوب للتعليق"""
        for pattern in COMMENT_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                comment = match.group(1).strip().strip('"\'')
                logger.info(f"[{self.name}] 📝 نص التعليق المطلوب: {comment}")
                return comment
        # حالة خاصة: سؤال "هل يستحق" بدون نص محدد
        if re.search(r'هل يستحق', text, re.IGNORECASE):
            return "يستحق"
        return None

    async def reply_comment(self, event, comment):
        """الرد على الرسالة بتعليق"""
        try:
            # إذا كانت الرسالة مُحولة (forwarded)، نحاول الرد في القناة الأصلية
            if event.message.fwd_from and event.message.fwd_from.from_id:
                original_chat_id = event.message.fwd_from.from_id.channel_id
                if original_chat_id:
                    original_chat = await self.client.get_entity(original_chat_id)
                    await self.client.send_message(original_chat, comment, reply_to=event.message.id)
                    logger.info(f"[{self.name}] ✅ تم التعليق في القناة الأصلية: {comment}")
                    self.parent.stats['captcha_solved'] += 1
                    return True
            # الرد بشكل طبيعي
            await event.reply(comment)
            logger.info(f"[{self.name}] ✅ تم التعليق: {comment}")
            self.parent.stats['captcha_solved'] += 1
            return True
        except Exception as e:
            logger.error(f"[{self.name}] فشل التعليق: {e}")
            return False

    async def click_participate_button(self, event):
        """الضغط على زر المشاركة (عادة أول زر أو زر يحوي كلمات مفتاحية)"""
        if not event.reply_markup:
            return False
        # محاولة الضغط على أول زر في أول صف (الأكثر شيوعاً)
        try:
            first_btn = event.reply_markup.rows[0].buttons[0]
            # تجنب الأزرار التي قد تكون خطيرة
            if first_btn.text not in ["إلغاء", "Cancel", "لا", "غلق"]:
                await event.click(0, 0)
                logger.info(f"[{self.name}] ✅ تم الضغط على أول زر: {first_btn.text}")
                self.parent.stats['wins'] += 1
                return True
        except:
            pass
        # بحث عن زر يحتوي على كلمات المشاركة
        for row_idx, row in enumerate(event.reply_markup.rows):
            for col_idx, btn in enumerate(row.buttons):
                if any(k in btn.text for k in PARTICIPATE_BUTTONS):
                    try:
                        await event.click(row_idx, col_idx)
                        logger.info(f"[{self.name}] ✅ تم الضغط على زر: {btn.text}")
                        self.parent.stats['wins'] += 1
                        return True
                    except:
                        pass
        return False

    async def extract_and_join_channels(self, text):
        """استخراج أسماء القنوات من النص والانضمام إليها"""
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
                logger.info(f"[{self.name}] ✅ انضم إلى القناة: {username}")
                self.parent.stats['joined_channels'] += 1
            except FloodWaitError as e:
                logger.warning(f"[{self.name}] FloodWait أثناء الانضمام: {e.seconds}s")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"[{self.name}] فشل الانضمام لـ {username}: {e}")
        return len(channels)

    async def handle_forwarded_post(self, event):
        """معالجة المنشورات المُعادة توجيهها - الرد على القناة الأصلية إذا لزم الأمر"""
        # هذا يندرج ضمن reply_comment أعلاه
        pass

    async def process_message(self, event):
        """معالجة الرسالة الرئيسية"""
        if event.id in self.cache:
            return
        text = event.raw_text or ""

        # تجنب المسابقات الخطيرة
        if any(word in text for word in DANGER_WORDS):
            return

        # 1. الانضمام للقنوات الإجبارية
        await self.extract_and_join_channels(text)

        # 2. حل الكابتشا والتفاعل
        if event.reply_markup:
            buttons = [[btn for btn in row.buttons] for row in event.reply_markup.rows]
            
            # محاولة حل مسألة حسابية
            math_pos = await self.solve_math_captcha(text, buttons)
            if math_pos:
                row, col = math_pos
                try:
                    await event.click(row, col)
                    logger.info(f"[{self.name}] 🧠 تم حل الكابتشا الحسابية")
                    self.parent.stats['captcha_solved'] += 1
                    await self.dynamic_delay()
                except Exception as e:
                    logger.error(f"[{self.name}] فشل الضغط على حل المسألة: {e}")
            else:
                # محاولة حل كابتشا إيموجي
                emoji_pos = await self.solve_emoji_captcha(text, buttons)
                if emoji_pos:
                    row, col = emoji_pos
                    try:
                        await event.click(row, col)
                        logger.info(f"[{self.name}] 😀 تم حل كابتشا الإيموجي")
                        self.parent.stats['captcha_solved'] += 1
                        await self.dynamic_delay()
                    except Exception as e:
                        logger.error(f"[{self.name}] فشل الضغط على الإيموجي: {e}")

        # 3. التعليق إذا طلب ذلك
        comment = await self.extract_comment_text(text)
        if comment:
            await self.reply_comment(event, comment)
            await self.dynamic_delay()

        # 4. الضغط على زر المشاركة
        if await self.click_participate_button(event):
            self.cache.add(event.id)
            return

        # 5. إذا لم نضغط على أي زر وجدت أزرار بشكل عام، نضغط على أول زر (بحذر)
        if event.reply_markup and event.id not in self.cache:
            try:
                first_btn = event.reply_markup.rows[0].buttons[0]
                if first_btn.text not in ["إلغاء", "Cancel", "لا"]:
                    await event.click(0, 0)
                    logger.info(f"[{self.name}] ⚠️ ضغط عام على أول زر: {first_btn.text}")
                    self.parent.stats['wins'] += 1
                    self.cache.add(event.id)
            except:
                pass

    async def keep_alive(self):
        """الحفاظ على اتصال الحساب"""
        while self.running:
            try:
                if not self.client.is_connected():
                    await self.client.connect()
                await self.client(UpdateStatusRequest(offline=False))
            except Exception as e:
                logger.error(f"[{self.name}] Keep-alive error: {e}")
            await asyncio.sleep(120)

    async def run(self):
        """تشغيل مستمع الأحداث لهذا الحساب"""
        @self.client.on(events.NewMessage)
        async def handler(event):
            # تجاهل الرسائل من الأدمن (الأوامر تتم معالجتها في الرئيسي)
            if event.sender_id == ADMIN_ID and event.raw_text.startswith("."):
                return
            if event.is_channel or event.is_group:
                await self.process_message(event)
        
        # بدء مهمة البقاء على قيد الحياة
        asyncio.create_task(self.keep_alive())
        logger.info(f"[{self.name}] جاهز ومتصل")
        await self.client.run_until_disconnected()

# ========== الفئة الرئيسية التي تدير الحسابات ==========
class OmegaFlawlessV4:
    def __init__(self):
        self.accounts = []  # قائمة كائنات AccountHandler
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

    async def init_account(self, api_id, api_hash, session_str, name, account_id):
        """تهيئة حساب واحد"""
        if not api_id or not api_hash or not session_str:
            logger.warning(f"بيانات {name} غير مكتملة، تخطي.")
            return None
        client = TelegramClient(StringSession(session_str), api_id, api_hash)
        try:
            await client.connect()
            if not await client.is_user_authorized():
                logger.error(f"{name} غير مصرح به، تخطي.")
                return None
            handler = AccountHandler(client, name, account_id, self)
            self.accounts.append(handler)
            self.clients.append(client)
            if account_id == 1:
                self.main_client = client
            logger.info(f"✅ {name} تمت تهيئته بنجاح")
            return handler
        except Exception as e:
            logger.error(f"فشل تهيئة {name}: {e}")
            return None

    async def start_all(self):
        """بدء تشغيل جميع الحسابات"""
        # تهيئة الحسابات
        await self.init_account(API_ID_1, API_HASH_1, SESSION_1, "الحساب_الأول", 1)
        if API_ID_2 and SESSION_2:
            await self.init_account(API_ID_2, API_HASH_2, SESSION_2, "الحساب_الثاني", 2)
        if API_ID_3 and SESSION_3:
            await self.init_account(API_ID_3, API_HASH_3, SESSION_3, "الحساب_الثالث", 3)

        if not self.accounts:
            logger.critical("لا يوجد أي حساب صالح للتشغيل.")
            return

        # بدء مراقبة VPS (على الحساب الرئيسي فقط)
        if VPS_CHANNEL_ID and self.main_client:
            @self.main_client.on(events.NewMessage(chats=VPS_CHANNEL_ID))
            async def vps_handler(event):
                await self.vps_watcher(event)

        # أوامر الأدمن على الحساب الرئيسي
        if self.main_client:
            @self.main_client.on(events.NewMessage(from_users=ADMIN_ID))
            async def admin_cmd(event):
                if event.raw_text.startswith("."):
                    await self.handle_command(event, event.raw_text.split())

        # تشغيل إحصائيات حية
        asyncio.create_task(self.live_stats())

        # تشغيل جميع الحسابات بشكل متزامن
        tasks = [acc.run() for acc in self.accounts]
        await asyncio.gather(*tasks)

    async def vps_watcher(self, event):
        """استخراج VPS من الرسائل وإرسالها وتغيير كلمة المرور اختيارياً"""
        text = event.raw_text or ""
        ip, user, pwd = self.extract_vps(text)
        if ip and pwd:
            self.stats['vps'] += 1
            msg = f"🔥 **VPS جديد**\n▪️ IP: `{ip}`\n▪️ User: `{user}`\n▪️ Pass: `{pwd}`"
            await self.main_client.send_message(NOTIFY_USER, msg)
            logger.info(f"✅ VPS مُرسَل: {ip}")
            if AUTO_CHANGE_VPS_PASS and SSH_AVAILABLE:
                await self.change_vps_password(ip, user, pwd)

    def extract_vps(self, text):
        """استخراج IP, user, password من النص"""
        ip_match = re.search(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b', text)
        if not ip_match:
            return None, None, None
        ip = ip_match.group(1)
        # محاولة العثور على user و password
        user = "root"
        user_match = re.search(r'(?:User|Username|login)[\s:]*([a-zA-Z0-9_@.-]+)', text, re.I)
        if user_match:
            user = user_match.group(1)
        pwd_match = re.search(r'(?:Password|Pass|New password)[\s:]*([^\s]+)', text, re.I)
        pwd = pwd_match.group(1) if pwd_match else None
        if not pwd:
            # تنسيق خاص: كلمة مرور على سطر منفصل
            pwd_match2 = re.search(r'(?:^|\n)\s*([^\s]+@[^\s]+|[A-Za-z0-9!@#%^&*]+)\s*(?:\n|$)', text, re.MULTILINE)
            if pwd_match2:
                pwd = pwd_match2.group(1)
        return ip, user, pwd

    async def change_vps_password(self, ip, user, old_pass):
        """تغيير كلمة مرور VPS عبر SSH"""
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
                logger.error(f"خطأ في تغيير كلمة مرور {ip}: {err}")
                return
            ssh.close()
            logger.info(f"🔐 تم تغيير كلمة مرور {ip} إلى {new_pass}")
            msg = f"✅ **تم تغيير كلمة مرور VPS**\n🌐 IP: `{ip}`\n👤 User: `{user}`\n🔑 New Pass: `{new_pass}`"
            await self.main_client.send_message(NOTIFY_USER, msg)
        except Exception as e:
            logger.error(f"فشل SSH لـ {ip}: {e}")

    def generate_strong_password(self, length=14):
        chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
        return ''.join(random.choice(chars) for _ in range(length))

    async def live_stats(self):
        """إرسال إحصائيات حية إلى الخاص"""
        msg_id = None
        while self.running:
            uptime = str(timedelta(seconds=int(time.time() - self.stats['start'])))
            msg = (
                f"📊 **Flawless V4**\n"
                f"🕒 {datetime.now():%H:%M:%S}\n"
                f"⏱️ {uptime}\n"
                f"🌐 VPS: {self.stats['vps']}\n"
                f"🏆 فوز: {self.stats['wins']}\n"
                f"📢 انضم: {self.stats['joined_channels']}\n"
                f"🧩 كابتشا: {self.stats['captcha_solved']}\n"
                f"🚪 مغادرة: {self.stats['left']}\n"
                f"👥 حسابات: {len(self.accounts)}"
            )
            if self.main_client:
                try:
                    if msg_id:
                        await self.main_client.edit_message('me', msg_id, msg)
                    else:
                        sent = await self.main_client.send_message('me', msg)
                        msg_id = sent.id
                except:
                    pass
            await asyncio.sleep(5)

    async def handle_command(self, event, parts):
        """أوامر التحكم"""
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
            await event.reply("📊 الإحصائيات في الخاص")
        else:
            await event.reply("أوامر متاحة: .start | .stop | .stats")

    async def run(self):
        """تشغيل النظام بالكامل"""
        logger.info("🚀 بدء تشغيل Omega Flawless V4 ...")
        await self.start_all()

if __name__ == "__main__":
    v4 = OmegaFlawlessV4()
    asyncio.run(v4.run())
