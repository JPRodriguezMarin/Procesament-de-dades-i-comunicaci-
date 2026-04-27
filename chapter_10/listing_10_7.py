# =============================================================================
# listing_10_7.py — Product Service (puerto 8000)
# =============================================================================
# Objetivo:
#   Microservicio que devuelve el catálogo completo de productos.
#   Expone GET /products, consulta la tabla 'product' de la base de
#   datos 'products' y devuelve la lista de todos los productos con
#   su product_id y product_name.
#
#   Es el servicio MÁS CRÍTICO del sistema: el BFF (listing_10_8.py)
#   lo trata como dato OBLIGATORIO. Si no responde en 1 segundo, el
#   BFF devuelve HTTP 504 inmediatamente sin intentar obtener el
#   inventario, el carrito ni los favoritos. Sin el catálogo de
#   productos, no tiene sentido mostrar ningún dato al cliente.
#
#   A diferencia de los servicios de carrito y favoritos, este no
#   recibe parámetros del usuario (sin {id} en la ruta), por lo que
#   no necesita validación de input ni manejo de HTTP 400/404.
#
#   Requiere: base de datos 'products' con tabla 'product' creada
#   por los listings del capítulo 5 (listing_5_3.py a listing_5_6.py).
#   Esta BD es un prerequisito del capítulo 10 que viene del cap. 5.
# =============================================================================

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
