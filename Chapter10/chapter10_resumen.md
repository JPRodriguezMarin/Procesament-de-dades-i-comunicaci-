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

> **Descripción del diagrama:** El cliente hace una única llamada al BFF (puerto 9000). El BFF es el único que conoce la existencia de los cuatro microservicios internos. Los llama todos en paralelo y agrega sus respuestas antes de contestar al cliente. El cliente no sabe cuántos servicios hay detrás ni en qué puertos están.

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

**¿Qué hace este bloque?**
- `DB_KEY = 'database'` → Constante string que actúa como clave de diccionario. Todos los servicios usan esta misma clave para guardar y recuperar el pool desde el objeto `app`, evitando strings literales dispersos por el código.
- `asyncpg.create_pool(...)` → Abre un conjunto de conexiones a PostgreSQL. Con `min_size=6` y `max_size=6` se mantienen siempre 6 conexiones abiertas, listas para atender requests sin el coste de abrir/cerrar por cada petición.
- `app[DB_KEY] = pool` → Guarda el pool en el diccionario interno de la aplicación aiohttp. Desde cualquier handler se puede recuperar con `request.app[DB_KEY]`.
- `destroy_database_pool` → Lee el pool del diccionario y lo cierra limpiamente al apagar el servidor, liberando todas las conexiones a la base de datos.

Se guarda el pool en la instancia `Application` con una clave (`DB_KEY`), así todos los handlers pueden accederlo via `request.app[DB_KEY]`.

---

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

**¿Qué hace este bloque?**
- `routes = web.RouteTableDef()` → Crea el registro de rutas donde se anotarán los handlers con decoradores.
- `@routes.get('/products/{id}/inventory')` → Registra el handler para `GET /products/{id}/inventory`. El fragmento `{id}` es un parámetro de ruta dinámico (en este servicio no se usa porque el inventario es aleatorio).
- `random.randint(0, 5)` → Elige un delay aleatorio entre 0 y 5 segundos. Simula la variabilidad de latencia que tendría un servicio de inventario real (consulta a base de datos, caché, red interna...).
- `await asyncio.sleep(delay)` → Pausa la corutina el tiempo elegido **sin bloquear el event loop**. Mientras este handler espera, el servidor puede atender otras peticiones.
- `random.randint(0, 100)` → Genera el stock disponible de forma aleatoria. En producción aquí iría una query a la base de datos.
- `web.json_response(...)` → Serializa el dict `{'inventory': N}` como JSON y devuelve HTTP 200.
- `web.run_app(app, port=8001)` → Arranca el servidor en el puerto 8001, ejecuta `on_startup` (no hay ninguno) e inicia el event loop.

---

### Tablas SQL necesarias

**Base de datos `cart`:**
```sql
CREATE TABLE user_cart (
    user_id    INT NOT NULL,
    product_id INT NOT NULL
);
INSERT INTO user_cart VALUES (1, 1), (1, 2), (1, 3), (2, 1), (2, 2), (2, 5);
```

**¿Qué hace este bloque?**
- `CREATE TABLE user_cart` → Crea la tabla de relación entre usuarios y productos en su carrito. La relación es N:N (un usuario puede tener varios productos; un producto puede estar en varios carritos).
- `user_id INT NOT NULL` / `product_id INT NOT NULL` → Ambas columnas son obligatorias. No se usa clave primaria compuesta para simplificar el ejemplo (en producción se añadiría).
- `INSERT INTO user_cart VALUES ...` → Inserta datos de prueba: el usuario 1 tiene los productos 1, 2 y 3 en su carrito; el usuario 2 tiene los productos 1, 2 y 5.

**Base de datos `favorites`:**
```sql
CREATE TABLE user_favorite (
    user_id    INT NOT NULL,
    product_id INT NOT NULL
);
INSERT INTO user_favorite VALUES (1, 1), (1, 2), (1, 3), (3, 1), (3, 2), (3, 3);
```

