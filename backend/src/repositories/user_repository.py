from sqlalchemy.orm import Session

from src.db.models.user_model import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, email: str, password_hash: str, age: int) -> User:
        user = User(email=email, password_hash=password_hash, age=age)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def find_by_id(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def find_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def list_all(self) -> list[User]:
        return self.db.query(User).order_by(User.id).all()

    def update(self, user_id: int, **fields) -> User | None:
        user = self.find_by_id(user_id)
        if user is None:
            return None
        for k, v in fields.items():
            setattr(user, k, v)
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, user_id: int) -> bool:
        user = self.find_by_id(user_id)
        if user is None:
            return False
        self.db.delete(user)
        self.db.commit()
        return True
