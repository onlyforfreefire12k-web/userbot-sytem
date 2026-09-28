"""
Admin Commands Module
Handles all admin/moderation commands with permission checking
"""

import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, UserAdminInvalid, ChatAdminRequired, UserNotParticipant
from pyrogram.enums import ChatMemberStatus, ChatMembersFilter
import asyncio
from database import db
from security import security_monitor
import config

logger = logging.getLogger(__name__)


class AdminCommands:
    """Handles admin moderation commands"""

    def __init__(self, bot: Client, userbot: Client = None):
        self.bot = bot
        self.userbot = userbot

    def set_userbot(self, userbot: Client):
        """Set userbot client after initialization"""
        self.userbot = userbot

    async def get_user_from_message(self, message: Message):
        """Extract user from command or reply"""
        user_id = None
        username = None

        # Check if replying to a message
        if message.reply_to_message:
            user_id = message.reply_to_message.from_user.id
            username = message.reply_to_message.from_user.username
        # Check command arguments
        elif len(message.command) > 1:
            user_input = message.command[1]
            
            # Username
            if user_input.startswith('@'):
                username = user_input[1:]
            # User ID
            elif user_input.isdigit():
                user_id = int(user_input)
            else:
                username = user_input

        return user_id, username

    async def resolve_user(self, user_id: int = None, username: str = None):
        """Resolve user ID from username or vice versa"""
        if user_id:
            return user_id
        
        if username:
            try:
                # Try to get user from bot
                user = await self.bot.get_users(username)
                return user.id
            except:
                pass
        
        return None

    async def mute_user(self, message: Message):
        """Mute a user in the group"""
        if not message.chat or message.chat.type == 'private':
            await message.reply("❌ This command only works in groups.")
            return

        user_id, username = await self.get_user_from_message(message)
        target_id = await self.resolve_user(user_id, username)

        if not target_id:
            await message.reply("❌ Please reply to a user or provide username/ID.")
            return

        # Check permissions
        permission_check = await security_monitor.check_admin_permissions(
            self.userbot if self.userbot else self.bot,
            message.chat.id,
            message.from_user.id,
            target_id,
            'mute'
        )

        if not permission_check['allowed']:
            await message.reply(f"❌ {permission_check['reason']}")
            return

        # Check role permissions
        if not await security_monitor.check_role_permission(message.from_user.id, 'mute'):
            await message.reply("❌ You don't have permission to mute users.")
            return

        try:
            client = self.userbot if self.userbot else self.bot
            
            # Mute user (restrict from sending messages)
            await client.restrict_chat_member(
                message.chat.id,
                target_id,
                permissions=None  # Remove all permissions
            )

            await db.log_admin_action(
                message.chat.id,
                message.from_user.id,
                target_id,
                'MUTE',
                'SUCCESS'
            )

            await message.reply(f"✅ User muted successfully.")
            logger.info(f"User {target_id} muted in {message.chat.id} by {message.from_user.id}")

        except FloodWait as e:
            await message.reply(f"⏳ Flood wait: {e.value} seconds")
            logger.warning(f"FloodWait: {e.value}s")
        except ChatAdminRequired:
            await message.reply("❌ Bot needs admin rights to mute users.")
        except UserAdminInvalid:
            await message.reply("❌ Cannot mute this admin.")
        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")
            logger.error(f"Mute error: {e}")

    async def unmute_user(self, message: Message):
        """Unmute a user in the group"""
        if not message.chat or message.chat.type == 'private':
            await message.reply("❌ This command only works in groups.")
            return

        user_id, username = await self.get_user_from_message(message)
        target_id = await self.resolve_user(user_id, username)

        if not target_id:
            await message.reply("❌ Please reply to a user or provide username/ID.")
            return

        if not await security_monitor.check_role_permission(message.from_user.id, 'unmute'):
            await message.reply("❌ You don't have permission to unmute users.")
            return

        try:
            client = self.userbot if self.userbot else self.bot
            
            # Get default chat permissions
            chat = await client.get_chat(message.chat.id)
            
            # Restore default permissions
            await client.restrict_chat_member(
                message.chat.id,
                target_id,
                permissions=chat.permissions
            )

            await db.log_admin_action(
                message.chat.id,
                message.from_user.id,
                target_id,
                'UNMUTE',
                'SUCCESS'
            )

            await message.reply(f"✅ User unmuted successfully.")
            logger.info(f"User {target_id} unmuted in {message.chat.id} by {message.from_user.id}")

        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")
            logger.error(f"Unmute error: {e}")

    async def ban_user(self, message: Message):
        """Ban a user from the group"""
        if not message.chat or message.chat.type == 'private':
            await message.reply("❌ This command only works in groups.")
            return

        user_id, username = await self.get_user_from_message(message)
        target_id = await self.resolve_user(user_id, username)

        if not target_id:
            await message.reply("❌ Please reply to a user or provide username/ID.")
            return

        # Check permissions
        permission_check = await security_monitor.check_admin_permissions(
            self.userbot if self.userbot else self.bot,
            message.chat.id,
            message.from_user.id,
            target_id,
            'ban'
        )

        if not permission_check['allowed']:
            await message.reply(f"❌ {permission_check['reason']}")
            return

        if not await security_monitor.check_role_permission(message.from_user.id, 'ban'):
            await message.reply("❌ You don't have permission to ban users.")
            return

        try:
            client = self.userbot if self.userbot else self.bot
            
            # Ban user
            await client.ban_chat_member(message.chat.id, target_id)

            # Log action for mass-ban detection
            await db.log_admin_action(
                message.chat.id,
                message.from_user.id,
                target_id,
                'BAN',
                'SUCCESS'
            )

            # Check for mass-ban activity
            ban_check = await security_monitor.check_mass_ban_protection(
                message.from_user.id,
                message.chat.id
            )

            if ban_check['level'] == 2:  # Critical
                # Attempt emergency protection
                protection_result = await security_monitor.handle_suspicious_admin(
                    message.from_user.id,
                    message.chat.id,
                    client,
                    'MASS_BAN'
                )
                
                if protection_result['admin_demoted']:
                    await message.reply("⚠️ Emergency protection activated - admin demoted due to mass ban activity.")
                    return

            await message.reply(f"✅ User banned successfully.")
            logger.info(f"User {target_id} banned from {message.chat.id} by {message.from_user.id}")

        except FloodWait as e:
            await message.reply(f"⏳ Flood wait: {e.value} seconds")
        except ChatAdminRequired:
            await message.reply("❌ Bot needs admin rights to ban users.")
        except UserAdminInvalid:
            await message.reply("❌ Cannot ban this admin.")
        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")
            logger.error(f"Ban error: {e}")

    async def unban_user(self, message: Message):
        """Unban a user from the group"""
        if not message.chat or message.chat.type == 'private':
            await message.reply("❌ This command only works in groups.")
            return

        user_id, username = await self.get_user_from_message(message)
        target_id = await self.resolve_user(user_id, username)

        if not target_id:
            await message.reply("❌ Please reply to a user or provide username/ID.")
            return

        if not await security_monitor.check_role_permission(message.from_user.id, 'unban'):
            await message.reply("❌ You don't have permission to unban users.")
            return

        try:
            client = self.userbot if self.userbot else self.bot
            
            # Unban user
            await client.unban_chat_member(message.chat.id, target_id)

            await db.log_admin_action(
                message.chat.id,
                message.from_user.id,
                target_id,
                'UNBAN',
                'SUCCESS'
            )

            await message.reply(f"✅ User unbanned successfully.")
            logger.info(f"User {target_id} unbanned from {message.chat.id} by {message.from_user.id}")

        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")
            logger.error(f"Unban error: {e}")

    async def global_mute(self, message: Message):
        """Globally mute a user across all monitored groups"""
        if message.from_user.id != config.OWNER_ID:
            if not await security_monitor.check_role_permission(message.from_user.id, 'gmute'):
                await message.reply("❌ You don't have permission to use global mute.")
                return

        user_id, username = await self.get_user_from_message(message)
        target_id = await self.resolve_user(user_id, username)

        if not target_id:
            await message.reply("❌ Please reply to a user or provide username/ID.")
            return

        if target_id == config.OWNER_ID:
            await message.reply("❌ Cannot globally mute the owner.")
            return

        # Get reason if provided
        reason = ' '.join(message.command[2:]) if len(message.command) > 2 else "No reason provided"

        try:
            # Add to global mute database
            await db.add_global_mute(target_id, message.from_user.id, reason)

            # Get all monitored groups
            groups = await db.get_monitored_groups()
            
            muted_count = 0
            failed_count = 0

            client = self.userbot if self.userbot else self.bot

            # Mute in all groups where we have permission
            for group in groups:
                try:
                    await client.restrict_chat_member(
                        group['group_id'],
                        target_id,
                        permissions=None
                    )
                    muted_count += 1
                except Exception as e:
                    failed_count += 1
                    logger.warning(f"Failed to gmute in group {group['group_id']}: {e}")

            await db.log_security_event(
                event_type='GLOBAL_MUTE',
                admin_id=message.from_user.id,
                target_id=target_id,
                action='GMUTE',
                details=f"Reason: {reason}. Applied to {muted_count} groups.",
                severity='WARNING'
            )

            await message.reply(
                f"✅ User globally muted.\n"
                f"Applied to {muted_count} groups.\n"
                f"Failed in {failed_count} groups.\n"
                f"Reason: {reason}"
            )

        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")
            logger.error(f"Global mute error: {e}")

    async def global_unmute(self, message: Message):
        """Remove global mute"""
        if message.from_user.id != config.OWNER_ID:
            if not await security_monitor.check_role_permission(message.from_user.id, 'ungmute'):
                await message.reply("❌ You don't have permission to use global unmute.")
                return

        user_id, username = await self.get_user_from_message(message)
        target_id = await self.resolve_user(user_id, username)

        if not target_id:
            await message.reply("❌ Please reply to a user or provide username/ID.")
            return

        try:
            # Check if globally muted
            if not await db.is_globally_muted(target_id):
                await message.reply("ℹ️ This user is not globally muted.")
                return

            # Remove from global mute database
            await db.remove_global_mute(target_id)

            # Get all monitored groups
            groups = await db.get_monitored_groups()
            
            unmuted_count = 0
            client = self.userbot if self.userbot else self.bot

            # Unmute in all groups
            for group in groups:
                try:
                    chat = await client.get_chat(group['group_id'])
                    await client.restrict_chat_member(
                        group['group_id'],
                        target_id,
                        permissions=chat.permissions
                    )
                    unmuted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to ungmute in group {group['group_id']}: {e}")

            await message.reply(f"✅ User globally unmuted in {unmuted_count} groups.")

        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")
            logger.error(f"Global unmute error: {e}")

    async def lockdown(self, message: Message):
        """Activate lockdown mode for the group"""
        if not message.chat or message.chat.type == 'private':
            await message.reply("❌ This command only works in groups.")
            return

        if not await security_monitor.check_role_permission(message.from_user.id, 'lockdown'):
            await message.reply("❌ You don't have permission to use lockdown.")
            return

        try:
            await security_monitor.activate_emergency_mode(message.chat.id)
            await message.reply("🔒 LOCKDOWN MODE ACTIVATED\n\nIncreased security monitoring is now active.")
            logger.info(f"Lockdown activated in {message.chat.id} by {message.from_user.id}")

        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")
            logger.error(f"Lockdown error: {e}")

    async def unlock(self, message: Message):
        """Deactivate lockdown mode"""
        if not message.chat or message.chat.type == 'private':
            await message.reply("❌ This command only works in groups.")
            return

        if not await security_monitor.check_role_permission(message.from_user.id, 'unlock'):
            await message.reply("❌ You don't have permission to unlock.")
            return

        try:
            await security_monitor.deactivate_emergency_mode(message.chat.id)
            await message.reply("🔓 Lockdown mode deactivated.\n\nNormal operations resumed.")
            logger.info(f"Lockdown deactivated in {message.chat.id} by {message.from_user.id}")

        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")
            logger.error(f"Unlock error: {e}")
