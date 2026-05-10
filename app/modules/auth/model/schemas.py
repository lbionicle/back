from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.modules.users.model.schemas import UserRead


class SignUpRequest(BaseModel):
    full_name: str = Field(alias="fullName", min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    confirm_password: str = Field(alias="confirmPassword", min_length=6, max_length=128)

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def validate_passwords(self):
        if self.password != self.confirm_password:
            raise ValueError("Пароли не совпадают")

        return self


class SignInRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class AuthResponse(BaseModel):
    access_token: str = Field(alias="accessToken")
    token_type: str = Field(default="bearer", alias="tokenType")
    user: UserRead

    model_config = ConfigDict(populate_by_name=True)