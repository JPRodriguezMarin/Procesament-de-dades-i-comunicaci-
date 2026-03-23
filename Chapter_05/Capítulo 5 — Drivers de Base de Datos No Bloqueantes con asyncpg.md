# Capítulo 5 — Drivers de Base de Datos No Bloqueantes con asyncpg

> **Fuente principal:** Fowler, Matthew. *Python Concurrency with Asyncio*. Manning Publications, 2022. Capítulo 5: Non-blocking database drivers.

***

## Visión General del Capítulo

Este capítulo aborda el problema fundamental de acceder a bases de datos relacionales de forma **asíncrona y no bloqueante** desde Python. Las bibliotecas SQL tradicionales (como `psycopg2`) bloquean el hilo principal hasta que la base de datos devuelve una respuesta, lo que impide al *event loop* de asyncio ejecutar otras tareas de forma concurrente. La solución es usar una biblioteca compatible con asyncio que utilice sockets no bloqueantes: **asyncpg**.[^1]

Los cuatro grandes temas del capítulo son:[^1]

1. Ejecutar consultas de forma compatible con asyncio usando **asyncpg**.
2. Crear **pools de conexiones** para ejecutar múltiples consultas concurrentemente.
3. Gestionar **transacciones** asíncronas de base de datos.
4. Usar **generadores asíncronos** para transmitir (*stream*) resultados de consultas.

***

## 5.1 — Introducción a asyncpg

### ¿Por qué no funcionan las bibliotecas clásicas?

Las bibliotecas tradicionales de acceso a bases de datos en Python siguen la especificación PEP-249 (Python Database API), que es sincrónica por diseño. Al ejecutar una consulta, el hilo queda bloqueado hasta que llega la respuesta, paralizando el *event loop* de asyncio e impidiendo la concurrencia real.[^1]

### La biblioteca asyncpg

`asyncpg` es una biblioteca diseñada específicamente para conectarse a PostgreSQL de forma asíncrona, usando sockets no bloqueantes compatibles con asyncio. Algunas características clave:[^2][^1]

- Es, en promedio, **5 veces más rápida** que `psycopg3` según los benchmarks de su documentación oficial.[^2]
- **No implementa PEP-249** de forma deliberada, ya que una implementación concurrente es inherentemente diferente de una síncrona.[^1]
- Implementa directamente el protocolo binario del servidor PostgreSQL, lo que le permite exponer características como cursores desplazables, iteración parcial de resultados y codificación/decodificación automática de tipos compuestos.[^2]
- La biblioteca equivalente para MySQL se llama `aiomysql`, y aunque tiene un API similar, sí implementa PEP-249, resultando más familiar para usuarios de drivers síncronos.[^1]

### Instalación

```bash
pip3 install -Iv asyncpg==0.23.0
```

***

## 5.2 — Conectando a una Base de Datos PostgreSQL

El punto de entrada principal es la función `asyncpg.connect()`, que devuelve una corrutina (debe ser esperada con `await`) y establece una única conexión TCP al servidor de PostgreSQL.[^3][^1]

### Listing 5.1 — Primera conexión

```python
import asyncpg
import asyncio

async def main():
    connection = await asyncpg.connect(
        host='127.0.0.1',
        port=5432,
        user='postgres',
        database='postgres',
        password='password'
    )
    version = connection.get_server_version()
    print(f'Connected! Postgres version is {version}')
    await connection.close()

asyncio.run(main())
```

**Explicación línea a línea:**

| Instrucción | Qué hace |
|---|---|
| `asyncpg.connect(...)` | Abre una conexión TCP al servidor PostgreSQL. Retorna una corrutina, por eso se usa `await`. |
| `connection.get_server_version()` | Método síncrono (no requiere `await`) que devuelve la versión del servidor como un objeto con campos `major`, `minor`, `micro`. |
| `await connection.close()` | Cierra la conexión de forma limpia. Es una corrutina y requiere `await`. |
| `asyncio.run(main())` | Inicia el *event loop* de asyncio y ejecuta la corrutina `main`. |

> ⚠️ **Advertencia de seguridad (del propio libro):** Las contraseñas están escritas directamente en el código con fines didácticos. En producción, **nunca** se deben escribir contraseñas en el código fuente. Se deben usar variables de entorno u otros mecanismos de configuración seguros.[^1]

***

## 5.3 — Definiendo el Esquema de Base de Datos

El capítulo trabaja sobre un escenario de tienda de comercio electrónico para ilustrar los conceptos. Se modelan cinco entidades con las siguientes relaciones:[^1]

