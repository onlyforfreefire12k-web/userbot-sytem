# Telegram Security Management System

A production-ready Telegram Userbot + Security Management System for group moderation and protection.

## ⚠️ Important Security Notice

This is a **legitimate group moderation and security system** designed for:
- Group administrator permissions management
- Security monitoring and threat detection
- Emergency protection against compromised administrators
- Automated moderation within legal Telegram permissions

### What This System DOES NOT Do

❌ **This system does NOT:**
- Perform spam operations
- Mass message users
- Conduct raids or flooding
- Bypass Telegram's permission system
- Expose credentials (OTP, 2FA, sessions)
- Automatically promote unauthorized users

✅ **This system DOES:**
- Monitor administrator actions for suspicious activity
- Provide moderation commands within permission boundaries
- Detect and respond to mass-ban/mass-delete attacks
- Maintain audit logs of security events
- Support global moderation across authorized groups

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│                  live.py (Flask)                │
│           Health Server + Coordinator           │
└────────────┬────────────────────────┬───────────┘
             │                        │
    ┌────────▼────────┐      ┌───────▼────────┐
    │   bot.py        │      │  userbot.py    │
    │ Bot Commands    │      │ MTProto Client │
    └────────┬────────┘      └───────┬────────┘
             │                        │
             └──────────┬─────────────┘
                        │
         ┌──────────────▼───────────────┐
         │      database.py (SQLite)    │
         │    security.py (Monitor)     │
         │  admin_commands.py (Actions) │
         └──────────────────────────────┘
```

## 📋 Features

### Authentication & Session Management
- Secure MTProto login flow
- 2FA password support
- Encrypted session storage
- Session revocation/logout
- No credential exposure in logs

### Moderation Commands
- `/mute` - Mute user in group
- `/unmute` - Unmute user
- `/ban` - Ban user from group
- `/unban` - Unban user
- `/gmute` - Global mute across all monitored groups
- `/ungmute` - Remove global mute

### Security Features
- **Mass-Ban Protection**: Detects when an admin performs unusual ban activity
- **Mass-Delete Protection**: Monitors message deletion patterns
- **Emergency Mode**: `/lockdown` and `/unlock` for heightened security
- **Admin Monitoring**: Tracks new admin promotions
- **Permission Verification**: Validates actions against Telegram's admin hierarchy
- **Owner Protection**: Prevents commands from affecting owner account

### Audit & Logging
- Complete security event logging
- Admin action tracking
- Automated threat detection
- Real-time owner notifications

## 🔧 Installation

### Prerequisites

1. **Python 3.9+**
2. **Telegram API Credentials**
3. **Telegram Bot Token**

### Get Telegram API Credentials

1. Visit https://my.telegram.org/auth
2. Log in with your phone number
3. Navigate to "API development tools"
4. Create a new application
5. Note your `API_ID` and `API_HASH`

### Create Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot`
3. Follow the instructions
4. Save your bot token

### Local Setup

```bash
# Clone or create project directory
mkdir telegram-security-bot
cd telegram-security-bot

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
BOT_TOKEN=your_bot_token_here
API_ID=your_api_id_here
API_HASH=your_api_hash_here
OWNER_ID=your_telegram_user_id
PORT=5000
DATABASE_PATH=security_bot.db
SESSION_ENCRYPTION_KEY=change-this-to-random-string

# Security Thresholds (optional)
BAN_LIMIT_1=5
BAN_WINDOW_1=60
BAN_LIMIT_2=15
BAN_WINDOW_2=300
DELETE_LIMIT_1=10
DELETE_WINDOW_1=60
DELETE_LIMIT_2=30
DELETE_WINDOW_2=300
EOF

# Run the bot
python live.py
```

### Get Your Telegram User ID

