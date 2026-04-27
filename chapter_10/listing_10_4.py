import asyncpg                          # Driver asíncrono para PostgreSQL; proporciona create_pool y Pool
from aiohttp.web_app import Application # Tipo de la instancia de aplicación aiohttp; usado para type hints
from asyncpg.pool import Pool           # Tipo del pool de conexiones; usado para type hints

DB_KEY = 'database'                     # Clave string para guardar y recuperar el pool desde app[DB_KEY]


async def create_database_pool(app: Application, host: str, port: int,
                                user: str, database: str, password: str):
    # Crea un pool de conexiones a PostgreSQL con mínimo y máximo de 6 conexiones simultáneas
    pool: Pool = await asyncpg.create_pool(
        host=host,          # Dirección del servidor PostgreSQL
        port=port,          # Puerto de PostgreSQL (por defecto 5432)
        user=user,          # Usuario de la base de datos
        password=password,  # Contraseña del usuario
        database=database,  # Nombre de la base de datos a la que conectar
        min_size=6,         # Número mínimo de conexiones abiertas en el pool
        max_size=6          # Número máximo de conexiones abiertas en el pool
    )
    app[DB_KEY] = pool      # Guarda el pool en el dict de la aplicación para que los handlers lo accedan


async def destroy_database_pool(app: Application):
    pool: Pool = app[DB_KEY]  # Recupera el pool guardado al arrancar
    await pool.close()        # Cierra todas las conexiones del pool de forma asíncrona y limpia
