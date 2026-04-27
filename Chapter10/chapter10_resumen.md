# Capítulo 10: Microservicios con asyncio

## 1. ¿Qué son los Microservicios?

Los microservicios son una arquitectura donde la aplicación se divide en **servicios pequeños, independientes y desplegables por separado**, en contraposición al modelo **monolítico** donde todo el código vive y se despliega como una única unidad.

### Principios clave de los microservicios

- **Bajo acoplamiento e independencia**: cada servicio se puede desplegar sin afectar a los demás.
- **Stack propio**: cada servicio tiene su propio modelo de datos y base de datos.
- **Comunicación via protocolo**: se comunican entre sí via REST o gRPC.
- **Responsabilidad única** (*single responsibility*): cada servicio "hace una cosa y la hace bien".

### Monolito vs Microservicios

| Característica | Monolito | Microservicios |
|---|---|---|
| Despliegue | Todo junto | Independiente por servicio |
| Escalado | Escala toda la app | Escala solo el servicio que lo necesita |
| Complejidad operacional | Baja | Alta |
| Complejidad de código | Crece con el tiempo | Separada por dominio |
| Equipos | Conflictos en merge | Equipos independientes |
| Tech stack | Único | Puede variar por servicio |

### ¿Por qué usar microservicios?

#### Complejidad de código
A medida que una aplicación crece, los modelos de datos se acoplan más y la deuda técnica aumenta. Con microservicios, cada servicio tiene un dominio acotado, lo que reduce esta complejidad.

#### Escalabilidad
En un e-commerce, hay muchas más visitas al catálogo de productos que pedidos. Con un monolito, para escalar el servicio de productos también escalas el de pedidos (innecesariamente). Con microservicios, escala solo lo que necesita escalar.

#### Independencia de equipos y tecnología
Equipos distintos pueden trabajar en servicios distintos sin conflictos de merge. Incluso pueden usar tecnologías diferentes (un servicio en Java, otro en Python).

### ¿Cómo ayuda asyncio?

Los microservicios se comunican entre sí por red (REST/gRPC). Al necesitar comunicarnos con **múltiples servicios al mismo tiempo**, podemos hacerlo **concurrentemente** con asyncio, reduciendo el tiempo de espera total. Además, las APIs de asyncio como `wait` y `gather` permiten agregar y manejar errores de un grupo de corutinas de forma elegante.

---

## 2. El Patrón Backend-for-Frontend (BFF)

### Problema que resuelve

Cuando una UI necesita datos de múltiples servicios:
1. **Latencia**: el cliente haría N llamadas a N servicios por la red (lento si la conexión es mala).
2. **Duplicación de lógica**: la lógica de combinar respuestas se repetiría en cada cliente (web, iOS, Android).

### Solución: BFF

Se crea un **nuevo servicio intermediario** que:
- Recibe una única petición del cliente.
- Llama a todos los microservicios necesarios (concurrentemente con asyncio).
- Agrega y combina las respuestas.
- Devuelve una respuesta unificada al cliente.

Esto permite además encapsular la lógica de reintentos, timeouts y failovers en un solo lugar.

```
Cliente (Web/iOS/Android)
        │
        ▼
  Backend-for-Frontend  ◄── servicio intermediario
   /    |    \    \
  ▼     ▼     ▼    ▼
Prod. Cart Fav. Inv.   ◄── microservicios independientes
```

---

## 3. Arquitectura del ejemplo práctico

El ejemplo del libro implementa una **página de listado de productos** de un e-commerce con:
- Barra de navegación con número de items en el carrito y en favoritos.
- Listado de productos con inventario disponible (aviso si queda poco stock).

### Servicios implementados

| Servicio | Puerto | Base de datos | Descripción |
|---|---|---|---|
| Product Service | 8000 | `products` | Lista todos los productos |
| Inventory Service | 8001 | — (aleatorio) | Devuelve inventario simulado |
| Favorites Service | 8002 | `favorites` | Productos favoritos por usuario |
| Cart Service | 8003 | `cart` | Carrito de compra por usuario |
| Backend-for-Frontend | 9000 | — | Agrega todos los anteriores |

---

## 4. Implementación de los servicios base

### Utilidades de base de datos compartidas (Listing 10.4)

Para no repetir código de conexión, se crea un módulo reutilizable con funciones `on_startup` y `on_cleanup` de aiohttp:

