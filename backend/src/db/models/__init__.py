# Importar todos los modelos acá para que SQLAlchemy resuelva las relaciones por nombre
# y Base.metadata.create_all() conozca todas las tablas.
from src.db.models.user_model import User  # noqa: F401
from src.db.models.pasajero_model import Pasajero  # noqa: F401
from src.db.models.conductores_model import Conductores  # noqa: F401
from src.db.models.inversor_model import Inversor, favoritos  # noqa: F401
from src.db.models.cuenta_model import Cuenta, Movimiento, Tenencia  # noqa: F401
from src.db.models.activo_model import Activo, CierreDiario, CotizacionIntradia, Dividendo  # noqa: F401
from src.db.models.operacion_model import Operacion  # noqa: F401
