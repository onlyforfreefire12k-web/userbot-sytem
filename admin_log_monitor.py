"""
Admin Log Monitor - REAL IMPLEMENTATION
Monitors Telegram admin log events using Pyrogram for ACTUAL abuse detection
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pyrogram import Client, filters
from pyrogram.types import Message, ChatMemberUpdated
from pyrogram.enums import ChatMemberStatus
from database import db
from action_correlator import action_correlator
from security import security_monitor
import config

logger = logging.getLogger(__name__)


class AdminLogMonitor:
    """
    Real admin log monitoring that actually works
    Uses Pyrogram ChatMemberUpdated events to detect bans/kicks/restrictions
    """

    def __init__(self):
        self.client = None
        self.monitoring_groups = set()
        self.mass_action_tracker = {}  # {(group_id, initiator_id): [targets]}
        
    def set_client(self, client: Client):
        """Set the Pyrogram client for monitoring"""
        self.client = client
        logger.info("Admin log monitor client set")

    async def start_monitoring(self):
        """Start monitoring admin actions"""
        if not self.client:
            logger.error("No client set for admin log monitoring")
            return False
        
        logger.info("=" * 60)
        logger.info("STARTING ADMIN LOG MONITORING")
        logger.info("=" * 60)
        
        # Monitor ChatMemberUpdated events for ban/kick/restrict
        @self.client.on_chat_member_updated()
        async def on_member_updated(client: Client, update: ChatMemberUpdated):
            """
            CRITICAL: This detects actual Telegram moderation actions
            Triggered when user is banned, kicked, restricted, etc.
            """
            try:
                chat_id = update.chat.id
                
                # Check if we're monitoring this group
                group = await db.get_group(chat_id)
                if not group or not group.get('is_monitored'):
                    return
                
                old_member = update.old_chat_member
                new_member = update.new_chat_member
                
                if not old_member or not new_member:
                    return
                
                target_id = new_member.user.id
                old_status = old_member.status
                new_status = new_member.status
                
                # Detect action type
                action_type = None
                executor_id = None
                
                # BAN/KICK detection
                if old_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.RESTRICTED] and \
                   new_status in [ChatMemberStatus.BANNED, ChatMemberStatus.LEFT]:
                    
                    action_type = 'BAN'
                    # Try to get who did it (often it's in new_member.promoted_by or we need to infer)
                    # For now, we'll correlate with pending commands
                    
                    logger.info(f"[ADMIN LOG] User {target_id} BANNED/KICKED from {chat_id}")
                    logger.info(f"[ADMIN LOG] Old status: {old_status}, New status: {new_status}")
                
                # RESTRICT detection
                elif old_status == ChatMemberStatus.MEMBER and new_status == ChatMemberStatus.RESTRICTED:
                    action_type = 'RESTRICT'
                    logger.info(f"[ADMIN LOG] User {target_id} RESTRICTED in {chat_id}")
                
                # PROMOTE detection
                elif old_status != ChatMemberStatus.ADMINISTRATOR and new_status == ChatMemberStatus.ADMINISTRATOR:
                    action_type = 'PROMOTE'
                    logger.info(f"[ADMIN LOG] User {target_id} PROMOTED in {chat_id}")
                
                # DEMOTE detection
                elif old_status == ChatMemberStatus.ADMINISTRATOR and new_status != ChatMemberStatus.ADMINISTRATOR:
                    action_type = 'DEMOTE'
                    logger.info(f"[ADMIN LOG] User {target_id} DEMOTED in {chat_id}")
                
                if action_type:
                    # Process the action
                    await self.process_admin_action(
                        chat_id=chat_id,
                        action_type=action_type,
                        target_id=target_id,
                        timestamp=datetime.now()
                    )
                    
            except Exception as e:
                logger.error(f"[ADMIN LOG] Error processing member update: {e}", exc_info=True)
        
        # Also monitor group messages for command detection
        @self.client.on_message(filters.group & filters.text)
        async def on_group_message(client: Client, message: Message):
            """
            CRITICAL: Detect moderation commands like /banall
            This identifies the INITIATOR
            """
            try:
                chat_id = message.chat.id
                
                # Check if monitoring this group
                group = await db.get_group(chat_id)
                if not group or not group.get('is_monitored'):
                    return
                
                if not message.from_user:
                    return
                
                initiator_id = message.from_user.id
                command_text = message.text.strip()
                
                # Detect moderation command
                detected = action_correlator.detect_moderation_command(command_text)
                
                if detected:
                    action_type, target_identifier = detected
                    
                    logger.info("=" * 60)
                    logger.info(f"[SECURITY COMMAND] DETECTED")
                    logger.info(f"Chat ID: {chat_id}")
                    logger.info(f"Sender ID: {initiator_id}")
                    logger.info(f"Sender: @{message.from_user.username or 'unknown'}")
                    logger.info(f"Command: {command_text}")
                    logger.info(f"Action type: {action_type}")
                    logger.info("=" * 60)
                    
                    # Check if this is a MASS command
                    is_mass_command = action_type in ['mass_ban', 'mass_mute', 'mass_kick']
                    
                    # Register pending action
                    target_id = None
                    if message.reply_to_message and message.reply_to_message.from_user:
                        target_id = message.reply_to_message.from_user.id
                    elif target_identifier and target_identifier.isdigit():
                        target_id = int(target_identifier)
                    
                    await action_correlator.register_command(
                        group_id=chat_id,
                        initiator_id=initiator_id,
                        action_type=action_type,
                        target_id=target_id,
                        target_identifier=target_identifier,
                        message_id=message.id
                    )
                    
                    logger.info(f"[SECURITY PENDING] Registered pending {action_type} by {initiator_id}")
                    
                    # If it's a mass command, start tracking
                    if is_mass_command:
                        key = (chat_id, initiator_id)
                        self.mass_action_tracker[key] = {
                            'initiator_id': initiator_id,
                            'action_type': action_type,
                            'command': command_text,
                            'started_at': datetime.now(),
                            'targets': [],
                            'executor_id': None
                        }
                        logger.info(f"[MASS ACTION] Started tracking mass action for {initiator_id}")
                
            except Exception as e:
                logger.error(f"[SECURITY COMMAND] Error: {e}", exc_info=True)
        
        logger.info("Admin log monitoring handlers registered")
        return True

    async def process_admin_action(self, chat_id: int, action_type: str, 
                                   target_id: int, timestamp: datetime):
        """
        Process an admin action detected from admin log
        This is where we correlate with pending commands
        """
        logger.info(f"[CORRELATION] Processing {action_type} on user {target_id} in {chat_id}")
        
        # Check for pending mass actions first
        mass_action_found = False
        for key, mass_data in list(self.mass_action_tracker.items()):
            group_id, initiator_id = key
            
            if group_id != chat_id:
                continue
            
            # Check if this action happened within the correlation window
            age = (timestamp - mass_data['started_at']).total_seconds()
            if age > config.CORRELATION_WINDOW_SECONDS:
                # Expired, remove
                logger.info(f"[MASS ACTION] Expired mass action for {initiator_id}")
                del self.mass_action_tracker[key]
                continue
            
            # Check if action type matches
            expected_actions = action_correlator.action_mapping.get(
                mass_data['action_type'], []
            )
            if action_type not in expected_actions:
                continue
            
            # This is part of the mass action!
            mass_data['targets'].append(target_id)
            target_count = len(mass_data['targets'])
            
            logger.info("=" * 60)
            logger.info(f"[MASS ACTION] Target added")
            logger.info(f"Initiator: {initiator_id}")
            logger.info(f"Action: {mass_data['action_type']}")
            logger.info(f"Target count: {target_count}")
            logger.info("=" * 60)
            
            # Log the correlated action
            await db.log_correlated_action(
                group_id=chat_id,
                initiator_id=initiator_id,
                executor_id=initiator_id,  # We'll update this if we detect the bot
                target_id=target_id,
                action_type=action_type,
                correlation_type='MASS_COMMAND',
                source=f"Mass command {mass_data['command']} by {initiator_id}"
            )
            
            # Check threshold
            if target_count >= config.ADMIN_MASS_BAN_THRESHOLD:
                logger.critical("=" * 60)
                logger.critical(f"[SECURITY THRESHOLD] MASS ACTION THRESHOLD REACHED")
                logger.critical(f"Initiator: {initiator_id}")
                logger.critical(f"Target count: {target_count}")
                logger.critical(f"Threshold: {config.ADMIN_MASS_BAN_THRESHOLD}")
                logger.critical("=" * 60)
                
                # Trigger security action
                await self.trigger_security_action(
                    chat_id=chat_id,
                    initiator_id=initiator_id,
                    action_type=mass_data['action_type'],
                    targets=mass_data['targets'],
                    command=mass_data['command']
                )
                
                # Clean up this mass action
                del self.mass_action_tracker[key]
            
            mass_action_found = True
            break
        
        if not mass_action_found:
            # Try regular single-action correlation
            logger.info(f"[CORRELATION] Checking for regular (non-mass) pending actions")
            # This would use the existing correlate_admin_action method
            # For now, log it as unmatched
            logger.warning(f"[UNMATCHED ADMIN ACTION] executor=unknown, target={target_id}, action={action_type}")

    async def trigger_security_action(self, chat_id: int, initiator_id: int,
                                      action_type: str, targets: List[int],
                                      command: str):
        """
        CRITICAL: Trigger security action when mass abuse is detected
        """
        target_count = len(targets)
        
        logger.critical("=" * 60)
        logger.critical("TRIGGERING SECURITY ACTION")
        logger.critical(f"Chat ID: {chat_id}")
        logger.critical(f"Initiator ID: {initiator_id}")
        logger.critical(f"Action: {action_type}")
        logger.critical(f"Command: {command}")
        logger.critical(f"Targets: {target_count}")
        logger.critical("=" * 60)
        
        # Check if initiator is owner (protected)
        if initiator_id == config.OWNER_ID:
            logger.info("[SECURITY ACTION] Initiator is owner - no action taken")
            return
        
        # Log security event
        await db.log_security_event(
            event_type='MASS_ABUSE_DETECTED',
            group_id=chat_id,
            admin_id=initiator_id,
            action=action_type,
            details=f"Mass action: {command} - {target_count} targets",
            severity='CRITICAL'
        )
        
        # Prepare alert message
        alert_message = f"""
