import asyncio
from asyncio import Task
import logging
from typing import Dict, List, Optional, Set, Awaitable

import aiohttp
from aiohttp import web, ClientSession
from aiohttp.web_request import Request
from aiohttp.web_response import Response

routes = web.RouteTableDef()

PRODUCT_BASE = 'http://127.0.0.1:8000'
INVENTORY_BASE = 'http://127.0.0.1:8001'
FAVORITE_BASE = 'http://127.0.0.1:8002'
CART_BASE = 'http://127.0.0.1:8003'


@routes.get('/products/all')
async def all_products(request: Request) -> Response:
    async with aiohttp.ClientSession() as session:
        products = asyncio.create_task(session.get(f'{PRODUCT_BASE}/products'))
        favorites = asyncio.create_task(session.get(f'{FAVORITE_BASE}/users/3/favorites'))
        cart = asyncio.create_task(session.get(f'{CART_BASE}/users/3/cart'))

        requests = [products, favorites, cart]
        done, pending = await asyncio.wait(requests, timeout=1.0)

        if products in pending:
            [req.cancel() for req in requests]
            return web.json_response({'error': 'Could not reach products service.'}, status=504)
        elif products in done and products.exception() is not None:
            [req.cancel() for req in requests]
            logging.exception('Server error reaching product service.', exc_info=products.exception())
            return web.json_response({'error': 'Server error reaching products service.'}, status=500)
        else:
            product_response = await products.result().json()
            product_results = await get_products_with_inventory(session, product_response)
            cart_count = await get_response_item_count(cart, done, pending, 'Error getting user cart.')
            favorite_count = await get_response_item_count(favorites, done, pending, 'Error getting user favorites.')

            return web.json_response({
                'cart_items': cart_count,
                'favorite_items': favorite_count,
                'products': product_results
            })


async def get_products_with_inventory(session: ClientSession, product_response) -> List[Dict]:
    def get_inventory(session: ClientSession, product_id: str) -> Task:
        url = f'{INVENTORY_BASE}/products/{product_id}/inventory'
        return asyncio.create_task(session.get(url))

    def create_product_record(product_id: int, inventory: Optional[int]) -> Dict:
        return {'product_id': product_id, 'inventory': inventory}

    inventory_tasks = {
        get_inventory(session, p['product_id']): p['product_id']
        for p in product_response
    }

    inv_done, inv_pending = await asyncio.wait(inventory_tasks.keys(), timeout=1.0)

    product_results = []

    for task in inv_done:
        product_id = inventory_tasks[task]
        if task.exception() is None:
            inventory = await task.result().json()
            product_results.append(create_product_record(product_id, inventory['inventory']))
        else:
            product_results.append(create_product_record(product_id, None))
            logging.exception(f'Error getting inventory for id {product_id}', exc_info=task.exception())

    for task in inv_pending:
        task.cancel()
        product_id = inventory_tasks[task]
        product_results.append(create_product_record(product_id, None))

    return product_results


async def get_response_item_count(task: Task, done: Set[Awaitable],
                                   pending: Set[Awaitable], error_msg: str) -> Optional[int]:
    if task in done and task.exception() is None:
        return len(await task.result().json())
    elif task in pending:
        task.cancel()
    else:
        logging.exception(error_msg, exc_info=task.exception())
    return None


app = web.Application()
app.add_routes(routes)
web.run_app(app, port=9000)
