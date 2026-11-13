from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.db.connection import get_db
from src.dtos.user_dto import CreateUserDTO, UpdateUserDTO, UserResponseDTO
from src.schemas.user_schema import CreateUserSchema, UpdateUserSchema
from src.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponseDTO, status_code=status.HTTP_201_CREATED)
def create_user(payload: CreateUserSchema, db: Session = Depends(get_db)):
    """Ejemplo completo: valida con Schema, arma DTO, llama al service."""
    dto = CreateUserDTO(**payload.model_dump())
    return UserService(db).create(dto)


@router.get("/{user_id}", response_model=UserResponseDTO)
def get_user(user_id: int, db: Session = Depends(get_db)):
    return UserService(db).get_by_id(user_id)


@router.get("/", response_model=list[UserResponseDTO])
def list_users(db: Session = Depends(get_db)):
    return UserService(db).list_all()


@router.put("/{user_id}", response_model=UserResponseDTO)
def update_user(user_id: int, payload: UpdateUserSchema, db: Session = Depends(get_db)):
    dto = UpdateUserDTO(**payload.model_dump(exclude_unset=True))
    return UserService(db).update(user_id, dto)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    UserService(db).delete(user_id)