```python
import asyncpg
from aiohttp.web_app import Application
from asyncpg.pool import Pool

DB_KEY = 'database'

async def create_database_pool(app: Application, host: str, port: int,
                                user: str, database: str, password: str):
    pool: Pool = await asyncpg.create_pool(
        host=host, port=port, user=user,
        password=password, database=database,
        min_size=6, max_size=6
    )
    app[DB_KEY] = pool

async def destroy_database_pool(app: Application):
    pool: Pool = app[DB_KEY]
    await pool.close()
```

Se guarda el pool en la instancia `Application` con una clave (`DB_KEY`), así todos los handlers pueden accederlo via `request.app[DB_KEY]`.

### Servicio de inventario (Listing 10.1)

Este es el servicio más simple. No tiene base de datos; devuelve un número aleatorio de inventario con un delay aleatorio para simular latencia real:

```python
import asyncio
import random
from aiohttp import web
from aiohttp.web_response import Response

routes = web.RouteTableDef()

@routes.get('/products/{id}/inventory')
async def get_inventory(request) -> Response:
    delay: int = random.randint(0, 5)
    await asyncio.sleep(delay)          # Simula latencia de red
    inventory: int = random.randint(0, 100)
    return web.json_response({'inventory': inventory})

app = web.Application()
app.add_routes(routes)
web.run_app(app, port=8001)
```

### Tablas SQL necesarias

**Base de datos `cart`:**
```sql
CREATE TABLE user_cart (
    user_id    INT NOT NULL,
    product_id INT NOT NULL
);
INSERT INTO user_cart VALUES (1, 1), (1, 2), (1, 3), (2, 1), (2, 2), (2, 5);
```

**Base de datos `favorites`:**
```sql
CREATE TABLE user_favorite (
    user_id    INT NOT NULL,
    product_id INT NOT NULL
);
INSERT INTO user_favorite VALUES (1, 1), (1, 2), (1, 3), (3, 1), (3, 2), (3, 3);
```

### Servicio de favoritos (Listing 10.5)

Expone `GET /users/{id}/favorites`. Conecta a la base de datos `favorites` en el puerto 8002:

```python
import functools
from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response
from chapter_10.listing_10_4 import DB_KEY, create_database_pool, destroy_database_pool

routes = web.RouteTableDef()

@routes.get('/users/{id}/favorites')
async def favorites(request: Request) -> Response:
    try:
        user_id = int(request.match_info['id'])
        db = request.app[DB_KEY]
        query = 'SELECT product_id FROM user_favorite WHERE user_id = $1'
        result = await db.fetch(query, user_id)
        if result is not None:
            return web.json_response([dict(record) for record in result])
        else:
            raise web.HTTPNotFound()
    except ValueError:
        raise web.HTTPBadRequest()

app = web.Application()
app.on_startup.append(functools.partial(
    create_database_pool, host='127.0.0.1', port=5432,
    user='postgres', password='password', database='favorites'
))
app.on_cleanup.append(destroy_database_pool)
app.add_routes(routes)
web.run_app(app, port=8002)
```

### Servicio de carrito (Listing 10.6)

Análogo al de favoritos pero sobre la tabla `user_cart` en la base de datos `cart`, en el puerto 8003:

```python
# Igual que favorites pero con:
# - tabla: user_cart
# - endpoint: /users/{id}/cart
# - database: 'cart'
# - puerto: 8003
```

### Servicio de productos (Listing 10.7)

Devuelve todos los productos de la base de datos `products` en el puerto 8000:

```python
import functools
from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response
from chapter_10.listing_10_4 import DB_KEY, create_database_pool, destroy_database_pool

routes = web.RouteTableDef()

@routes.get('/products')
async def products(request: Request) -> Response:
    db = request.app[DB_KEY]
    result = await db.fetch('SELECT product_id, product_name FROM product')
    return web.json_response([dict(record) for record in result])

app = web.Application()
app.on_startup.append(functools.partial(
    create_database_pool, host='127.0.0.1', port=5432,
    user='postgres', password='password', database='products'
))
app.on_cleanup.append(destroy_database_pool)
app.add_routes(routes)
web.run_app(app, port=8000)
```

---

## 5. El servicio Backend-for-Frontend (Listing 10.8)

Este es el servicio central del capítulo. Expone `GET /products/all` y agrega datos de todos los servicios.

### Requisitos de negocio del API

- Si el servicio de productos tarda **más de 1 segundo** → responder con error 504 (timeout).
- Los datos de carrito y favoritos son **opcionales**: si no llegan en 1 segundo, devolver `null`.
- El inventario también es **opcional**: si falla, devolver el producto sin inventario.