1. Search for [@userinfobot](https://t.me/userinfobot) on Telegram
2. Send `/start`
3. The bot will reply with your User ID
4. Use this ID for `OWNER_ID` in your .env file

## 🚀 Render Deployment

### Step 1: Prepare Repository

1. Create a new GitHub repository
2. Upload all project files:
   - `bot.py`
   - `userbot.py`
   - `security.py`
   - `admin_commands.py`
   - `database.py`
   - `config.py`
   - `live.py`
   - `requirements.txt`
   - `README.md`

### Step 2: Create Render Service

1. Go to [render.com](https://render.com)
2. Sign up or log in
3. Click "New +" → "Web Service"
4. Connect your GitHub repository

### Step 3: Configure Service

**Build Settings:**
- **Environment**: Python 3
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python live.py`

**Service Settings:**
- **Instance Type**: Free or Starter (recommended: Starter for 24/7 uptime)
- **Auto-Deploy**: Yes

### Step 4: Environment Variables

Add these environment variables in Render dashboard:

| Key | Value | Example |
|-----|-------|---------|
| `BOT_TOKEN` | Your bot token from BotFather | `123456:ABC-DEF...` |
| `API_ID` | Your API ID from my.telegram.org | `12345678` |
| `API_HASH` | Your API hash | `abcdef1234567890...` |
| `OWNER_ID` | Your Telegram user ID | `987654321` |
| `PORT` | Port number | `5000` |
| `DATABASE_PATH` | Database file path | `security_bot.db` |
| `SESSION_ENCRYPTION_KEY` | Random secret key | `random-secure-key-here` |

**Optional Security Thresholds:**
| Key | Description | Default |
|-----|-------------|---------|
| `BAN_LIMIT_1` | Bans before warning | `5` |
| `BAN_WINDOW_1` | Warning window (seconds) | `60` |
| `BAN_LIMIT_2` | Bans before emergency | `15` |
| `BAN_WINDOW_2` | Emergency window (seconds) | `300` |

### Step 5: Deploy

1. Click "Create Web Service"
2. Wait for deployment to complete
3. Check logs for successful startup
4. Your bot is now live!

## 📱 Usage

### Initial Setup

1. **Start the bot**
   - Search for your bot on Telegram
   - Send `/start`

2. **Connect your account**
   - Send `/login`
   - Provide your phone number (international format: +1234567890)
   - Enter verification code sent to Telegram
   - If 2FA is enabled, enter your password
   - ✅ Login complete!

3. **Add bot to groups**
   - Add your bot to groups you want to monitor
   - Grant administrator permissions
   - The bot needs these permissions:
     - Delete messages
     - Ban users
     - Restrict members
     - Add administrators (for emergency protection)

### Using Moderation Commands

**In Groups:**

Reply to a user's message:
```
/mute
/ban
/gmute
```

Or specify user:
```
/mute @username
/ban 123456789
/gmute @spammer Reason: Spam
```

**Security Commands:**

```
/lockdown     - Activate emergency mode
/unlock       - Deactivate emergency mode
/security     - View security status
/logs         - View recent security events
```

**Session Management:**

```
/session      - View active session status
/logout       - Disconnect and revoke session
```

## 🔒 Security Architecture

### Permission Hierarchy

1. **OWNER** - Full system access (configured in env)
2. **SECURITY_ADMIN** - Can manage security settings
3. **TRUSTED_ADMIN** - Can ban/mute/moderate
4. **MODERATOR** - Can mute and delete only
5. **USER** - No special permissions

### Mass-Action Protection

**Level 1 - Warning**
- Trigger: 5 bans in 60 seconds
- Action: Log event, notify owner
- Status: Monitoring increased

**Level 2 - Emergency**
- Trigger: 15 bans in 5 minutes
- Action: Demote admin (if permissions allow), lockdown
- Status: Emergency protection active

### What Can Be Modified

✅ **The system CAN modify:**
- Regular members
- Admins with lower permissions (per Telegram hierarchy)
- Actions within granted permissions

❌ **The system CANNOT modify:**
- The owner account (protected)
- Admins with equal/higher permissions
- Actions beyond granted Telegram permissions

### Session Security

- Sessions stored encrypted locally
- Never transmitted in plain text
- No OTP/2FA credentials logged
- `/logout` properly revokes session
- Session files isolated per user

## 🛡️ Telegram Permission Requirements

For the bot to function properly, grant these admin permissions in your groups:

**Required:**
- ✅ Delete messages
- ✅ Ban users
- ✅ Restrict members

**Recommended (for emergency protection):**
- ✅ Add administrators
- ✅ Manage chat

**Not Required:**
- Pin messages
- Manage video chats
- Edit group info

## 📊 Database Schema

The system uses SQLite with these tables:

- `users` - User information and roles
- `sessions` - Encrypted session data
- `groups` - Monitored groups
- `admins` - Group admin mappings
- `global_mutes` - Global mute list
- `warnings` - Warning history
- `security_events` - Security audit log
- `admin_actions` - Admin action tracking
- `settings` - Bot configuration

## 🐛 Troubleshooting

### Bot not responding
1. Check Render logs for errors
2. Verify all environment variables are set
3. Ensure bot has admin rights in groups

### Login fails
1. Verify `API_ID` and `API_HASH` are correct
2. Check phone number format (+1234567890)
3. Wait for FloodWait timeout if rate limited

### Commands don't work
1. Ensure you've logged in with `/login`
2. Verify bot has admin permissions in group
3. Check that you have sufficient role permissions

### Mass-action protection too sensitive
Adjust thresholds in environment variables:
```
BAN_LIMIT_1=10
BAN_WINDOW_1=120
```

## 📝 Configuration Reference

### Security Thresholds

All thresholds are configurable via environment variables:

```python
# Mass-Ban Protection
BAN_LIMIT_1 = 5      # Warning threshold
BAN_WINDOW_1 = 60    # Warning window (seconds)
BAN_LIMIT_2 = 15     # Emergency threshold
BAN_WINDOW_2 = 300   # Emergency window (seconds)

# Mass-Delete Protection
DELETE_LIMIT_1 = 10
DELETE_WINDOW_1 = 60
DELETE_LIMIT_2 = 30
DELETE_WINDOW_2 = 300
```

### Role Permissions

Edit `config.py` to customize role permissions:

```python
ROLE_PERMISSIONS = {
    'OWNER': ['*'],  # All permissions
    'SECURITY_ADMIN': ['mute', 'ban', 'gmute', 'lockdown', ...],
    'TRUSTED_ADMIN': ['mute', 'ban', 'gmute'],
    'MODERATOR': ['mute', 'delete'],
}
```

## 🔍 Monitoring & Alerts

The system automatically notifies the owner about:
- New admin promotions
- Mass-ban attempts
- Emergency protection activation
- Security events
- Failed permission checks

All events are logged to database for audit purposes.

## ⚖️ Legal & Ethical Use

This system is designed for **legitimate group moderation** only.

**Acceptable Use:**
- Protecting groups from spam
- Moderating content within admin rights
- Detecting compromised admin accounts
- Emergency protection during raids

**Prohibited Use:**
- Spam or mass messaging
- Unauthorized access
- Harassment or abuse
- Bypassing Telegram's security
- Any violation of Telegram's Terms of Service

Users are responsible for compliance with Telegram's Terms of Service and local laws.

## 📄 License

This project is provided as-is for educational and legitimate moderation purposes.

## 🤝 Support

For issues or questions:
1. Check logs in Render dashboard
2. Review this README
3. Verify configuration settings
4. Check Telegram permissions

## 🔄 Updates

Keep your deployment updated:
1. Pull latest changes from repository
2. Render auto-deploys on git push
3. Review changelog for breaking changes
4. Update environment variables if needed

---

**Remember:** This is a security tool. Use responsibly and within Telegram's Terms of Service.
