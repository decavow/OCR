# CLI commands for admin management
# Usage:
#   python -m app.cli create-admin <email> <password>
#   python -m app.cli promote <email>
#   python -m app.cli demote <email>

import sys

from app.infrastructure.database.connection import get_db_context, init_db
from app.infrastructure.database.repositories import UserRepository
from app.modules.auth.utils import hash_password


def create_admin(email: str, password: str):
    """Create a new admin user or promote existing user."""
    init_db()
    with get_db_context() as db:
        user_repo = UserRepository(db)
        existing = user_repo.get_by_email(email)

        if existing:
            if existing.is_admin:
                print(f"User '{email}' is already an admin.")
                return
            existing.is_admin = True
            db.flush()
            print(f"Existing user '{email}' promoted to admin.")
        else:
            user = user_repo.create_user(email, hash_password(password))
            user.is_admin = True
            db.flush()
            print(f"Admin user '{email}' created.")


def promote(email: str):
    """Promote an existing user to admin."""
    init_db()
    with get_db_context() as db:
        user_repo = UserRepository(db)
        user = user_repo.get_by_email(email)

        if not user:
            print(f"Error: User '{email}' not found.")
            sys.exit(1)

        if user.is_admin:
            print(f"User '{email}' is already an admin.")
            return

        user.is_admin = True
        db.flush()
        print(f"User '{email}' promoted to admin.")


def demote(email: str):
    """Remove admin privileges from a user."""
    init_db()
    with get_db_context() as db:
        user_repo = UserRepository(db)
        user = user_repo.get_by_email(email)

        if not user:
            print(f"Error: User '{email}' not found.")
            sys.exit(1)

        if not user.is_admin:
            print(f"User '{email}' is not an admin.")
            return

        user.is_admin = False
        db.flush()
def main():
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python -m app.cli create-admin <email> <password>")
        print("  python -m app.cli promote <email>")
        print("  python -m app.cli demote <email>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "create-admin":
        if len(sys.argv) < 4:
            print("Usage: python -m app.cli create-admin <email> <password>")
            sys.exit(1)
        create_admin(sys.argv[2], sys.argv[3])
    elif command == "promote":
        promote(sys.argv[2])
    elif command == "demote":
        demote(sys.argv[2])
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