| Entidad | Descripción | Relación |
|---|---|---|
| `brand` | Fabricante/marca de productos (ej. Ford) | Uno a muchos con `product` |
| `product` | Producto concreto (ej. Ford Fiesta) | Uno a muchos con `sku` |
| `product_color` | Color disponible (Blue, Black) | Uno a muchos con `sku` |
| `product_size` | Talla disponible (Small, Medium, Large) | Uno a muchos con `sku` |
| `sku` | *Stock Keeping Unit*: combinación única de producto + talla + color | Entidad hoja |

### Listing 5.2 — Sentencias SQL de creación de tablas

```python
CREATE_BRAND_TABLE = """
CREATE TABLE IF NOT EXISTS brand(
    brand_id SERIAL PRIMARY KEY,
    brand_name TEXT NOT NULL
);"""

CREATE_PRODUCT_TABLE = """
CREATE TABLE IF NOT EXISTS product(
    product_id SERIAL PRIMARY KEY,
    product_name TEXT NOT NULL,
    brand_id INT NOT NULL,
    FOREIGN KEY (brand_id) REFERENCES brand(brand_id)
);"""

CREATE_PRODUCT_COLOR_TABLE = """
CREATE TABLE IF NOT EXISTS product_color(
    product_color_id SERIAL PRIMARY KEY,
    product_color_name TEXT NOT NULL
);"""

CREATE_PRODUCT_SIZE_TABLE = """
CREATE TABLE IF NOT EXISTS product_size(
    product_size_id SERIAL PRIMARY KEY,
    product_size_name TEXT NOT NULL
);"""

CREATE_SKU_TABLE = """
CREATE TABLE IF NOT EXISTS sku(
    sku_id SERIAL PRIMARY KEY,
    product_id INT NOT NULL,
    product_size_id INT NOT NULL,
    product_color_id INT NOT NULL,
    FOREIGN KEY (product_id) REFERENCES product(product_id),
    FOREIGN KEY (product_size_id) REFERENCES product_size(product_size_id),
    FOREIGN KEY (product_color_id) REFERENCES product_color(product_color_id)
);"""

COLOR_INSERT = """
INSERT INTO product_color VALUES(1, 'Blue');
INSERT INTO product_color VALUES(2, 'Black');
"""

SIZE_INSERT = """
INSERT INTO product_size VALUES(1, 'Small');
INSERT INTO product_size VALUES(2, 'Medium');
INSERT INTO product_size VALUES(3, 'Large');
"""
```

**Puntos clave del esquema SQL:**
- `SERIAL PRIMARY KEY`: PostgreSQL genera automáticamente un ID autoincremental.
- `IF NOT EXISTS`: Evita errores si la tabla ya existe al volver a ejecutar el script.
- Las claves foráneas (`FOREIGN KEY ... REFERENCES`) garantizan la integridad referencial.

***

## 5.4 — Ejecutando Consultas con asyncpg

### Crear la base de datos (fuera de Python)

Antes de ejecutar código Python, se debe crear la base de datos desde la línea de comandos:[^1]

```bash
sudo -u postgres psql -c "CREATE DATABASE products;"
```

### Los tres métodos fundamentales de consulta

| Método | Uso | Retorna |
|---|---|---|
| `await connection.execute(sql)` | Ejecutar sentencias DDL o DML sin retorno de filas | `str` con el estado de la operación (p. ej. `"CREATE TABLE"`) |
| `await connection.fetch(sql)` | Obtener múltiples filas | `List[Record]` (toda la lista en memoria) |
| `await connection.fetchrow(sql)` | Obtener una sola fila | `Record` o `None` |

### Listing 5.3 — Ejecutar las sentencias CREATE con execute()

```python
import asyncpg
import asyncio

async def main():
    connection = await asyncpg.connect(
        host='127.0.0.1', port=5432,
        user='postgres', database='products', password='password'
    )
    statements = [
        CREATE_BRAND_TABLE, CREATE_PRODUCT_TABLE,
        CREATE_PRODUCT_COLOR_TABLE, CREATE_PRODUCT_SIZE_TABLE,
        CREATE_SKU_TABLE, SIZE_INSERT, COLOR_INSERT
    ]
    print('Creating the product database...')
    for statement in statements:
        status = await connection.execute(statement)
        print(status)
    print('Finished creating the product database!')
    await connection.close()

asyncio.run(main())
```

**Explicación clave:** Las sentencias se ejecutan **una por una en secuencia** dentro del bucle `for` (gracias al `await`). Esto es correcto en este caso porque algunas tablas dependen de otras (hay claves foráneas), por lo que no se pueden crear en paralelo.[^1]

### Listing 5.4 — Insertar y consultar marcas