🚨 MASS ABUSE DETECTED

Group ID: {chat_id}

Initiator (Admin):
User ID: {initiator_id}

Command:
{command}

Action detected:
{target_count} user removals in {config.ADMIN_MASS_BAN_WINDOW_SECONDS} seconds

Execution sources:
Multiple targets detected via command correlation

Security action:
Attempting to demote abusive admin...

Timestamp:
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        # Notify owner
        await security_monitor.notify_owner(alert_message, severity='CRITICAL')
        
        # Attempt to demote the initiator
        try:
            logger.info(f"[SECURITY ACTION] Attempting to demote admin {initiator_id}")
            
            # Get chat
            chat = await self.client.get_chat(chat_id)
            
            # Check our permissions
            me = await self.client.get_chat_member(chat_id, 'me')
            if not me.privileges or not me.privileges.can_promote_members:
                logger.error("[SECURITY ACTION] Bot lacks permission to demote admins")
                await security_monitor.notify_owner(
                    f"⚠️ Cannot demote admin {initiator_id} - insufficient permissions",
                    severity='ERROR'
                )
                return
            
            # Try to demote
            try:
                await self.client.promote_chat_member(
                    chat_id=chat_id,
                    user_id=initiator_id,
                    privileges=None  # Remove all privileges
                )
                
                logger.info(f"[SECURITY ACTION] Successfully demoted admin {initiator_id}")
                await security_monitor.notify_owner(
                    f"✅ Successfully demoted abusive admin {initiator_id}",
                    severity='CRITICAL'
                )
                
                await db.log_security_event(
                    event_type='ADMIN_DEMOTED_AUTO',
                    group_id=chat_id,
                    admin_id=initiator_id,
                    action='AUTO_DEMOTE',
                    details=f"Automatically demoted due to mass abuse: {command}",
                    severity='CRITICAL'
                )
                
            except Exception as e:
                logger.error(f"[SECURITY ACTION] Demotion failed: {e}")
                await security_monitor.notify_owner(
                    f"❌ Failed to demote admin {initiator_id}: {str(e)}\n\n"
                    f"Telegram permissions prevented automatic demotion.\n"
                    f"Please manually review this admin.",
                    severity='ERROR'
                )
        
        except Exception as e:
            logger.error(f"[SECURITY ACTION] Error in security action: {e}", exc_info=True)


# Global instance
admin_log_monitor = AdminLogMonitor()
