"""
Listing 12.7 y 12.8 - Cola LIFO (LifoQueue)
Demuestra: asyncio.LifoQueue donde el último elemento añadido es el
primero en procesarse (Last In, First Out - como una pila de platos).
"""
import asyncio
from asyncio import LifoQueue


# ─── Ejemplo A: LifoQueue básica ─────────────────────────────────────────────

async def example_basic_lifo():
    print('=== Ejemplo A: LifoQueue básica ===')
    queue = LifoQueue()

    await queue.put('Primera tarea')
    await queue.put('Segunda tarea')
    await queue.put('Tercera tarea')

    print('Procesando en orden LIFO (último en entrar, primero en salir):')
    while not queue.empty():
        item = await queue.get()
        print(f'  Procesando: {item}')
        queue.task_done()

    print()


# ─── Ejemplo B: LifoQueue con workers ────────────────────────────────────────

async def worker(queue: LifoQueue, worker_id: int):
    while True:
        task = await queue.get()
        print(f'Worker {worker_id} procesando: {task}')
        await asyncio.sleep(0.2)
        queue.task_done()


async def example_with_workers():
    print('=== Ejemplo B: LifoQueue con múltiples workers ===')
    queue = LifoQueue()

    for i in range(1, 8):
        await queue.put(f'Tarea {i}')
        print(f'Añadida: Tarea {i}')

    print('\nProcesando...')
    workers = [asyncio.create_task(worker(queue, i)) for i in range(2)]

    await queue.join()
    for w in workers:
        w.cancel()

    print('Todas las tareas completadas.\n')


# ─── Ejemplo C: Comparación FIFO vs LIFO ─────────────────────────────────────

async def example_comparison():
    print('=== Ejemplo C: Comparación FIFO vs LIFO ===')
    import asyncio

    fifo_queue = asyncio.Queue()
    lifo_queue = asyncio.LifoQueue()

    items = ['A', 'B', 'C', 'D', 'E']

    for item in items:
        await fifo_queue.put(item)
        await lifo_queue.put(item)

    fifo_result = []
    while not fifo_queue.empty():
        fifo_result.append(fifo_queue.get_nowait())

    lifo_result = []
    while not lifo_queue.empty():
        lifo_result.append(lifo_queue.get_nowait())

    print(f'Items añadidos:    {items}')
    print(f'FIFO (Queue):      {fifo_result}')
    print(f'LIFO (LifoQueue):  {lifo_result}')


async def main():
    await example_basic_lifo()
    await example_with_workers()
    await example_comparison()


asyncio.run(main())