```python
import asyncpg
import asyncio
from asyncpg import Record
from typing import List

async def main():
    connection = await asyncpg.connect(
        host='127.0.0.1', port=5432,
        user='postgres', database='products', password='password'
    )
    await connection.execute("INSERT INTO brand VALUES(DEFAULT, 'Levis')")
    await connection.execute("INSERT INTO brand VALUES(DEFAULT, 'Seven')")

    brand_query = 'SELECT brand_id, brand_name FROM brand'
    results: List[Record] = await connection.fetch(brand_query)

    for brand in results:
        print(f'id: {brand["brand_id"]}, name: {brand["brand_name"]}')

    await connection.close()

asyncio.run(main())
```

**Puntos a destacar:**
- `DEFAULT` en el INSERT le dice a PostgreSQL que genere el `brand_id` automáticamente.
- `connection.fetch()` trae **todos los resultados a memoria** como una lista de objetos `Record`.
- Un `Record` se comporta como un diccionario: se accede a los campos por nombre con corchetes (`brand["brand_id"]`).[^1]
- Salida esperada: `id: 1, name: Levis` y `id: 2, name: Seven`.

***

## 5.5 — Ejecutando Consultas Concurrentemente con Pools de Conexión

### El problema de la concurrencia con una sola conexión

Si se intenta usar `asyncio.gather` con una sola conexión para ejecutar dos consultas en paralelo, el resultado es un error en tiempo de ejecución:[^1]

```python
# ¡ESTO FALLA!
queries = [connection.execute(product_query), connection.execute(product_query)]
results = await asyncio.gather(*queries)
# RuntimeError: readexactly() called while another coroutine is already waiting for incoming data
```

**¿Por qué falla?** Una conexión SQL equivale a un único socket TCP. No se pueden leer resultados de múltiples consultas al mismo tiempo a través de ese socket.[^1]

### 5.5.1 — Insertando SKUs Aleatorios (Listing 5.5 y 5.6)

Antes de demostrar la concurrencia, el libro genera datos de prueba: 100 marcas, 1.000 productos y 100.000 SKUs aleatorios usando las palabras más comunes del inglés.

**Método clave: `executemany()`**

```python
# Sintaxis de parámetros posicionales en asyncpg: $1, $2, $3...
insert_query = "INSERT INTO brand VALUES(DEFAULT, $1)"
brands = [('Nike',), ('Adidas',), ('Puma',)]
await connection.executemany(insert_query, brands)
```

`executemany` acepta una sentencia SQL parametrizada y una lista de tuplas. Ejecuta la sentencia una vez por cada tupla. La parametrización previene inyecciones SQL al sanitizar los valores de entrada.[^1]

### Listing 5.5 — Insertar marcas aleatorias

```python
import asyncpg, asyncio
from typing import List, Tuple, Union
from random import sample

def load_common_words() -> List[str]:
    with open('common_words.txt') as common_words:
        return common_words.readlines()

def generate_brand_names(words: List[str]) -> List[Tuple[Union[str,]]]:
    return [(words[index],) for index in sample(range(100), 100)]

async def insert_brands(common_words, connection) -> int:
    brands = generate_brand_names(common_words)
    insert_brands = "INSERT INTO brand VALUES(DEFAULT, $1)"
    return await connection.executemany(insert_brands, brands)

async def main():
    common_words = load_common_words()
    connection = await asyncpg.connect(
        host='127.0.0.1', port=5432,
        user='postgres', database='products', password='password'
    )
    await insert_brands(common_words, connection)

asyncio.run(main())
```

### 5.5.2 — Creando un Pool de Conexiones

Un **pool de conexiones** es una caché de conexiones ya establecidas a la base de datos, reutilizables para distintas consultas. Su objetivo es evitar el coste de crear nuevas conexiones para cada operación (establecer una conexión TCP es caro en tiempo).[^3][^1]

**Funcionamiento del pool:**

1. La corrutina que necesita ejecutar una consulta **adquiere** una conexión del pool.
2. Si hay conexiones disponibles, obtiene una inmediatamente.
3. Si todas están ocupadas, **suspende** su ejecución hasta que una se libere.
4. Al terminar, la conexión se **devuelve** automáticamente al pool.

**Los parámetros `min_size` y `max_size`:**
- `min_size`: número mínimo de conexiones garantizadas desde el inicio.
- `max_size`: número máximo de conexiones simultáneas que puede tener el pool.[^3][^1]

### Listing 5.7 — Pool de conexiones y consultas concurrentes

