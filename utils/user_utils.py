from sqlalchemy.orm import Session

# Sample users for testing/demo purposes
SAMPLE_USERS = [
    {"username": "alice123", "email": "alice@example.com", "password_hash": "hash1"},
    {"username": "bobby_trax", "email": "bob@example.com", "password_hash": "hash2"},
]


# =============================================================================
# User Database Operations
# =============================================================================


def add_user(db, username, email=None, password_hash=None, is_active=True):
    """
    Add a single user to the database.

    Args:
        db: SQLAlchemy Session
        username: str
        email: str (optional)
        password_hash: str
        is_active: bool

    Returns:
        User: newly created User object
    """
    from models import User

    user = User(
        username=username, email=email, password_hash=password_hash, is_active=is_active
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def add_users(users: list, db: Session):
    """
    Add multiple users to the database.

    Args:
        db: SQLAlchemy Session
        users: List of dicts with keys username, email, password_hash, is_active

    Returns:
        List[User]: List of created User objects
    """
    created_users = []
    for u in users:
        user = add_user(
            db,
            username=u.get("username"),
            email=u.get("email"),
            password_hash=u.get("password_hash"),
            is_active=u.get("is_active", True),
        )
        created_users.append(user)
    return created_users
