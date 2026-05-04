# Capítulo 12: Colas Asíncronas con asyncio

> **Documento de estudio — basado en *Python Concurrency with asyncio* de Matthew Fowler**
> Nivel: principiante en el tema. Lenguaje sencillo y analogías prácticas.

---

## Introducción

Imagina que tienes una tienda online muy popular. Cada vez que alguien hace un pedido, tu servidor necesita hablar con un sistema externo lento (el almacén, el banco, el proveedor de envíos). Si esperas a que cada pedido termine antes de atender al siguiente, los usuarios esperarán eternamente. La solución: **las colas**.

Una **cola asíncrona** en Python es una estructura que permite:
- Acumular trabajo pendiente de forma ordenada.
- Que varios "trabajadores" (workers) lo procesen en paralelo.
- Que el servidor responda de inmediato al usuario mientras el trabajo ocurre en segundo plano.

Este capítulo enseña tres tipos de colas que ofrece `asyncio`:

| Tipo | Clase | Orden de procesado |
|------|-------|--------------------|
| Normal (FIFO) | `asyncio.Queue` | Primero en entrar, primero en salir |
| Prioridad | `asyncio.PriorityQueue` | Las tareas urgentes van antes |
| Pila (LIFO) | `asyncio.LifoQueue` | Último en entrar, primero en salir |

Al acabar este capítulo sabrás elegir la cola adecuada para cada problema, integrarla en una API web y evitar errores comunes de concurrencia.

---

## Sección 12.1 — Fundamentos de las colas asíncronas

### Objetivo

Entender qué es una cola, cuáles son sus operaciones básicas, y cómo implementar el patrón **productor-consumidor** con `asyncio.Queue`.

---

### Concepto clave: el patrón Productor-Consumidor

```
[Productor] ──put──▶ [  COLA  ] ──get──▶ [Worker 1]
                                  ──get──▶ [Worker 2]
                                  ──get──▶ [Worker 3]
```

- El **productor** genera trabajo y lo mete en la cola.
- Los **workers (consumidores)** sacan trabajo de la cola y lo ejecutan.
- La cola actúa de intermediaria: desacopla al productor de los consumidores.

### Analogía: el supermercado

| Supermercado | asyncio |
|---|---|
| Clientes con productos | Tareas a procesar |
| Cajeros | Workers (corrutinas) |
| La fila de espera | `asyncio.Queue` |
| El cajero llama "siguiente" | `await queue.get()` |
| El cajero termina | `queue.task_done()` |

---

### Métodos de `asyncio.Queue`

#### Añadir y sacar elementos — versiones **no bloqueantes**

```python
queue.put_nowait(item)    # Añade inmediatamente. Lanza QueueFull si está llena.
item = queue.get_nowait() # Saca inmediatamente. Lanza QueueEmpty si está vacía.
```

Estas versiones son **funciones normales** (no se usa `await`). Si la cola no puede atender la petición en ese instante, lanzan una excepción.

#### Añadir y sacar elementos — versiones **bloqueantes (corrutinas)**

```python
await queue.put(item)    # Espera hasta que haya espacio y añade el elemento.
item = await queue.get() # Espera hasta que haya un elemento y lo saca.
```

Estas versiones usan `await`. Si la cola está llena o vacía, la corrutina **pausa** (cede el control al event loop) sin bloquear el hilo. Son las más usadas en aplicaciones reales.

#### Control del trabajo completado

```python
queue.task_done()   # Llama esto después de procesar cada elemento.
await queue.join()  # Espera hasta que TODOS los elementos hayan llamado task_done().
```

La cola lleva un contador interno:
- Sube en 1 cada vez que sacas un elemento con `get()`.
- Baja en 1 cada vez que llamas a `task_done()`.
- `join()` espera hasta que el contador llegue a 0.

> ⚠️ **Error frecuente:** Si olvidas llamar `task_done()`, `join()` esperará para siempre.
> **Buena práctica:** Envuelve el procesado en `try/finally` para garantizar que `task_done()` siempre se ejecuta.

---

### Listado 12.1 — Cola de supermercado básica

**Descripción:** 10 clientes con productos aleatorios entran en una cola. Tres cajeros los atienden al mismo tiempo usando `get_nowait` y `put_nowait`.