**¿Qué hace este bloque?**
- `CREATE TABLE user_favorite` → Misma estructura que `user_cart` pero para la lista de favoritos. Cada base de datos (`cart`, `favorites`) es independiente y pertenece a su propio microservicio.
- `INSERT INTO user_favorite VALUES ...` → El usuario 1 tiene los productos 1, 2, 3 como favoritos; el usuario 3 también tiene los productos 1, 2, 3. El BFF siempre consulta los datos del usuario 3 en el ejemplo.

---

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

**¿Qué hace este bloque?**
- `from chapter_10.listing_10_4 import ...` → Reutiliza las utilidades de DB compartidas para no duplicar código de conexión entre servicios.
- `int(request.match_info['id'])` → Extrae el parámetro `{id}` de la URL como string y lo convierte a entero. Si la conversión falla (p.ej. `GET /users/abc/favorites`), lanza `ValueError`.
- `except ValueError: raise web.HTTPBadRequest()` → Captura el `ValueError` y lo convierte en una respuesta HTTP 400. aiohttp convierte automáticamente estas excepciones en respuestas HTTP.
- `query = '... WHERE user_id = $1'` → Query parametrizada: `$1` es un placeholder que asyncpg sustituye por `user_id` de forma segura, evitando SQL injection.
- `await db.fetch(query, user_id)` → Ejecuta la query en el pool de conexiones. `fetch` devuelve una lista de objetos `Record` (o lista vacía si no hay resultados).
- `[dict(record) for record in result]` → Convierte cada `Record` de asyncpg a un diccionario Python estándar para poder serializarlo como JSON.
- `functools.partial(create_database_pool, host=..., database='favorites')` → Crea una versión prefijada de `create_database_pool` con todos los parámetros de conexión ya fijados. Es necesario porque aiohttp en `on_startup` solo pasa el objeto `app`, y la función necesita más argumentos.
- `web.run_app(app, port=8002)` → Arranca este servicio en el puerto 8002 (distinto del de productos en 8000 y del de carrito en 8003).

---

### Servicio de carrito (Listing 10.6)

Análogo al de favoritos pero sobre la tabla `user_cart` en la base de datos `cart`, en el puerto 8003:

```python
# Igual que favorites pero con:
# - tabla: user_cart
# - endpoint: /users/{id}/cart
# - database: 'cart'
# - puerto: 8003
```

**¿Qué hace este bloque?**
- Este servicio es estructuralmente idéntico al de favoritos. La única diferencia es el nombre de la tabla (`user_cart`), el endpoint (`/users/{id}/cart`), la base de datos a la que conecta (`cart`) y el puerto en el que escucha (8003). Esta repetición intencionada demuestra el principio de **base de datos por servicio**: aunque la lógica es similar, cada microservicio tiene su propia BD aislada, de modo que un fallo o migración en `cart` no afecta a `favorites`.

---

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

**¿Qué hace este bloque?**
- `@routes.get('/products')` → Endpoint sin parámetros de ruta; devuelve el catálogo completo de productos.
- `db.fetch('SELECT product_id, product_name FROM product')` → Query sin parámetros de usuario, por lo que no hay riesgo de SQL injection ni necesidad de `$1`. Devuelve todas las filas de la tabla `product`.
- No hay `try/except` porque no hay input del usuario que validar: la única fuente de error sería un fallo de base de datos, que aiohttp propagaría como HTTP 500.
- `database='products'` en `functools.partial` → Conecta a la BD `products`, que fue creada en el capítulo 5 y contiene la tabla `product` con `product_id` y `product_name`.
- `web.run_app(app, port=8000)` → Este servicio es el primero que debe estar en marcha, ya que el BFF lo considera obligatorio y devuelve 504 si no responde.

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

**¿Qué representa este JSON?**
- `"cart_items": 1` → El usuario tiene 1 producto en el carrito. Es un conteo, no la lista completa.
- `"favorite_items": null` → El servicio de favoritos no respondió en el timeout de 1 segundo. Al ser un dato opcional, el BFF devuelve `null` en lugar de fallar toda la petición.
- `"products"` → Lista de productos con su inventario. Cada producto tiene `product_id` e `inventory`. Si el inventario de un producto no llegó a tiempo, `inventory` es `null` para ese producto concreto.

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

