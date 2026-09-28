"""
Action Correlator Module
EXECUTOR-AGNOSTIC admin abuse detection system
Correlates admin commands with actual Telegram actions regardless of executor
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import re
import config

logger = logging.getLogger(__name__)


class ActionCorrelator:
    """
    Correlates admin commands with Telegram admin log events
    to identify INITIATOR + EXECUTOR pairs
    """

    def __init__(self):
        # Pending actions queue: command → expected action
        # {group_id: [{initiator_id, target_id, action_type, timestamp, message_id}]}
        self.pending_actions = {}
        
        # Correlation window (seconds) - how long to wait for action execution
        self.correlation_window = 30
        
        # Configurable moderation command patterns
        self.command_patterns = {
            'ban': ['/ban', '.ban', '!ban', '/fban'],
            'kick': ['/kick', '.kick', '!kick'],
            'mute': ['/mute', '.mute', '!mute', '/tmute'],
            'restrict': ['/restrict', '.restrict', '!restrict'],
            'unban': ['/unban', '.unban', '!unban', '/unfban'],
            'unmute': ['/unmute', '.unmute', '!unmute'],
            'unrestrict': ['/unrestrict', '.unrestrict', '!unrestrict'],
            'promote': ['/promote', '.promote', '!promote'],
            'demote': ['/demote', '.demote', '!demote'],
            # MASS ACTION COMMANDS - CRITICAL FOR /banall DETECTION
            'mass_ban': ['/banall', '/kickall', '/removeall', '.banall', '!banall'],
            'mass_mute': ['/muteall', '/silenceall', '.muteall', '!muteall'],
            'mass_kick': ['/kickall', '.kickall', '!kickall'],
        }
        
        # Mapping of command types to admin log action types
        self.action_mapping = {
            'ban': ['BAN', 'KICK'],
            'kick': ['KICK', 'BAN'],
            'mute': ['MUTE', 'RESTRICT'],
            'restrict': ['RESTRICT', 'MUTE'],
            'unban': ['UNBAN'],
            'unmute': ['UNMUTE', 'UNRESTRICT'],
            'unrestrict': ['UNRESTRICT', 'UNMUTE'],
            'promote': ['PROMOTE'],
            'demote': ['DEMOTE'],
            # MASS ACTIONS - map to same as single actions
            'mass_ban': ['BAN', 'KICK'],
            'mass_mute': ['MUTE', 'RESTRICT'],
            'mass_kick': ['KICK', 'BAN'],
        }
        
        # Track ongoing mass actions: {group_id: {initiator_id: {targets: [], executor_id: None, ...}}}
        self.ongoing_mass_actions = {}

    def add_command_pattern(self, action_type: str, pattern: str):
        """Add a new command pattern for custom bots"""
        if action_type not in self.command_patterns:
            self.command_patterns[action_type] = []
        if pattern not in self.command_patterns[action_type]:
            self.command_patterns[action_type].append(pattern)
            logger.info(f"Added command pattern: {pattern} for {action_type}")

    def detect_moderation_command(self, message_text: str) -> Optional[Tuple[str, Optional[str]]]:
        """
        Detect moderation command in message
        Returns: (action_type, target_identifier) or None
        
        Examples:
        "/ban @user" → ('ban', '@user')
        ".mute 123456" → ('mute', '123456')
        "!kick" (reply) → ('kick', None)
        """
        if not message_text:
            return None
        
        text = message_text.strip()
        
        # Check each action type
        for action_type, patterns in self.command_patterns.items():
            for pattern in patterns:
                # Exact match or starts with pattern
                if text == pattern or text.startswith(pattern + ' '):
                    # Extract target if present
                    target = None
                    
                    # Pattern: /ban @username or /ban username
                    parts = text.split(maxsplit=1)
                    if len(parts) > 1:
                        target_part = parts[1].strip()
                        # Extract @username, user_id, or first word
                        if target_part.startswith('@'):
                            target = target_part
                        elif target_part.isdigit():
                            target = target_part
                        else:
                            # Take first word as potential username
                            target = target_part.split()[0]
                    
                    return (action_type, target)
        
        return None

    async def register_command(self, group_id: int, initiator_id: int, 
                              action_type: str, target_id: Optional[int] = None,
                              target_identifier: Optional[str] = None,
                              message_id: Optional[int] = None):
        """
        Register a moderation command from an admin
        This creates a pending action that will be correlated with admin log events
        """
        if group_id not in self.pending_actions:
            self.pending_actions[group_id] = []
        
        pending = {
            'initiator_id': initiator_id,
            'target_id': target_id,
            'target_identifier': target_identifier,
            'action_type': action_type,
            'timestamp': datetime.now(),
            'message_id': message_id
        }
        
        self.pending_actions[group_id].append(pending)
        
        logger.info(
            f"Registered pending action: {action_type} by {initiator_id} "
            f"target={target_id or target_identifier} in group {group_id}"
        )
        
        # Clean old pending actions
        await self._clean_old_pending_actions(group_id)

    async def correlate_admin_action(self, group_id: int, executor_id: int,
                                    target_id: int, action_type: str) -> Dict:
        """
        Correlate an admin log action with pending commands
        Returns: {
            'initiator_id': int or None (UNKNOWN if not correlated),
            'executor_id': int,
            'target_id': int,
            'action_type': str,
            'correlation': 'COMMAND' | 'DIRECT' | 'UNKNOWN',
            'source': str (description)
        }
        """
        result = {
            'initiator_id': None,
            'executor_id': executor_id,
            'target_id': target_id,
            'action_type': action_type,
            'correlation': 'UNKNOWN',
            'source': 'Unknown source'
        }
        
        # Check if executor is a known user account (not a bot)
        # If executor matches a user account, initiator = executor (direct action)
        if await self._is_user_account(executor_id):
            result['initiator_id'] = executor_id
            result['correlation'] = 'DIRECT'
            result['source'] = f"Direct action by user {executor_id}"
            return result
        
        # Executor is likely a bot, try to correlate with pending commands
        if group_id in self.pending_actions:
            # Find matching pending action
            matched = await self._find_matching_pending_action(
                group_id, target_id, action_type
            )
            
            if matched:
                result['initiator_id'] = matched['initiator_id']
                result['correlation'] = 'COMMAND'
                result['source'] = f"Command by admin {matched['initiator_id']} executed by bot {executor_id}"
                
                # Remove matched pending action
                self.pending_actions[group_id].remove(matched)
                
                logger.info(
                    f"Correlated action: initiator={matched['initiator_id']}, "
                    f"executor={executor_id}, target={target_id}, action={action_type}"
                )
                return result
        
        # No correlation found
        result['correlation'] = 'UNKNOWN'
        result['source'] = f"Executor {executor_id} (bot/unknown), initiator unknown"
        
        logger.warning(
            f"Unable to correlate action: executor={executor_id}, "
            f"target={target_id}, action={action_type} in group {group_id}"
        )
        
        return result

    async def _find_matching_pending_action(self, group_id: int, 
                                           target_id: int, 
                                           action_type: str) -> Optional[Dict]:
        """Find a matching pending action for correlation"""
        if group_id not in self.pending_actions:
            return None
        
        now = datetime.now()
        action_types = self.action_mapping.get(action_type.lower(), [action_type.upper()])
        
        for pending in self.pending_actions[group_id]:
            # Check if within correlation window
            age = (now - pending['timestamp']).total_seconds()
            if age > self.correlation_window:
                continue
            
            # Check if action type matches
            if pending['action_type'].upper() not in action_types:
                continue
            
            # Check if target matches
            if pending['target_id'] and pending['target_id'] == target_id:
                return pending
            
            # If target_identifier exists, we could enhance matching here
            # For now, if target_id matches, we have a correlation
        
        return None

    async def _clean_old_pending_actions(self, group_id: int):
        """Remove pending actions older than correlation window"""
        if group_id not in self.pending_actions:
            return
        
        now = datetime.now()
        cutoff = timedelta(seconds=self.correlation_window * 2)
        
        self.pending_actions[group_id] = [
            p for p in self.pending_actions[group_id]
            if (now - p['timestamp']) < cutoff
        ]

    async def _is_user_account(self, user_id: int) -> bool:
        """
        Check if user_id is a user account (not a bot)
        This is a heuristic - in production, maintain a list of known bots
        """
        # Import here to avoid circular dependency
        from database import db
        
        # Check if we have user info
        user = await db.get_user(user_id)
        if user:
            # If username exists and doesn't end with 'bot', likely a user
            username = user.get('username', '')
            if username and not username.lower().endswith('bot'):
                return True
        
        # Default: assume it might be a bot
        # In production, maintain a whitelist/blacklist
        return False

    def get_pending_actions_count(self, group_id: int) -> int:
        """Get count of pending actions for a group"""
        return len(self.pending_actions.get(group_id, []))


# Global action correlator instance
action_correlator = ActionCorrelator()
