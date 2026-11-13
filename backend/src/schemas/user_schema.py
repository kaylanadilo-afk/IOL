from pydantic import BaseModel, EmailStr, Field


class CreateUserSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    age: int = Field(ge=18)


class UpdateUserSchema(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8)
    age: int | None = Field(default=None, ge=18)