```python
import asyncio
import asyncpg

product_query = """
SELECT p.product_id, p.product_name, p.brand_id,
       s.sku_id, pc.product_color_name, ps.product_size_name
FROM product as p
JOIN sku as s on s.product_id = p.product_id
JOIN product_color as pc on pc.product_color_id = s.product_color_id
JOIN product_size as ps on ps.product_size_id = s.product_size_id
WHERE p.product_id = 100"""

async def query_product(pool):
    async with pool.acquire() as connection:   # ① Adquiere conexión del pool
        return await connection.fetchrow(product_query)

async def main():
    async with asyncpg.create_pool(
        host='127.0.0.1', port=5432,
        user='postgres', password='password',
        database='products', min_size=6, max_size=6   # ② Pool de 6 conexiones
    ) as pool:
        await asyncio.gather(                         # ③ Ejecuta en paralelo
            query_product(pool),
            query_product(pool)
        )

asyncio.run(main())
```

**Explicación detallada:**

| Instrucción | Qué hace |
|---|---|
| `asyncpg.create_pool(...)` | Crea el pool como gestor de contexto asíncrono (`async with`). Al salir del bloque, cierra todas las conexiones. |
| `pool.acquire()` | Corrutina que obtiene una conexión libre. Si no hay ninguna disponible, suspende la ejecución hasta que alguna se libere. Se usa como `async with` para devolverla automáticamente al pool. |
| `asyncio.gather(...)` | Programa las dos corrutinas para ejecutarse concurrentemente. |

> ⚠️ **Atención:** Si no se usa `async with pool.acquire()`, la conexión no se devuelve al pool y la aplicación puede bloquearse indefinidamente esperando una conexión que nunca quedará disponible.[^1]

### Listing 5.8 — Comparativa: secuencial vs. concurrente con 10.000 consultas

```python
import asyncio, asyncpg
from util import async_timed

async def query_product(pool):
    async with pool.acquire() as connection:
        return await connection.fetchrow(product_query)

@async_timed()
async def query_products_synchronously(pool, queries):
    # Await dentro de la comprensión → fuerza ejecución secuencial
    return [await query_product(pool) for _ in range(queries)]

@async_timed()
async def query_products_concurrently(pool, queries):
    # Crear lista de corrutinas sin await → ejecutar todas con gather
    queries = [query_product(pool) for _ in range(queries)]
    return await asyncio.gather(*queries)

async def main():
    async with asyncpg.create_pool(..., min_size=6, max_size=6) as pool:
        await query_products_synchronously(pool, 10000)
        await query_products_concurrently(pool, 10000)

asyncio.run(main())
```

**Resultados medidos (pueden variar según el hardware):**[^1]

| Enfoque | Tiempo |
|---|---|
| Secuencial (`await` dentro de la comprensión) | ~21.83 segundos |
| Concurrente (`asyncio.gather`) | ~4.85 segundos |

La versión concurrente es **casi 5 veces más rápida**. La diferencia clave es dónde se coloca `await`:
- En la comprensión de lista con `await`: obliga a esperar que cada consulta termine antes de iniciar la siguiente (secuencial).
- En la lista de corrutinas sin `await` + `gather`: todas las corrutinas se programan para ejecutarse a la vez (concurrente).[^1]

***

## 5.6 — Gestionando Transacciones con asyncpg

### Concepto ACID

Una transacción es un conjunto de sentencias SQL que se ejecutan como una **unidad atómica**. Si todas tienen éxito, se confirman (*commit*); si alguna falla, se revierten todas (*rollback*). Esto garantiza las propiedades ACID: **Atomicidad, Consistencia, Aislamiento y Durabilidad**.[^3][^1]

### Listing 5.9 — Transacción básica con gestor de contexto

```python
import asyncio
import asyncpg

async def main():
    connection = await asyncpg.connect(
        host='127.0.0.1', port=5432,
        user='postgres', database='products', password='password'
    )
    async with connection.transaction():   # ① Inicia la transacción
        await connection.execute("INSERT INTO brand VALUES(DEFAULT, 'brand_1')")
        await connection.execute("INSERT INTO brand VALUES(DEFAULT, 'brand_2')")
    # ② Si no hubo excepción → commit automático
    # ② Si hubo excepción → rollback automático

    query = """SELECT brand_name FROM brand WHERE brand_name LIKE 'brand%'"""
    brands = await connection.fetch(query)
    print(brands)   # Debería imprimir las dos marcas insertadas
    await connection.close()

asyncio.run(main())
```

**Comportamiento del gestor de contexto `connection.transaction()`:**
- Al entrar en el bloque `async with`: emite `BEGIN` a PostgreSQL.
- Si el bloque termina sin excepciones: emite `COMMIT`.
- Si ocurre una excepción: emite `ROLLBACK` automáticamente.[^3][^1]

### Listing 5.10 — Manejo de errores y rollback