```python
import asyncio
from asyncio import Queue
from random import randrange
from typing import List


class Product:
    def __init__(self, name: str, checkout_time: float):
        self.name = name
        self.checkout_time = checkout_time  # segundos para procesar este producto


class Customer:
    def __init__(self, customer_id, products: List[Product]):
        self.customer_id = customer_id
        self.products = products


async def checkout_customer(queue: Queue, cashier_number: int):
    while not queue.empty():                               # (1) trabaja mientras haya clientes
        customer: Customer = queue.get_nowait()            # saca cliente sin esperar
        print(f'Cajero {cashier_number} atiende cliente {customer.customer_id}')
        for product in customer.products:                  # (2) escanea cada producto
            print(f"Cajero {cashier_number} escanea {product.name}")
            await asyncio.sleep(product.checkout_time)     # simula tiempo de escaneo
        print(f'Cajero {cashier_number} termina con cliente {customer.customer_id}')
        queue.task_done()                                  # (3) marca el cliente como procesado


async def main():
    customer_queue = Queue()

    all_products = [Product('cerveza', 2),
                    Product('plátanos', .5),
                    Product('salchicha', .2),
                    Product('pañales', .2)]

    for i in range(10):                                    # (4) genera 10 clientes aleatorios
        products = [all_products[randrange(len(all_products))]
                    for _ in range(randrange(10))]
        customer_queue.put_nowait(Customer(i, products))   # mete cliente en cola

    cashiers = [asyncio.create_task(checkout_customer(customer_queue, i))
                for i in range(3)]                         # (5) lanza 3 cajeros en paralelo

    await asyncio.gather(customer_queue.join(), *cashiers)


asyncio.run(main())
```

**¿Qué ocurre paso a paso?**
1. Se crean 10 clientes y se meten en la cola con `put_nowait`.
2. Se crean 3 tareas (cajeros) que trabajan en paralelo.
3. Cada cajero revisa si la cola tiene clientes (`while not queue.empty()`), saca uno con `get_nowait` y lo procesa.
4. `gather` espera a que la cola esté vacía Y todos los cajeros terminen.

**Salida típica:**
```
Cajero 0 atiende cliente 0
Cajero 1 atiende cliente 1
Cajero 2 atiende cliente 2
Cajero 0 escanea cerveza
Cajero 1 escanea plátanos
...
```

---

### Listado 12.2 — Productor continuo con corrutinas `get` y `put`

**Descripción:** Mejora del anterior. Un **productor** genera clientes continuamente (cada segundo). Los cajeros usan `await queue.get()` para esperar si no hay clientes. La cola tiene un límite máximo de 5 clientes.

```python
import asyncio
from asyncio import Queue
from random import randrange
from typing import List


class Product:
    def __init__(self, name: str, checkout_time: float):
        self.name = name
        self.checkout_time = checkout_time


class Customer:
    def __init__(self, customer_id, products: List[Product]):
        self.customer_id = customer_id
        self.products = products


async def checkout_customer(queue: Queue, cashier_number: int):
    while True:                                            # trabaja indefinidamente
        customer: Customer = await queue.get()            # espera si no hay clientes
        print(f'Cajero {cashier_number} atiende cliente {customer.customer_id}')
        for product in customer.products:
            print(f"Cajero {cashier_number} escanea {product.name}")
            await asyncio.sleep(product.checkout_time)
        print(f'Cajero {cashier_number} termina con cliente {customer.customer_id}')
        queue.task_done()


def generate_customer(customer_id: int) -> Customer:
    all_products = [Product('cerveza', 2),
                    Product('plátanos', .5),
                    Product('salchicha', .2),
                    Product('pañales', .2)]
    products = [all_products[randrange(len(all_products))]
                for _ in range(randrange(10))]
    return Customer(customer_id, products)


async def customer_generator(queue: Queue):               # (1) productor
    customer_count = 0

    while True:
        customers = [generate_customer(i)
                     for i in range(customer_count,
                                    customer_count + randrange(5))]
        for customer in customers:
            print('Esperando espacio en la cola...')
            await queue.put(customer)                     # espera si la cola está llena
            print('¡Cliente en la cola!')
        customer_count = customer_count + len(customers)
        await asyncio.sleep(1)                            # genera clientes cada 1 segundo


async def main():
    customer_queue = Queue(5)                             # máximo 5 clientes en cola

    customer_producer = asyncio.create_task(customer_generator(customer_queue))

    cashiers = [asyncio.create_task(checkout_customer(customer_queue, i))
                for i in range(3)]

    await asyncio.gather(customer_producer, *cashiers)


asyncio.run(main())
```

**Diferencias clave con el Listado 12.1:**
- Los cajeros usan `await queue.get()` → si la cola está vacía, esperan en lugar de crashear.
- El productor usa `await queue.put()` → si la cola está llena (5 clientes), espera hasta que un cajero libere espacio.
- El sistema funciona indefinidamente (bucle `while True` en ambos lados).

---

### Glosario de la Sección 12.1

