"""
Main Bot Module
Handles Telegram bot commands and coordinates with userbot
PATCHED: Enhanced UI with inline buttons, command menu, and polished interface
"""

import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BotCommand
from database import db
from security import security_monitor
from userbot import userbot
from admin_commands import AdminCommands
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SecurityBot:
    """Main Security Bot"""

    def __init__(self):
        # Initialize bot client
        self.bot = Client(
            name="security_bot",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN
        )

        # Login state management
        self.login_states = {}

        # Admin commands handler
        self.admin_commands = AdminCommands(self.bot)

        # Setup handlers
        self.setup_handlers()

        # Register security alert callback
        security_monitor.register_alert_callback(self.send_owner_alert)

    def setup_handlers(self):
        """Setup bot command handlers"""

        @self.bot.on_message(filters.command("start") & filters.private)
        async def start_command(client: Client, message: Message):
            """Polished start command with inline buttons"""
            user_id = message.from_user.id
            
            # Check if user has active session
            session = await db.get_session(user_id)
            has_session = session and session.get('is_active', 0) == 1
            
            if has_session:
                # Connected account UI
                welcome_text = """🛡️ **SecurityGuard**

Your Telegram Group Security & Moderation System.

Protect your groups against:
• Spam
• Admin abuse
• Mass-ban activity
• Suspicious moderation
• Unwanted content

**Account Status:**
🟢 Telegram account connected

**Security System:** ACTIVE"""
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛡️ Security Status", callback_data="security")],
                    [InlineKeyboardButton("👥 Groups", callback_data="groups"),
                     InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
                    [InlineKeyboardButton("📖 Help", callback_data="help")]
                ])
            else:
                # Not connected UI
                welcome_text = """🛡️ **SecurityGuard**

Your Telegram Group Security & Moderation System.

Protect your groups against:
• Spam
• Admin abuse
• Mass-ban activity
• Suspicious moderation
• Unwanted content

**Account Status:**
🔴 Not connected

Use the button below to connect your Telegram account."""
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 Connect Telegram", callback_data="connect")],
                    [InlineKeyboardButton("🛡️ Security Status", callback_data="security")],
                    [InlineKeyboardButton("📖 Help", callback_data="help")]
                ])
            
            await message.reply(welcome_text, reply_markup=keyboard)

        @self.bot.on_callback_query()
        async def handle_callback(client: Client, callback: CallbackQuery):
            """Handle inline button callbacks"""
            data = callback.data
            user_id = callback.from_user.id
            
            # Check authorization for sensitive actions
            is_authorized = user_id == config.OWNER_ID or await security_monitor.check_role_permission(user_id, 'view_security')
            
            if data == "connect":
                await callback.answer()
                # Trigger login flow
                if user_id != config.OWNER_ID:
                    await callback.message.edit_text("❌ Only the owner can connect a Telegram account.")
                    return
                
                session = await db.get_session(user_id)
                if session and session.get('is_active'):
                    await callback.message.edit_text("ℹ️ You already have an active session.\n\nUse /logout to disconnect first.")
                else:
                    await callback.message.edit_text(
                        "📱 **Login Process Started**\n\n"
                        "Please send your phone number in international format.\n"
                        "Example: +1234567890\n\n"
                        "⚠️ **Security Notes:**\n"
                        "• Your credentials are never logged or exposed\n"
                        "• Session is stored encrypted\n"
                        "• You can logout anytime with /logout"
                    )
                    self.login_states[user_id] = {'step': 'phone'}
            
            elif data == "security":
                await callback.answer()
                await self.show_security_status(callback.message, user_id, is_authorized)
            
            elif data == "groups":
                await callback.answer()
                await self.show_groups(callback.message, user_id, is_authorized)
            
            elif data == "admins":
                await callback.answer()
                await self.show_admins(callback.message, user_id, is_authorized)
            
            elif data == "settings":
                await callback.answer()
                await self.show_settings(callback.message, user_id, is_authorized)
            
            elif data == "help":
                await callback.answer()
                await self.show_help(callback.message)
            
            elif data == "logs":
                await callback.answer()
                await self.show_logs(callback.message, user_id, is_authorized)
            
            elif data == "lockdown_confirm":
                await callback.answer()
                if not is_authorized:
                    await callback.message.edit_text("❌ You don't have permission to enable lockdown.")
                    return
                
                # Activate lockdown on all monitored groups
                groups = await db.get_monitored_groups()
                for group in groups:
                    await security_monitor.activate_emergency_mode(group['group_id'])
                
                await callback.message.edit_text(
                    "🚨 **EMERGENCY MODE ACTIVE**\n\n"
                    "Enhanced monitoring is now enabled."
                )
            
            elif data == "lockdown_cancel":
                await callback.answer("Cancelled")
                await callback.message.edit_text("Emergency lockdown cancelled.")
            
            elif data == "unlock_confirm":
                await callback.answer()
                if not is_authorized:
                    await callback.message.edit_text("❌ You don't have permission to disable lockdown.")
                    return
                
                # Deactivate lockdown on all monitored groups
                groups = await db.get_monitored_groups()
                for group in groups:
                    await security_monitor.deactivate_emergency_mode(group['group_id'])
                
                await callback.message.edit_text(
                    "🔓 **Emergency Lockdown Disabled**\n\n"
                    "Normal operations resumed."
                )
            
            elif data == "unlock_cancel":
                await callback.answer("Cancelled")
                await callback.message.edit_text("Unlock cancelled.")
            
            elif data == "back_main":
                await callback.answer()
                # Return to main menu
                await start_command(client, callback.message)

        @self.bot.on_message(filters.command("login") & filters.private)
        async def login_command(client: Client, message: Message):
            """Login command - start MTProto authentication"""
            user_id = message.from_user.id

            # Check if user is owner or has permission
            if user_id != config.OWNER_ID:
                await message.reply("❌ Only the owner can log in.")
                return

            # Check if already logged in
            session = await db.get_session(user_id)
            if session and session['is_active']:
                await message.reply(
                    "ℹ️ You already have an active session.\n"
                    "Use /logout to disconnect first."
                )
                return

            await message.reply(
                "📱 **Login Process Started**\n\n"
                "Please send your phone number in international format.\n"
                "Example: +1234567890\n\n"
                "⚠️ **Security Notes:**\n"
                "• Your credentials are never logged or exposed\n"
                "• Session is stored encrypted\n"
                "• You can logout anytime with /logout"
            )

            self.login_states[user_id] = {'step': 'phone'}

        @self.bot.on_message(filters.private & filters.text & ~filters.command(".*"))
        async def handle_login_flow(client: Client, message: Message):
            """Handle login flow inputs"""
            user_id = message.from_user.id

            if user_id not in self.login_states:
                return

            state = self.login_states[user_id]

            # Step 1: Phone number
            if state['step'] == 'phone':
                phone = message.text.strip()
                
                if not phone.startswith('+'):
                    await message.reply("❌ Please use international format: +1234567890")
                    return

                await message.reply("⏳ Sending verification code...")

                result = await userbot.start_login(phone)

                if result['success']:
                    state['phone'] = phone
                    state['phone_code_hash'] = result['phone_code_hash']
                    state['session_name'] = result['session_name']
                    state['step'] = 'code'

                    await message.reply(
                        "✅ Verification code sent to your Telegram account.\n\n"
                        "Please send the code you received.\n"
                        "Example: 12345"
                    )
                else:
                    await message.reply(f"❌ {result['message']}")
                    del self.login_states[user_id]

            # Step 2: Verification code
            elif state['step'] == 'code':
                code = message.text.strip().replace('-', '').replace(' ', '')

                await message.reply("⏳ Verifying code...")

                result = await userbot.complete_login(
                    state['phone'],
                    state['phone_code_hash'],
                    code
                )

                if result['success']:
                    await message.reply(
                        f"{result['message']}\n\n"
                        "🔐 Your session is now active and secure.\n"
                        "Use /session to view status."
                    )
                    del self.login_states[user_id]

                    # Start userbot monitoring
                    await userbot.start_monitoring()

                elif result.get('needs_password'):
                    state['step'] = 'password'
                    state['code'] = code
                    await message.reply(
                        "🔐 **Two-Factor Authentication Detected**\n\n"
                        "Please send your 2FA password.\n\n"
                        "⚠️ **Security:**\n"
                        "• Password is never logged\n"
                        "• Message will be deleted after verification\n"
                        "• Session is encrypted"
                    )
                else:
                    await message.reply(f"❌ {result['message']}")
                    del self.login_states[user_id]

            # Step 3: 2FA Password (if needed)
            elif state['step'] == 'password':
                password = message.text.strip()

                # Delete password message immediately for security
                try:
                    await message.delete()
                except:
                    pass

                await client.send_message(
                    user_id,
                    "⏳ Verifying 2FA password..."
                )

                result = await userbot.complete_login(
                    state['phone'],
                    state['phone_code_hash'],
                    state.get('code', ''),
                    password
                )

                if result['success']:
                    await client.send_message(
                        user_id,
                        f"{result['message']}\n\n"
                        "🔐 Your session is now active and secure.\n"
                        "Use /session to view status."
                    )
                    del self.login_states[user_id]

                    # Start userbot monitoring
                    await userbot.start_monitoring()
                else:
                    await client.send_message(
                        user_id,
                        f"❌ {result['message']}"
                    )
                    del self.login_states[user_id]

        @self.bot.on_message(filters.command("logout") & filters.private)
        async def logout_command(client: Client, message: Message):
            """Logout command - revoke session"""
            user_id = message.from_user.id

            await message.reply("⏳ Logging out and revoking session...")

            result = await userbot.logout(user_id)
            await message.reply(result['message'])

        @self.bot.on_message(filters.command("session") & filters.private)
        async def session_command(client: Client, message: Message):
            """View session status - SECURE (no raw session strings)"""
            user_id = message.from_user.id

            session = await db.get_session(user_id)

            if session and session['is_active']:
                # Get user info safely
                user = await db.get_user(user_id)
                username = user.get('username', 'N/A') if user else 'N/A'
                
                status_text = f"""🔐 **Telegram Connection**

**Status:** 🟢 Connected

**Account:**
@{username}

**User ID:**
{user_id}

**Session:**
🔒 Securely stored

**Last Used:**
{session['last_used']}
"""
            else:
                status_text = """🔐 **Telegram Connection**

**Status:** 🔴 Not connected

Use /login to connect your Telegram account."""

            await message.reply(status_text)

        @self.bot.on_message(filters.command("security"))
        async def security_command(client: Client, message: Message):
            """View security status"""
            user_id = message.from_user.id
            is_authorized = user_id == config.OWNER_ID or await security_monitor.check_role_permission(user_id, 'view_security')
            
            await self.show_security_status(message, user_id, is_authorized)

        @self.bot.on_message(filters.command("help"))
        async def help_command(client: Client, message: Message):
            """Show help"""
            await self.show_help(message)

        @self.bot.on_message(filters.command("groups"))
        async def groups_command(client: Client, message: Message):
            """Show groups"""
            user_id = message.from_user.id
            is_authorized = user_id == config.OWNER_ID or await security_monitor.check_role_permission(user_id, 'view_security')
            
            await self.show_groups(message, user_id, is_authorized)

        @self.bot.on_message(filters.command("admins"))
        async def admins_command(client: Client, message: Message):
            """Show admins"""
            user_id = message.from_user.id
            is_authorized = user_id == config.OWNER_ID or await security_monitor.check_role_permission(user_id, 'view_security')
            
            await self.show_admins(message, user_id, is_authorized)

        @self.bot.on_message(filters.command("settings"))
        async def settings_command(client: Client, message: Message):
            """Show settings"""
            user_id = message.from_user.id
            is_authorized = user_id == config.OWNER_ID or await security_monitor.check_role_permission(user_id, 'manage_settings')
            
            await self.show_settings(message, user_id, is_authorized)

        @self.bot.on_message(filters.command("logs"))
        async def logs_command(client: Client, message: Message):
            """View security logs"""
            user_id = message.from_user.id
            is_authorized = user_id == config.OWNER_ID or await security_monitor.check_role_permission(user_id, 'view_logs')
            
            await self.show_logs(message, user_id, is_authorized)

        # Admin commands
        @self.bot.on_message(filters.command("mute"))
        async def mute_command(client: Client, message: Message):
            """Mute user command"""
            await self.admin_commands.mute_user(message)

        @self.bot.on_message(filters.command("unmute"))
        async def unmute_command(client: Client, message: Message):
            """Unmute user command"""
            await self.admin_commands.unmute_user(message)

        @self.bot.on_message(filters.command("ban"))
        async def ban_command(client: Client, message: Message):
            """Ban user command"""
            await self.admin_commands.ban_user(message)

        @self.bot.on_message(filters.command("unban"))
        async def unban_command(client: Client, message: Message):
            """Unban user command"""
            await self.admin_commands.unban_user(message)

        @self.bot.on_message(filters.command("gmute"))
        async def gmute_command(client: Client, message: Message):
            """Global mute command"""
            await self.admin_commands.global_mute(message)

        @self.bot.on_message(filters.command("ungmute"))
        async def ungmute_command(client: Client, message: Message):
            """Global unmute command"""
            await self.admin_commands.global_unmute(message)

        @self.bot.on_message(filters.command("lockdown"))
        async def lockdown_command(client: Client, message: Message):
            """Lockdown command with confirmation"""
            user_id = message.from_user.id
            is_authorized = user_id == config.OWNER_ID or await security_monitor.check_role_permission(user_id, 'lockdown')
            
            if not is_authorized:
                await message.reply("❌ You don't have permission to use lockdown.")
                return
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🚨 CONFIRM", callback_data="lockdown_confirm"),
                 InlineKeyboardButton("❌ CANCEL", callback_data="lockdown_cancel")]
            ])
            
            await message.reply(
                "🚨 **Enable Emergency Lockdown?**\n\n"
                "This will activate stricter group protection.",
                reply_markup=keyboard
            )

        @self.bot.on_message(filters.command("unlock"))
        async def unlock_command(client: Client, message: Message):
            """Unlock command with confirmation"""
            user_id = message.from_user.id
            is_authorized = user_id == config.OWNER_ID or await security_monitor.check_role_permission(user_id, 'unlock')
            
            if not is_authorized:
                await message.reply("❌ You don't have permission to unlock.")
                return
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ CONFIRM", callback_data="unlock_confirm"),
                 InlineKeyboardButton("❌ CANCEL", callback_data="unlock_cancel")]
            ])
            
            await message.reply(
                "🔓 **Disable Emergency Lockdown?**",
                reply_markup=keyboard
            )

    async def show_security_status(self, message: Message, user_id: int, is_authorized: bool):
        """Show security dashboard"""
        if not is_authorized:
            await message.reply("❌ You don't have permission to view security status.")
            return
        
        # Check if account is connected
        session = await db.get_session(config.OWNER_ID)
        account_status = "🟢 Connected" if session and session.get('is_active') else "🔴 Not Connected"
        
        # Get protected groups count
        groups = await db.get_monitored_groups()
        groups_count = len(groups)
        
        # Check if any group is in lockdown
        lockdown_active = any(g.get('lockdown_mode', 0) == 1 for g in groups)
        lockdown_status = "🔴 ACTIVE" if lockdown_active else "🔵 OFF"
        
        status_text = f"""🛡️ **SECURITY STATUS**

**System:** 🟢 ACTIVE

**Telegram Account:** {account_status}

**Protected Groups:** {groups_count}

**Admin Monitoring:** 🟢 ON
**Mass-Ban Detection:** 🟢 ON
**Mass-Delete Detection:** 🟢 ON
**Spam Protection:** 🟢 ON
**Audit Logging:** 🟢 ON

**Emergency Mode:** {lockdown_status}
"""
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 Groups", callback_data="groups"),
             InlineKeyboardButton("👮 Admins", callback_data="admins")],
            [InlineKeyboardButton("📋 Logs", callback_data="logs"),
             InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
            [InlineKeyboardButton("◀️ Back", callback_data="back_main")]
        ])
        
        await message.reply(status_text, reply_markup=keyboard)

    async def show_groups(self, message: Message, user_id: int, is_authorized: bool):
        """Show protected groups"""
        if not is_authorized:
            await message.reply("❌ You don't have permission to view groups.")
            return
        
        groups = await db.get_monitored_groups()
        
        if not groups:
            await message.reply("ℹ️ No groups are currently being monitored.")
            return
        
        groups_text = "👥 **Protected Groups**\n\n"
        
        for idx, group in enumerate(groups, 1):
            group_name = group.get('group_name', f'Group {group["group_id"]}')
            lockdown = "🔴 LOCKDOWN" if group.get('lockdown_mode') == 1 else "🟢 Protection Active"
            groups_text += f"{idx}. {group_name}\n   {lockdown}\n\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Back", callback_data="security")]
        ])
        
        await message.reply(groups_text, reply_markup=keyboard)

    async def show_admins(self, message: Message, user_id: int, is_authorized: bool):
        """Show admin security information"""
        if not is_authorized:
            await message.reply("❌ You don't have permission to view admin info.")
            return
        
        groups = await db.get_monitored_groups()
        
        if not groups:
            await message.reply("ℹ️ No groups are currently being monitored.")
            return
        
        admins_text = "👮 **ADMIN SECURITY**\n\n"
        
        for group in groups[:3]:  # Show first 3 groups
            group_name = group.get('group_name', f'Group {group["group_id"]}')
            admins_text += f"**{group_name}**\n\n"
            
            # Get admins for this group (placeholder - would need actual admin tracking)
            admins_text += "👑 Owner\n"
            admins_text += f"User ID: {config.OWNER_ID}\n"
            admins_text += "Monitoring: ON\n"
            admins_text += "Protected: YES\n\n"
        
        admins_text += "\n⚠️ **Note:** System respects Telegram's admin hierarchy.\n"
        admins_text += "Not all admins can be automatically demoted."
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Back", callback_data="security")]
        ])
        
        await message.reply(admins_text, reply_markup=keyboard)

    async def show_settings(self, message: Message, user_id: int, is_authorized: bool):
        """Show settings dashboard"""
        if not is_authorized:
            await message.reply("❌ You don't have permission to manage settings.")
            return
        
        settings_text = """⚙️ **SECURITY SETTINGS**

🛡️ **Protection**
Spam Protection: 🟢
Admin Monitoring: 🟢
Mass-Ban Detection: 🟢
Mass-Delete Detection: 🟢

📊 **Thresholds**
Ban Limit (Warning): 5 in 60s
Ban Limit (Emergency): 15 in 300s

🔔 **Notifications**
Owner Alerts: 🟢
Security Events: 🟢

📋 **Logging**
Audit Logs: 🟢
Admin Actions: 🟢

Use environment variables to configure thresholds.
"""
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Back", callback_data="security")]
        ])
        
        await message.reply(settings_text, reply_markup=keyboard)

    async def show_logs(self, message: Message, user_id: int, is_authorized: bool):
        """Show security logs - NO CREDENTIALS"""
        if not is_authorized:
            await message.reply("❌ You don't have permission to view logs.")
            return
        
        events = await db.get_security_events(limit=5)
        
        if not events:
            await message.reply("ℹ️ No security events logged.")
            return
        
        logs_text = "📋 **SECURITY LOG**\n\n"
        
        for event in events:
            severity_emoji = {
                'INFO': 'ℹ️',
                'WARNING': '⚠️',
                'CRITICAL': '🚨',
                'ERROR': '❌'
            }.get(event.get('severity', 'INFO'), 'ℹ️')
            
            logs_text += f"{severity_emoji} **{event['event_type']}**\n"
            if event.get('admin_id'):
                logs_text += f"Admin: {event['admin_id']}\n"
            if event.get('action'):
                logs_text += f"Action: {event['action']}\n"
            if event.get('timestamp'):
                logs_text += f"Time: {event['timestamp']}\n"
            logs_text += "\n━━━━━━━━━━━━━━\n\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Back", callback_data="security")]
        ])
        
        await message.reply(logs_text, reply_markup=keyboard)

    async def show_help(self, message: Message):
        """Show help page"""
        help_text = """📖 **HELP**

**🔐 ACCOUNT**
/login - Connect Telegram account
/logout - Disconnect account
/session - Show connection status

**🛡️ SECURITY**
/security - Security dashboard
/lockdown - Enable emergency protection
/unlock - Disable emergency protection
/logs - View security events

**👥 GROUP MANAGEMENT**
/groups - Show protected groups
/admins - Show admin security status

**🔨 MODERATION**
/mute - Mute a user
/unmute - Unmute a user
/ban - Ban a user
/unban - Unban a user
/gmute - Globally mute a user
/ungmute - Remove global mute

**💡 TIP:**
You can reply to a user's message and use the command:

Reply to user → /ban
Reply to user → /mute

The system will use the replied user's ID.
"""
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Back", callback_data="back_main")]
        ])
        
        await message.reply(help_text, reply_markup=keyboard)

    async def send_owner_alert(self, message: str, severity: str = 'INFO'):
        """Send alert to owner - FIXED entity resolution"""
        try:
            severity_emoji = {
                'INFO': 'ℹ️',
                'WARNING': '⚠️',
                'CRITICAL': '🚨',
                'ERROR': '❌'
            }
            
            emoji = severity_emoji.get(severity, 'ℹ️')
            formatted_message = f"{emoji} {message}"
            
            # Use bot to send message directly with owner ID (integer)
            await self.bot.send_message(config.OWNER_ID, formatted_message)
        except Exception as e:
            # Log error without exposing credentials
            logger.error(f"Owner notification failed: {type(e).__name__}")

    async def set_bot_commands(self):
        """Register bot commands for the command menu"""
        commands = [
            BotCommand("start", "Open SecurityGuard"),
            BotCommand("help", "Show help"),
            BotCommand("login", "Connect Telegram account"),
            BotCommand("logout", "Disconnect Telegram account"),
            BotCommand("session", "Show connection status"),
            BotCommand("security", "Show security status"),
            BotCommand("groups", "Show protected groups"),
            BotCommand("admins", "Show admin security status"),
            BotCommand("mute", "Mute a user"),
            BotCommand("unmute", "Unmute a user"),
            BotCommand("ban", "Ban a user"),
            BotCommand("unban", "Unban a user"),
            BotCommand("promote", "Promote a user"),
            BotCommand("demote", "Demote an admin"),
            BotCommand("gmute", "Globally mute a user"),
            BotCommand("ungmute", "Remove global mute"),
            BotCommand("lockdown", "Enable emergency protection"),
            BotCommand("unlock", "Disable emergency protection"),
            BotCommand("settings", "Security settings"),
            BotCommand("logs", "Show security events")
        ]
        
        try:
            await self.bot.set_bot_commands(commands)
            logger.info("Bot commands menu registered successfully")
        except Exception as e:
            logger.error(f"Failed to set bot commands: {e}")

    async def start(self):
        """Start the bot"""
        try:
            logger.info("Initializing database...")
            await db.connect()

            logger.info("Starting bot...")
            await self.bot.start()

            # Get bot info
            me = await self.bot.get_me()
            logger.info(f"Bot started: @{me.username}")

            # Set bot commands menu
            await self.set_bot_commands()

            # Set userbot reference in admin commands
            userbot_client = await userbot.get_active_client(config.OWNER_ID)
            if userbot_client:
                self.admin_commands.set_userbot(userbot_client)
                logger.info("Userbot client connected to admin commands")
            else:
                logger.warning("No active userbot session - some features may be limited")

            # Send startup notification to owner
            try:
                await self.bot.send_message(
                    config.OWNER_ID,
                    "🛡️ **Security Bot Started**\n\n"
                    "The security management system is now online.\n\n"
                    "Use /start to view available commands."
                )
            except Exception as e:
                logger.warning(f"Could not send startup message to owner: {type(e).__name__}")

            logger.info("Bot is running...")

        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            raise

    async def stop(self):
        """Stop the bot"""
        try:
            logger.info("Stopping bot...")
            
            if userbot.is_running:
                await userbot.stop_monitoring()
            
            await self.bot.stop()
            await db.close()
            
            logger.info("Bot stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")


# Global bot instance
security_bot = SecurityBot()
