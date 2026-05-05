from .base import ClientError


class UserAlreadyExists(ClientError):
    pass


class InvalidCredentials(ClientError):
    def __str__(self):
        return "Неверный логин или пароль"
