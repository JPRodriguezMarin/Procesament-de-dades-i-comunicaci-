import asyncio                          # Proporciona asyncio.sleep para simular latencia sin bloquear el event loop
import random                           # Genera números aleatorios para el delay y el inventario
from aiohttp import web                 # Framework web asíncrono; 'web' expone Application, RouteTableDef, json_response, etc.
from aiohttp.web_response import Response  # Tipo de retorno de los handlers HTTP

routes = web.RouteTableDef()            # Registro de rutas; permite usar @routes.get(...) como decorador


@routes.get('/products/{id}/inventory') # Asocia GET /products/{id}/inventory a este handler; {id} es un parámetro de ruta
async def get_inventory(request) -> Response:
    delay: int = random.randint(0, 5)   # Elige un delay aleatorio entre 0 y 5 segundos para simular latencia de red
    await asyncio.sleep(delay)          # Pausa la corutina 'delay' segundos sin bloquear el event loop
    inventory: int = random.randint(0, 100)  # Genera un número de inventario aleatorio entre 0 y 100
    return web.json_response({'inventory': inventory})  # Serializa el dict a JSON y devuelve HTTP 200


app = web.Application()                 # Crea la instancia principal de la aplicación aiohttp
app.add_routes(routes)                  # Registra todas las rutas definidas en el RouteTableDef
web.run_app(app, port=8001)             # Arranca el servidor HTTP escuchando en el puerto 8001