**¿Qué hace el handler `all_products`?**
- `async with aiohttp.ClientSession() as session` → Abre una sesión HTTP reutilizable para todas las peticiones salientes. El bloque `async with` garantiza que se cierra aunque ocurra una excepción.
- `asyncio.create_task(session.get(...))` × 3 → Lanza las tres peticiones HTTP salientes de forma concurrente. Las tres empiezan a ejecutarse al mismo tiempo sin esperar la una a la otra.
- `done, pending = await asyncio.wait(requests, timeout=1.0)` → Espera como máximo 1 segundo. Tras ese tiempo, `done` contiene las tasks que terminaron y `pending` las que no.
- `if products in pending` → Si el servicio de productos no respondió en 1s, cancela todas las tasks y devuelve HTTP 504. Los productos son datos **obligatorios**: sin ellos no tiene sentido responder.
- `elif products.exception() is not None` → Si productos respondió pero con error de red o aplicación, devuelve HTTP 500. Se diferencia del 504 porque aquí el servicio respondió pero falló internamente.
- `[req.cancel() for req in requests]` → En ambos casos de error se cancelan todas las tasks para liberar recursos del event loop. Una task no cancelada seguiría consumiendo conexiones.
- `await products.result().json()` → `result()` devuelve la `ClientResponse` de aiohttp (la respuesta HTTP). `.json()` es una corutina que lee el cuerpo y lo deserializa.
- `get_products_with_inventory(session, product_response)` → Segunda ronda de concurrencia: lanza una petición de inventario por cada producto en paralelo.
- `get_response_item_count(cart, done, pending, ...)` → Evalúa si el carrito respondió a tiempo y devuelve el número de items o `None`. Mismo para favoritos.

**¿Qué hace `get_products_with_inventory`?**
- `inventory_tasks = { get_inventory(...): p['product_id'] for p in product_response }` → Crea un diccionario `{Task: product_id}`. Como las tasks son los objetivos de `asyncio.wait`, el dict permite recuperar qué producto corresponde a cada task cuando ésta termina.
- `asyncio.wait(inventory_tasks.keys(), timeout=1.0)` → Segunda llamada a `wait`: lanza todas las peticiones de inventario en paralelo con 1s de timeout. El inventario del servicio de inventario puede tardar entre 0 y 5s por diseño, así que algunos superarán el timeout.
- `for task in inv_done` → Procesa las tasks que terminaron. Si no tienen excepción, extrae el número de inventario; si tienen excepción, añade el producto con `inventory=None`.
- `for task in inv_pending: task.cancel()` → Cancela las que no terminaron en 1s y las añade con `inventory=None`. La cancelación es necesaria para no dejar corutinas colgadas.

**¿Qué hace `get_response_item_count`?**
- Recibe la task de carrito o favoritos y los conjuntos `done`/`pending` del `asyncio.wait` original.
- Si la task está en `done` y sin excepción: deserializa el JSON y devuelve la longitud de la lista (número de items).
- Si está en `pending`: la cancela y devuelve `None` (timeout).
- Si está en `done` con excepción: registra el error y devuelve `None`. En los tres casos sin resultado, `None` indica al cliente que ese dato no está disponible.

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

> **Descripción del diagrama:** Muestra los dos niveles de concurrencia del BFF. En el primero se llama en paralelo a los tres servicios principales (productos, favoritos, carrito) con un timeout de 1s. Si productos responde bien, se abre el segundo nivel de concurrencia: una petición de inventario por cada producto, también con 1s de timeout. Finalmente se combina todo en una única respuesta JSON.

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

> **Descripción del diagrama:** El circuito empieza en estado **CLOSED** (cerrado = normal). Cada vez que una petición falla, se incrementa `current_failures`. Cuando `current_failures >= max_failures`, el circuito pasa a **OPEN** (abierto = falla rápido): ya no se hacen peticiones reales, se lanza `CircuitOpenException` inmediatamente. Tras esperar `reset_interval` segundos, el circuito intenta cerrarse de nuevo haciendo una petición de prueba.

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

