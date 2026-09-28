"""
Database Module
Handles all database operations using SQLite with async support
"""

import aiosqlite
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
import config
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = config.DATABASE_PATH):
        self.db_path = db_path
        self.db = None

    async def connect(self):
        """Initialize database connection and create tables"""
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row
        await self.create_tables()
        logger.info(f"Database connected: {self.db_path}")

    async def close(self):
        """Close database connection"""
        if self.db:
            await self.db.close()
            logger.info("Database connection closed")

    async def create_tables(self):
        """Create all required tables"""
        
        # Users table - stores user information
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                role TEXT DEFAULT 'USER',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Sessions table - stores encrypted session data
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                user_id INTEGER PRIMARY KEY,
                phone_number TEXT NOT NULL,
                session_file TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Groups table - stores monitored groups
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                group_id INTEGER PRIMARY KEY,
                group_name TEXT,
                is_monitored INTEGER DEFAULT 1,
                lockdown_mode INTEGER DEFAULT 0,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Admins table - stores admin information per group
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT DEFAULT 'MODERATOR',
                is_trusted INTEGER DEFAULT 0,
                added_by INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES groups(group_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                UNIQUE(group_id, user_id)
            )
        """)

        # Global Mutes table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS global_mutes (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                muted_by INTEGER NOT NULL,
                muted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (muted_by) REFERENCES users(user_id)
            )
        """)

        # Warnings table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                group_id INTEGER NOT NULL,
                reason TEXT,
                warned_by INTEGER NOT NULL,
                warned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (group_id) REFERENCES groups(group_id),
                FOREIGN KEY (warned_by) REFERENCES users(user_id)
            )
        """)

        # Security Events table - audit log
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS security_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                group_id INTEGER,
                admin_id INTEGER,
                target_id INTEGER,
                action TEXT,
                details TEXT,
                severity TEXT DEFAULT 'INFO',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES groups(group_id),
                FOREIGN KEY (admin_id) REFERENCES users(user_id),
                FOREIGN KEY (target_id) REFERENCES users(user_id)
            )
        """)

        # Settings table - stores bot settings
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Admin Actions table - tracks admin moderation actions
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS admin_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                admin_id INTEGER NOT NULL,
                target_id INTEGER,
                action_type TEXT NOT NULL,
                result TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES groups(group_id),
                FOREIGN KEY (admin_id) REFERENCES users(user_id)
            )
        """)

        await self.db.commit()
        logger.info("All database tables created successfully")

    # User Operations
    async def add_user(self, user_id: int, username: str = None, 
                      first_name: str = None, last_name: str = None, 
                      role: str = 'USER'):
        """Add or update user"""
        await self.db.execute("""
            INSERT INTO users (user_id, username, first_name, last_name, role, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, username, first_name, last_name, role))
        await self.db.commit()

    async def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        async with self.db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_user_role(self, user_id: int) -> str:
        """Get user role"""
        user = await self.get_user(user_id)
        return user['role'] if user else 'USER'

    async def set_user_role(self, user_id: int, role: str):
        """Set user role"""
        await self.db.execute(
            "UPDATE users SET role = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (role, user_id)
        )
        await self.db.commit()

    # Session Operations
    async def add_session(self, user_id: int, phone_number: str, session_file: str):
        """Add or update session"""
        await self.db.execute("""
            INSERT INTO sessions (user_id, phone_number, session_file, last_used)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                phone_number = excluded.phone_number,
                session_file = excluded.session_file,
                is_active = 1,
                last_used = CURRENT_TIMESTAMP
        """, (user_id, phone_number, session_file))
        await self.db.commit()

    async def get_session(self, user_id: int) -> Optional[Dict]:
        """Get active session"""
        async with self.db.execute(
            "SELECT * FROM sessions WHERE user_id = ? AND is_active = 1", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def deactivate_session(self, user_id: int):
        """Deactivate session"""
        await self.db.execute(
            "UPDATE sessions SET is_active = 0 WHERE user_id = ?", (user_id,)
        )
        await self.db.commit()

    # Group Operations
    async def add_group(self, group_id: int, group_name: str = None):
        """Add or update group"""
        await self.db.execute("""
            INSERT INTO groups (group_id, group_name, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(group_id) DO UPDATE SET
                group_name = excluded.group_name,
                updated_at = CURRENT_TIMESTAMP
        """, (group_id, group_name))
        await self.db.commit()

    async def get_group(self, group_id: int) -> Optional[Dict]:
        """Get group by ID"""
        async with self.db.execute(
            "SELECT * FROM groups WHERE group_id = ?", (group_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def set_lockdown(self, group_id: int, lockdown: bool):
        """Set group lockdown status"""
        await self.db.execute(
            "UPDATE groups SET lockdown_mode = ?, updated_at = CURRENT_TIMESTAMP WHERE group_id = ?",
            (1 if lockdown else 0, group_id)
        )
        await self.db.commit()

    async def is_lockdown(self, group_id: int) -> bool:
        """Check if group is in lockdown"""
        group = await self.get_group(group_id)
        return group['lockdown_mode'] == 1 if group else False

    async def get_monitored_groups(self) -> List[Dict]:
        """Get all monitored groups"""
        async with self.db.execute(
            "SELECT * FROM groups WHERE is_monitored = 1"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # Global Mute Operations
    async def add_global_mute(self, user_id: int, muted_by: int, reason: str = None):
        """Add user to global mute list"""
        await self.db.execute("""
            INSERT INTO global_mutes (user_id, muted_by, reason)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                reason = excluded.reason,
                muted_by = excluded.muted_by,
                muted_at = CURRENT_TIMESTAMP
        """, (user_id, muted_by, reason))
        await self.db.commit()

    async def remove_global_mute(self, user_id: int):
        """Remove user from global mute list"""
        await self.db.execute("DELETE FROM global_mutes WHERE user_id = ?", (user_id,))
        await self.db.commit()

    async def is_globally_muted(self, user_id: int) -> bool:
        """Check if user is globally muted"""
        async with self.db.execute(
            "SELECT 1 FROM global_mutes WHERE user_id = ?", (user_id,)
        ) as cursor:
            return await cursor.fetchone() is not None

    async def get_global_mutes(self) -> List[Dict]:
        """Get all globally muted users"""
        async with self.db.execute("SELECT * FROM global_mutes") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # Security Event Operations
    async def log_security_event(self, event_type: str, group_id: int = None,
                                admin_id: int = None, target_id: int = None,
                                action: str = None, details: str = None,
                                severity: str = 'INFO'):
        """Log security event"""
        await self.db.execute("""
            INSERT INTO security_events 
            (event_type, group_id, admin_id, target_id, action, details, severity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (event_type, group_id, admin_id, target_id, action, details, severity))
        await self.db.commit()

    async def get_security_events(self, limit: int = 100, 
                                 severity: str = None) -> List[Dict]:
        """Get recent security events"""
        query = "SELECT * FROM security_events"
        params = []
        
        if severity:
            query += " WHERE severity = ?"
            params.append(severity)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        async with self.db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # Admin Action Tracking
    async def log_admin_action(self, group_id: int, admin_id: int, 
                              target_id: int = None, action_type: str = None,
                              result: str = 'SUCCESS'):
        """Log admin action for monitoring"""
        await self.db.execute("""
            INSERT INTO admin_actions (group_id, admin_id, target_id, action_type, result)
            VALUES (?, ?, ?, ?, ?)
        """, (group_id, admin_id, target_id, action_type, result))
        await self.db.commit()

    async def get_recent_admin_actions(self, admin_id: int, group_id: int,
                                      action_type: str, window_seconds: int) -> List[Dict]:
        """Get recent admin actions within time window"""
        async with self.db.execute("""
            SELECT * FROM admin_actions
            WHERE admin_id = ? AND group_id = ? AND action_type = ?
            AND timestamp >= datetime('now', '-' || ? || ' seconds')
            ORDER BY timestamp DESC
        """, (admin_id, group_id, action_type, window_seconds)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # Settings Operations
    async def set_setting(self, key: str, value: str):
        """Set a setting value"""
        await self.db.execute("""
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
        """, (key, value))
        await self.db.commit()

    async def get_setting(self, key: str, default: str = None) -> Optional[str]:
        """Get a setting value"""
        async with self.db.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
            return row['value'] if row else default

    # Correlated Action Tracking (EXECUTOR-AGNOSTIC)
    async def log_correlated_action(self, group_id: int, initiator_id: Optional[int],
                                    executor_id: int, target_id: int, action_type: str,
                                    correlation_type: str, source: str):
        """
        Log a correlated admin action with both initiator and executor
        
        initiator_id: The admin who initiated/commanded the action (can be None if unknown)
        executor_id: The account/bot that executed the action
        correlation_type: 'COMMAND', 'DIRECT', 'UNKNOWN'
        source: Description of how the action was executed
        """
        await self.db.execute("""
            INSERT INTO admin_actions 
            (group_id, admin_id, target_id, action_type, result, timestamp)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (group_id, initiator_id or executor_id, target_id, action_type, 
              f"{correlation_type}:{executor_id}"))
        await self.db.commit()
        
        # Also log as security event for audit
        await self.log_security_event(
            event_type='CORRELATED_ACTION',
            group_id=group_id,
            admin_id=initiator_id,
            target_id=target_id,
            action=action_type,
            details=f"Executor: {executor_id}, Correlation: {correlation_type}, Source: {source}",
            severity='INFO'
        )

    async def get_initiator_actions(self, initiator_id: int, group_id: int,
                                   action_type: str, window_seconds: int) -> List[Dict]:
        """
        Get recent actions by initiator (regardless of executor)
        This counts ALL actions initiated by an admin across all execution methods
        """
        async with self.db.execute("""
            SELECT * FROM admin_actions
            WHERE admin_id = ? AND group_id = ? AND action_type = ?
            AND timestamp >= datetime('now', '-' || ? || ' seconds')
            ORDER BY timestamp DESC
        """, (initiator_id, group_id, action_type, window_seconds)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_executor_info(self, executor_id: int) -> Optional[Dict]:
        """Get information about an executor (bot or user account)"""
        # Check if we have info in users table
        user = await self.get_user(executor_id)
        if user:
            return {
                'executor_id': executor_id,
                'username': user.get('username'),
                'is_bot': user.get('username', '').lower().endswith('bot'),
                'type': 'bot' if user.get('username', '').lower().endswith('bot') else 'user'
            }
        return {
            'executor_id': executor_id,
            'username': None,
            'is_bot': None,
            'type': 'unknown'
        }

    async def get_admin_activity_summary(self, initiator_id: int, group_id: int,
                                        window_seconds: int) -> Dict:
        """
        Get summary of admin's activity across all executors
        Returns statistics about how the admin performed actions
        """
        async with self.db.execute("""
            SELECT action_type, result, COUNT(*) as count
            FROM admin_actions
            WHERE admin_id = ? AND group_id = ?
            AND timestamp >= datetime('now', '-' || ? || ' seconds')
            GROUP BY action_type, result
        """, (initiator_id, group_id, window_seconds)) as cursor:
            rows = await cursor.fetchall()
            
            summary = {
                'total_actions': 0,
                'by_action_type': {},
                'by_executor': {},
                'initiator_id': initiator_id
            }
            
            for row in rows:
                action_type = row['action_type']
                result = row['result']
                count = row['count']
                
                summary['total_actions'] += count
                
                if action_type not in summary['by_action_type']:
                    summary['by_action_type'][action_type] = 0
                summary['by_action_type'][action_type] += count
                
                # Parse executor from result field (format: "CORRELATION_TYPE:executor_id")
                if ':' in result:
                    parts = result.split(':')
                    if len(parts) == 2:
                        correlation_type = parts[0]
                        executor_id = parts[1]
                        
                        if executor_id not in summary['by_executor']:
                            summary['by_executor'][executor_id] = {
                                'count': 0,
                                'correlation': correlation_type
                            }
                        summary['by_executor'][executor_id]['count'] += count
            
            return summary


# Global database instance
db = Database()