| Término | Definición |
|---------|-----------|
| **Cola (Queue)** | Estructura de datos FIFO: primero en entrar, primero en salir |
| **FIFO** | First In, First Out — orden de llegada |
| **Productor** | Corrutina que genera trabajo y lo mete en la cola |
| **Consumidor / Worker** | Corrutina que saca trabajo de la cola y lo procesa |
| **`asyncio.Queue`** | Implementación de cola thread-safe para asyncio |
| **`put_nowait(item)`** | Añade elemento a la cola. Lanza `QueueFull` si está llena |
| **`get_nowait()`** | Saca elemento de la cola. Lanza `QueueEmpty` si está vacía |
| **`await queue.put(item)`** | Añade elemento. Pausa y espera si la cola está llena |
| **`await queue.get()`** | Saca elemento. Pausa y espera si la cola está vacía |
| **`task_done()`** | Señala que el elemento extraído fue procesado |
| **`await queue.join()`** | Espera hasta que todos los elementos estén procesados |
| **`QueueFull`** | Excepción cuando `put_nowait` falla por cola llena |
| **`QueueEmpty`** | Excepción cuando `get_nowait` falla por cola vacía |
| **`maxsize`** | Parámetro de `Queue(maxsize=N)` para limitar el tamaño |
| **Patrón Productor-Consumidor** | Separación entre generación y procesado de trabajo |

---

## Sección 12.1.1 — Colas en Aplicaciones Web

### Objetivo

Aprender a integrar una cola asyncio en una API web con `aiohttp` para que el servidor responda inmediatamente al usuario mientras los pedidos se procesan en segundo plano.

---

### El problema que resuelve

**Sin cola:** El endpoint espera a que el sistema lento responda antes de devolver la respuesta HTTP. El usuario espera segundos.

```
POST /order → [procesa pedido 3 segundos] → HTTP 200 ¡Pedido listo!
```

**Con cola:** El endpoint mete el pedido en la cola y responde al instante. Un worker lo procesa en segundo plano.

```
POST /order → [mete en cola] → HTTP 200 ¡Pedido recibido!
                ↓
          [worker procesa 3 segundos en segundo plano]
```

### Ventajas

1. **Respuesta inmediata** para el usuario.
2. **Control de concurrencia** — si tienes 5 workers, como máximo 5 pedidos se procesan simultáneamente. Protege al sistema lento de sobrecarga.
3. **Desacoplamiento** — el endpoint no sabe nada del sistema de procesado.

### Limitación importante

Las colas asyncio son **solo en memoria (RAM)**. Si el servidor se cae o se reinicia, todos los pedidos pendientes en la cola **se pierden**. Para datos críticos (pedidos reales, transacciones) se necesita una solución con persistencia como Celery + RabbitMQ.

---

### Listado 12.3 — Cola integrada en una aplicación web (aiohttp)

**Descripción:** Una API REST con un endpoint `POST /order`. Los pedidos entran en una cola. Cinco workers los procesan en paralelo. La cola y los workers se crean al arrancar la app y se limpian al apagarla.

```python
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


async def process_order_worker(worker_id: int, queue: Queue):   # (1) worker de pedidos
    while True:
        print(f'Worker {worker_id}: Esperando un pedido...')
        order = await queue.get()
        print(f'Worker {worker_id}: Procesando pedido {order}')
        await asyncio.sleep(order)                               # simula tiempo de procesado
        print(f'Worker {worker_id}: Pedido {order} completado')
        queue.task_done()


@routes.post('/order')
async def place_order(request: Request) -> Response:            # (2) endpoint HTTP
    order_queue = app[QUEUE_KEY]
    await order_queue.put(randrange(5))                          # mete pedido en cola
    return Response(body='¡Pedido recibido!')                    # respuesta INMEDIATA


async def create_order_queue(app: Application):                  # (3) hook de arranque
    print('Creando cola de pedidos y workers.')
    queue: Queue = asyncio.Queue(10)                             # máximo 10 pedidos en cola
    app[QUEUE_KEY] = queue
    app[TASKS_KEY] = [asyncio.create_task(process_order_worker(i, queue))
                      for i in range(5)]                         # 5 workers


async def destroy_queue(app: Application):                       # (4) hook de apagado
    order_tasks: List[Task] = app[TASKS_KEY]
    queue: Queue = app[QUEUE_KEY]
    print('Esperando a que los workers terminen...')
    try:
        await asyncio.wait_for(queue.join(), timeout=10)         # espera máx. 10 segundos
    finally:
        print('Cancelando workers...')
        [task.cancel() for task in order_tasks]                  # cancela todos los workers


app = web.Application()
app.on_startup.append(create_order_queue)    # se ejecuta al arrancar
app.on_shutdown.append(destroy_queue)        # se ejecuta al apagar

app.add_routes(routes)
web.run_app(app)
```

**Flujo completo de un pedido:**
```
1. Cliente → POST /order
2. Endpoint → await order_queue.put(pedido)
3. Endpoint → return Response('¡Pedido recibido!') ← respuesta inmediata
4. Worker libre → await queue.get() → obtiene el pedido
5. Worker → procesa el pedido (3-4 segundos)
6. Worker → queue.task_done() → listo para el siguiente
```

**Apagado limpio (graceful shutdown):**
- Al recibir señal de apagado, se llama a `destroy_queue`.
- Espera hasta 10 segundos a que los pedidos en curso terminen.
- Cancela los workers aunque no hayan terminado (si pasan los 10 segundos).

---

### Glosario de la Sección 12.1.1