**¿Qué hace `CircuitOpenException`?**
- Excepción personalizada que se lanza cuando el circuito está abierto. Al heredar de `Exception`, el llamador puede capturarla específicamente para diferenciar un fallo de circuito abierto de un timeout real o un error de red.

**¿Qué hace `__init__`?**
- `self.callback` → La corutina que se protege (p.ej. `session.get(...)`).
- `self.timeout` → Tiempo máximo por petición. Si el callback tarda más, se lanza `asyncio.TimeoutError`.
- `self.time_window` → Ventana temporal: si el primer fallo fue hace más de `time_window` segundos, los fallos anteriores ya no cuentan y se resetea el contador.
- `self.max_failures` → Umbral: al superar este número de fallos, el circuito se abre.
- `self.reset_interval` → Cuánto tiempo debe esperar el circuito abierto antes de intentar cerrarse.
- `self.last_request_time = None` → Se actualiza en `_do_request` con cada petición real. Sirve para calcular cuándo puede cerrarse el circuito.
- `self.last_failure_time = None` → Marca el inicio de la ventana de fallos. Solo se asigna en el primer fallo dentro de una ventana.
- `self.current_failures = 0` → Contador de fallos en la ventana actual.

**¿Qué hace `request`?**
- Es el método público. Decide si hacer la petición real o fallar inmediatamente según el estado del circuito.
- `if self.current_failures >= self.max_failures` → Circuito ABIERTO. Comprueba si ha pasado el `reset_interval` desde la última petición real (`last_request_time`). Si pasó, resetea y hace una petición de prueba. Si no pasó, lanza `CircuitOpenException` sin hacer nada.
- `else` → Circuito CERRADO. Antes de hacer la petición, comprueba si la ventana de tiempo de los fallos anteriores expiró. Si expiró, resetea el contador (aunque no haya llegado a `max_failures`).

**¿Qué hace `_reset`?**
- Borra `last_failure_time` (inicia una nueva ventana de conteo) y pone `current_failures` a 0. Es el único punto donde el circuito vuelve a estado CLOSED.

**¿Qué hace `_do_request`?**
- `self.last_request_time = datetime.now()` → Registra el momento antes de la llamada. Este timestamp (no el de `request`) es el que determina cuándo puede cerrarse el circuito, porque cuenta desde la última petición real intentada.
- `asyncio.wait_for(self.callback(...), timeout=self.timeout)` → Ejecuta el callback con un límite de tiempo. Si tarda más, lanza `asyncio.TimeoutError`.
- `except Exception` → Captura cualquier excepción (timeout, red, aplicación). Incrementa el contador, marca el inicio de la ventana si es el primer fallo y re-lanza la excepción para que el llamador la gestione.

---

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

**¿Qué hace este bloque?**
- `slow_callback` → Corutina que siempre tarda 2 segundos. Como el `CircuitBreaker` tiene `timeout=1.0`, esta función **siempre** superará el timeout y fallará.
- `CircuitBreaker(slow_callback, timeout=1.0, time_window=5, max_failures=2, reset_interval=5)` → Configura el circuito para que se abra tras 2 fallos consecutivos dentro de una ventana de 5 segundos, y espere 5 segundos antes de intentar cerrarse.
- **Primera ronda (4 intentos):**
  - Intento 1: circuito cerrado → hace la petición → timeout tras 1s → `current_failures = 1`
  - Intento 2: circuito cerrado → hace la petición → timeout tras 1s → `current_failures = 2` → **circuito abre**
  - Intento 3: circuito abierto → falla inmediatamente con `CircuitOpenException` (0 segundos de espera)
  - Intento 4: circuito abierto → falla inmediatamente con `CircuitOpenException`
