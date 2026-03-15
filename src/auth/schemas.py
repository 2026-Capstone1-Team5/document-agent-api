from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class UserProfile(BaseSchema):
    id: UUID
    email: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class RegisterRequest(BaseSchema):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseSchema):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)


class AuthTokenResponse(BaseSchema):
    access_token: str = Field(alias="accessToken")
    token_type: str = Field(alias="tokenType")
    expires_in: int = Field(alias="expiresIn")
    user: UserProfile


class UserResponse(BaseSchema):
    user: UserProfile
