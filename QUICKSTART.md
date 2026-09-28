# Quick Start Guide

Get your Telegram Security Bot running in 10 minutes.

## Prerequisites Checklist

Before starting, gather these:

- [ ] Telegram account
- [ ] Telegram bot token (from @BotFather)
- [ ] Telegram API ID and API Hash (from my.telegram.org)
- [ ] Your Telegram User ID (from @userinfobot)
- [ ] Python 3.9+ installed
- [ ] Render account (for deployment)

## Option 1: Local Testing (5 minutes)

### Step 1: Get Credentials

1. **Bot Token:**
   - Open Telegram → Search @BotFather
   - Send `/newbot` and follow instructions
   - Copy the token

2. **API Credentials:**
   - Visit https://my.telegram.org/auth
   - Create application → Copy API_ID and API_HASH

3. **Your User ID:**
   - Search @userinfobot on Telegram
   - Send `/start` → Copy your ID

### Step 2: Setup Project

```bash
# Create project directory
mkdir telegram-security-bot
cd telegram-security-bot

# Download all files (or clone repository)
# Files needed: bot.py, userbot.py, security.py, admin_commands.py,
#               database.py, config.py, live.py, requirements.txt

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your credentials
```

### Step 3: Configure .env

Edit `.env` file:

```env
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
API_ID=12345678
API_HASH=abcdef1234567890abcdef1234567890
OWNER_ID=987654321
PORT=5000
DATABASE_PATH=security_bot.db
SESSION_ENCRYPTION_KEY=random-secure-key-here
```

### Step 4: Test Setup

```bash
# Run verification script
python test_setup.py

# If all tests pass, start the bot
python live.py
```

You should see:
```
Starting Flask server on 0.0.0.0:5000
Starting Telegram bot worker...
Bot started: @your_bot_username
Bot is running...
```

### Step 5: Test Bot

1. Open Telegram
2. Search for your bot
3. Send `/start`
4. Send `/login` and follow the flow

✅ **Done!** Your bot is running locally.

---

## Option 2: Render Deployment (10 minutes)

### Step 1: Prepare Files

1. Create GitHub repository (private recommended)
2. Upload all project files:
   ```
   bot.py
   userbot.py
   security.py
   admin_commands.py
   database.py
   config.py
   live.py
   requirements.txt
   README.md
   .gitignore
   ```
   
   **DO NOT upload .env file!**

### Step 2: Deploy to Render

1. Go to https://render.com
2. Sign up/Login
3. New + → Web Service
4. Connect your GitHub repository

**Configure:**
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `python live.py`
- **Instance Type:** Starter ($7/month recommended)

### Step 3: Add Environment Variables

In Render dashboard, add these environment variables:

```
BOT_TOKEN = your_bot_token
API_ID = your_api_id
API_HASH = your_api_hash
OWNER_ID = your_telegram_user_id
PORT = 5000
DATABASE_PATH = security_bot.db
SESSION_ENCRYPTION_KEY = random-secure-string
```

### Step 4: Deploy

1. Click "Create Web Service"
2. Wait 2-5 minutes for deployment
3. Check logs for "Bot started" message

### Step 5: Test

1. Open Telegram
2. Search for your bot
3. Send `/start`
4. You should receive welcome message

✅ **Done!** Your bot is deployed and running 24/7.

---

## First Use

### 1. Login Your Account

```
You: /login
Bot: Please send your phone number in international format

You: +1234567890
Bot: Verification code sent to your Telegram account

You: 12345
Bot: ✅ Login successful!
```

If you have 2FA enabled:
```
Bot: 🔐 Two-Factor Authentication Detected
     Please send your 2FA password

You: your_password
Bot: ✅ Login successful!
```

### 2. Add Bot to Groups

1. Add your bot to target group
2. Promote bot to administrator
3. Grant permissions:
   - ✅ Delete messages
   - ✅ Ban users
   - ✅ Restrict members
   - ✅ Add administrators

### 3. Test Commands

In your group:

```
/security
```

You should see security status.

Test moderation (reply to a user):
```
/mute
```

---

## Common Commands

### Essential Commands

```
/start       - Get started with the bot
/login       - Connect your Telegram account
/logout      - Disconnect and revoke session
/session     - View current session status
/security    - View security overview
/logs        - View recent security events
```

### Moderation Commands

Reply to user or specify:
```
/mute @username      - Mute user in group
/unmute @username    - Unmute user
/ban @username       - Ban user from group
/unban @username     - Unban user
/gmute @username     - Global mute across all groups
/ungmute @username   - Remove global mute
```

### Emergency Commands

```
/lockdown    - Activate emergency mode
/unlock      - Deactivate emergency mode
```

---

## Troubleshooting

### Bot doesn't respond

**Check:**
- Bot token is correct
- All environment variables are set
- Service is running (Render logs)

**Fix:**
```bash
# Local:
python live.py

# Render:
Check logs in dashboard
```

### Login fails

**Check:**
- Phone number format: +1234567890
- API_ID and API_HASH are correct
- You're not rate limited

**Fix:**
- Use international format
- Wait 5 minutes if FloodWait
- Verify credentials at my.telegram.org

### Commands don't work in groups

**Check:**
- Bot is admin in group
- Bot has required permissions
- You completed /login process

**Fix:**
1. Remove bot from group
2. Re-add as administrator
3. Grant all permissions
4. Test with /security

---

## Next Steps

### Security Setup

1. **Review Logs:**
   ```
   /logs
   ```

2. **Test Emergency Mode:**
   ```
   /lockdown
   /unlock
   ```

3. **Configure Thresholds:**
   Edit environment variables:
   ```
   BAN_LIMIT_1=10
   BAN_WINDOW_1=120
   ```

### Advanced Features

1. **Global Mute:**
   ```
   /gmute @spammer Reason: Spam
   ```

2. **Monitor Multiple Groups:**
   - Add bot to multiple groups
   - Grant admin permissions
   - Bot monitors all automatically

3. **Review Security Events:**
   ```
   /security
   /logs
   ```

### Best Practices

1. ✅ Keep bot token secret
2. ✅ Use strong 2FA on Telegram
3. ✅ Review security logs regularly
4. ✅ Test in private group first
5. ✅ Monitor owner notifications
6. ✅ Backup database periodically

---

## Getting Help

### Resources

- **Full Documentation:** See README.md
- **Deployment Guide:** See DEPLOYMENT_GUIDE.md
- **Security Info:** See SECURITY_NOTES.md
- **Render Docs:** https://render.com/docs
- **Pyrogram Docs:** https://docs.pyrogram.org

### Common Issues

**"FloodWait" error:**
- Wait the specified time
- Telegram rate limiting is active

**"Insufficient permissions":**
- Bot needs admin rights
- Check permission hierarchy

**"Cannot modify owner":**
- Owner account is protected
- This is expected behavior

**Service sleeping (Free Tier):**
- Upgrade to Starter plan
- Or use uptime monitor

---

## Support

For issues:
1. Check logs (Render dashboard or console)
2. Verify configuration (.env or environment variables)
3. Review DEPLOYMENT_GUIDE.md
4. Check Telegram permissions in group

---

**Your security bot is now ready to protect your groups! 🛡️**

**Important:** Use this bot responsibly and within Telegram's Terms of Service.