- `await asyncio.sleep(5)` → Espera el `reset_interval`. Tras esto, el circuito intentará cerrarse en la siguiente petición.
- **Segunda ronda (4 intentos):** mismo comportamiento. El intento 1 reinicia el circuito, falla por timeout, y el ciclo se repite.
- `except Exception: pass` → Captura tanto `asyncio.TimeoutError` como `CircuitOpenException` para que el bucle continúe y se vea el comportamiento completo.
- `asyncio.run(main())` → Crea el event loop, ejecuta `main()` y lo cierra al terminar. Punto de entrada estándar para scripts asyncio.

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

> **Descripción de la salida:** Las dos primeras líneas `Circuit is closed, requesting!` tardan 1 segundo cada una (el timeout). Las dos siguientes `Circuit is open, failing fast!` son instantáneas: no hay ninguna petición real, solo se lanza la excepción. El `sleep(5)` es la pausa visible. Después, la línea `Circuit is going from open to closed, resetting!` confirma que el circuito se cerró, y el ciclo de 4 intentos se repite exactamente igual.

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

**¿Qué hace este bloque?**
- Es la versión simplificada del capítulo 9, base conceptual del capítulo 10. Muestra el patrón completo aiohttp + asyncpg sin `functools.partial`, porque `create_database_pool` aquí solo recibe `app` (los parámetros de conexión están hardcodeados).
- `create_database_pool(app: Application)` → Solo acepta `app`. Por eso no necesita `partial`: la firma ya coincide con lo que aiohttp pasa en `on_startup`.
- `if __name__ == '__main__'` → Protege el arranque del servidor para que el módulo pueda importarse sin lanzar el servidor (buena práctica que en el capítulo 10 se omite por simplicidad).
- El flujo completo es: `on_startup` crea el pool → handlers lo usan vía `request.app[DB_KEY]` → `on_cleanup` lo cierra.

---

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

**¿Qué hace este bloque?**
- Es el equivalente de `listing_9_2.py` pero usando **Starlette** en lugar de **aiohttp**. Sirve como referencia comparativa para entender que el patrón es el mismo pero la API del framework varía.
- `app.state.DB = pool` → En Starlette el almacenamiento compartido de la aplicación es `app.state` (un objeto con atributos), no un diccionario como en aiohttp (`app[DB_KEY]`).
- `request.app.state.DB` → Equivalente a `request.app[DB_KEY]` en aiohttp.
- `@asynccontextmanager async def lifespan(app)` → Starlette gestiona el ciclo de vida con un context manager asíncrono. El código antes del `yield` es el startup; el código después del `yield` es el cleanup. Es equivalente a `on_startup` + `on_cleanup` de aiohttp pero en un solo bloque.
- `Starlette(routes=[Route('/brands', brands)], lifespan=lifespan)` → Starlette recibe rutas y el lifespan en el constructor, no mediante llamadas a métodos.

**Diferencia clave**: aiohttp usa `on_startup`/`on_cleanup` hooks; Starlette usa el context manager `lifespan`.

---

## 8. Preparación del entorno

### Prerequisitos del capítulo 9 (base para el 10)

1. **Activar el entorno virtual** con las dependencias instaladas.
2. **Ejecutar PostgreSQL en Docker**:
   ```bash
   docker run --name some-postgres -e POSTGRES_PASSWORD=password -p 5432:5432 -d postgres
   ```
   > Lanza un contenedor Docker con PostgreSQL. `-e POSTGRES_PASSWORD=password` establece la contraseña del usuario `postgres`. `-p 5432:5432` expone el puerto de PostgreSQL al host. `-d` ejecuta el contenedor en segundo plano.

3. **Crear la base de datos `products`**:
   ```bash
   docker exec -u postgres some-postgres psql -c "CREATE DATABASE products;"
   ```
   > `docker exec` ejecuta un comando dentro del contenedor en ejecución. `-u postgres` usa el usuario `postgres` del sistema. `psql -c` ejecuta el SQL directamente sin abrir una sesión interactiva.

