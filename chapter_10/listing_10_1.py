# =============================================================================
# listing_10_1.py — Inventory Service (puerto 8001)
# =============================================================================
# Objetivo:
#   Microservicio que simula un servicio de inventario de productos.
#   Expone un único endpoint GET /products/{id}/inventory que devuelve
#   el stock disponible de un producto como número aleatorio (0-100).
#
#   Para reproducir la variabilidad real de un servicio de inventario
#   (consulta a BD, caché, red interna), introduce un delay aleatorio
#   de 0 a 5 segundos antes de responder. Este comportamiento es clave
#   para el capítulo: el BFF (listing_10_8.py) usa asyncio.wait con
#   timeout=1s para las peticiones de inventario, por lo que este
#   servicio responderá a tiempo solo cuando el delay sea 0s.
#
#   No tiene base de datos ni on_startup/on_cleanup. Es el servicio
#   más simple del capítulo y sirve como punto de partida para
#   entender la estructura básica de un microservicio con aiohttp.
# =============================================================================

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
