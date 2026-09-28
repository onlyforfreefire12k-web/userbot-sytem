"""
Configuration Module
Loads environment variables and provides configuration constants
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Telegram Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
OWNER_ID = int(os.getenv('OWNER_ID', '0'))

# Server Configuration
PORT = int(os.getenv('PORT', '5000'))
HOST = '0.0.0.0'

# Database Configuration
DATABASE_PATH = os.getenv('DATABASE_PATH', 'security_bot.db')

# Session Configuration
SESSION_DIR = 'sessions'
SESSION_ENCRYPTION_KEY = os.getenv('SESSION_ENCRYPTION_KEY', 'change-this-in-production')

# Security Thresholds - Configurable
# Mass-Ban Protection
BAN_LIMIT_1 = int(os.getenv('BAN_LIMIT_1', '5'))  # 5 bans in 60 seconds triggers alert
BAN_WINDOW_1 = int(os.getenv('BAN_WINDOW_1', '60'))  # seconds

BAN_LIMIT_2 = int(os.getenv('BAN_LIMIT_2', '15'))  # 15 bans in 5 minutes triggers emergency
BAN_WINDOW_2 = int(os.getenv('BAN_WINDOW_2', '300'))  # seconds

# Mass-Delete Protection
DELETE_LIMIT_1 = int(os.getenv('DELETE_LIMIT_1', '10'))
DELETE_WINDOW_1 = int(os.getenv('DELETE_WINDOW_1', '60'))

DELETE_LIMIT_2 = int(os.getenv('DELETE_LIMIT_2', '30'))
DELETE_WINDOW_2 = int(os.getenv('DELETE_WINDOW_2', '300'))

# Admin Role Hierarchy
ROLES = {
    'OWNER': 4,
    'SECURITY_ADMIN': 3,
    'TRUSTED_ADMIN': 2,
    'MODERATOR': 1,
    'USER': 0
}

# Role Permissions
ROLE_PERMISSIONS = {
    'OWNER': ['*'],  # All permissions
    'SECURITY_ADMIN': [
        'mute', 'unmute', 'ban', 'unban', 'gmute', 'ungmute',
        'promote_moderator', 'demote_moderator', 'lockdown', 'unlock',
        'view_logs', 'manage_settings'
    ],
    'TRUSTED_ADMIN': [
        'mute', 'unmute', 'ban', 'unban', 'gmute', 'ungmute',
        'view_logs'
    ],
    'MODERATOR': [
        'mute', 'unmute', 'delete', 'warn'
    ],
    'USER': []
}

# Timezone
TIMEZONE = os.getenv('TIMEZONE', 'Asia/Kolkata')

# Emergency Mode Settings
LOCKDOWN_RESTRICT_PERMISSIONS = True
LOCKDOWN_NOTIFY_OWNER = True

# Mass-Action Detection (for /banall, /kickall, etc.)
ADMIN_MASS_BAN_THRESHOLD = int(os.getenv('ADMIN_MASS_BAN_THRESHOLD', '3'))  # 3+ removals = mass action
ADMIN_MASS_BAN_WINDOW_SECONDS = int(os.getenv('ADMIN_MASS_BAN_WINDOW_SECONDS', '30'))  # within 30 seconds
CORRELATION_WINDOW_SECONDS = int(os.getenv('CORRELATION_WINDOW_SECONDS', '30'))  # command → action correlation

# Validation
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")
if not API_ID:
    raise ValueError("API_ID environment variable is required")
if not API_HASH:
    raise ValueError("API_HASH environment variable is required")
if not OWNER_ID:
    raise ValueError("OWNER_ID environment variable is required")

# Create sessions directory if it doesn't exist
os.makedirs(SESSION_DIR, exist_ok=True)