### Formato de respuesta

```json
{
  "cart_items": 1,
  "favorite_items": null,
  "products": [
    {"product_id": 4, "inventory": 4},
    {"product_id": 3, "inventory": 65}
  ]
}
```

`favorite_items` es `null` si el servicio de favoritos no respondió a tiempo.

### Implementación completa

```python
import asyncio
from asyncio import Task
import aiohttp
from aiohttp import web, ClientSession
from aiohttp.web_request import Request
from aiohttp.web_response import Response
import logging
from typing import Dict, Set, Awaitable, Optional, List

routes = web.RouteTableDef()

PRODUCT_BASE   = 'http://127.0.0.1:8000'
INVENTORY_BASE = 'http://127.0.0.1:8001'
FAVORITE_BASE  = 'http://127.0.0.1:8002'
CART_BASE      = 'http://127.0.0.1:8003'

@routes.get('/products/all')
async def all_products(request: Request) -> Response:
    async with aiohttp.ClientSession() as session:
        # Lanzar las 3 peticiones concurrentemente
        products  = asyncio.create_task(session.get(f'{PRODUCT_BASE}/products'))
        favorites = asyncio.create_task(session.get(f'{FAVORITE_BASE}/users/3/favorites'))
        cart      = asyncio.create_task(session.get(f'{CART_BASE}/users/3/cart'))

        requests = [products, favorites, cart]
        done, pending = await asyncio.wait(requests, timeout=1.0)  # timeout global de 1s

        # Si products no terminó en 1s → error crítico
        if products in pending:
            [req.cancel() for req in requests]
            return web.json_response({'error': 'Could not reach products service.'}, status=504)

        # Si products terminó pero con excepción → error de servidor
        elif products in done and products.exception() is not None:
            [req.cancel() for req in requests]
            logging.exception('Server error reaching product service.', exc_info=products.exception())
            return web.json_response({'error': 'Server error reaching products service.'}, status=500)

        else:
            product_response = await products.result().json()
            # Obtener inventario para cada producto (también concurrente)
            product_results = await get_products_with_inventory(session, product_response)
            # Contar items del carrito y favoritos (datos opcionales)
            cart_count     = await get_response_item_count(cart,      done, pending, 'Error getting user cart.')
            favorite_count = await get_response_item_count(favorites, done, pending, 'Error getting user favorites.')

            return web.json_response({
                'cart_items':     cart_count,
                'favorite_items': favorite_count,
                'products':       product_results
            })


async def get_products_with_inventory(session: ClientSession, product_response) -> List[Dict]:
    """Lanza peticiones de inventario en paralelo para todos los productos."""

    def get_inventory(session: ClientSession, product_id: str) -> Task:
        url = f'{INVENTORY_BASE}/products/{product_id}/inventory'
        return asyncio.create_task(session.get(url))

    def create_product_record(product_id: int, inventory: Optional[int]) -> Dict:
        return {'product_id': product_id, 'inventory': inventory}

    # Mapa task → product_id para saber a qué producto pertenece cada task
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
    """Devuelve el número de items si la tarea terminó bien, None si no."""
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
```

### Flujo de ejecución del BFF

```
GET /products/all
        │
        ├──► [concurrente con asyncio.wait(timeout=1s)]
        │         ├── GET /products          (obligatorio)
        │         ├── GET /users/3/favorites (opcional)
        │         └── GET /users/3/cart      (opcional)
        │
        ├── Si products timeout → 504
        ├── Si products error   → 500
        └── Si products OK:
                │
                ├──► [concurrente con asyncio.wait(timeout=1s)]
                │         └── GET /inventory para cada producto
                │
                └── Combinar todo y responder
```

---

## 6. Manejo de Fallos y Reintentos

### El problema

En sistemas distribuidos, los fallos son inevitables. Si un servicio empieza a fallar y seguimos enviándole peticiones, desperdiciamos recursos y tiempo de espera.

### El patrón Circuit Breaker (Interruptor de Circuito)

Inspirado en los interruptores eléctricos: si hay demasiados fallos, **"abre el circuito"** y falla rápidamente (*fail fast*) sin ni siquiera intentar la llamada, dando tiempo al servicio problemático para recuperarse.

#### Estados del Circuit Breaker

```
  CLOSED (normal)  ──── demasiados fallos ────►  OPEN (falla rápido)
       ▲                                               │
       └──────── reset_interval elapsed ───────────────┘
```

