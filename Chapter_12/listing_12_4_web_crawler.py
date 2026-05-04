"""
Listing 12.4 - Rastreador web (Web Crawler)
Demuestra: patrón especial donde los workers son a la vez productores y
consumidores. Los workers procesan URLs y añaden nuevas URLs a la cola.
Incluye control de URLs ya visitadas para evitar bucles infinitos.
"""
import asyncio
from asyncio import Queue


visited_urls: set = set()


async def crawl_page(url: str, queue: Queue):
    print(f'Descargando: {url}')
    await asyncio.sleep(0.5)  # simula tiempo de descarga

    # simula encontrar nuevos enlaces en la página
    new_links = [f'{url}/link-{i}' for i in range(2)]
    for link in new_links:
        if link not in visited_urls:
            visited_urls.add(link)
            await queue.put(link)
            print(f'  → Nuevo link encontrado: {link}')

    queue.task_done()


async def worker(queue: Queue, worker_id: int):
    while True:
        url = await queue.get()
        print(f'[Worker {worker_id}] Procesando: {url}')
        await crawl_page(url, queue)


async def main():
    queue = Queue()

    # URL inicial (semilla)
    seed_url = 'https://ejemplo.com'
    visited_urls.add(seed_url)
    await queue.put(seed_url)

    print(f'Iniciando rastreo desde: {seed_url}')
    print('-' * 50)

    workers = [asyncio.create_task(worker(queue, i)) for i in range(3)]

    # esperar a que todas las URLs estén procesadas
    await queue.join()

    for w in workers:
        w.cancel()

    print('-' * 50)
    print(f'Rastreo completo. URLs visitadas: {len(visited_urls)}')
    for url in sorted(visited_urls):
        print(f'  {url}')


asyncio.run(main())