```python
import asyncio, logging, asyncpg

async def main():
    connection = await asyncpg.connect(
        host='127.0.0.1', port=5432,
        user='postgres', database='products', password='password'
    )
    try:
        async with connection.transaction():
            insert_brand = "INSERT INTO brand VALUES(9999, 'big_brand')"
            await connection.execute(insert_brand)      # ① Primer INSERT: funciona
            await connection.execute(insert_brand)      # ② Segundo INSERT: falla (clave duplicada)
    except Exception:
        logging.exception('Error while running transaction')   # ③ Loguea el error
    finally:
        query = """SELECT brand_name FROM brand WHERE brand_name LIKE 'big_%'"""
        brands = await connection.fetch(query)
        print(f'Query result was: {brands}')  # ④ Debería estar vacío (rollback exitoso)
    await connection.close()

asyncio.run(main())
```

**Salida esperada:**
```
ERROR:root:Error while running transaction
asyncpg.exceptions.UniqueViolationError: duplicate key value violates unique constraint "brand_pkey"
Query result was: []
```

El resultado vacío confirma que el *rollback* fue exitoso: ninguno de los dos INSERTs quedó en la base de datos.[^1]

### 5.6.1 — Transacciones Anidadas (Savepoints)

Las transacciones anidadas en asyncpg se implementan mediante la característica de PostgreSQL llamada **savepoints**. Un savepoint es un punto de control dentro de una transacción: si la parte interna falla, solo se revierte hasta ese punto sin afectar a la transacción externa.[^3][^1]

### Listing 5.11 — Transacción anidada

```python
import asyncio, asyncpg, logging

async def main():
    connection = await asyncpg.connect(
        host='127.0.0.1', port=5432,
        user='postgres', database='products', password='password'
    )
    async with connection.transaction():               # ① Transacción externa (SAVEPOINT padre)
        await connection.execute("INSERT INTO brand VALUES(DEFAULT, 'my_new_brand')")
        try:
            async with connection.transaction():       # ② Transacción interna (SAVEPOINT hijo)
                await connection.execute("INSERT INTO product_color VALUES(1, 'black')")  # ③ Falla: clave duplicada
        except Exception as ex:
            logging.warning('Ignoring error inserting product color', exc_info=ex)
        # ④ La marca 'my_new_brand' SÍ se insertó correctamente
    await connection.close()

asyncio.run(main())
```

**Mecanismo:**
- El `INSERT INTO brand` externo tiene éxito.
- El `INSERT INTO product_color` interno falla (el color con id=1 ya existe).
- Como el fallo ocurre dentro de la transacción anidada y la excepción es capturada, **solo se revierte el INSERT interno**.
- La marca `my_new_brand` queda persistida en la base de datos.[^1]

Sin la transacción anidada, el fallo del segundo INSERT habría revertido también el primero.

### 5.6.2 — Gestión Manual de Transacciones

En casos especiales, puede ser necesario controlar manualmente el inicio, *commit* y *rollback* de una transacción (por ejemplo, para ejecutar lógica personalizada en el *rollback*).[^1]

### Listing 5.12 — Transacción gestionada manualmente

```python
import asyncio, asyncpg
from asyncpg.transaction import Transaction

async def main():
    connection = await asyncpg.connect(
        host='127.0.0.1', port=5432,
        user='postgres', database='products', password='password'
    )
    transaction: Transaction = connection.transaction()  # ① Crear instancia (no inicia aún)
    await transaction.start()                            # ② Inicia la transacción (emite BEGIN)
    try:
        await connection.execute("INSERT INTO brand VALUES(DEFAULT, 'brand_1')")
        await connection.execute("INSERT INTO brand VALUES(DEFAULT, 'brand_2')")
    except asyncpg.PostgresError:
        print('Errors, rolling back transaction!')
        await transaction.rollback()                     # ③ Rollback explícito en caso de error
    else:
        print('No errors, committing transaction!')
        await transaction.commit()                       # ④ Commit explícito si todo fue bien

    query = """SELECT brand_name FROM brand WHERE brand_name LIKE 'brand%'"""
    brands = await connection.fetch(query)
    print(brands)
    await connection.close()

asyncio.run(main())
```

**Comparativa de enfoques para transacciones:**

| Enfoque | Cuándo usarlo | Ventaja |
|---|---|---|
| `async with connection.transaction()` | Mayoría de los casos | Menos verboso, gestión automática |
| Objeto `Transaction` manual | Lógica personalizada en rollback; condición de rollback distinta a una excepción | Control total del flujo |

***

## 5.7 — Generadores Asíncronos y Streaming de Resultados

### El problema de fetch() y la memoria

El método `connection.fetch()` carga **todos los resultados en memoria RAM** de una sola vez. Para consultas que devuelven millones de filas, esto puede saturar la memoria del sistema.[^3][^1]

