# =============================================================================
# listing_10_5.py — User Favorites Service (puerto 8002)
# =============================================================================
# Objetivo:
#   Microservicio que gestiona los productos favoritos de un usuario.
#   Expone GET /users/{id}/favorites, consulta la tabla user_favorite
#   de la base de datos 'favorites' y devuelve la lista de product_id
#   favoritos del usuario indicado.
#
#   Demuestra el patrón completo de un microservicio con aiohttp y
#   asyncpg: pool de conexiones compartido via on_startup/on_cleanup,
#   validación de input del usuario (HTTP 400 si {id} no es entero),
#   query parametrizada con $1 para evitar SQL injection, y conversión
#   de Records asyncpg a dicts JSON-serializables.
#
#   El BFF (listing_10_8.py) llama a este servicio concurrentemente
#   junto con productos y carrito. Los favoritos son un dato OPCIONAL:
#   si este servicio no responde en 1 segundo, el BFF devuelve
#   favorite_items=null en lugar de fallar toda la petición.
#
#   Requiere: base de datos 'favorites' con tabla user_favorite
#   (user_id INT, product_id INT). Ver sección 8 del resumen para
#   los comandos de creación e inserción de datos de prueba.
# =============================================================================

import functools                         # Proporciona partial() para pre-aplicar argumentos a funciones
from aiohttp import web                 # Framework web asíncrono
from aiohttp.web_request import Request # Tipo del objeto de petición HTTP entrante
from aiohttp.web_response import Response  # Tipo de retorno del handler
from chapter_10.listing_10_4 import DB_KEY, create_database_pool, destroy_database_pool
# ↑ Importa las utilidades compartidas de DB: la clave del pool y las funciones de ciclo de vida

routes = web.RouteTableDef()            # Registro de rutas del servicio de favoritos


@routes.get('/users/{id}/favorites')   # Asocia GET /users/{id}/favorites a este handler
async def favorites(request: Request) -> Response:
    try:
        user_id = int(request.match_info['id'])  # Extrae el parámetro {id} de la URL y lo convierte a entero
        db = request.app[DB_KEY]                 # Obtiene el pool de conexiones almacenado en la app
        query = 'SELECT product_id FROM user_favorite WHERE user_id = $1'  # Query parametrizada; $1 evita SQL injection
        result = await db.fetch(query, user_id)  # Ejecuta la query pasando user_id como $1; devuelve lista de Records
        if result is not None:                   # fetch() devuelve lista vacía (no None) si no hay filas, pero se comprueba
            return web.json_response([dict(record) for record in result])  # Convierte cada Record a dict y devuelve JSON
        else:
            raise web.HTTPNotFound()             # Devuelve HTTP 404 si no hay resultados
    except ValueError:
        raise web.HTTPBadRequest()               # Devuelve HTTP 400 si {id} no es un entero válido


app = web.Application()                 # Crea la aplicación aiohttp del servicio de favoritos
app.on_startup.append(functools.partial(
    # partial() crea una versión de create_database_pool con los parámetros de DB ya fijados;
    # aiohttp solo pasa 'app' a los hooks on_startup, así que partial inyecta el resto de argumentos
    create_database_pool,
    host='127.0.0.1',       # PostgreSQL en local
    port=5432,              # Puerto estándar de PostgreSQL
    user='postgres',        # Usuario de la BD
    password='password',    # Contraseña de la BD
    database='favorites'    # Base de datos específica de este servicio
))
app.on_cleanup.append(destroy_database_pool)  # Registra el cierre del pool al apagar el servidor
app.add_routes(routes)                        # Registra las rutas definidas arriba
web.run_app(app, port=8002)                   # Arranca el servidor en el puerto 8002