| Término | Definición |
|---------|-----------|
| **`aiohttp`** | Framework web asíncrono para Python basado en asyncio |
| **`web.RouteTableDef`** | Clase de aiohttp para definir rutas HTTP con decoradores |
| **`on_startup`** | Lista de corrutinas que se ejecutan al arrancar la app aiohttp |
| **`on_shutdown`** | Lista de corrutinas que se ejecutan al apagar la app aiohttp |
| **`app[KEY]`** | Almacenamiento de estado compartido en la aplicación aiohttp |
| **Graceful shutdown** | Apagado limpio: esperar a que el trabajo en curso termine antes de cerrar |
| **`asyncio.wait_for`** | Ejecuta una corrutina con un timeout máximo |
| **`task.cancel()`** | Cancela una tarea asyncio (lanza `CancelledError` en ella) |
| **Persistencia de cola** | Capacidad de que los datos sobrevivan a un reinicio del proceso |
| **Celery + RabbitMQ** | Solución externa para colas con persistencia en disco |
| **`fail fast`** | Filosofía de fallar rápido: si la cola está llena, rechazar la petición inmediatamente |

---

## Sección 12.1.2 — Cola para un Rastreador Web (Web Crawler)

### Objetivo

Entender un patrón especial donde los **consumidores también son productores**: al procesar una URL, encuentran nuevas URLs que añaden a la cola.

---

### El concepto

Un rastreador web (web crawler) visita páginas, extrae los enlaces que contiene, y los visita también. Los workers son a la vez productores (añaden nuevas URLs) y consumidores (procesan URLs):

```
[Cola: "ejemplo.com"]
       ↓
[Worker descarga ejemplo.com] → encuentra links → añade a cola
[Cola: "ejemplo.com/a", "ejemplo.com/b"]
       ↓
[Workers descargan esas páginas] → encuentran más links → añaden a cola
...
```

### Precaución: bucles infinitos

Un crawler real puede entrar en bucles si una página A enlaza a B y B enlaza a A. **Siempre hay que llevar un registro de URLs ya visitadas.**

### Listado 12.4 — Rastreador web básico

```python
import asyncio
from asyncio import Queue


visited_urls = set()   # URLs ya visitadas (evita bucles)


async def crawl_page(url: str, queue: Queue):
    print(f'Descargando: {url}')
    await asyncio.sleep(1)   # simula descarga

    # simula encontrar nuevos enlaces en la página
    new_links = [f'{url}/link-{i}' for i in range(2)]
    for link in new_links:
        if link not in visited_urls:
            visited_urls.add(link)
            await queue.put(link)   # los nuevos links van a la cola

    queue.task_done()


async def worker(queue: Queue, worker_id: int):
    while True:
        url = await queue.get()
        await crawl_page(url, queue)


async def main():
    queue = Queue()

    # URL inicial (semilla)
    seed_url = 'https://ejemplo.com'
    visited_urls.add(seed_url)
    await queue.put(seed_url)

    # crear workers
    workers = [asyncio.create_task(worker(queue, i)) for i in range(3)]

    # esperar a que todo esté procesado
    await queue.join()

    for w in workers:
        w.cancel()


asyncio.run(main())
```

---

### Glosario de la Sección 12.1.2

| Término | Definición |
|---------|-----------|
| **Web Crawler** | Programa que visita páginas web de forma automática siguiendo enlaces |
| **URL semilla (seed URL)** | URL inicial desde la que empieza el rastreo |
| **Consumidor-Productor dual** | Worker que al mismo tiempo consume y produce nuevas tareas |
| **`visited_urls`** | Conjunto (set) de URLs ya procesadas para evitar bucles |
| **Profundidad de rastreo** | Límite de cuántos niveles de enlaces seguir |
| **Bucle infinito en crawler** | Cuando A enlaza a B y B enlaza a A, puede procesarse indefinidamente |

---

## Sección 12.2 — Colas con Prioridad (`asyncio.PriorityQueue`)

### Objetivo

Aprender a procesar tareas según su **urgencia**, no según su orden de llegada, usando `asyncio.PriorityQueue`.

---

### ¿Cuándo usar una cola de prioridad?

Cuando no todos los trabajos son igualmente urgentes. Ejemplos:
- Sistema médico: pacientes críticos antes que consultas rutinarias.
- Sistema de tickets: bugs críticos antes que mejoras estéticas.
- Procesado de pedidos: pedidos VIP antes que pedidos normales.

### Cómo funciona

Los elementos deben ser **comparables** (tuplas o dataclasses con `order=True`). La cola los ordena automáticamente. **Menor número = mayor prioridad:**

```python
await queue.put((1, 'urgente'))    # sale primero
await queue.put((5, 'normal'))     # sale último
await queue.put((2, 'importante')) # sale segundo
```

### Listado 12.5 — Cola con prioridad básica

