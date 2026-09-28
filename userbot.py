"""
Userbot Module
Handles MTProto userbot operations for security monitoring
"""

import logging
import asyncio
import os
from pyrogram import Client, filters
from pyrogram.types import Message, ChatPermissions
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneNumberInvalid, FloodWait
from database import db
from security import security_monitor
import config

logger = logging.getLogger(__name__)


class Userbot:
    """Telegram Userbot for security monitoring"""

    def __init__(self):
        self.client = None
        self.is_running = False
        self.session_name = None

    async def start_login(self, phone_number: str) -> dict:
        """
        Start login process and send verification code
        Returns: {
            'success': bool,
            'message': str,
            'phone_code_hash': str (if success),
            'session_name': str (if success)
        }
        """
        try:
            # Create unique session name
            self.session_name = f"{config.SESSION_DIR}/user_{phone_number.replace('+', '')}"
            
            # Create client
            self.client = Client(
                name=self.session_name,
                api_id=config.API_ID,
                api_hash=config.API_HASH,
                phone_number=phone_number,
                in_memory=False
            )

            await self.client.connect()

            # Send code
            sent_code = await self.client.send_code(phone_number)
            
            logger.info(f"Verification code sent to {phone_number}")

            return {
                'success': True,
                'message': 'Verification code sent to your Telegram account.',
                'phone_code_hash': sent_code.phone_code_hash,
                'session_name': self.session_name
            }

        except PhoneNumberInvalid:
            return {
                'success': False,
                'message': 'Invalid phone number format. Use international format (+1234567890).'
            }
        except FloodWait as e:
            return {
                'success': False,
                'message': f'Too many attempts. Please wait {e.value} seconds.'
            }
        except Exception as e:
            logger.error(f"Login start error: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }

    async def complete_login(self, phone_number: str, phone_code_hash: str, 
                           verification_code: str, password: str = None) -> dict:
        """
        Complete login with verification code and optional 2FA password
        Returns: {
            'success': bool,
            'message': str,
            'user_id': int (if success)
        }
        """
        try:
            if not self.client:
                return {
                    'success': False,
                    'message': 'Login session not started. Use /login first.'
                }

            # Sign in with code
            try:
                signed_in = await self.client.sign_in(
                    phone_number,
                    phone_code_hash,
                    verification_code
                )
                
            except SessionPasswordNeeded:
                # 2FA is enabled, need password
                if not password:
                    return {
                        'success': False,
                        'message': '2FA is enabled. Please provide your password.',
                        'needs_password': True
                    }
                
                # Sign in with password
                try:
                    signed_in = await self.client.check_password(password)
                except Exception as e:
                    return {
                        'success': False,
                        'message': 'Invalid 2FA password.'
                    }

            # Get user info
            me = await self.client.get_me()
            user_id = me.id

            # Save session to database
            await db.add_session(
                user_id=user_id,
                phone_number=phone_number,
                session_file=self.session_name
            )

            # Add user to database
            await db.add_user(
                user_id=user_id,
                username=me.username,
                first_name=me.first_name,
                last_name=me.last_name,
                role='USER'
            )

            # Set owner role if this is the owner
            if user_id == config.OWNER_ID:
                await db.set_user_role(user_id, 'OWNER')

            logger.info(f"User {user_id} logged in successfully")

            await db.log_security_event(
                event_type='USER_LOGIN',
                admin_id=user_id,
                action='LOGIN_SUCCESS',
                details=f"User logged in via MTProto",
                severity='INFO'
            )

            return {
                'success': True,
                'message': '✅ Login successful! Your session is now active.',
                'user_id': user_id
            }

        except PhoneCodeInvalid:
            return {
                'success': False,
                'message': 'Invalid verification code.'
            }
        except Exception as e:
            logger.error(f"Login completion error: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }

    async def logout(self, user_id: int) -> dict:
        """
        Logout and terminate session
        IMPORTANT: This revokes the session for security
        """
        try:
            # Get session info
            session = await db.get_session(user_id)
            if not session:
                return {
                    'success': False,
                    'message': 'No active session found.'
                }

            # Create client with existing session
            session_client = Client(
                name=session['session_file'],
                api_id=config.API_ID,
                api_hash=config.API_HASH
            )

            await session_client.start()
            
            # Log out and terminate session
            await session_client.log_out()
            
            # Deactivate in database
            await db.deactivate_session(user_id)

            # Remove session file
            session_file_path = f"{session['session_file']}.session"
            if os.path.exists(session_file_path):
                os.remove(session_file_path)

            await db.log_security_event(
                event_type='USER_LOGOUT',
                admin_id=user_id,
                action='LOGOUT_SUCCESS',
                details='User session terminated',
                severity='INFO'
            )

            logger.info(f"User {user_id} logged out successfully")

            return {
                'success': True,
                'message': '✅ Logged out successfully. Session terminated.'
            }

        except Exception as e:
            logger.error(f"Logout error: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }

    async def get_active_client(self, user_id: int = None) -> Client:
        """Get active userbot client"""
        # Use owner's session by default
        target_user = user_id or config.OWNER_ID
        
        session = await db.get_session(target_user)
        if not session:
            return None

        try:
            client = Client(
                name=session['session_file'],
                api_id=config.API_ID,
                api_hash=config.API_HASH
            )

            if not client.is_connected:
                await client.start()
            
            return client

        except Exception as e:
            logger.error(f"Error getting active client: {e}")
            return None

    async def monitor_group_events(self, client: Client):
        """Monitor group events for security threats"""
        
        @client.on_message(filters.group)
        async def handle_group_message(client: Client, message: Message):
            """Monitor messages in groups"""
            try:
                # Check if user is globally muted
                if message.from_user and await db.is_globally_muted(message.from_user.id):
                    # Delete message and restrict user
                    try:
                        await message.delete()
                        await client.restrict_chat_member(
                            message.chat.id,
                            message.from_user.id,
                            permissions=ChatPermissions()
                        )
                        logger.info(f"Globally muted user {message.from_user.id} restricted in {message.chat.id}")
                    except Exception as e:
                        logger.warning(f"Could not restrict globally muted user: {e}")

            except Exception as e:
                logger.error(f"Error handling group message: {e}")

        @client.on_chat_member_updated()
        async def handle_admin_changes(client: Client, update):
            """Monitor admin promotion/demotion events"""
            try:
                chat_id = update.chat.id
                
                # Check if this is an admin change
                if update.old_chat_member and update.new_chat_member:
                    old_status = update.old_chat_member.status
                    new_status = update.new_chat_member.status
                    
                    user_id = update.new_chat_member.user.id
                    
                    # Admin promoted
                    if old_status != ChatMemberStatus.ADMINISTRATOR and \
                       new_status == ChatMemberStatus.ADMINISTRATOR:
                        
                        await db.log_security_event(
                            event_type='ADMIN_PROMOTED',
                            group_id=chat_id,
                            target_id=user_id,
                            action='PROMOTE',
                            details='New admin detected',
                            severity='WARNING'
                        )

                        # Notify owner
                        await security_monitor.notify_owner(
                            f"⚠️ NEW ADMIN DETECTED\n\n"
                            f"Group ID: {chat_id}\n"
                            f"User ID: {user_id}\n"
                            f"Username: @{update.new_chat_member.user.username or 'N/A'}\n\n"
                            f"Please verify this admin promotion.",
                            severity='WARNING'
                        )

                    # Admin demoted
                    elif old_status == ChatMemberStatus.ADMINISTRATOR and \
                         new_status != ChatMemberStatus.ADMINISTRATOR:
                        
                        await db.log_security_event(
                            event_type='ADMIN_DEMOTED',
                            group_id=chat_id,
                            target_id=user_id,
                            action='DEMOTE',
                            details='Admin removed',
                            severity='INFO'
                        )

            except Exception as e:
                logger.error(f"Error handling admin changes: {e}")

        logger.info("Group event monitoring activated")

    async def start_monitoring(self):
        """Start userbot monitoring with REAL ADMIN LOG MONITORING"""
        try:
            # Get owner's active client
            client = await self.get_active_client(config.OWNER_ID)
            
            if not client:
                logger.warning("No active userbot session found")
                return False

            # Setup event monitors (existing global mute enforcement and admin changes)
            await self.monitor_group_events(client)
            
            # Setup REAL ADMIN LOG MONITORING (this is the fix!)
            logger.info("=" * 60)
            logger.info("INITIALIZING ADMIN LOG MONITOR")
            logger.info("=" * 60)
            
            from admin_log_monitor import admin_log_monitor
            admin_log_monitor.set_client(client)
            await admin_log_monitor.start_monitoring()
            
            logger.info("=" * 60)
            logger.info("ADMIN LOG MONITOR ACTIVE")
            logger.info("Monitoring for:")
            logger.info("  - /banall, /kickall commands")
            logger.info("  - Mass user removals")
            logger.info("  - Admin abuse patterns")
            logger.info("=" * 60)
            
            self.client = client
            self.is_running = True
            
            logger.info("Userbot monitoring started successfully with REAL abuse detection")
            return True

        except Exception as e:
            logger.error(f"Error starting userbot monitoring: {e}")
            return False

    async def stop_monitoring(self):
        """Stop userbot monitoring"""
        if self.client and self.is_running:
            try:
                await self.client.stop()
                self.is_running = False
                logger.info("Userbot monitoring stopped")
            except Exception as e:
                logger.error(f"Error stopping userbot: {e}")


# Global userbot instance
userbot = Userbot()