- **CLOSED**: se hacen las peticiones normalmente.
- **OPEN**: se falla inmediatamente con `CircuitOpenException`, sin hacer la petición.
- Después de `reset_interval` segundos en estado OPEN, vuelve a CLOSED y prueba de nuevo.

### Implementación (Listing 10.11)

```python
import asyncio
from datetime import datetime, timedelta

class CircuitOpenException(Exception):
    pass

class CircuitBreaker:
    def __init__(self, callback, timeout: float, time_window: float,
                 max_failures: int, reset_interval: float):
        self.callback = callback
        self.timeout = timeout           # Segundos antes de timeout en cada petición
        self.time_window = time_window   # Ventana de tiempo para contar fallos
        self.max_failures = max_failures # Fallos máximos antes de abrir el circuito
        self.reset_interval = reset_interval  # Segundos hasta intentar cerrar el circuito
        self.last_request_time = None
        self.last_failure_time = None
        self.current_failures = 0

    async def request(self, *args, **kwargs):
        if self.current_failures >= self.max_failures:
            # Circuito ABIERTO
            if datetime.now() > self.last_request_time + timedelta(seconds=self.reset_interval):
                self._reset('Circuit is going from open to closed, resetting!')
                return await self._do_request(*args, **kwargs)
            else:
                print('Circuit is open, failing fast!')
                raise CircuitOpenException()
        else:
            # Circuito CERRADO
            if self.last_failure_time and \
               datetime.now() > self.last_failure_time + timedelta(seconds=self.time_window):
                self._reset('Interval since first failure elapsed, resetting!')
            print('Circuit is closed, requesting!')
            return await self._do_request(*args, **kwargs)

    def _reset(self, msg: str):
        print(msg)
        self.last_failure_time = None
        self.current_failures = 0

    async def _do_request(self, *args, **kwargs):
        try:
            print('Making request!')
            self.last_request_time = datetime.now()
            return await asyncio.wait_for(self.callback(*args, **kwargs), timeout=self.timeout)
        except Exception as e:
            self.current_failures += 1
            if self.last_failure_time is None:
                self.last_failure_time = datetime.now()
            raise
```

### Uso del Circuit Breaker (Listing 10.12)

```python
import asyncio
from chapter_10.listing_10_11 import CircuitBreaker

async def main():
    async def slow_callback():
        await asyncio.sleep(2)  # Siempre tarda 2 segundos

    cb = CircuitBreaker(
        slow_callback,
        timeout=1.0,        # Timeout de 1s (siempre fallará)
        time_window=5,      # Ventana de 5s para contar fallos
        max_failures=2,     # Abre después de 2 fallos
        reset_interval=5    # Intenta cerrar después de 5s
    )

    # Primera ronda: los 2 primeros fallan por timeout,
    # los 2 siguientes fallan inmediatamente (circuito abierto)
    for _ in range(4):
        try:
            await cb.request()
        except Exception as e:
            pass

    print('Sleeping for 5 seconds so breaker closes...')
    await asyncio.sleep(5)  # Esperar reset_interval

    # Segunda ronda: igual comportamiento
    for _ in range(4):
        try:
            await cb.request()
        except Exception as e:
            pass

asyncio.run(main())
```

**Salida esperada:**
```
Circuit is closed, requesting!   # → timeout después de 1s
Circuit is closed, requesting!   # → timeout después de 1s (2 fallos: circuito abre)
Circuit is open, failing fast!   # → falla instantáneamente
Circuit is open, failing fast!   # → falla instantáneamente
Sleeping for 5 seconds so breaker closes...
Circuit is going from open to closed, resetting!
Circuit is closed, requesting!
... (se repite)
```

---

## 7. Referencia rápida de los archivos del capítulo 9 (prerequisitos)

### listing_9_2.py — API con aiohttp + asyncpg

```python
import asyncpg
from aiohttp import web
from aiohttp.web_app import Application
from aiohttp.web_request import Request
from aiohttp.web_response import Response
from asyncpg import Record
from asyncpg.pool import Pool
from typing import List, Dict

routes = web.RouteTableDef()
DB_KEY = 'database'

async def create_database_pool(app: Application):
    print('Creating database pool.')
    pool: Pool = await asyncpg.create_pool(
        host='127.0.0.1', port=5432,
        user='postgres', password='password',
        database='products', min_size=6, max_size=6
    )
    app[DB_KEY] = pool

async def destroy_database_pool(app: Application):
    print('Destroying database pool.')
    pool: Pool = app[DB_KEY]
    await pool.close()

@routes.get('/brands')
async def brands(request: Request) -> Response:
    connection: Pool = request.app[DB_KEY]
    brand_query = 'SELECT brand_id, brand_name FROM brand'
    results: List[Record] = await connection.fetch(brand_query)
    result_as_dict: List[Dict] = [dict(brand) for brand in results]
    return web.json_response(result_as_dict)

if __name__ == '__main__':
    app = web.Application()
    app.on_startup.append(create_database_pool)
    app.on_cleanup.append(destroy_database_pool)
    app.add_routes(routes)
    web.run_app(app)
```

