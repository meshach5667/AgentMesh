import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.documents.user import UserRole

SELF_REGISTRATION_ROLES = (UserRole.customer, UserRole.provider)


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    role: UserRole

    @field_validator("role")
    @classmethod
    def _self_service_roles_only(cls, role: UserRole) -> UserRole:
        # Operator/admin accounts must be provisioned by an existing administrator, never self-registered.
        if role not in SELF_REGISTRATION_ROLES:
            raise ValueError("role must be 'customer' or 'provider'")
        return role


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    role: UserRole
    is_active: bool
    mfa_enabled: bool = False

    model_config = ConfigDict(from_attributes=True)


class MeOut(UserOut):
    mfa_required: bool = False  # this account must use a second factor
    mfa_verified: bool = False  # this session completed it


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # access token lifetime, seconds
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=200)


class MfaChallenge(BaseModel):
    """Returned by login instead of tokens when the account has a second factor."""

    mfa_required: bool = True
    mfa_token: str


class MfaVerify(BaseModel):
    mfa_token: str = Field(min_length=20, max_length=2000)
    code: str = Field(pattern=r"^\d{6}$")


class MfaCode(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class MfaSetup(BaseModel):
    secret: str  # base32, for typing into an authenticator app
    otpauth_uri: str
