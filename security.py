"""
Security Module
Handles security monitoring, mass-action detection, and emergency protection
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import config
from database import db

logger = logging.getLogger(__name__)


class SecurityMonitor:
    """Monitors and responds to security threats in groups"""

    def __init__(self):
        self.alert_callbacks = []

    def register_alert_callback(self, callback):
        """Register callback for security alerts"""
        self.alert_callbacks.append(callback)

    async def notify_owner(self, message: str, severity: str = 'WARNING'):
        """Notify owner through registered callbacks"""
        for callback in self.alert_callbacks:
            try:
                await callback(message, severity)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

    async def check_mass_ban_protection(self, admin_id: int, group_id: int) -> Dict:
        """
        EXECUTOR-AGNOSTIC mass ban detection
        Checks if admin is performing mass bans REGARDLESS of execution method
        (Rose, custom bots, userbots, direct actions, etc.)
        
        Returns: {
            'is_suspicious': bool,
            'level': int (0=normal, 1=warning, 2=critical),
            'count': int,
            'action': str,
            'executors': dict (which executors were used)
        }
        """
        # Don't check owner
        if admin_id == config.OWNER_ID:
            return {'is_suspicious': False, 'level': 0, 'count': 0, 'action': 'ALLOWED'}

        # Use INITIATOR-based tracking (executor-agnostic)
        # This counts ALL bans initiated by this admin, regardless of executor
        recent_bans_1 = await db.get_initiator_actions(
            admin_id, group_id, 'BAN', config.BAN_WINDOW_1
        )
        count_1 = len(recent_bans_1)

        recent_bans_2 = await db.get_initiator_actions(
            admin_id, group_id, 'BAN', config.BAN_WINDOW_2
        )
        count_2 = len(recent_bans_2)
        
        # Get activity summary to show which executors were used
        activity_summary = await db.get_admin_activity_summary(
            admin_id, group_id, config.BAN_WINDOW_2
        )

        result = {
            'is_suspicious': False,
            'level': 0,
            'count': count_2,
            'action': 'ALLOWED',
            'admin_id': admin_id,
            'group_id': group_id,
            'executors': activity_summary.get('by_executor', {})
        }

        # Critical threshold reached
        if count_2 >= config.BAN_LIMIT_2:
            result['is_suspicious'] = True
            result['level'] = 2
            result['action'] = 'EMERGENCY_PROTECTION'
            
            # Format executor list for alert
            executor_list = self._format_executor_list(activity_summary.get('by_executor', {}))
            
            await db.log_security_event(
                event_type='MASS_BAN_CRITICAL',
                group_id=group_id,
                admin_id=admin_id,
                action='EMERGENCY_PROTECTION_ACTIVATED',
                details=f"Admin performed {count_2} bans in {config.BAN_WINDOW_2}s via {executor_list}",
                severity='CRITICAL'
            )

            await self.notify_owner(
                self._format_security_alert_with_executors(
                    'CRITICAL: Mass Ban Detected',
                    group_id,
                    admin_id,
                    f"{count_2} bans in {config.BAN_WINDOW_2} seconds",
                    executor_list,
                    'Emergency protection activated'
                ),
                severity='CRITICAL'
            )

        # Warning threshold reached
        elif count_1 >= config.BAN_LIMIT_1:
            result['is_suspicious'] = True
            result['level'] = 1
            result['action'] = 'WARNING'
            
            await db.log_security_event(
                event_type='MASS_BAN_WARNING',
                group_id=group_id,
                admin_id=admin_id,
                action='MONITORING_INCREASED',
                details=f"Admin performed {count_1} bans in {config.BAN_WINDOW_1}s",
                severity='WARNING'
            )

            await self.notify_owner(
                self._format_security_alert(
                    'WARNING: Elevated Ban Activity',
                    group_id,
                    admin_id,
                    f"{count_1} bans in {config.BAN_WINDOW_1} seconds",
                    'Monitoring increased'
                ),
                severity='WARNING'
            )

        return result

    async def check_mass_delete_protection(self, admin_id: int, group_id: int) -> Dict:
        """
        Check if admin is performing mass deletes
        Similar logic to mass ban protection
        """
        if admin_id == config.OWNER_ID:
            return {'is_suspicious': False, 'level': 0, 'count': 0, 'action': 'ALLOWED'}

        recent_deletes_1 = await db.get_recent_admin_actions(
            admin_id, group_id, 'DELETE', config.DELETE_WINDOW_1
        )
        count_1 = len(recent_deletes_1)

        recent_deletes_2 = await db.get_recent_admin_actions(
            admin_id, group_id, 'DELETE', config.DELETE_WINDOW_2
        )
        count_2 = len(recent_deletes_2)

        result = {
            'is_suspicious': False,
            'level': 0,
            'count': count_2,
            'action': 'ALLOWED',
            'admin_id': admin_id,
            'group_id': group_id
        }

        if count_2 >= config.DELETE_LIMIT_2:
            result['is_suspicious'] = True
            result['level'] = 2
            result['action'] = 'EMERGENCY_PROTECTION'
            
            await db.log_security_event(
                event_type='MASS_DELETE_CRITICAL',
                group_id=group_id,
                admin_id=admin_id,
                action='EMERGENCY_PROTECTION_ACTIVATED',
                details=f"Admin deleted {count_2} messages in {config.DELETE_WINDOW_2}s",
                severity='CRITICAL'
            )

            await self.notify_owner(
                self._format_security_alert(
                    'CRITICAL: Mass Delete Detected',
                    group_id,
                    admin_id,
                    f"{count_2} deletions in {config.DELETE_WINDOW_2} seconds",
                    'Emergency protection activated'
                ),
                severity='CRITICAL'
            )

        elif count_1 >= config.DELETE_LIMIT_1:
            result['is_suspicious'] = True
            result['level'] = 1
            result['action'] = 'WARNING'
            
            await db.log_security_event(
                event_type='MASS_DELETE_WARNING',
                group_id=group_id,
                admin_id=admin_id,
                action='MONITORING_INCREASED',
                details=f"Admin deleted {count_1} messages in {config.DELETE_WINDOW_1}s",
                severity='WARNING'
            )

        return result

    async def handle_suspicious_admin(self, admin_id: int, group_id: int, 
                                     client, action_type: str) -> Dict:
        """
        Handle suspicious admin behavior
        Attempts to demote/remove admin if permissions allow
        """
        result = {
            'admin_demoted': False,
            'admin_removed': False,
            'notification_sent': False,
            'error': None
        }

        # Never demote owner
        if admin_id == config.OWNER_ID:
            result['error'] = 'Cannot demote owner'
            return result

        try:
            # Get chat
            chat = await client.get_chat(group_id)
            
            # Check if we have permission to demote
            me = await client.get_chat_member(group_id, 'me')
            target_admin = await client.get_chat_member(group_id, admin_id)

            # Verify we have admin rights and can demote this admin
            if not me.privileges or not me.privileges.can_promote_members:
                result['error'] = 'Insufficient permissions to demote admin'
                logger.warning(f"Cannot demote admin {admin_id} - insufficient permissions")
                return result

            # Attempt to demote (remove admin rights)
            await client.set_administrator(
                group_id,
                admin_id,
                privileges=None  # Removes all admin privileges
            )
            result['admin_demoted'] = True

            await db.log_security_event(
                event_type='ADMIN_DEMOTED',
                group_id=group_id,
                admin_id=admin_id,
                action='AUTO_DEMOTE',
                details=f"Auto-demoted due to {action_type}",
                severity='CRITICAL'
            )

            logger.info(f"Successfully demoted suspicious admin {admin_id} in group {group_id}")

        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Error handling suspicious admin: {e}")

            await db.log_security_event(
                event_type='ADMIN_PROTECTION_FAILED',
                group_id=group_id,
                admin_id=admin_id,
                action='DEMOTE_FAILED',
                details=str(e),
                severity='ERROR'
            )

        return result

    def _format_security_alert(self, title: str, group_id: int, admin_id: int,
                               action_detected: str, actions_taken: str) -> str:
        """Format security alert message"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
        
        message = f"""
🚨 SECURITY ALERT

{title}

Group ID: {group_id}
Admin ID: {admin_id}

Action detected:
{action_detected}

Actions:
✓ Event recorded
✓ Owner notified
{actions_taken}

Timestamp:
{timestamp}
"""
        return message

    async def check_admin_permissions(self, client, group_id: int, 
                                    admin_id: int, target_id: int,
                                    required_permission: str) -> Dict:
        """
        Check if admin has permission to perform action on target
        Returns: {
            'allowed': bool,
            'reason': str,
            'admin_can_modify': bool,
            'target_is_protected': bool
        }
        """
        result = {
            'allowed': False,
            'reason': '',
            'admin_can_modify': False,
            'target_is_protected': False
        }

        # Owner can do anything except modify themselves in certain ways
        if admin_id == config.OWNER_ID:
            if target_id == config.OWNER_ID:
                result['reason'] = 'Cannot modify owner account'
                result['target_is_protected'] = True
                return result
            result['allowed'] = True
            result['admin_can_modify'] = True
            return result

        # Check if target is owner - always protected
        if target_id == config.OWNER_ID:
            result['reason'] = 'Target is owner - protected'
            result['target_is_protected'] = True
            return result

        try:
            # Get admin and target member info
            admin_member = await client.get_chat_member(group_id, admin_id)
            target_member = await client.get_chat_member(group_id, target_id)

            # Check if admin has required permission
            if not admin_member.privileges:
                result['reason'] = 'User is not an admin'
                return result

            permission_map = {
                'ban': 'can_restrict_members',
                'mute': 'can_restrict_members',
                'delete': 'can_delete_messages',
                'promote': 'can_promote_members',
                'demote': 'can_promote_members'
            }

            required_attr = permission_map.get(required_permission)
            if required_attr and not getattr(admin_member.privileges, required_attr, False):
                result['reason'] = f'Missing permission: {required_permission}'
                return result

            # Check if target is also an admin
            if target_member.privileges:
                # Check admin hierarchy - we can only modify if target has less privileges
                # This is a simplified check - Telegram has complex admin hierarchy
                result['reason'] = 'Target is an admin - check Telegram admin hierarchy'
                result['admin_can_modify'] = False
                return result

            result['allowed'] = True
            result['admin_can_modify'] = True
            return result

        except Exception as e:
            result['reason'] = f'Error checking permissions: {str(e)}'
            logger.error(f"Permission check error: {e}")
            return result

    async def activate_emergency_mode(self, group_id: int):
        """Activate emergency/lockdown mode for a group"""
        await db.set_lockdown(group_id, True)
        
        await db.log_security_event(
            event_type='EMERGENCY_MODE_ACTIVATED',
            group_id=group_id,
            action='LOCKDOWN',
            details='Emergency protection activated',
            severity='CRITICAL'
        )

        await self.notify_owner(
            f"🔒 EMERGENCY MODE ACTIVATED\nGroup ID: {group_id}\nIncreased security monitoring active.",
            severity='CRITICAL'
        )

    async def deactivate_emergency_mode(self, group_id: int):
        """Deactivate emergency/lockdown mode"""
        await db.set_lockdown(group_id, False)
        
        await db.log_security_event(
            event_type='EMERGENCY_MODE_DEACTIVATED',
            group_id=group_id,
            action='UNLOCK',
            details='Emergency mode deactivated',
            severity='INFO'
        )

    async def check_role_permission(self, user_id: int, permission: str) -> bool:
        """Check if user role has specific permission"""
        if user_id == config.OWNER_ID:
            return True

        role = await db.get_user_role(user_id)
        
        if role == 'OWNER':
            return True
        
        if role not in config.ROLE_PERMISSIONS:
            return False
        
        permissions = config.ROLE_PERMISSIONS[role]
        
        # '*' means all permissions
        if '*' in permissions:
            return True
        
        return permission in permissions

    def _format_executor_list(self, executors: Dict) -> str:
        """
        Format the list of executors for security alerts
        executors: {executor_id: {'count': N, 'correlation': 'TYPE'}}
        """
        if not executors:
            return "unknown executors"
        
        executor_names = []
        for executor_id, info in executors.items():
            count = info.get('count', 0)
            correlation = info.get('correlation', 'UNKNOWN')
            
            # Try to get executor name
            if executor_id.isdigit():
                executor_names.append(f"ID:{executor_id}({count})")
            else:
                executor_names.append(f"{executor_id}({count})")
        
        return ", ".join(executor_names) if executor_names else "multiple sources"

    def _format_security_alert_with_executors(self, title: str, group_id: int, 
                                             admin_id: int, action_detected: str,
                                             executors: str, actions_taken: str) -> str:
        """
        Format security alert with executor information
        EXECUTOR-AGNOSTIC - shows which methods the admin used
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
        
        message = f"""
🚨 SECURITY ALERT

{title}

**Initiator (Admin):**
User ID: {admin_id}

**Group ID:** {group_id}

**Action detected:**
{action_detected}

**Execution sources:**
{executors}

**Actions:**
✓ Event recorded
✓ Owner notified
{actions_taken}

**Timestamp:**
{timestamp}

⚠️ **Note:** This admin used multiple execution methods.
Detection is EXECUTOR-AGNOSTIC and tracks the initiating admin.
"""
        return message


# Global security monitor instance
security_monitor = SecurityMonitor()
