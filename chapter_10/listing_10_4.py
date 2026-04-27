# =============================================================================
# listing_10_4.py — Database Pool Utilities (módulo compartido)
# =============================================================================
# Objetivo:
#   Módulo de utilidades reutilizable que encapsula la creación y
#   destrucción del pool de conexiones a PostgreSQL (asyncpg).
#   No es una aplicación aiohttp ni expone ningún endpoint HTTP.
#
#   El problema que resuelve: los servicios de favoritos (10_5),
#   carrito (10_6) y productos (10_7) necesitan todos conectarse a
#   PostgreSQL. Sin este módulo, cada uno repetiría el mismo código
#   de conexión. Aquí se centraliza en dos funciones:
#     - create_database_pool: crea el pool y lo guarda en app[DB_KEY]
#     - destroy_database_pool: cierra el pool al apagar el servidor
#
#   Los servicios lo usan via functools.partial en on_startup/on_cleanup,
#   ya que aiohttp solo pasa el objeto `app` a esos hooks y estas
#   funciones necesitan también los parámetros de conexión (host,
#   puerto, usuario, contraseña, nombre de BD).
#
#   DB_KEY es la constante string que todos los servicios usan como
#   clave de diccionario para acceder al pool desde request.app[DB_KEY].
# =============================================================================

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
