"""
Listing 12.5 y 12.6 - Cola con prioridad (PriorityQueue)
Demuestra: asyncio.PriorityQueue donde los elementos con menor número
de prioridad se procesan primero. Incluye ejemplo con tuplas y con dataclass.
"""
import asyncio
from asyncio import PriorityQueue
from dataclasses import dataclass, field
from typing import Any


# ─── Ejemplo A: PriorityQueue con tuplas ─────────────────────────────────────

async def example_with_tuples():
    print('=== Ejemplo A: PriorityQueue con tuplas ===')
    queue = PriorityQueue()

    await queue.put((3, 'Pedido normal'))
    await queue.put((1, 'Pedido URGENTE'))
    await queue.put((2, 'Pedido prioritario'))
    await queue.put((3, 'Otro pedido normal'))

    print('Procesando en orden de prioridad:')
    while not queue.empty():
        priority, item = await queue.get()
        print(f'  Prioridad {priority}: {item}')
        queue.task_done()

    print()


# ─── Ejemplo B: PriorityQueue con dataclass ───────────────────────────────────

@dataclass(order=True)
class PrioritizedItem:
    priority: int
    item: Any = field(compare=False)  # el contenido no afecta la comparación


async def worker(queue: PriorityQueue, worker_id: int):
    while True:
        prioritized = await queue.get()
        print(f'Worker {worker_id} (prioridad {prioritized.priority}): {prioritized.item}')
        await asyncio.sleep(0.2)
        queue.task_done()


async def example_with_dataclass():
    print('=== Ejemplo B: PriorityQueue con dataclass y workers ===')
    queue = PriorityQueue()

    await queue.put(PrioritizedItem(priority=5, item='Tarea rutinaria A'))
    await queue.put(PrioritizedItem(priority=1, item='URGENTE: fallo en producción'))
    await queue.put(PrioritizedItem(priority=3, item='Tarea importante B'))
    await queue.put(PrioritizedItem(priority=2, item='Tarea crítica C'))
    await queue.put(PrioritizedItem(priority=4, item='Tarea menor D'))

    workers = [asyncio.create_task(worker(queue, i)) for i in range(2)]

    await queue.join()
    for w in workers:
        w.cancel()

    print()


async def main():
    await example_with_tuples()
    await example_with_dataclass()
    print('Todos los ejemplos completados.')


asyncio.run(main())
