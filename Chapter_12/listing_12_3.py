"""
Listing 12.3 - Cola integrada en aplicación web con aiohttp
Demuestra: endpoint POST /order que responde inmediatamente mientras
5 workers procesan pedidos en segundo plano. Arranque y apagado limpio.

Requiere: pip install aiohttp
Ejecutar: python listing_12_3.py
Probar:   curl -X POST http://localhost:8080/order
"""
import asyncio
from asyncio import Queue, Task
from typing import List
from random import randrange
from aiohttp import web
from aiohttp.web_app import Application
from aiohttp.web_request import Request
from aiohttp.web_response import Response


routes = web.RouteTableDef()

QUEUE_KEY = 'order_queue'
TASKS_KEY = 'order_tasks'


async def process_order_worker(worker_id: int, queue: Queue):
    while True:
        print(f'Worker {worker_id}: Esperando un pedido...')
        order = await queue.get()
        print(f'Worker {worker_id}: Procesando pedido {order}')
        await asyncio.sleep(order)
        print(f'Worker {worker_id}: Pedido {order} completado')
        queue.task_done()


@routes.post('/order')
async def place_order(request: Request) -> Response:
    order_queue = app[QUEUE_KEY]
    await order_queue.put(randrange(5))
    return Response(body='¡Pedido recibido!')


async def create_order_queue(app: Application):
    print('Creando cola de pedidos y workers.')
    queue: Queue = asyncio.Queue(maxsize=10)
    app[QUEUE_KEY] = queue
    app[TASKS_KEY] = [asyncio.create_task(process_order_worker(i, queue))
                      for i in range(5)]


async def destroy_queue(app: Application):
    order_tasks: List[Task] = app[TASKS_KEY]
    queue: Queue = app[QUEUE_KEY]
    print('Esperando a que los workers terminen...')
    try:
        await asyncio.wait_for(queue.join(), timeout=10)
    finally:
        print('Cancelando workers...')
        [task.cancel() for task in order_tasks]


app = web.Application()
app.on_startup.append(create_order_queue)
app.on_shutdown.append(destroy_queue)

app.add_routes(routes)
web.run_app(app)
