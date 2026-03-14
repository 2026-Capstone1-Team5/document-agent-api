class InvalidEmailFormatError(Exception):
    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__("Invalid email format.")


class UserAlreadyExistsError(Exception):
    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__(f"User already exists: {email}")


class InvalidCredentialsError(Exception):
    pass


class InvalidAccessTokenError(Exception):
    pass


class ExpiredAccessTokenError(Exception):
    pass
