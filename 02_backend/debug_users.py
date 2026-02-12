import sys
import os

# Add the current directory to sys.path to allow importing app modules
sys.path.append(os.getcwd())

from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.database.models import User

def debug_users():
    db = SessionLocal()
    try:
        users = db.query(User).all()
        print(f"Total Users in DB: {len(users)}")
        for user in users:
            print(f"User: {user.email}, ID: {user.id}, IsAdmin: {user.is_admin}, CreatedAt: {user.created_at}, DeletedAt: {user.deleted_at}")
            
        print("-" * 20)
        active_users = db.query(User).filter(User.deleted_at.is_(None)).all()
        print(f"Active Users (deleted_at is None): {len(active_users)}")
        for user in active_users:
             print(f"Active User: {user.email}")
             
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    debug_users()