```python
import asyncio
from asyncio import PriorityQueue


async def main():
    queue = PriorityQueue()

    await queue.put((3, 'Pedido normal'))
    await queue.put((1, 'Pedido urgente'))
    await queue.put((2, 'Pedido prioritario'))
    await queue.put((3, 'Otro pedido normal'))

    print('Procesando en orden de prioridad:')
    while not queue.empty():
        priority, item = await queue.get()
        print(f'  Prioridad {priority}: {item}')
        queue.task_done()


asyncio.run(main())
```

**Salida:**
```
Prioridad 1: Pedido urgente
Prioridad 2: Pedido prioritario
Prioridad 3: Pedido normal
Prioridad 3: Otro pedido normal
```

### Listado 12.6 — Cola con prioridad y dataclass

Usar una tupla funciona, pero si el contenido de la tarea es un string complejo o un objeto, la comparación puede fallar. La solución es un `dataclass`:

```python
import asyncio
from asyncio import PriorityQueue
from dataclasses import dataclass, field
from typing import Any


@dataclass(order=True)
class PrioritizedItem:
    priority: int
    item: Any = field(compare=False)   # el contenido NO participa en la comparación


async def worker(queue: PriorityQueue, worker_id: int):
    while True:
        prioritized = await queue.get()
        print(f'Worker {worker_id} (prioridad {prioritized.priority}): {prioritized.item}')
        await asyncio.sleep(0.5)
        queue.task_done()


async def main():
    queue = PriorityQueue()

    await queue.put(PrioritizedItem(priority=5, item='Tarea rutinaria A'))
    await queue.put(PrioritizedItem(priority=1, item='URGENTE: fallo en producción'))
    await queue.put(PrioritizedItem(priority=3, item='Tarea importante B'))
    await queue.put(PrioritizedItem(priority=2, item='Tarea crítica C'))

    workers = [asyncio.create_task(worker(queue, i)) for i in range(2)]

    await queue.join()
    for w in workers:
        w.cancel()


asyncio.run(main())
```

**Salida:**
```
Worker 0 (prioridad 1): URGENTE: fallo en producción
Worker 1 (prioridad 2): Tarea crítica C
Worker 0 (prioridad 3): Tarea importante B
Worker 1 (prioridad 5): Tarea rutinaria A
```

---

### Glosario de la Sección 12.2

| Término | Definición |
|---------|-----------|
| **`asyncio.PriorityQueue`** | Cola que saca elementos según su prioridad (menor número = antes) |
| **Prioridad** | Valor numérico que determina el orden de procesado |
| **`@dataclass(order=True)`** | Decorador que permite a Python comparar instancias del dataclass automáticamente |
| **`field(compare=False)`** | Indica que ese campo NO se usa al comparar dos dataclasses |
| **Heap interno** | Estructura de datos interna que usa PriorityQueue para ordenar elementos |
| **Elementos comparables** | Elementos que Python puede ordenar (tuplas, dataclasses con `order=True`) |

---

## Sección 12.3 — Colas LIFO (`asyncio.LifoQueue`)

### Objetivo

Entender la estructura **Last In, First Out** (último en entrar, primero en salir) y sus casos de uso.

---

### Analogía: la pila de platos

Imagina una pila de platos sucios:
- Pones un plato encima → es el último en entrar.
- Coges un plato para fregar → coges el de arriba (el último que pusiste).

```
Cola FIFO:  pones [A, B, C] → sacas A, B, C  (orden de llegada)
Cola LIFO:  pones [A, B, C] → sacas C, B, A  (al revés)
```

### Cuándo usar LIFO

- **Algoritmos de búsqueda en profundidad** (DFS — Depth-First Search): explorar el camino más reciente primero.
- **Deshacer acciones** (Ctrl+Z / undo): la última acción es la primera en deshacerse.
- **Procesar los trabajos más nuevos primero:** cuando la frescura importa más que el orden.

### Listado 12.7 — Cola LIFO básica

```python
import asyncio
from asyncio import LifoQueue


async def main():
    queue = LifoQueue()

    await queue.put('Primera tarea')
    await queue.put('Segunda tarea')
    await queue.put('Tercera tarea')

    print('Procesando en orden LIFO:')
    while not queue.empty():
        item = await queue.get()
        print(f'  Procesando: {item}')
        queue.task_done()


asyncio.run(main())
```

**Salida:**
```
Procesando en orden LIFO:
  Procesando: Tercera tarea
  Procesando: Segunda tarea
  Procesando: Primera tarea
```

### Listado 12.8 — Cola LIFO con workers

```python
import asyncio
from asyncio import LifoQueue


async def worker(queue: LifoQueue, worker_id: int):
    while True:
        task = await queue.get()
        print(f'Worker {worker_id} procesando: {task}')
        await asyncio.sleep(0.3)
        queue.task_done()


async def main():
    queue = LifoQueue()

    for i in range(1, 6):
        await queue.put(f'Tarea {i}')
        print(f'Añadida: Tarea {i}')

    workers = [asyncio.create_task(worker(queue, i)) for i in range(2)]

    await queue.join()
    for w in workers:
        w.cancel()

    print('Todas las tareas completadas.')


asyncio.run(main())
```