### listing_9_8.py — API con Starlette + asyncpg

```python
from contextlib import asynccontextmanager
import asyncpg
from asyncpg import Record
from asyncpg.pool import Pool
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from typing import List, Dict

async def create_database_pool(app):
    pool: Pool = await asyncpg.create_pool(
        host='127.0.0.1', port=5432,
        user='postgres', password='password',
        database='products', min_size=6, max_size=6
    )
    app.state.DB = pool

async def destroy_database_pool(app):
    pool = app.state.DB
    await pool.close()

async def brands(request: Request) -> Response:
    connection: Pool = request.app.state.DB
    brand_query = 'SELECT brand_id, brand_name FROM brand'
    results: List[Record] = await connection.fetch(brand_query)
    result_as_dict: List[Dict] = [dict(brand) for brand in results]
    return JSONResponse(result_as_dict)

@asynccontextmanager
async def lifespan(app):
    await create_database_pool(app)
    yield
    await destroy_database_pool(app)

app = Starlette(routes=[Route('/brands', brands)], lifespan=lifespan)
```

**Diferencia clave**: aiohttp usa `on_startup`/`on_cleanup` hooks; Starlette usa el context manager `lifespan`.

---

## 8. Preparación del entorno

### Prerequisitos del capítulo 9 (base para el 10)

1. **Activar el entorno virtual** con las dependencias instaladas.
2. **Ejecutar PostgreSQL en Docker**:
   ```bash
   docker run --name some-postgres -e POSTGRES_PASSWORD=password -p 5432:5432 -d postgres
   ```
3. **Crear la base de datos `products`**:
   ```bash
   docker exec -u postgres some-postgres psql -c "CREATE DATABASE products;"
   ```
4. **Ejecutar los listings del capítulo 5** (crean tablas e insertan datos):
   ```bash
   cd chapter_05
   seq 3 6 | xargs -Iiii python3 listing_5_iii.py
   ```

### Prerequisitos adicionales del capítulo 10

Crear las bases de datos `cart` y `favorites` e insertar datos:

```bash
docker exec -u postgres some-postgres psql -d favorites -c "
CREATE TABLE user_favorite (
    user_id    INT NOT NULL,
    product_id INT NOT NULL
);
INSERT INTO user_favorite VALUES (1, 1), (1, 2), (1, 3), (3, 1), (3, 2), (3, 3);"

docker exec -u postgres some-postgres psql -d cart -c "
CREATE TABLE user_cart (
    user_id    INT NOT NULL,
    product_id INT NOT NULL
);
INSERT INTO user_cart VALUES (1, 1), (1, 2), (1, 3), (2, 1), (2, 2), (2, 5);"
```

> ⚠️ Recuerda eliminar el contenedor al finalizar la sesión:
> ```bash
> docker stop some-postgres && docker rm some-postgres
> ```

---

## 9. Conceptos clave resumidos

| Concepto | Descripción |
|---|---|
| **Microservicio** | Servicio pequeño, independiente, con su propio data model |
| **BFF (Backend-for-Frontend)** | Servicio intermediario que agrega respuestas de múltiples servicios |
| **`asyncio.wait(timeout=N)`** | Ejecuta tareas concurrentemente, devuelve `done` y `pending` tras el timeout |
| **`asyncio.create_task()`** | Crea una tarea asyncio para ejecutar una corutina concurrentemente |
| **Circuit Breaker** | Patrón que "abre el circuito" si hay demasiados fallos, evitando cascada de errores |
| **`asyncio.wait_for(timeout=N)`** | Ejecuta una corutina con un timeout específico |
| **asyncpg Pool** | Pool de conexiones a PostgreSQL, reutilizable entre requests |
| **aiohttp `on_startup`/`on_cleanup`** | Hooks del ciclo de vida de la aplicación para crear/destruir recursos |
| **Fail fast** | Fallar inmediatamente (sin esperar) cuando sabemos que el servicio no está disponible |
