# =============================================================================
# listing_10_8.py — Backend-for-Frontend Service (puerto 9000)
# =============================================================================
# Objetivo:
#   Servicio central del capítulo. Implementa el patrón BFF (Backend-
#   for-Frontend): recibe una única petición del cliente y agrega los
#   datos de los cuatro microservicios restantes de forma concurrente.
#
#   Expone GET /products/all y aplica dos niveles de concurrencia:
#
#   Nivel 1 — asyncio.wait con timeout=1s sobre tres peticiones:
#     - GET /products        (obligatorio: HTTP 504 si no responde)
#     - GET /users/3/favorites (opcional: devuelve null si no responde)
#     - GET /users/3/cart      (opcional: devuelve null si no responde)
#
#   Nivel 2 — asyncio.wait con timeout=1s sobre N peticiones:
#     - GET /products/{id}/inventory por cada producto del catálogo
#       (opcional por producto: inventory=null si ese no responde)
#
#   La separación entre done y pending que devuelve asyncio.wait es
#   clave: permite tratar de forma diferente los datos obligatorios
#   (productos) y los opcionales (inventario, carrito, favoritos),
#   cancelando siempre las tasks pendientes para liberar recursos.
#
#   Este servicio no tiene base de datos propia ni on_startup/on_cleanup.
#   Depende de que los cuatro microservicios estén corriendo antes de
#   recibir peticiones.
# =============================================================================

import asyncio                          # Proporciona create_task() y wait() para concurrencia
from asyncio import Task               # Tipo Task para type hints
import logging                         # Registra errores de servicios externos sin interrumpir el flujo
from typing import Dict, List, Optional, Set, Awaitable  # Type hints

import aiohttp                         # Cliente HTTP asíncrono para llamar a los microservicios
from aiohttp import web, ClientSession # web: framework servidor; ClientSession: cliente HTTP reutilizable
from aiohttp.web_request import Request
from aiohttp.web_response import Response

routes = web.RouteTableDef()           # Registro de rutas del BFF

# URLs base de cada microservicio; centralizar aquí facilita cambiarlos sin tocar la lógica
PRODUCT_BASE   = 'http://127.0.0.1:8000'
INVENTORY_BASE = 'http://127.0.0.1:8001'
FAVORITE_BASE  = 'http://127.0.0.1:8002'
CART_BASE      = 'http://127.0.0.1:8003'


@routes.get('/products/all')           # Endpoint único del BFF; el cliente solo llama aquí
async def all_products(request: Request) -> Response:
    async with aiohttp.ClientSession() as session:   # Abre una sesión HTTP; se cierra automáticamente al salir del bloque
        # Lanza las 3 peticiones como tasks concurrentes sin esperar ninguna todavía
        products  = asyncio.create_task(session.get(f'{PRODUCT_BASE}/products'))
        favorites = asyncio.create_task(session.get(f'{FAVORITE_BASE}/users/3/favorites'))
        cart      = asyncio.create_task(session.get(f'{CART_BASE}/users/3/cart'))

        requests = [products, favorites, cart]
        done, pending = await asyncio.wait(requests, timeout=1.0)
        # ↑ Espera máximo 1 segundo; devuelve 'done' (terminadas) y 'pending' (aún en curso)

        if products in pending:
            # El servicio de productos es obligatorio; si no responde en 1s → Gateway Timeout
            [req.cancel() for req in requests]       # Cancela todas las tasks para no dejarlas colgadas
            return web.json_response({'error': 'Could not reach products service.'}, status=504)

        elif products in done and products.exception() is not None:
            # Productos respondió pero con una excepción → error interno del servidor
            [req.cancel() for req in requests]       # Cancela el resto de tasks
            logging.exception('Server error reaching product service.', exc_info=products.exception())
            return web.json_response({'error': 'Server error reaching products service.'}, status=500)

        else:
            # Productos respondió correctamente; carrito y favoritos son opcionales
            product_response = await products.result().json()  # result() devuelve la ClientResponse; .json() la deserializa
            product_results  = await get_products_with_inventory(session, product_response)  # Obtiene inventario en paralelo
            cart_count       = await get_response_item_count(cart,      done, pending, 'Error getting user cart.')
            favorite_count   = await get_response_item_count(favorites, done, pending, 'Error getting user favorites.')
            # ↑ Ambas funciones devuelven None si el servicio no respondió a tiempo (datos opcionales)

            return web.json_response({
                'cart_items':     cart_count,      # None si el servicio de carrito falló o superó el timeout
                'favorite_items': favorite_count,  # None si el servicio de favoritos falló o superó el timeout
                'products':       product_results  # Lista con inventario por producto (None si ese inventario falló)
            })


async def get_products_with_inventory(session: ClientSession, product_response) -> List[Dict]:
    def get_inventory(session: ClientSession, product_id: str) -> Task:
        url = f'{INVENTORY_BASE}/products/{product_id}/inventory'
        return asyncio.create_task(session.get(url))  # Crea una task para cada producto sin bloquear

    def create_product_record(product_id: int, inventory: Optional[int]) -> Dict:
        return {'product_id': product_id, 'inventory': inventory}  # Estructura del registro de producto en la respuesta

    # Dict {task: product_id} para saber a qué producto pertenece cada task cuando termine
    inventory_tasks = {
        get_inventory(session, p['product_id']): p['product_id']
        for p in product_response
    }

    inv_done, inv_pending = await asyncio.wait(inventory_tasks.keys(), timeout=1.0)
    # ↑ Lanza todas las peticiones de inventario en paralelo con timeout de 1 segundo

    product_results = []

    for task in inv_done:                                  # Procesa las tasks que terminaron dentro del timeout
        product_id = inventory_tasks[task]                 # Recupera el product_id asociado a esta task
        if task.exception() is None:                       # Terminó sin error → incluye el inventario real
            inventory = await task.result().json()         # Deserializa la respuesta JSON del servicio de inventario
            product_results.append(create_product_record(product_id, inventory['inventory']))
        else:                                              # Terminó con error → inventario None, se registra el error
            product_results.append(create_product_record(product_id, None))
            logging.exception(f'Error getting inventory for id {product_id}', exc_info=task.exception())

    for task in inv_pending:                               # Procesa las tasks que NO terminaron en 1 segundo
        task.cancel()                                      # Cancela la task para liberar recursos del event loop
        product_id = inventory_tasks[task]
        product_results.append(create_product_record(product_id, None))  # Inventario None por timeout

    return product_results


async def get_response_item_count(task: Task, done: Set[Awaitable],
                                   pending: Set[Awaitable], error_msg: str) -> Optional[int]:
    if task in done and task.exception() is None:
        return len(await task.result().json())  # Cuenta los elementos del JSON devuelto por el servicio
    elif task in pending:
        task.cancel()                           # Cancela si no terminó; devuelve None implícitamente
    else:
        logging.exception(error_msg, exc_info=task.exception())  # Estaba en done pero con excepción
    return None                                 # Retorna None para carrito/favoritos opcionales no disponibles


app = web.Application()        # El BFF no necesita base de datos propia, solo enruta peticiones
app.add_routes(routes)         # Registra el único endpoint /products/all
web.run_app(app, port=9000)    # Arranca el BFF en el puerto 9000