**Salida:**
```
Worker 0 procesando: Tarea 5
Worker 1 procesando: Tarea 4
Worker 0 procesando: Tarea 3
Worker 1 procesando: Tarea 2
Worker 0 procesando: Tarea 1
Todas las tareas completadas.
```

---

### Glosario de la Sección 12.3

| Término | Definición |
|---------|-----------|
| **`asyncio.LifoQueue`** | Cola que saca el último elemento añadido primero |
| **LIFO** | Last In, First Out — el último en entrar es el primero en salir |
| **Pila (stack)** | Otra forma de llamar a una estructura LIFO |
| **DFS** | Depth-First Search — algoritmo de búsqueda que usa LIFO |
| **Undo** | Operación de "deshacer" que necesita LIFO (última acción se deshace primero) |

---

## Sección 12.4 — Limitaciones y Buenas Prácticas

### Objetivo

Conocer los peligros de las colas asyncio y cómo evitar los errores más comunes.

---

### Limitación 1: Sin persistencia (el gran problema)

Las colas asyncio viven **solo en RAM**. Si el proceso Python muere (crash, reinicio del servidor, apagado), **todos los datos de la cola se pierden sin dejar rastro**.

```
asyncio.Queue  → solo RAM → datos perdidos si cae el proceso ❌
RabbitMQ/Celery → disco + RAM → datos seguros aunque caiga el proceso ✅
```

**Guía de decisión:**

| Situación | Solución |
|-----------|----------|
| Logs, notificaciones no críticas | `asyncio.Queue` (aceptable perder algunos) |
| Pedidos, transacciones, datos importantes | Celery + RabbitMQ o similar |
| Prototipo / aprendizaje | `asyncio.Queue` siempre |

### Limitación 2: Solo un proceso

Las colas asyncio funcionan dentro de **un solo proceso Python**. No se pueden compartir entre varios servidores o procesos distintos. Para escalar a múltiples máquinas se necesita un broker externo.

### Buena práctica: `try/finally` con `task_done()`

Si el procesado de un elemento lanza una excepción y no capturas el error, `task_done()` nunca se llamará y `join()` esperará para siempre.

**Patrón correcto:**
```python
async def worker(queue):
    while True:
        item = await queue.get()
        try:
            await process(item)   # puede lanzar excepciones
        finally:
            queue.task_done()     # siempre se ejecuta, incluso si hubo error
```

### Buena práctica: timeout en `join()` al apagar

Sin timeout, si un worker tarda demasiado, la aplicación nunca se apagaría:
```python
try:
    await asyncio.wait_for(queue.join(), timeout=10)  # máximo 10 segundos
finally:
    [task.cancel() for task in worker_tasks]  # cancela workers pase lo que pase
```

---

### Glosario de la Sección 12.4

| Término | Definición |
|---------|-----------|
| **Persistencia** | Capacidad de que los datos sobrevivan a un fallo del proceso |
| **Broker de mensajes** | Sistema externo (RabbitMQ, Redis, etc.) que gestiona colas con persistencia |
| **Celery** | Librería Python para colas de tareas distribuidas y persistentes |
| **RabbitMQ** | Software de broker de mensajes muy usado en producción |
| **`try/finally`** | Bloque Python que garantiza que el código de `finally` siempre se ejecuta |
| **Graceful shutdown** | Apagado limpio: terminar el trabajo en curso antes de cerrar |
| **Timeout** | Tiempo máximo de espera antes de abortar una operación |
| **Single-process limitation** | Las colas asyncio no se comparten entre procesos distintos |

---

## Resumen comparativo — Los tres tipos de cola

| | `asyncio.Queue` (FIFO) | `asyncio.PriorityQueue` | `asyncio.LifoQueue` |
|---|---|---|---|
| **Orden de salida** | Orden de llegada | Menor número = primero | Al revés de llegada |
| **Tipo de elemento** | Cualquiera | Tupla o dataclass comparable | Cualquiera |
| **Caso de uso típico** | Pedidos web, tareas en serie | Tareas con urgencia variable | DFS, undo, frescura |
| **Analogía** | Cola del supermercado | Cola médica por gravedad | Pila de platos |
| **Persistencia** | No | No | No |

## asyncio.Queue vs Solución Externa

| Criterio | `asyncio.Queue` | Celery / RabbitMQ |
|----------|----------------|-------------------|
| **Complejidad** | Baja (Python puro) | Alta (broker externo) |
| **Persistencia** | No | Sí |
| **Multi-proceso** | No | Sí |
| **Rendimiento** | Muy alto (RAM) | Algo menor (disco) |
| **Cuándo usarlo** | Prototipos, datos no críticos | Producción, datos importantes |

---

## 20 Preguntes de Test — Capítol 12

### Pregunta 1: Tipus de coles asyncio
Quines d'aquestes classes Python implementen una cua asíncrona?

[X] a. `asyncio.Queue`

[ ] b. `asyncio.TaskQueue`

