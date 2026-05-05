from datetime import datetime, timedelta, timezone

import jwt
from passlib.hash import pbkdf2_sha256

from core.exceptions.auth import InvalidCredentials
from settings import settings


class Security:
    def __init__(self) -> None:
        self.secret_key = settings.secret_key
        self.jwt_algorithm = settings.jwt_algorithm
        self.access_token_expires_in_minutes = settings.access_token_expires_in_minutes
        self.refresh_token_expires_in_days = settings.refresh_token_expires_in_days

    def create_access_token(self, sub: str) -> str:
        expiration = datetime.now(timezone.utc) + timedelta(
            minutes=self.access_token_expires_in_minutes
        )
        payload = {"sub": sub, "exp": expiration}
        token = jwt.encode(payload, self.secret_key, algorithm=self.jwt_algorithm)
        return token

    def create_refresh_token(self, sub: str) -> str:
        expiration = datetime.now(timezone.utc) + timedelta(
            days=self.refresh_token_expires_in_days
        )
        payload = {"sub": sub, "exp": expiration}
        token = jwt.encode(payload, self.secret_key, algorithm=self.jwt_algorithm)
        return token

    def decode_token(self, token: str) -> dict:
        try:
            payload = jwt.decode(
                token, self.secret_key, algorithms=[self.jwt_algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise InvalidCredentials
        except jwt.InvalidTokenError:
            raise InvalidCredentials

    def hash_password(self, password: str) -> str:
        return pbkdf2_sha256.hash(password)

    def verify_password(self, password: str, hashed_password: str) -> bool:
        return pbkdf2_sha256.verify(password, hashed_password)
