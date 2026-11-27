import uvicorn

from src.config.env import settings

if __name__ == "__main__":
    # Solo en esta compu: el celular entra por la página (puerto 3000), que le pasa los pedidos a la API
    uvicorn.run("src.app:app", host="127.0.0.1", port=settings.PORT, reload=True)
