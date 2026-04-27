import functools                         # Proporciona partial() para pre-aplicar argumentos a funciones
from aiohttp import web                 # Framework web asíncrono
from aiohttp.web_request import Request # Tipo del objeto de petición HTTP entrante
from aiohttp.web_response import Response  # Tipo de retorno del handler
from chapter_10.listing_10_4 import DB_KEY, create_database_pool, destroy_database_pool
# ↑ Importa las utilidades compartidas de DB: la clave del pool y las funciones de ciclo de vida

routes = web.RouteTableDef()            # Registro de rutas del servicio de productos


@routes.get('/products')               # Asocia GET /products a este handler
async def products(request: Request) -> Response:
    db = request.app[DB_KEY]           # Obtiene el pool de conexiones almacenado en la aplicación
    result = await db.fetch('SELECT product_id, product_name FROM product')  # Devuelve todos los productos de la tabla
    return web.json_response([dict(record) for record in result])  # Convierte cada Record asyncpg a dict y serializa a JSON


app = web.Application()                 # Crea la aplicación aiohttp del servicio de productos
app.on_startup.append(functools.partial(
    # partial() pre-aplica los parámetros de conexión; aiohttp solo pasa 'app' a los hooks on_startup
    create_database_pool,
    host='127.0.0.1',       # PostgreSQL en local
    port=5432,              # Puerto estándar de PostgreSQL
    user='postgres',        # Usuario de la BD
    password='password',    # Contraseña de la BD
    database='products'     # Base de datos con la tabla 'product' (creada en el capítulo 5)
))
app.on_cleanup.append(destroy_database_pool)  # Registra el cierre del pool al apagar el servidor
app.add_routes(routes)                        # Registra las rutas definidas arriba
web.run_app(app, port=8000)                   # Arranca el servidor en el puerto 8000
