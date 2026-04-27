import functools                         # Proporciona partial() para pre-aplicar argumentos a funciones
from aiohttp import web                 # Framework web asíncrono
from aiohttp.web_request import Request # Tipo del objeto de petición HTTP entrante
from aiohttp.web_response import Response  # Tipo de retorno del handler
from chapter_10.listing_10_4 import DB_KEY, create_database_pool, destroy_database_pool
# ↑ Importa las utilidades compartidas de DB: la clave del pool y las funciones de ciclo de vida

routes = web.RouteTableDef()            # Registro de rutas del servicio de carrito


@routes.get('/users/{id}/cart')        # Asocia GET /users/{id}/cart a este handler
async def cart(request: Request) -> Response:
    try:
        user_id = int(request.match_info['id'])  # Extrae el parámetro {id} de la URL y lo convierte a entero
        db = request.app[DB_KEY]                 # Obtiene el pool de conexiones almacenado en la app
        query = 'SELECT product_id FROM user_cart WHERE user_id = $1'  # Query parametrizada; $1 evita SQL injection
        result = await db.fetch(query, user_id)  # Ejecuta la query pasando user_id como $1; devuelve lista de Records
        if result is not None:                   # Comprueba que hay resultados antes de serializar
            return web.json_response([dict(record) for record in result])  # Convierte cada Record a dict y devuelve JSON
        else:
            raise web.HTTPNotFound()             # Devuelve HTTP 404 si no hay resultados
    except ValueError:
        raise web.HTTPBadRequest()               # Devuelve HTTP 400 si {id} no es un entero válido


app = web.Application()                 # Crea la aplicación aiohttp del servicio de carrito
app.on_startup.append(functools.partial(
    # partial() pre-aplica los parámetros de conexión; aiohttp solo pasa 'app' a los hooks on_startup
    create_database_pool,
    host='127.0.0.1',       # PostgreSQL en local
    port=5432,              # Puerto estándar de PostgreSQL
    user='postgres',        # Usuario de la BD
    password='password',    # Contraseña de la BD
    database='cart'         # Base de datos específica de este servicio (distinta de 'favorites')
))
app.on_cleanup.append(destroy_database_pool)  # Registra el cierre del pool al apagar el servidor
app.add_routes(routes)                        # Registra las rutas definidas arriba
web.run_app(app, port=8003)                   # Arranca el servidor en el puerto 8003