4. **Ejecutar los listings del capítulo 5** (crean tablas e insertan datos):
   ```bash
   cd chapter_05
   seq 3 6 | xargs -Iiii python3 listing_5_iii.py
   ```
   > `seq 3 6` genera los números 3, 4, 5, 6. `xargs -Iiii` sustituye `iii` por cada número en el comando siguiente. Equivale a ejecutar `listing_5_3.py`, `listing_5_4.py`, `listing_5_5.py` y `listing_5_6.py` en secuencia. Estos listings crean la tabla `product` y la tabla `brand` con datos de prueba.

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

> **Descripción del bloque:**
> - `-d favorites` → Conecta directamente a la base de datos `favorites` dentro del contenedor (equivale a `\c favorites` en psql).
> - El primer comando crea la tabla `user_favorite` e inserta 6 filas: el usuario 1 tiene los favoritos 1, 2, 3; el usuario 3 también tiene los favoritos 1, 2, 3. El BFF consulta siempre los datos del usuario 3.
> - El segundo comando hace lo mismo en la BD `cart`: el usuario 1 tiene los productos 1, 2, 3 en el carrito; el usuario 2 tiene los productos 1, 2, 5.
> - Ambas bases de datos son independientes, cada una pertenece a su propio microservicio.

> ⚠️ Recuerda eliminar el contenedor al finalizar la sesión:
> ```bash
> docker stop some-postgres && docker rm some-postgres
> ```
> `docker stop` envía una señal de parada al contenedor (espera que se cierre limpiamente). `docker rm` lo elimina por completo. Sin `rm`, el contenedor seguiría ocupando espacio en disco y el nombre `some-postgres` no podría reutilizarse en la próxima sesión.

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

---

## 10. Glosario

