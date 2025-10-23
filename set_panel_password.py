"""
Set or update the admin panel password in the config table.

Usage:
    python set_panel_password.py

This script will prompt for a password and store its SHA-256 hash in the config table.
"""
import os
import asyncio
import asyncpg
import hashlib
import getpass
from dotenv import load_dotenv

load_dotenv()


def hash_password(password: str) -> str:
    """Hash password using SHA-256."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


async def set_password():
    DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('DATABASE_URL_UNPOOLED')
    
    if not DATABASE_URL:
        print("❌ DATABASE_URL not set in environment")
        return
    
    # Prompt for password
    print("🔐 Admin Panel Password Setup")
    print("=" * 60)
    password = getpass.getpass("Enter new admin password: ")
    password_confirm = getpass.getpass("Confirm password: ")
    
    if password != password_confirm:
        print("❌ Passwords do not match!")
        return
    
    if len(password) < 6:
        print("❌ Password must be at least 6 characters long!")
        return
    
    # Hash the password
    password_hash = hash_password(password)
    
    # Connect to database
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # Ensure config table exists
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        ''')
        
        # Insert or update the password
        await conn.execute('''
            INSERT INTO config (key, value, updated_at)
            VALUES ('panel_passcode', $1, NOW())
            ON CONFLICT (key) 
            DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
        ''', password_hash)
        
        print("✅ Admin panel password set successfully!")
        print(f"🔑 Password hash: {password_hash[:20]}...")
        print("\n💡 You can now access the admin panel at /admin.html")
        
    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(set_password())
