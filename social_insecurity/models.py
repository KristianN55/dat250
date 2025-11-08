from flask_login import UserMixin
from social_insecurity.database import sqlite

class User(UserMixin):
    def __init__(self, id, username, password, first_name=None, last_name=None):
        self.id = id
        self.username = username
        self.password = password
        self.first_name = first_name
        self.last_name = last_name

    @classmethod
    def get(cls, user_id):
        query = "SELECT * FROM Users WHERE id = ?"
        user_row = sqlite.query(query, [user_id], one=True)
        if user_row:
            return cls(
                id=user_row["id"],
                username=user_row["username"],
                password=user_row["password"],
                first_name=user_row["first_name"] if "first_name" in user_row.keys() else None,
                last_name=user_row["last_name"] if "last_name" in user_row.keys() else None,
            )
        return None