[X] c. `asyncio.PriorityQueue`

[X] d. `asyncio.LifoQueue`

---

### Pregunta 2: Comportament de `get_nowait`
Quines afirmacions sobre `queue.get_nowait()` són certes?

[X] a. És una funció normal, no una corutina (no cal `await`).

[ ] b. Espera fins que hi hagi un element a la cua si aquesta és buida.

[X] c. Llança `asyncio.queues.QueueEmpty` si la cua és buida.

[ ] d. Retorna `None` si la cua és buida.

---

### Pregunta 3: `task_done()` i `join()`
Quines afirmacions sobre `task_done()` i `join()` són certes?

[X] a. Cal cridar `task_done()` una vegada per cada element extret amb `get()`.

[X] b. `await queue.join()` espera fins que el comptador intern arribi a zero.

[ ] c. Si oblides cridar `task_done()`, la cua elimina automàticament el comptador.

[X] d. Si oblides cridar `task_done()`, `join()` esperarà indefinidament.

---

### Pregunta 4: Patrón Productor-Consumidor
En el patró productor-consumidor amb `asyncio.Queue`, quines afirmacions són correctes?

[X] a. El productor genera tasques i les posa a la cua amb `put` o `put_nowait`.

[X] b. Els consumidors (workers) treuen tasques de la cua i les processen.

[ ] c. El productor i els consumidors comparteixen el mateix bucle `while`.

[X] d. Poden coexistir múltiples consumidors treballant en paral·lel sobre la mateixa cua.

---

### Pregunta 5: `await queue.put()` vs `queue.put_nowait()`
Quina és la diferència principal entre `await queue.put(item)` i `queue.put_nowait(item)`?

[ ] a. `put_nowait` és més ràpid perquè no comprova si la cua és plena.

[X] b. `await queue.put(item)` pausa la corutina si la cua és plena i espera fins que hi hagi espai.

[X] c. `queue.put_nowait(item)` llança `QueueFull` immediatament si la cua és plena.

[ ] d. `await queue.put(item)` bloqueja el fil principal de Python.

---

### Pregunta 6: Cues en aplicacions web
Per quina raó s'utilitza una cua asyncio en el Listado 12.3 (endpoint `POST /order`)?

[ ] a. Per guardar els pedidos de forma persistent al disc.

[X] b. Per respondre al client immediatament mentre el pedido es processa en segon pla.

[X] c. Per limitar el nombre màxim de pedidos que es processen simultàniament.

[ ] d. Per evitar que dos workers processin el mateix pedido.

---

### Pregunta 7: Limitació principal de `asyncio.Queue`
Quina és la limitació més important de `asyncio.Queue` respecte a solucions com Celery o RabbitMQ?

[ ] a. `asyncio.Queue` no suporta múltiples workers.

[ ] b. `asyncio.Queue` és molt més lenta que RabbitMQ.

[X] c. `asyncio.Queue` no té persistència: si el procés cau, les dades de la cua es perden.

[ ] d. `asyncio.Queue` no pot tenir un tamany màxim.

---

### Pregunta 8: Hooks d'aiohttp
En l'exemple del Listado 12.3, quina és la funció dels hooks `on_startup` i `on_shutdown`?

[X] a. `on_startup` s'utilitza per crear la cua i els workers quan arrenca l'aplicació.

[ ] b. `on_startup` s'executa per cada petició HTTP rebuda.

[X] c. `on_shutdown` s'utilitza per esperar que els pedidos pendents acabin i cancel·lar els workers.

[ ] d. `on_shutdown` elimina automàticament les tasques sense necessitat de cridar `cancel()`.

---

### Pregunta 9: `asyncio.PriorityQueue` — format dels elements
Quines afirmacions sobre els elements d'una `asyncio.PriorityQueue` són certes?

[X] a. Els elements han de ser comparables entre ells (per exemple, tuples o dataclasses amb `order=True`).

[X] b. Un element amb prioritat numèrica 1 surt de la cua abans que un amb prioritat 5.

[ ] c. No cal que els elements siguin comparables; la cua els ordena per ordre d'inserció.

[X] d. Es pot usar `@dataclass(order=True)` amb `field(compare=False)` per evitar que el contingut de la tasca afecti la comparació.

---

### Pregunta 10: `asyncio.LifoQueue` — ordre de sortida
Si afegim a una `asyncio.LifoQueue` els elements A, B, C (en aquest ordre), en quin ordre sortiran?

[ ] a. A, B, C

[ ] b. B, A, C

[X] c. C, B, A

[ ] d. L'ordre és aleatori

---

### Pregunta 11: Web Crawler — patró especial
Quina característica fa especial el patró de web crawler respecte al patró productor-consumidor clàssic?

[ ] a. El web crawler no utilitza cap cua.

[X] b. Els workers consumidors també actuen com a productors: en processar una URL troben noves URLs i les afegeixen a la cua.

[ ] c. El web crawler utilitza sempre una `PriorityQueue` per processar les URLs més curtes primer.

