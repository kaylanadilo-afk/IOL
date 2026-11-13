from datetime import datetime
from pydantic import BaseModel


class CreateUserDTO(BaseModel):
    email: str
    password: str
    age: int


class UpdateUserDTO(BaseModel):
    email: str | None = None
    password: str | None = None
    age: int | None = None


class UserResponseDTO(BaseModel):
    id: int
    email: str
    age: int
    created_at: datetime

    model_config = {"from_attributes": True}
