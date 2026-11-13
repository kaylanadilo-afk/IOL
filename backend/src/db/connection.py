from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.config.env import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
# expire_on_commit=False: los objetos siguen usables después del commit (para armar el DTO de respuesta)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
Base = declarative_base()


def get_db():
    """Dependency de FastAPI: abre una sesión por request y la cierra al final.

    Si algo falla antes del commit, se descarta todo (por ejemplo, la segunda pata del MEP).
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