Las alternativas típicas de paginación (con `LIMIT/OFFSET`) implican enviar la misma consulta múltiples veces al servidor, generando carga extra en la base de datos. La solución óptima para grandes conjuntos de datos es el **streaming con cursores**.[^1]

### Cursores en PostgreSQL y asyncpg

Un **cursor** es un puntero a la posición actual dentro de un conjunto de resultados en PostgreSQL. En lugar de devolver todas las filas a la vez, el cursor permite obtener filas de forma incremental, reduciendo el consumo de memoria en la aplicación.[^3][^1]

Asyncpg expone los cursores a través de `connection.cursor()`, que soporta:[^3]
- Iteración asíncrona mediante `async for`.
- Lectura de bloques de filas con `cursor.fetch(n)`.
- Salto de filas con `cursor.forward(n)`.

> **Requisito importante:** Los cursores deben ejecutarse **dentro de una transacción activa** (`async with connection.transaction()`).[^3][^1]

### Generadores Asíncronos en Python

Antes de ver el código de cursores del libro, es necesario entender el concepto de **generadores asíncronos** (introducidos en Python 3.6 con PEP-525).

Un generador asíncrono es una función `async def` que contiene la instrucción `yield`. Al llamarla, no ejecuta el cuerpo inmediatamente; en su lugar, devuelve un objeto iterable asíncrono que se puede recorrer con `async for`.[^1]

**Ejemplo conceptual de generador asíncrono:**

```python
async def mi_generador_asincrono():
    yield 1      # Emite el valor 1 y suspende la ejecución
    yield 2      # Cuando se pide el siguiente, emite 2
    yield 3      # Idem para 3

async def main():
    async for valor in mi_generador_asincrono():
        print(valor)   # Imprime: 1, 2, 3
```

La diferencia respecto a los generadores síncronos es que `yield` puede combinarse con `await`, permitiendo operaciones asíncronas entre cada valor emitido.

### Uso de cursores con async for

El código de los últimos listados del capítulo (5.13 y 5.14, mostrados en las imágenes del documento) ilustra cómo crear un generador asíncrono que use un cursor para transmitir filas de la base de datos. El patrón general es:[^4][^3][^1]

```python
import asyncio
import asyncpg

async def fetch_rows_with_cursor(connection, query: str):
    """Generador asíncrono que emite filas de una por una."""
    async with connection.transaction():            # ① Cursor requiere transacción activa
        async for record in connection.cursor(query):   # ② Itera sobre el cursor
            yield record                            # ③ Emite cada fila individualmente

async def main():
    connection = await asyncpg.connect(
        host='127.0.0.1', port=5432,
        user='postgres', database='products', password='password'
    )
    query = "SELECT product_id, product_name FROM product"

    async for row in fetch_rows_with_cursor(connection, query):   # ④ Consume el generador
        print(f'Product: {row["product_id"]} - {row["product_name"]}')

    await connection.close()

asyncio.run(main())
```

**Explicación del flujo:**

| Paso | Instrucción | Qué ocurre |
|---|---|---|
| ① | `async with connection.transaction()` | Se abre una transacción; requerida por el cursor. |
| ② | `connection.cursor(query)` | Se crea el cursor; asyncpg prefetch 50 filas por defecto. |
| ③ | `yield record` | El generador emite la fila y **suspende** su ejecución hasta que se le pida la siguiente. |
| ④ | `async for row in fetch_rows_with_cursor(...)` | El llamador consume el generador fila a fila, sin cargar todo en memoria. |

### Comparativa: fetch() vs. cursor streaming

| Característica | `connection.fetch()` | Cursor con `async for` |
|---|---|---|
| Consumo de memoria | Alto (todo en RAM) | Bajo (pocas filas en RAM) |
| Viajes de red | Uno (traer todo) | Varios (por bloques o por fila) |
| Adecuado para | Consultas con pocos resultados | Consultas con millones de filas |
| Complejidad de código | Baja | Media |
| Requiere transacción | No | Sí |

***

## Resumen de Conceptos Clave del Capítulo

| Concepto | Clase/Función | Descripción |
|---|---|---|
| Conexión única | `asyncpg.connect()` | Una conexión = un socket = una consulta a la vez |
| Pool de conexiones | `asyncpg.create_pool()` | Múltiples conexiones reutilizables para concurrencia |
| Adquirir conexión | `pool.acquire()` | Obtener una conexión libre del pool (`async with`) |
| Ejecutar sentencia | `connection.execute()` | Para DDL/DML sin retorno de filas |
| Inserción múltiple | `connection.executemany()` | Ejecutar una sentencia con muchos conjuntos de parámetros |
| Consultar filas | `connection.fetch()` | Todas las filas en memoria como `List[Record]` |
| Consultar una fila | `connection.fetchrow()` | Solo la primera fila |
| Transacción | `connection.transaction()` | Gestor de contexto; auto-commit/rollback |
| Transacción anidada | Anidar `connection.transaction()` | Implementa savepoints de PostgreSQL |
| Streaming | `connection.cursor()` | Iterar resultados fila a fila con `async for` |