| Nombre | Tipo | Objetivo | Descripción |
|---|---|---|---|
| **Microservicio** | Patrón arquitectural | Dividir una aplicación en unidades autónomas | Servicio pequeño e independiente con su propio modelo de datos, base de datos y ciclo de despliegue. Se comunica con otros servicios vía REST o gRPC. |
| **Monolito** | Patrón arquitectural | Construir toda la lógica en una única unidad | Aplicación donde todo el código se despliega como una sola unidad. Escala y falla en bloque; problemático cuando crece en complejidad. |
| **BFF (Backend-for-Frontend)** | Patrón arquitectural | Agregar datos de múltiples servicios en una sola respuesta | Servicio intermediario entre el cliente y los microservicios. Llama a todos los servicios necesarios concurrentemente y devuelve una respuesta unificada. |
| **Circuit Breaker** | Patrón de resiliencia | Evitar la cascada de fallos en sistemas distribuidos | Interruptor que "abre" cuando se acumulan demasiados fallos, causando *fail fast* en lugar de esperar timeouts. Se restablece tras un intervalo. |
| **Fail fast** | Principio de diseño | Reducir latencia ante servicios caídos | En lugar de esperar un timeout largo, fallar inmediatamente cuando se sabe que el servicio no está disponible (circuito abierto). |
| **`asyncio.wait()`** | Función — `asyncio` | Ejecutar tareas concurrentemente con control granular | Recibe un iterable de awaitables y un `timeout`. Devuelve dos conjuntos: `done` (completadas) y `pending` (aún en ejecución). Permite decidir qué hacer con cada grupo. |
| **`asyncio.wait_for()`** | Función — `asyncio` | Ejecutar una corutina con un límite de tiempo | Envuelve una corutina y lanza `asyncio.TimeoutError` si no termina en `timeout` segundos. Usado internamente en el `CircuitBreaker`. |
| **`asyncio.create_task()`** | Función — `asyncio` | Lanzar una corutina como tarea concurrente | Programa una corutina para ejecutarse en el event loop sin esperar su resultado inmediatamente. Devuelve un objeto `Task`. |
| **`asyncio.gather()`** | Función — `asyncio` | Ejecutar múltiples corutinas y recoger todos los resultados | Alternativa a `wait`. No separa `done`/`pending`, por lo que no permite control granular de timeouts. Se usa cuando todos los resultados son obligatorios. |
| **`asyncio.run()`** | Función — `asyncio` | Punto de entrada para ejecutar código asíncrono | Crea un nuevo event loop, ejecuta la corutina pasada como argumento y lo cierra al terminar. Usado en `listing_10_12.py`. |
| **`Task`** | Clase — `asyncio` | Representar una corutina en ejecución dentro del event loop | Subclase de `Future`. Permite consultar el estado de una corutina (`done()`, `exception()`, `result()`, `cancel()`). |
| **`Task.result()`** | Método — `asyncio.Task` | Obtener el valor de retorno de una tarea completada | Solo se puede llamar cuando la tarea ya está en `done`. En los servicios aiohttp devuelve la `ClientResponse`. |
| **`Task.exception()`** | Método — `asyncio.Task` | Comprobar si una tarea terminó con error | Devuelve la excepción que causó el fallo, o `None` si terminó correctamente. Solo válido en tareas dentro de `done`. |
| **`Task.cancel()`** | Método — `asyncio.Task` | Cancelar una tarea pendiente | Lanza `CancelledError` en la corutina subyacente. Esencial para liberar recursos cuando una tarea en `pending` ya no se necesita. |
| **`aiohttp.web.Application`** | Clase — `aiohttp` | Contenedor principal de una aplicación web asíncrona | Gestiona rutas, hooks de ciclo de vida (`on_startup`, `on_cleanup`) y el almacenamiento compartido entre handlers (accesible como diccionario `app[key]`). |
| **`aiohttp.web.RouteTableDef`** | Clase — `aiohttp` | Declarar rutas HTTP de forma decorativa | Permite usar `@routes.get(...)`, `@routes.post(...)`, etc. para asociar handlers a rutas sin llamar directamente a `app.router.add_route()`. |
| **`aiohttp.web.run_app()`** | Función — `aiohttp` | Arrancar el servidor HTTP | Inicia el event loop, ejecuta los hooks `on_startup`, pone el servidor a escuchar en el puerto indicado y ejecuta `on_cleanup` al cerrar. |
| **`aiohttp.ClientSession`** | Clase — `aiohttp` | Realizar peticiones HTTP salientes de forma asíncrona | Gestiona conexiones, cookies y cabeceras de forma reutilizable. Se usa como context manager (`async with`) para asegurar el cierre de conexiones. Usado en el BFF para llamar a los demás servicios. |
| **`on_startup`** | Hook — `aiohttp` | Ejecutar código antes de que el servidor empiece a aceptar peticiones | Lista de corutinas que aiohttp llama al arrancar. Se usa para crear el pool de base de datos. Solo recibe el objeto `app` como argumento. |
| **`on_cleanup`** | Hook — `aiohttp` | Ejecutar código al apagar el servidor | Lista de corutinas llamadas al cerrar. Se usa para destruir el pool de base de datos y liberar conexiones. |
| **`functools.partial()`** | Función — `functools` | Crear una función parcialmente aplicada | Permite pasar argumentos adicionales a una función que solo acepta un parámetro. En aiohttp, `on_startup` solo pasa `app`, por lo que `partial` inyecta el resto de parámetros de conexión a la base de datos. |
| **`asyncpg.create_pool()`** | Función — `asyncpg` | Crear un pool de conexiones a PostgreSQL | Establece un conjunto de conexiones reutilizables (`min_size`, `max_size`). Evita abrir/cerrar una conexión por cada request, mejorando el rendimiento. |
| **`pool.fetch()`** | Método — `asyncpg.Pool` | Ejecutar una query y obtener todas las filas | Devuelve una lista de objetos `Record`. Cada `Record` se puede convertir a `dict` con `dict(record)`. Equivalente a `SELECT` con múltiples resultados. |
| **`DB_KEY`** | Constante — `listing_10_4` | Clave para acceder al pool de DB desde el objeto `app` | String `'database'` usado como clave en el diccionario `Application`. Centraliza el acceso al pool sin acoplar los servicios a strings literales. |
| **`web.json_response()`** | Función — `aiohttp` | Devolver una respuesta HTTP con cuerpo JSON | Serializa automáticamente el diccionario o lista a JSON y establece `Content-Type: application/json`. Acepta `status` para códigos de error (400, 404, 500, 504). |
| **`web.HTTPBadRequest`** | Excepción — `aiohttp` | Señalizar un error 400 al cliente | Se lanza cuando la entrada del cliente es inválida (p.ej. `user_id` no es un entero). aiohttp la convierte automáticamente en una respuesta HTTP 400. |
| **`web.HTTPNotFound`** | Excepción — `aiohttp` | Señalizar un error 404 al cliente | Se lanza cuando el recurso solicitado no existe en la base de datos. aiohttp la convierte en una respuesta HTTP 404. |
| **`CircuitBreaker`** | Clase — `listing_10_11` | Proteger llamadas a servicios externos ante fallos repetidos | Mantiene contadores de fallos y tiempos. Si `current_failures >= max_failures`, el circuito está abierto y falla instantáneamente. Se resetea tras `reset_interval` segundos. |
| **`CircuitOpenException`** | Excepción — `listing_10_11` | Señalizar que el circuito está abierto | Se lanza en `CircuitBreaker.request()` cuando el circuito está abierto y no ha pasado el `reset_interval`. El llamador puede capturarla para aplicar un fallback. |
| **`current_failures`** | Atributo — `CircuitBreaker` | Contar los fallos acumulados en la ventana de tiempo | Se incrementa en `_do_request()` cada vez que el callback lanza una excepción. Se resetea a 0 cuando se llama a `_reset()`. |
| **`time_window`** | Parámetro — `CircuitBreaker` | Ventana de tiempo en la que se cuentan los fallos | Si el primer fallo ocurrió hace más de `time_window` segundos, los fallos anteriores se descartan y el circuito se resetea (aunque no haya llegado a `max_failures`). |
| **`reset_interval`** | Parámetro — `CircuitBreaker` | Tiempo de espera antes de intentar cerrar el circuito | Cuando el circuito está abierto, si han pasado `reset_interval` segundos desde la última petición real, se intenta cerrar el circuito y se hace una nueva petición de prueba. |
| **`timeout`** | Parámetro — `CircuitBreaker` / `asyncio.wait` | Tiempo máximo de espera para una operación | En el `CircuitBreaker`, es el límite por petición en `_do_request`. En `asyncio.wait`, es el límite global para el conjunto de tareas concurrentes. |
| **`done` / `pending`** | Conjuntos — `asyncio.wait` | Separar tareas completadas de tareas aún en ejecución | `done` contiene tasks que terminaron (con éxito o con error); `pending` contiene las que no terminaron antes del timeout. Esta separación permite un manejo diferenciado de cada caso. |
| **`ClientResponse.json()`** | Método — `aiohttp` | Deserializar el cuerpo de una respuesta HTTP como JSON | Es una corutina, por lo que requiere `await`. Equivale a `json.loads(await response.text())`. Se accede como `await task.result().json()`. |
| **Bajo acoplamiento** | Principio de diseño | Minimizar las dependencias entre servicios | Cada microservicio puede desplegarse, escalarse y fallar de forma independiente. Un cambio en un servicio no debería requerir cambios en los demás. |
| **Responsabilidad única** | Principio de diseño | Que cada servicio haga una sola cosa bien | Derivado del *Single Responsibility Principle*. Reduce la complejidad interna y facilita el mantenimiento y la escalabilidad selectiva. |
| **HTTP 504 Gateway Timeout** | Código de estado HTTP | Informar que un servicio upstream no respondió a tiempo | Usado en el BFF cuando el Product Service no responde en 1 segundo. Indica al cliente que el problema es de disponibilidad, no de su petición. |
| **HTTP 500 Internal Server Error** | Código de estado HTTP | Informar de un error inesperado en el servidor | Usado en el BFF cuando el Product Service responde pero lanza una excepción. Diferencia un fallo de red (504) de un error de aplicación (500). |
