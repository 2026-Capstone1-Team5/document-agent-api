from src.queueing.backends import RedisParseJobQueue


def test_redis_auth_parts_supports_acl_username() -> None:
    parts = RedisParseJobQueue._auth_parts(username="default", password="secret")

    assert parts == ("AUTH", "default", "secret")


def test_redis_auth_parts_falls_back_to_password_only() -> None:
    parts = RedisParseJobQueue._auth_parts(username=None, password="secret")

    assert parts == ("AUTH", "secret")


def test_redis_auth_parts_returns_none_without_password() -> None:
    parts = RedisParseJobQueue._auth_parts(username="default", password=None)

    assert parts is None