***

## 10 Preguntas de Autoevaluación

### Preguntas de Teoría

**1.** ¿Por qué las bibliotecas de acceso a bases de datos que siguen PEP-249 no son adecuadas para usar con asyncio?

- A) Porque no soportan PostgreSQL.
- B) Porque bloquean el hilo principal hasta recibir la respuesta, paralizando el *event loop* de asyncio.
- C) Porque no implementan transacciones.
- D) Porque consumen demasiada memoria RAM.

> ✅ **Respuesta correcta: B.** Las bibliotecas síncronas bloquean el hilo de ejecución mientras esperan la respuesta de la base de datos, lo que impide que el *event loop* procese otras tareas.[^1]

***

**2.** ¿Qué sucede si se intenta ejecutar dos consultas de forma concurrente usando `asyncio.gather` sobre **una sola conexión** de asyncpg?

- A) Las consultas se ejecutan concurrentemente sin problemas.
- B) La segunda consulta espera en cola hasta que termina la primera.
- C) Se produce un `RuntimeError` porque el socket subyacente no puede leer dos respuestas a la vez.
- D) Se ejecutan en paralelo en hilos separados.

> ✅ **Respuesta correcta: C.** Una conexión es un único socket TCP; intentar leer resultados de dos consultas simultáneamente genera `RuntimeError: readexactly() called while another coroutine is already waiting for incoming data`.[^1]

***

**3.** En un pool de conexiones de asyncpg con `min_size=6` y `max_size=6`, ¿qué ocurre cuando una séptima corrutina intenta adquirir una conexión mientras las seis están en uso?

- A) Lanza una excepción `PoolExhaustedError`.
- B) Crea automáticamente una séptima conexión temporal.
- C) Su ejecución se **suspende** hasta que una de las seis conexiones quede libre.
- D) La consulta se descarta silenciosamente.

> ✅ **Respuesta correcta: C.** `pool.acquire()` es una corrutina que suspende la ejecución de la tarea llamante hasta que haya una conexión disponible.[^1]

***

**4.** ¿Cuál es la diferencia principal entre `connection.transaction()` usado como `async with` y la gestión manual del objeto `Transaction`?

- A) La gestión manual no soporta *rollback*.
- B) El `async with` solo funciona para inserciones, no para consultas SELECT.
- C) El `async with` gestiona automáticamente el *commit* y *rollback*; la gestión manual permite lógica personalizada o condiciones de *rollback* distintas a una excepción.
- D) No hay diferencia funcional entre ambos enfoques.

> ✅ **Respuesta correcta: C.** El gestor de contexto simplifica el código al automatizar el *commit/rollback*, pero la gestión manual es necesaria cuando se requiere ejecutar código personalizado en caso de *rollback* o cuando el criterio de revertir no es una excepción.[^1]

***

**5.** ¿En qué se diferencia una transacción anidada en asyncpg de una transacción normal? ¿Qué característica de PostgreSQL utiliza?

- A) No hay diferencia; asyncpg no soporta transacciones anidadas.
- B) Utiliza la instrucción `SAVEPOINT` de PostgreSQL: el fallo en la transacción interna solo revierte hasta el savepoint, sin afectar a la transacción externa.
- C) Utiliza hilos separados para aislar las transacciones.
- D) La transacción interna siempre hace *commit* independientemente de errores.

> ✅ **Respuesta correcta: B.** Al llamar a `connection.transaction()` dentro de un bloque `connection.transaction()` ya activo, asyncpg emite un `SAVEPOINT` de PostgreSQL, permitiendo que el fallo interno se revierta de forma aislada.[^3][^1]

***

### Preguntas de Código

**6.** Observa el siguiente fragmento de código. ¿Cuál es el resultado esperado y por qué?

```python
async def main():
    connection = await asyncpg.connect(...)
    async with connection.transaction():
        insert = "INSERT INTO brand VALUES(9999, 'test_brand')"
        await connection.execute(insert)
        await connection.execute(insert)  # Falla: clave duplicada
```

- A) Las dos inserciones quedan en la base de datos porque la primera tuvo éxito.
- B) Ninguna inserción queda en la base de datos; se hace *rollback* de las dos.
- C) Solo la segunda inserción se revierte; la primera queda en la base de datos.
- D) El programa se bloquea indefinidamente.

