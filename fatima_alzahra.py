#!/usr/bin/env python3
"""
███████████████████████████████████████████████████████████████████████████████
Omega Flawless v3 – صائد الـ VPS والروليت المتكامل
- حل جميع أنواع الكابتشا (حسابي، إيموجي، تعليق)
- انضمام إجباري للقنوات المطلوبة
- تفاعل مع أزرار المشاركة والتدوير
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
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.account import UpdateStatusRequest
from telethon.errors import (
    FloodWaitError, UserBannedInChannelError, UserChannelsTooMuchError,
    ChannelsTooMuchError, AuthKeyDuplicatedError
)

# تثبيت paramiko إذا لم يكن موجوداً
try:
    import paramiko
    from paramiko import SSHClient, AutoAddPolicy
    SSH_AVAILABLE = True
except ImportError:
    SSH_AVAILABLE = False
    logging.warning("⚠️ paramiko غير مثبت. لن يتم تغيير كلمات مرور VPS تلقائياً.")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('flawless_v3.log'), logging.StreamHandler()]
)
logger = logging.getLogger("FlawlessV3")

# ========== إعدادات البيئة ==========
API_ID_1 = int(os.environ["API_ID_1"])
API_HASH_1 = os.environ["API_HASH_1"]
SESSION_1 = os.environ["SESSION_1"]

API_ID_2 = int(os.environ.get("API_ID_2", 0))
API_HASH_2 = os.environ.get("API_HASH_2", "")
SESSION_2 = os.environ.get("SESSION_2", "")

ADMIN_ID = int(os.environ["ADMIN_ID"])
NOTIFY_USER = os.environ.get("NOTIFY_USER", "me")
VPS_CHANNEL_ID = int(os.environ.get("VPS_CHANNEL_ID", 0))

# كلمات مفتاحية للأزرار التي يجب الضغط عليها
HUNT_BUTTONS = [
    "مشاركة", "انضمام", "سحب", "تدوير", "دخول", "تأكيد", "اضغط هنا",
    "المشاركة", "اشترك", "join", "participate", "spin"
]

# كلمات تدل على مسابقات خطيرة (نتجنبها)
DANGER_WORDS = ["أكثر نجوم", "من يضع", "تصويت بنجوم", "اكثر شخص يحط", "يحط يربح", "مزاد نجوم"]

# أنماط المسائل الحسابية
MATH_PATTERNS = [
    r'(\d+)\s*\+\s*(\d+)',           # 5 + 8
    r'(\d+)\s*\-\s*(\d+)',           # 10 - 3
    r'(\d+)\s*\*\s*(\d+)',           # 2 * 4
    r'(\d+)\s*\/\s*(\d+)',           # 8 / 2
    r'ناتج\s*:\s*(\d+)\s*\+\s*(\d+)' # ناتج: 5 + 8
]

# أنماط طلب التعليق
COMMENT_PATTERNS = [
    r'هل يستحق\s*(.*?)\?',
    r'اكتب\s*"([^"]+)"',
    r'علق\s*بـ\s*([^\s]+)'
]

# ========== الفئة الرئيسية ==========
class OmegaFlawlessV3:
    def __init__(self):
        self.c1 = TelegramClient(StringSession(SESSION_1), API_ID_1, API_HASH_1)
        self.c2 = TelegramClient(StringSession(SESSION_2), API_ID_2, API_HASH_2) if SESSION_2 else None
        self.running = True
        self.stats = {"vps": 0, "wins": 0, "left": 0, "captcha_solved": 0, "start": time.time()}
        self.cache = set()  # لتجنب معالجة نفس الرسالة مرتين
        self.speed = self.load_speed()
        self.join_queue = asyncio.Queue()
        self.main_client = None
        self.ssh_clients = {}  # لتخزين جلسات SSH النشطة

    # ---------- إدارة التأخير الديناميكي ----------
    def load_speed(self):
        try:
            with open(SPEED_FILE := "flawless_speed.json", 'r') as f:
                return json.load(f)
        except:
            return {"delay": 60, "fails": 0}

    def save_speed(self):
        with open("flawless_speed.json", 'w') as f:
            json.dump(self.speed, f, indent=2)

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

    # ---------- الاتصال والحفاظ على النشاط ----------
    async def connect(self, client, name):
        for _ in range(3):
            try:
                await client.connect()
                if await client.is_user_authorized():
                    logger.info(f"✅ {name} متصل")
                    return True
            except AuthKeyDuplicatedError:
                logger.critical(f"🔑 {name} جلسة مكررة! قم بتغيير SESSION.")
                break
            except Exception as e:
                logger.error(f"❌ {name}: {e}")
            await asyncio.sleep(10)
        return False

    async def keep_alive(self, client, name):
        while self.running:
            try:
                if not client.is_connected():
                    await client.connect()
                await client(UpdateStatusRequest(offline=False))
            except Exception as e:
                logger.error(f"KeepAlive {name}: {e}")
            await asyncio.sleep(120)

    # ---------- إحصائيات حية ----------
    async def live_stats(self):
        global STATS_MSG_ID
        STATS_MSG_ID = None
        while self.running:
            if self.main_client:
                uptime = str(timedelta(seconds=int(time.time() - self.stats['start'])))
                msg = (
                    f"📊 **Flawless V3**\n"
                    f"🕒 {datetime.now():%H:%M:%S}\n"
                    f"⏱️ {uptime}\n"
                    f"🌐 VPS: {self.stats['vps']}\n"
                    f"🏆 روليت: {self.stats['wins']}\n"
                    f"🧩 كابتشا: {self.stats['captcha_solved']}\n"
                    f"🚪 مغادرة: {self.stats['left']}\n"
                    f"🐌 تأخير: {self.speed['delay']}s"
                )
                try:
                    if STATS_MSG_ID:
                        await self.main_client.edit_message('me', STATS_MSG_ID, msg)
                    else:
                        sent = await self.main_client.send_message('me', msg)
                        STATS_MSG_ID = sent.id
                except:
                    pass
            await asyncio.sleep(5)

    # ========== وظائف الكابتشا والتفاعل المتقدم ==========
    async def solve_math_captcha(self, text, buttons):
        """
        يبحث عن مسألة حسابية في النص ويحسب الناتج، ثم يبحث عن زر يحمل نفس الرقم.
        يعيد الزر (row, col) إذا وجد، وإلا None.
        """
        for pattern in MATH_PATTERNS:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    try:
                        a, b = int(groups[0]), int(groups[1])
                        # تحديد العملية من النص
                        if '+' in match.group(0):
                            result = a + b
                        elif '-' in match.group(0):
                            result = a - b
                        elif '*' in match.group(0):
                            result = a * b
                        elif '/' in match.group(0):
                            result = a // b if b != 0 else 0
                        else:
                            result = a + b  # افتراضي جمع
                        logger.info(f"🧮 حل مسألة: {a} ? {b} = {result}")
                        # البحث عن زر بنفس الرقم
                        for row_idx, row in enumerate(buttons):
                            for col_idx, btn in enumerate(row):
                                if btn.text.strip() == str(result):
                                    return row_idx, col_idx
                    except:
                        pass
        return None

    async def solve_emoji_captcha(self, text, buttons):
        """
        يبحث عن جملة مثل "اضغط على الزر اللي يشبه هذا الإيموجي ✅"
        ثم يبحث عن زر يحتوي على نفس الإيموجي.
        """
        emoji_pattern = r'يشبه هذا الإيموجي\s*([\U00010000-\U0010FFFF])'
        match = re.search(emoji_pattern, text)
        if match:
            target_emoji = match.group(1)
            logger.info(f"😀 إيموجي مطلوب: {target_emoji}")
            for row_idx, row in enumerate(buttons):
                for col_idx, btn in enumerate(row):
                    if target_emoji in btn.text:
                        return row_idx, col_idx
        return None

    async def extract_comment_text(self, text):
        """
        يستخرج النص المطلوب للتعليق (مثل "يستحق" أو "لا يستحق")
        """
        for pattern in COMMENT_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                comment = match.group(1).strip()
                # تنظيف الاقتباسات
                comment = comment.strip('"\'')
                logger.info(f"📝 نص التعليق المطلوب: {comment}")
                return comment
        # إذا كان السؤال "هل يستحق؟" بدون نص محدد، نرد بـ "يستحق"
        if re.search(r'هل يستحق', text, re.IGNORECASE):
            return "يستحق"
        return None

    async def reply_comment(self, event, comment):
        """
        يرد على الرسالة بالتعليق المطلوب
        """
        try:
            await event.reply(comment)
            logger.info(f"✅ تم التعليق: {comment}")
            self.stats['captcha_solved'] += 1
            return True
        except Exception as e:
            logger.error(f"فشل التعليق: {e}")
            return False

    async def click_button_by_text(self, event, keywords):
        """
        يضغط على أول زر يحتوي على أي من الكلمات المفتاحية
        """
        if not event.reply_markup:
            return False
        for row_idx, row in enumerate(event.reply_markup.rows):
            for col_idx, btn in enumerate(row.buttons):
                if any(k in btn.text for k in keywords):
                    try:
                        await event.click(row_idx, col_idx)
                        logger.info(f"✅ تم الضغط على زر: {btn.text}")
                        self.stats['wins'] += 1
                        await self.success_action()
                        return True
                    except FloodWaitError as e:
                        await self.handle_flood(e)
                    except Exception as e:
                        logger.error(f"خطأ في الضغط: {e}")
        return False

    async def join_required_channels(self, text, client):
        """
        يستخرج أسماء القنوات من النص (مثل @channel) وينضم إليها عبر الطابور
        """
        # أنماط مختلفة للقنوات
        patterns = [
            r'(?:@|t\.me/)([a-zA-Z0-9_]+)',          # @username
            r'الاشتراك في\s*([@a-zA-Z0-9_]+)',       # الاشتراك في @channel
            r'قنوات التالية:\s*(?:[0-9]+\.\s*)?(@[a-zA-Z0-9_]+)',  # 1. @channel
        ]
        channels = set()
        for pat in patterns:
            matches = re.findall(pat, text)
            for m in matches:
                username = m.strip('@')
                if username and username.lower() not in ['bot', 'c', 'me', 'telegram']:
                    channels.add(username)

        for username in channels:
            try:
                entity = await client.get_entity(username)
                await self.join_queue.put(entity.id)
                logger.info(f"📢 أضيفت القناة {username} إلى طابور الانضمام")
            except Exception as e:
                logger.warning(f"فشل الحصول على كيان {username}: {e}")
        return len(channels)

    # ========== معالجة رسائل الروليت الشاملة ==========
    async def process_roulette(self, event, client):
        if event.id in self.cache:
            return
        text = event.raw_text or ""

        # تجنب المسابقات الخطيرة
        if any(w in text for w in DANGER_WORDS):
            return

        # 1. الانضمام للقنوات المطلوبة
        await self.join_required_channels(text, client)

        # 2. حل الكابتشا الحسابية أو الإيموجي أولاً (قبل الضغط على أزرار المشاركة)
        if event.reply_markup:
            buttons = [[btn for btn in row.buttons] for row in event.reply_markup.rows]
            # محاولة حل مسألة حسابية
            math_pos = await self.solve_math_captcha(text, buttons)
            if math_pos:
                row, col = math_pos
                try:
                    await event.click(row, col)
                    logger.info("🧠 تم حل الكابتشا الحسابية")
                    self.stats['captcha_solved'] += 1
                    await self.success_action()
                    # بعد حل الكابتشا، قد نحتاج للانتظار قليلاً ثم الضغط على زر المشاركة
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"فشل الضغط على حل المسألة: {e}")
            else:
                # محاولة حل كابتشا الإيموجي
                emoji_pos = await self.solve_emoji_captcha(text, buttons)
                if emoji_pos:
                    row, col = emoji_pos
                    try:
                        await event.click(row, col)
                        logger.info("😀 تم حل كابتشا الإيموجي")
                        self.stats['captcha_solved'] += 1
                        await self.success_action()
                        await asyncio.sleep(1)
                    except Exception as e:
                        logger.error(f"فشل الضغط على الإيموجي: {e}")

        # 3. التعليق إذا طلب ذلك
        comment_text = await self.extract_comment_text(text)
        if comment_text:
            await self.reply_comment(event, comment_text)
            await self.dynamic_delay()

        # 4. الضغط على أزرار المشاركة والانضمام
        if await self.click_button_by_text(event, HUNT_BUTTONS):
            self.cache.add(event.id)
            return

        # 5. إذا لم نضغط على أي زر، نجرب الضغط على أول زر بشكل عام (لكن بحذر)
        if event.reply_markup and not self.cache:
            try:
                # نتفادى الأزرار التي قد تكون خطيرة مثل "إلغاء"
                first_btn = event.reply_markup.rows[0].buttons[0]
                if first_btn.text not in ["إلغاء", "Cancel", "لا", "غلق"]:
                    await event.click(0, 0)
                    logger.info(f"⚠️ ضغط عام على أول زر: {first_btn.text}")
                    self.stats['wins'] += 1
                    self.cache.add(event.id)
            except:
                pass

    # ========== معالجة الـ VPS وتغيير كلمة المرور ==========
    def extract_vps(self, text):
        """
        استخراج IP, user, password من النص بأكبر عدد من التنسيقات
        """
        ip = user = pwd = None

        # تنسيق IP: أي أربع أرقام بين 0-255
        ip_match = re.search(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b', text)
        if ip_match:
            ip = ip_match.group(1)
            # محاولة العثور على user و password في نفس النص
            user_match = re.search(r'(?:User|Username|login)[\s:]*([a-zA-Z0-9_@.-]+)', text, re.I)
            if user_match:
                user = user_match.group(1)
            else:
                user = "root"  # الافتراضي
            pwd_match = re.search(r'(?:Password|Pass|New password)[\s:]*([^\s]+)', text, re.I)
            if pwd_match:
                pwd = pwd_match.group(1)
            # تنسيق خاص: "37.60.235.208" في سطر و"ACON@VPS" في سطر آخر
            if not pwd:
                pwd_match2 = re.search(r'(?:^|\n)\s*([^\s]+@[^\s]+)\s*(?:\n|$)', text, re.MULTILINE)
                if pwd_match2:
                    pwd = pwd_match2.group(1)
        return ip, user, pwd

    async def change_vps_password(self, ip, user, old_pass, new_pass=None):
        """
        تغيير كلمة مرور VPS عبر SSH.
        يتطلب توفر مكتبة paramiko.
        """
        if not SSH_AVAILABLE:
            logger.warning("paramiko غير مثبت، لا يمكن تغيير كلمة المرور.")
            return False
        if not new_pass:
            new_pass = self.generate_strong_password()
        try:
            ssh = SSHClient()
            ssh.set_missing_host_key_policy(AutoAddPolicy())
            ssh.connect(ip, username=user, password=old_pass, timeout=10)
            # تغيير كلمة المرور (للـ root أو المستخدم)
            command = f'echo "{user}:{new_pass}" | chpasswd'
            stdin, stdout, stderr = ssh.exec_command(command)
            err = stderr.read().decode()
            if err:
                logger.error(f"خطأ في تغيير كلمة مرور {ip}: {err}")
                return False
            ssh.close()
            logger.info(f"🔐 تم تغيير كلمة مرور {ip} إلى {new_pass}")
            # إرسال التفاصيل الجديدة
            msg = f"✅ **تم تغيير كلمة مرور VPS**\n🌐 IP: `{ip}`\n👤 User: `{user}`\n🔑 New Pass: `{new_pass}`"
            await self.main_client.send_message(NOTIFY_USER, msg)
            return True
        except Exception as e:
            logger.error(f"فشل SSH لـ {ip}: {e}")
            return False

    def generate_strong_password(self, length=14):
        chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
        return ''.join(random.choice(chars) for _ in range(length))

    async def vps_watcher(self, event):
        text = event.raw_text or ""
        ip, user, pwd = self.extract_vps(text)
        if ip and pwd:
            self.stats['vps'] += 1
            # إرسال VPS كما هو
            msg = f"🔥 **VPS جديد**\n▪️ IP: `{ip}`\n▪️ User: `{user}`\n▪️ Pass: `{pwd}`"
            await self.main_client.send_message(NOTIFY_USER, msg)
            logger.info(f"✅ VPS مُرسَل: {ip}")
            # تغيير كلمة المرور تلقائياً (اختياري، يمكن تعطيله)
            if os.environ.get("AUTO_CHANGE_VPS_PASS", "false").lower() == "true":
                await self.change_vps_password(ip, user, pwd)

    # ========== طابور الانضمام ==========
    async def join_worker(self):
        while self.running:
            channel_id = await self.join_queue.get()
            try:
                await self.dynamic_delay()
                await self.c1(JoinChannelRequest(channel_id))
                await self.success_action()
                logger.info(f"✅ انضم إلى القناة {channel_id}")
            except (UserChannelsTooMuchError, ChannelsTooMuchError):
                logger.warning("⚠️ الحساب ممتلئ، مغادرة أقدم 5 قنوات")
                await self.leave_oldest(5)
                await asyncio.sleep(10)
                try:
                    await self.c1(JoinChannelRequest(channel_id))
                except:
                    pass
            except FloodWaitError as e:
                await self.handle_flood(e)
            except Exception as e:
                logger.error(f"فشل الانضمام {channel_id}: {e}")
            self.join_queue.task_done()

    async def leave_oldest(self, count=5):
        dialogs = await self.c1.get_dialogs()
        channels = [d for d in dialogs if d.is_channel]
        channels.sort(key=lambda d: d.date or datetime.min)
        for d in channels[:count]:
            try:
                await self.c1(LeaveChannelRequest(d.entity))
                self.stats['left'] += 1
                await asyncio.sleep(2)
            except:
                pass

    #    # ========== أوامر التحكم ==========
    async def handle_command(self, event, parts):
        cmd = parts[0][1:].lower()
        if cmd == "stop":
            self.running = False
            await event.reply("🛑 تم إيقاف البوت")
        elif cmd == "start":
            self.running = True
            await event.reply("✅ تم تشغيل البوت")
        elif cmd == "stats":
            await event.reply("📊 الإحصائيات تُعرض في الخاص")
        elif cmd == "panel":
            await event.respond("🔥 **لوحة تحكم Flawless V3**", buttons=[
                [Button.inline("📊 إحصائيات", b"stats"), Button.inline("🔐 تغيير كلمة VPS", b"change_vps")]
            ])
        elif cmd.startswith("vpspass"):
            # تغيير كلمة مرور VPS يدوياً: .vpspass IP user old new
            if len(parts) >= 5:
                ip, user, old, new = parts[1], parts[2], parts[3], parts[4]
                await self.change_vps_password(ip, user, old, new)
            else:
                await event.reply("الاستخدام: .vpspass IP user old_pass new_pass")

    # ========== التشغيل الرئيسي ==========
    async def main(self):
        if not await self.connect(self.c1, "الحساب الرئيسي"):
            logger.critical("لا يمكن الاتصال بالحساب الرئيسي")
            return
        self.main_client = self.c1

        if self.c2 and not await self.connect(self.c2, "الحساب الثانوي"):
            self.c2 = None
            logger.warning("الحساب الثانوي لم يتصل، سيتم العمل بحساب واحد.")

        # مراقبة قنوات VPS
        if VPS_CHANNEL_ID:
            @self.c1.on(events.NewMessage(chats=VPS_CHANNEL_ID))
            async def vps_handler(event):
                await self.vps_watcher(event)
        else:
            logger.info("لم يتم تعيين VPS_CHANNEL_ID، لن يتم مراقبة الـ VPS.")

        # معالجة الرسائل العامة للحساب الرئيسي
        @self.c1.on(events.NewMessage())
        async def main_handler(event):
            # أوامر الأدمن
            if event.sender_id == ADMIN_ID and event.raw_text.startswith("."):
                await self.handle_command(event, event.raw_text.split())
            # معالجة الروليت في القنوات والمجموعات
            elif event.is_channel or event.is_group:
                await self.process_roulette(event, self.c1)

        # معالجة الحساب الثانوي
        if self.c2:
            @self.c2.on(events.NewMessage())
            async def secondary_handler(event):
                if event.is_channel or event.is_group:
                    await self.process_roulette(event, self.c2)

        # معالجة الاستعلامات (callback queries)
        @self.c1.on(events.CallbackQuery)
        async def callback_handler(event):
            data = event.data.decode()
            if data == "stats":
                await event.answer(f"VPS: {self.stats['vps']}, Wins: {self.stats['wins']}", alert=True)
            elif data == "change_vps":
                await event.answer("أرسل .vpspass IP user old_pass new_pass", alert=True)

        # تشغيل المهام الخلفية
        asyncio.create_task(self.join_worker())
        asyncio.create_task(self.keep_alive(self.c1, "ح1"))
        if self.c2:
            asyncio.create_task(self.keep_alive(self.c2, "ح2"))
        asyncio.create_task(self.live_stats())

        # تنظيف دوري كل 12 ساعة
        async def periodic_clean():
            while self.running:
                await asyncio.sleep(43200)  # 12 ساعة
                left = 0
                async for dialog in self.c1.iter_dialogs():
                    if dialog.is_channel:
                        try:
                            # مغادرة القنوات غير النشطة (آخر رسالة أقدم من 7 أيام)
                            if dialog.date and (datetime.now().astimezone() - dialog.date).days > 7:
                                await self.c1(LeaveChannelRequest(dialog.entity))
                                left += 1
                                await asyncio.sleep(1)
                        except:
                            pass
                self.stats['left'] += left
                logger.info(f"تنظيف: غادر {left} قناة")
        asyncio.create_task(periodic_clean())

        await self.c1(UpdateStatusRequest(offline=False))
        logger.info("🚀 Omega Flawless V3 يعمل بكامل طاقته - جاهز للكابتشا والـ VPS")
        await self.c1.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(OmegaFlawlessV3().main())
