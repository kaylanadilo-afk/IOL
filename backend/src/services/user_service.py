from sqlalchemy.orm import Session

from src.dtos.user_dto import CreateUserDTO, UpdateUserDTO, UserResponseDTO
from src.mappers.user_mapper import to_user_response
from src.repositories.user_repository import UserRepository
from src.utils.errors import ConflictError, NotFoundError
from src.utils.hash import hash_password


class UserService:
    def __init__(self, db: Session):
        self.repo = UserRepository(db)

    def create(self, dto: CreateUserDTO) -> UserResponseDTO:
        """Ejemplo completo: hashea la password, crea el user y devuelve el DTO de respuesta."""
        password_hash = hash_password(dto.password)
        user = self.repo.create(
            email=dto.email,
            password_hash=password_hash,
            age=dto.age,
        )
        return to_user_response(user)

    def get_by_id(self, user_id: int) -> UserResponseDTO:
        user = self.repo.find_by_id(user_id)
        if user is None:
            raise NotFoundError("Usuario no encontrado")
        return to_user_response(user)

    def list_all(self) -> list[UserResponseDTO]:
        return [to_user_response(u) for u in self.repo.list_all()]

    def update(self, user_id: int, dto: UpdateUserDTO) -> UserResponseDTO:
        if self.repo.find_by_id(user_id) is None:
            raise NotFoundError("Usuario no encontrado")
        fields = dto.model_dump(exclude_none=True)
        if "email" in fields:
            otro = self.repo.find_by_email(fields["email"])
            if otro and otro.id != user_id:
                raise ConflictError("Ya existe un usuario con ese email")
        if "password" in fields:
            fields["password_hash"] = hash_password(fields.pop("password"))
        return to_user_response(self.repo.update(user_id, **fields))

    def delete(self, user_id: int) -> None:
        if not self.repo.delete(user_id):
            raise NotFoundError("Usuario no encontrado")