> ✅ **Respuesta correcta: B.** Cuando el segundo `execute` lanza `UniqueViolationError`, el gestor de contexto de la transacción hace *rollback* automático de **toda** la transacción, incluyendo la primera inserción que había tenido éxito.[^1]

***

**7.** ¿Qué diferencia existe entre estos dos fragmentos de código en términos de rendimiento y comportamiento?

```python
# Fragmento A
result = [await query_product(pool) for _ in range(1000)]

# Fragmento B
coroutines = [query_product(pool) for _ in range(1000)]
result = await asyncio.gather(*coroutines)
```

- A) Son equivalentes en rendimiento; la diferencia es solo sintáctica.
- B) El Fragmento A es más rápido porque evita la sobrecarga de `gather`.
- C) El Fragmento A ejecuta las consultas **secuencialmente** (espera una antes de iniciar la siguiente); el Fragmento B las ejecuta **concurrentemente** (se ejecutan solapadas en el tiempo).
- D) El Fragmento B siempre falla porque `query_product` no devuelve una lista.

> ✅ **Respuesta correcta: C.** En el Fragmento A, `await` dentro de la comprensión de lista fuerza la ejecución secuencial. En el Fragmento B, la comprensión crea corrutinas **sin ejecutarlas** (`query_product(pool)` sin `await`), y `asyncio.gather` las programa todas concurrentemente.[^1]

***

**8.** El siguiente código genera un error en tiempo de ejecución. ¿Cuál es la causa y cómo se soluciona?

```python
async def query_product(pool):
    connection = pool.acquire()       # Línea problemática
    return await connection.fetchrow(product_query)
```

- A) `pool.acquire()` no existe; debe usarse `pool.connect()`.
- B) Falta `await` antes de `pool.acquire()` y el bloque `async with` para liberar la conexión automáticamente al pool.
- C) `fetchrow` debe ser llamado con `execute`.
- D) El pool debe ser creado dentro de la misma función.

> ✅ **Respuesta correcta: B.** `pool.acquire()` es una corrutina y debe esperarse con `await`. Además, al no usar `async with`, la conexión nunca se devuelve al pool, causando un agotamiento de conexiones. La forma correcta es `async with pool.acquire() as connection:`.[^1]

***

**9.** ¿Cuál de las siguientes afirmaciones sobre el método `executemany` es **incorrecta**?

- A) Acepta una sentencia SQL parametrizada con `$1`, `$2`, etc., y una lista de tuplas de valores.
- B) Previene inyecciones SQL al sanitizar los parámetros de entrada.
- C) Devuelve una lista con todos los IDs generados por las inserciones.
- D) Internamente genera una sentencia INSERT por cada tupla de la lista.

> ✅ **Respuesta correcta: C.** `executemany` descarta los resultados de las operaciones; no devuelve los IDs generados. Solo confirma que las operaciones se ejecutaron.[^3][^1]

***

**10.** ¿Por qué el uso de cursores para hacer *streaming* de resultados requiere estar dentro de una transacción activa? ¿Cuál es la ventaja principal de este enfoque sobre `connection.fetch()`?

- A) Es un requisito de asyncpg, no de PostgreSQL; la ventaja es que el código es más sencillo.
- B) PostgreSQL requiere una transacción activa para mantener el cursor abierto en el servidor; la ventaja es reducir el consumo de memoria al traer resultados de forma incremental en lugar de cargar todo el conjunto en RAM.
- C) La transacción garantiza que nadie más pueda leer los datos mientras se itera.
- D) No es un requisito obligatorio; los cursores funcionan también sin transacción.

> ✅ **Respuesta correcta: B.** PostgreSQL necesita una transacción activa para mantener el estado del cursor entre peticiones. La ventaja principal es el **ahorro de memoria**: en lugar de cargar millones de filas en RAM, solo se mantienen en memoria las filas que se están procesando en ese momento.[^3][^1]

***

*Fuente: Fowler, Matthew. Python Concurrency with Asyncio. Manning Publications, 2022 — Capítulo 5.*

---

## References

1. 5-Non-blocking-database-drivers.docx - Libro base del capítulo: Python Concurrency with Asyncio (Manning Publications)

2. [asyncpg - PyPI](https://pypi.org/project/asyncpg/) - An asyncio PostgreSQL driver

3. [API Reference — asyncpg Documentation](https://magicstack.github.io/asyncpg/current/api/index.html)

4. [Python PGWire Guide - QuestDB](https://questdb.com/docs/query/pgwire/python/) - Python clients for QuestDB PGWire protocol. Learn how to use the PGWire protocol with Python for que...

