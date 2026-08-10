"""
Database Reset Script for ResearchGPT Authentication System.
Purges all old user accounts, stale passwords, obsolete sessions, and verification records.
Preserves non-user academic paper analysis collections while ensuring clean state.
"""
from app.db import get_db

def reset_authentication_database():
    db = get_db()
    
    # 1. Clear legacy user accounts
    users_deleted = db.users.delete_many({}).deleted_count
    print(f"[RESET DB] Deleted {users_deleted} legacy user records from 'users' collection.")
    
    # 2. Clear legacy OTP verification codes
    otps_deleted = db.otps.delete_many({}).deleted_count
    print(f"[RESET DB] Deleted {otps_deleted} old OTP documents from 'otps' collection.")
    
    # 3. Clear orphaned sessions / tokens if any exist
    if "sessions" in db.list_collection_names():
        sessions_deleted = db.sessions.delete_many({}).deleted_count
        print(f"[RESET DB] Deleted {sessions_deleted} legacy session documents from 'sessions' collection.")
        
    print("[RESET DB] Authentication database reset complete. Fresh state ready.")

if __name__ == "__main__":
    reset_authentication_database()