[ ] d. El web crawler no pot tenir múltiples workers simultanis.

---

### Pregunta 12: Buena práctica — `try/finally`
Per quina raó es recomana embolicar el processament d'un element amb `try/finally` en un worker?

[ ] a. Per accelerar el processament.

[X] b. Per garantir que `task_done()` es crida sempre, fins i tot si el processament llança una excepció.

[ ] c. Per evitar que la cua es quedi bloquejada quan hi ha molts elements.

[ ] d. Perquè `asyncio` ho requereix obligatòriament.

---

### Pregunta 13: Creació d'una cua amb límit
Quin paràmetre s'utilitza per crear una cua amb un màxim de 10 elements?

[ ] a. `asyncio.Queue(limit=10)`

[X] b. `asyncio.Queue(maxsize=10)` o `asyncio.Queue(10)`

[ ] c. `asyncio.Queue.set_max(10)`

[ ] d. `asyncio.Queue(capacity=10)`

---

### Pregunta 14: Apagado limpio amb timeout
Per quin motiu s'afegeix un `timeout` a `asyncio.wait_for(queue.join(), timeout=10)` en el hook de shutdown?

[X] a. Per evitar que l'aplicació s'encalli indefinidament si un worker triga massa a acabar.

[ ] b. Perquè `join()` sense timeout sempre llança una excepció.

[ ] c. Per processar els elements pendents més ràpidament.

[ ] d. El timeout no fa res en aquest context; és decoratiu.

---

### Pregunta 15: `asyncio.Queue` vs Celery
Quina és la situació on s'hauria de preferir Celery/RabbitMQ en lloc d'`asyncio.Queue`?

[ ] a. Quan es desenvolupa un prototip senzill.

[X] b. Quan les dades de la cua no es poden perdre (pedidos, transaccions financeres).

[X] c. Quan cal escalar el processament a múltiples servidors o processos.

[ ] d. Quan la cua necessita suportar múltiples workers asyncio.

---

### Pregunta 16: Comportament de `await queue.get()`
Quines afirmacions sobre `await queue.get()` són correctes?

[X] a. Si la cua és buida, la corutina es pausa fins que s'afegeixi un element.

[ ] b. Si la cua és buida, llança `QueueEmpty`.

[X] c. No bloqueja el fil principal de Python mentre espera.

[ ] d. Retorna `None` si la cua porta més de 5 segons buida.

---

### Pregunta 17: Patró productor a l'exemple web (Listado 12.2)
En el Listado 12.2, quin és el comportament del `customer_generator` quan la cua arriba al seu tamany màxim?

[ ] a. Llança una excepció i el programa acaba.

[X] b. La corutina es pausa en `await queue.put(customer)` fins que un cajero allibera espai.

[ ] c. Descarta els nous clients i continua generant-ne.

[ ] d. Reinicia la cua buidant-la.

---

### Pregunta 18: Casos d'ús de cada tipus de cua
Relaciona cada cas d'ús amb el tipus de cua més adequat:

| Cas d'ús | Cua recomanada |
|----------|---------------|
| Processar pedidos en ordre d'arribada | `asyncio.Queue` (FIFO) |
| Atendre primer els pacients en estat crític | `asyncio.PriorityQueue` |
| Implementar l'operació "desfer" (Ctrl+Z) | `asyncio.LifoQueue` |
| Cerca en profunditat (DFS) en un graf | `asyncio.LifoQueue` |

Quines parelles anteriors són correctes?

[X] a. Pedidos en ordre → `asyncio.Queue`

[X] b. Pacients crítics primer → `asyncio.PriorityQueue`

[X] c. Desfer (Ctrl+Z) → `asyncio.LifoQueue`

[X] d. DFS en graf → `asyncio.LifoQueue`

---

### Pregunta 19: Workers infinits vs finits
Quina diferència hi ha entre el Listado 12.1 i el Listado 12.2 pel que fa als workers?

[X] a. Al Listado 12.1 els workers acaben quan la cua és buida (`while not queue.empty()`).

[X] b. Al Listado 12.2 els workers funcionen indefinidament (`while True`) esperant nous elements.

[ ] c. Al Listado 12.1 els workers utilitzen `await queue.get()`.

[ ] d. Al Listado 12.2 els workers utilitzen `queue.get_nowait()`.

---

### Pregunta 20: Excepcions de les cues
Quines excepcions pot llançar `asyncio.Queue`?

[X] a. `asyncio.queues.QueueFull` — quan `put_nowait` intenta afegir un element a una cua plena.

[X] b. `asyncio.queues.QueueEmpty` — quan `get_nowait` intenta extreure d'una cua buida.

[ ] c. `asyncio.queues.QueueTimeout` — quan `get` espera massa temps.

[ ] d. `asyncio.QueueOverflow` — quan la cua supera el doble del seu tamany màxim.

---

*Font: Python Concurrency with asyncio — Matthew Fowler (Manning Publications)*
