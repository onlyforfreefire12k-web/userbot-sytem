"""
Setup Verification Script
Tests configuration and dependencies before deployment
"""

import sys
import os

def print_header(text):
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)

def print_success(text):
    print(f"✅ {text}")

def print_error(text):
    print(f"❌ {text}")

def print_warning(text):
    print(f"⚠️  {text}")

def test_python_version():
    """Check Python version"""
    print_header("Python Version Check")
    
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    
    print(f"Current version: {version_str}")
    
    if version.major == 3 and version.minor >= 9:
        print_success(f"Python {version_str} is compatible")
        return True
    else:
        print_error(f"Python {version_str} is not compatible")
        print("   Required: Python 3.9 or higher")
        return False

def test_dependencies():
    """Check if dependencies are installed"""
    print_header("Dependency Check")
    
    dependencies = [
        ('pyrogram', 'Pyrogram'),
        ('telethon', 'Telethon'),
        ('flask', 'Flask'),
        ('aiosqlite', 'aiosqlite'),
        ('cryptography', 'Cryptography'),
        ('dotenv', 'python-dotenv')
    ]
    
    all_installed = True
    
    for module, name in dependencies:
        try:
            __import__(module)
            print_success(f"{name} installed")
        except ImportError:
            print_error(f"{name} not installed")
            all_installed = False
    
    if not all_installed:
        print("\n   Run: pip install -r requirements.txt")
    
    return all_installed

def test_env_file():
    """Check if .env file exists and has required variables"""
    print_header("Environment Configuration Check")
    
    if not os.path.exists('.env'):
        print_error(".env file not found")
        print("   Copy .env.example to .env and fill in your credentials")
        return False
    
    print_success(".env file exists")
    
    # Try to load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        required_vars = [
            'BOT_TOKEN',
            'API_ID',
            'API_HASH',
            'OWNER_ID'
        ]
        
        missing_vars = []
        
        for var in required_vars:
            value = os.getenv(var)
            if not value or value == 'your_value_here' or value.startswith('123456'):
                print_error(f"{var} not configured")
                missing_vars.append(var)
            else:
                print_success(f"{var} is set")
        
        if missing_vars:
            print("\n   Please configure these variables in .env file")
            return False
        
        return True
        
    except Exception as e:
        print_error(f"Error loading .env: {e}")
        return False

def test_config():
    """Test config.py imports"""
    print_header("Configuration Module Check")
    
    try:
        import config
        
        checks = [
            ('BOT_TOKEN', config.BOT_TOKEN),
            ('API_ID', config.API_ID),
            ('API_HASH', config.API_HASH),
            ('OWNER_ID', config.OWNER_ID),
            ('PORT', config.PORT),
        ]
        
        all_valid = True
        
        for name, value in checks:
            if value:
                print_success(f"{name}: {str(value)[:20]}...")
            else:
                print_error(f"{name} is empty")
                all_valid = False
        
        return all_valid
        
    except Exception as e:
        print_error(f"Error importing config: {e}")
        return False

def test_file_structure():
    """Check if all required files exist"""
    print_header("File Structure Check")
    
    required_files = [
        'bot.py',
        'userbot.py',
        'security.py',
        'admin_commands.py',
        'database.py',
        'config.py',
        'live.py',
        'requirements.txt'
    ]
    
    all_exist = True
    
    for filename in required_files:
        if os.path.exists(filename):
            print_success(f"{filename} exists")
        else:
            print_error(f"{filename} not found")
            all_exist = False
    
    return all_exist

def test_database():
    """Test database initialization"""
    print_header("Database Check")
    
    try:
        import asyncio
        from database import Database
        
        async def test_db():
            db = Database(':memory:')  # Use in-memory database for testing
            await db.connect()
            
            # Try to create a test user
            await db.add_user(12345, 'testuser', 'Test', 'User')
            user = await db.get_user(12345)
            
            await db.close()
            
            return user is not None
        
        result = asyncio.run(test_db())
        
        if result:
            print_success("Database operations working")
            return True
        else:
            print_error("Database operations failed")
            return False
            
    except Exception as e:
        print_error(f"Database test failed: {e}")
        return False

def test_directories():
    """Check and create required directories"""
    print_header("Directory Structure Check")
    
    required_dirs = ['sessions']
    
    for dirname in required_dirs:
        if os.path.exists(dirname):
            print_success(f"{dirname}/ exists")
        else:
            try:
                os.makedirs(dirname)
                print_success(f"{dirname}/ created")
            except Exception as e:
                print_error(f"Could not create {dirname}/: {e}")
                return False
    
    return True

def main():
    """Run all tests"""
    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║     Telegram Security Bot - Setup Verification            ║")
    print("╚════════════════════════════════════════════════════════════╝")
    
    tests = [
        ("Python Version", test_python_version),
        ("Dependencies", test_dependencies),
        ("Environment File", test_env_file),
        ("Configuration", test_config),
        ("File Structure", test_file_structure),
        ("Directories", test_directories),
        ("Database", test_database),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print_error(f"Test failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print_header("Summary")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print_success("\nAll tests passed! You're ready to deploy.")
        print("\n   Next steps:")
        print("   1. Review your .env configuration")
        print("   2. Deploy to Render (see DEPLOYMENT_GUIDE.md)")
        print("   3. Test with /start command on Telegram")
        return 0
    else:
        print_error(f"\n{total - passed} test(s) failed. Please fix the issues above.")
        print("\n   Common fixes:")
        print("   • Run: pip install -r requirements.txt")
        print("   • Copy .env.example to .env and configure")
        print("   • Ensure all Python files are present")
        return 1

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
