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


class InvalidApiKeyError(Exception):
    pass


class InvalidApiKeyNameError(Exception):
    pass


class ApiKeyNameAlreadyExistsError(Exception):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"API key name already exists: {name}")


class ApiKeyNotFoundError(Exception):
    def __init__(self, api_key_id: str) -> None:
        self.api_key_id = api_key_id
        super().__init__(f"API key not found: {api_key_id}")
