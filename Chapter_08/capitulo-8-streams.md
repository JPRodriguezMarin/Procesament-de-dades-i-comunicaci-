# Capítulo 8 — Streams en asyncio

> **Libro:** *Python Concurrency with Asyncio*
> **Nivel:** Introductorio · Lenguaje sencillo

---

## Objetivo del Capítulo

> **Contexto:** Una **aplicación de red** es cualquier programa que envía o recibe datos a través de una red — un chat, un navegador, una API REST, un servidor de archivos. Para hacerlo, el programa abre una conexión con otro equipo (o proceso) y se comunica enviando y leyendo bytes. Este capítulo enseña exactamente cómo hacer eso con asyncio de forma sencilla y eficiente.

En este capítulo aprenderemos a comunicarnos por red con asyncio usando **streams**: la API de alto nivel que nos ahorra gestionar sockets a mano. El recorrido va de lo más cercano al sistema operativo hasta la aplicación real:

1. **Transportes y Protocolos** — la capa más próxima al SO: asyncio envía y recibe bytes usando *callbacks* (funciones que se llaman solas al llegar datos) en vez de `await`.
2. **StreamReader / StreamWriter** — la forma recomendada de leer y escribir en red: más sencilla, sin callbacks, compatible con `await` directamente.
3. **Stdin como stream** — cómo conectar el teclado al event loop de asyncio para que esperar input no bloquee el resto del programa.
4. **Creación de servidores** — cómo hacer que un único hilo de Python atienda a múltiples clientes a la vez con `asyncio.start_server`.
5. **Aplicación real** — un servidor y cliente de chat completo que integra todo lo anterior, funcionando en un solo hilo.

---

## ¿Qué son los Streams?

En asyncio, los **streams** son un conjunto de clases y funciones de alto nivel que nos permiten crear y gestionar conexiones de red y flujos genéricos de datos. Con ellos podemos:

- Crear conexiones de cliente para leer y escribir en servidores.
- Crear nuestros propios servidores y gestionarlos directamente.
- Abstraer todo lo complejo de trabajar con sockets (SSL, conexiones perdidas, buffers…) para que podamos centrarnos en la lógica de nuestra aplicación.

Piensa en un stream como si fuera una "tubería" por la que viajan datos: puedes meter datos por un extremo (escritura) y sacarlos por el otro (lectura), sin preocuparte de cómo viajan por dentro.

### Tipos de Streams

| Clase / Concepto | Rol |
|---|---|
| `StreamReader` | Lee datos de una conexión de red de forma asíncrona |
| `StreamWriter` | Escribe datos en una conexión de red de forma asíncrona |
| Transports (bajo nivel) | Abstracción directa sobre el socket; gestiona el envío/recepción de bytes |
| Protocols (bajo nivel) | Clase Python que define los callbacks que se llaman cuando ocurren eventos (conexión, datos recibidos, etc.) |

### Objetivo de los Streams

El objetivo principal es **simplificar el desarrollo de aplicaciones de red**. Los streams encapsulan toda la complejidad de trabajar con sockets directamente, haciendo que crear clientes y servidores sea mucho más sencillo y seguro. El uso de streams es la **forma recomendada** para construir aplicaciones de red con asyncio.

**¿Qué pasa si gestionas sockets a mano?** Estos son los problemas reales que aparecen:

| Problema | Descripción |
|---|---|
| **Gestión manual de buffers** | Los datos no llegan de golpe: pueden llegar troceados en varios paquetes. Hay que acumularlos en un buffer y detectar cuándo el mensaje está completo. |
| **Bloqueos** | Las operaciones de socket son bloqueantes por defecto: `recv()` congela el hilo hasta que llegan datos. Con asyncio esto rompe el event loop. |
| **Manejo de errores de red** | Conexiones perdidas, timeouts, EOF inesperado — cada caso hay que detectarlo y manejarlo manualmente. |
| **SSL/TLS** | Cifrar la conexión requiere añadir una capa extra y gestionar el handshake criptográfico a mano. |
| **Cierre limpio** | Cerrar un socket correctamente (esperar a que se vacíe el buffer, notificar al otro extremo) implica varios pasos que es fácil olvidar. |

Los streams de asyncio resuelven todos estos problemas internamente.

### Glosario — Conceptos básicos

| Término | Definición |
|---|---|
| **Callback** | Función que no llamamos nosotros directamente, sino que entregamos a otro código para que la llame cuando ocurra algo (un evento). Ejemplo: "cuando lleguen datos, llama a esta función mía". Es como dejar tu número de teléfono para que te avisen en vez de llamar tú repetidamente a preguntar. |
| **Stream** | Flujo bidireccional de datos que abstrae la comunicación de red o E/S |
| **StreamReader** | Objeto asyncio para leer bytes de una conexión de forma asíncrona |
| **StreamWriter** | Objeto asyncio para escribir bytes en una conexión de forma asíncrona |
| **Socket** | Punto de conexión entre dos programas que quieren comunicarse por red. Es como un enchufe: tu programa lo abre, lo conecta a otra dirección (IP + puerto) y desde ese momento puede enviar y recibir bytes como si fuera un archivo. El sistema operativo gestiona todo lo que ocurre por debajo (cables, paquetes, etc.). |
| **Buffer** | Área de memoria temporal que almacena datos mientras se transfieren |
| **Coroutine** | Función asíncrona que puede pausarse y resumirse sin bloquear el hilo |
| **Concurrencia cooperativa** | Modelo donde las tareas ceden el control voluntariamente (vs. preemptiva) |

---

## 8.1 Introduciendo los Streams

Los streams de asyncio se construyen sobre una capa de APIs de más bajo nivel conocidas como **transports** (transportes) y **protocols** (protocolos). Estas APIs envuelven directamente los sockets que se usaban en capítulos anteriores, proporcionando una interfaz limpia para leer y escribir datos.

Una diferencia importante respecto a lo que hemos visto antes es que estas APIs funcionan con un **diseño basado en callbacks**: en lugar de usar `await` para esperar datos, *definimos de antemano qué queremos que ocurra* (un método de nuestra clase) y asyncio lo llama automáticamente cuando los datos llegan. Es como dejar tu número de teléfono para que te avisen, en vez de llamar tú repetidamente a preguntar si hay novedades.

Para entender bien cómo funciona todo, el capítulo comienza explicando la capa de transportes y protocolos (de más bajo nivel) y luego sube al nivel de streams (`StreamReader` y `StreamWriter`), que es lo que se usa en la práctica.

### Glosario — 8.1

| Término | Definición |
|---|---|
| **Transport** | Objeto de asyncio que envuelve un socket y expone tres operaciones simples: leer, escribir y cerrar. Oculta los detalles del socket para que el resto del código no tenga que tratar con él directamente. |
| **Protocol** | Clase Python con callbacks (`connection_made`, `data_received`, etc.) que reacciona a eventos de red |
| **Callback** | Función que se llama automáticamente cuando ocurre un evento (no se llama manualmente) |
| **Diseño basado en callbacks** | Arquitectura donde el código no espera activamente sino que define qué hacer cuando llegan datos |
| **Event loop** | Bucle central de asyncio que gestiona y despacha eventos y coroutines |

---

## 8.2 Transportes y Protocolos

### ¿Qué es un Transport?

Un **transport** (transporte) es una capa que envuelve un socket (o cualquier otro canal de datos) y expone siempre las mismas tres operaciones, sin importar qué haya por debajo: **leer**, **escribir** y **cerrar**. La idea es que el código que usa el transport no necesita saber si está hablando con un socket TCP, UDP o con stdin — la interfaz es siempre la misma.

asyncio incluye varias implementaciones de transporte:

- **`ReadTransport`** — solo lectura
- **`WriteTransport`** — solo escritura
- **`Transport`** — lectura y escritura (hereda de los dos anteriores)
- **`DatagramTransport`** — para conexiones UDP
- **`SubprocessTransport`** — para comunicación con subprocesos

Todos heredan de `BaseTransport`. En la mayoría de casos trabajamos con `Transport` (el que combina lectura y escritura).

### ¿Qué es un Protocol?

Un **protocol** (protocolo) aquí no tiene nada que ver con HTTP o FTP. Se trata de una **clase Python** que escribimos nosotros y que define qué hacer cuando ocurren ciertos eventos en la conexión. Piénsalo como un "receptor de notificaciones": asyncio nos avisa, nosotros decidimos qué hacer:

- Cuando la conexión se establece → se llama a `connection_made(transport)`
- Cuando llegan datos → se llama a `data_received(data)`
- Cuando el servidor cierra la conexión → se llama a `eof_received()`
- Si la conexión se pierde → se llama a `connection_lost(exc)`

El transport llama a estos métodos del protocol cuando ocurren los eventos, y el protocol puede usar el transport para escribir datos de vuelta. Es una relación de colaboración: **el transport gestiona el canal, el protocol gestiona la lógica**.

---

### Listing 8.1 — Haciendo una petición HTTP con transportes y protocolos

> **Objetivo:** Demostrar la API de bajo nivel de asyncio (transportes y protocolos) implementando manualmente un cliente HTTP GET. Muestra cómo se implementan los callbacks del ciclo de vida de la conexión, cómo se acumulan datos recibidos en un buffer, y cómo se usa un `Future` para "conectar" el mundo de callbacks con el mundo de coroutines (`await`).

> **¿Qué es un `Future`?** Un `Future` es un objeto que representa un valor que **todavía no existe pero existirá en el futuro**. Funciona como una "caja vacía": alguien la llenará más tarde con un resultado (o un error), y quien esté esperando recibirá ese valor en ese momento. En asyncio se usa para comunicar dos mundos que no pueden hablar directamente: los callbacks (que no usan `await`) y las coroutines (que sí). El callback llena la caja con `set_result()`; la coroutine espera a que se llene con `await`.

> **`get_response()`** — Coroutine que simplemente hace `await self._future`. No hace nada más: solo espera a que la caja (`_future`) tenga un valor. Cuando alguien llame `await protocol.get_response()`, ese código quedará suspendido hasta que el future se complete. Desde fuera, parece magia — en realidad es el future actuando de mensajero.

> **`self._future.set_result(self._response_buffer.decode())`** — Esta línea "llena la caja". Se ejecuta en `eof_received()`, cuando ya han llegado todos los datos. Toma el buffer acumulado (bytes crudos), lo convierte a texto con `.decode()` y lo mete en el future como resultado. En ese instante, cualquier coroutine que estuviera haciendo `await get_response()` se despierta y recibe ese texto.

```python
import asyncio
from asyncio import Transport, Future, AbstractEventLoop
from typing import Optional

class HTTPGetClientProtocol(asyncio.Protocol):

    def __init__(self, host: str, loop: AbstractEventLoop):
        self._host: str = host
        self._future: Future = loop.create_future()
        self._transport: Optional[Transport] = None
        self._response_buffer: bytes = b''

    async def get_response(self):                              # ❶
        return await self._future

    def _get_request_bytes(self) -> bytes:                     # ❷
        request = f"GET / HTTP/1.1\r\n" \
                  f"Connection: close\r\n" \
                  f"Host: {self._host}\r\n\r\n"
        return request.encode()

    def connection_made(self, transport: Transport):           # ❸
        print(f'Connection made to {self._host}')
        self._transport = transport
        self._transport.write(self._get_request_bytes())

    def data_received(self, data):                             # ❹
        print(f'Data received!')
        self._response_buffer = self._response_buffer + data

    def eof_received(self) -> Optional[bool]:                  # ❺
        self._future.set_result(self._response_buffer.decode())
        return False

    def connection_lost(self, exc: Optional[Exception]) -> None:  # ❻
        if exc is None:
            print('Connection closed without error.')
        else:
            self._future.set_exception(exc)
```

**Explicación de los puntos clave:**

- **❶** `get_response()` es una coroutine que espera el future interno. Esto es el puente entre callbacks y `await`: el código externo puede hacer `await protocol.get_response()` de forma natural.
- **❷** Construye la petición HTTP/1.1 en bytes con las cabeceras mínimas requeridas. `Connection: close` le dice al servidor que cierre la conexión tras responder (esto dispara `eof_received`).
- **❸** asyncio llama a este método automáticamente cuando la conexión TCP se establece. Guardamos el transport y enviamos la petición inmediatamente.
- **❹** asyncio llama a este método cada vez que llegan datos del socket. No sabemos cuántos bytes llegarán de golpe, por eso acumulamos en un buffer. **Aquí no se envía nada al mundo asíncrono todavía** — solo se guarda. El puente hacia `await` ocurre más tarde, en `eof_received`, cuando todos los datos han llegado y se llama `set_result()`.

  > **Ejemplo real:** imagina que el servidor HTTP responde con 3 paquetes separados (la red los trocea así):
  > ```
  > Paquete 1 → data_received: b"HTTP/1.1 200 OK\r\nContent-Type: "
  > Paquete 2 → data_received: b"text/html\r\n\r\n"
  > Paquete 3 → data_received: b"<html>Hello</html>"
  > ```
  > Cada llamada añade su trozo al buffer. Cuando el servidor cierra la conexión:
  > ```
  > eof_received → set_result("HTTP/1.1 200 OK\r\n....<html>Hello</html>")
  > ```
  > Solo en ese momento se despierta quien estaba haciendo `await protocol.get_response()` y recibe la respuesta completa y ensamblada. Sin el buffer, perderías los paquetes 1 y 2.
- **❺** asyncio llama a esto cuando el servidor cierra su extremo (EOF). En este momento tenemos la respuesta completa y completamos el future.
- **❻** Si la conexión se pierde con error, propagamos la excepción al future para que `get_response()` la lance.

> **Nota clave:** El `Future` actúa como "mensajero" entre el mundo de callbacks (síncrono) y el mundo de coroutines (asíncrono). Los callbacks completan el future; las coroutines lo esperan con `await`.

---

### Listing 8.2 — Usando el protocolo

> **Objetivo:** Mostrar cómo conectar el protocolo definido en el Listing 8.1 con `loop.create_connection`. Ilustra el patrón de `protocol_factory` (función que devuelve una instancia del protocolo) y cómo obtener la respuesta desde el protocolo usando `await`.

```python
import asyncio
from asyncio import AbstractEventLoop
from chapter_08.listing_8_1 import HTTPGetClientProtocol

async def make_request(host: str, port: int, loop: AbstractEventLoop) -> str:
    def protocol_factory():
        return HTTPGetClientProtocol(host, loop)

    _, protocol = await loop.create_connection(protocol_factory, host=host, port=port)

    return await protocol.get_response()

async def main():
    loop = asyncio.get_running_loop()
    result = await make_request('www.example.com', 80, loop)
    print(result)

asyncio.run(main())
```

**Explicación función por función:**

---

**`protocol_factory()` — fábrica del protocolo**

```python
def protocol_factory():
    return HTTPGetClientProtocol(host, loop)
```

No es el protocolo en sí — es una función que *crea* el protocolo cuando asyncio lo necesite. asyncio la llama internamente al establecer la conexión.

¿Por qué una función y no pasar la instancia directamente? Porque asyncio podría necesitar crear varias instancias (por ejemplo, si hay reintentos o múltiples conexiones). La factory permite eso sin que tú lo gestiones.

> **Ejemplo real:** es como una máquina de café. No le das un café ya hecho — le das la máquina para que prepare uno cada vez que alguien lo pida.

---

**`make_request(host, port, loop)` — orquesta todo**

```python
async def make_request(host: str, port: int, loop: AbstractEventLoop) -> str:
    def protocol_factory():
        return HTTPGetClientProtocol(host, loop)

    _, protocol = await loop.create_connection(protocol_factory, host=host, port=port)
    return await protocol.get_response()
```

Esta es la función que realmente usas. Hace tres cosas en orden:
1. Define la factory del protocolo
2. Abre la conexión TCP con `create_connection` — asyncio llama a `connection_made` internamente, que ya envía la petición HTTP
3. Espera la respuesta completa con `await protocol.get_response()`

`create_connection` devuelve `(transport, protocol)`. El `_` descarta el transport porque el protocolo ya lo guarda dentro — no lo necesitamos aquí fuera.

> **Ejemplo real:** `make_request('www.example.com', 80, loop)` abre una conexión al servidor de example.com en el puerto 80 (HTTP), envía `GET / HTTP/1.1...` y espera hasta recibir la página completa. El resultado es el HTML de la página como texto.

---

**`main()` — punto de entrada**

```python
async def main():
    loop = asyncio.get_running_loop()
    result = await make_request('www.example.com', 80, loop)
    print(result)
```

Obtiene el event loop en ejecución y lo pasa a `make_request` porque el protocolo necesita el loop para crear el `Future` con `loop.create_future()`. Imprime la respuesta HTTP completa: cabeceras + cuerpo.

> **Salida esperada:**
> ```
> HTTP/1.1 200 OK
> Content-Type: text/html; charset=UTF-8
> ...
> <html>...</html>
> ```

---

> **Limitación:** Esta forma (con transportes y protocolos directamente) implica mucho código boilerplate. Es útil para entender la base, pero en la práctica se usa la API de alto nivel: `StreamReader`/`StreamWriter`.

### Glosario — 8.2

| Término | Definición |
|---|---|
| **`asyncio.Protocol`** | Clase base que se hereda para implementar callbacks de eventos de red |
| **`Future`** | Objeto que representa un valor que todavía no existe pero existirá. Actúa de "caja vacía": alguien la llena con `set_result()` y quien espera con `await` recibe ese valor en ese momento |
| **`set_result(valor)`** | Método de `Future` que "llena la caja" con el resultado. Cualquier coroutine que esté haciendo `await` sobre ese future se despierta inmediatamente y recibe el valor |
| **`set_exception(exc)`** | Método de `Future` que mete un error en la caja en vez de un valor. Quien esté haciendo `await` recibirá la excepción y el programa puede capturarla con `try/except` |
| **`.decode()`** | Método de `bytes` que convierte bytes crudos a texto (`str`). Necesario porque por la red siempre viajan bytes, nunca texto directamente. Ejemplo: `b"hola".decode()` → `"hola"` |
| **`.encode()`** | Lo contrario de `.decode()`: convierte texto a bytes para poder enviarlo por la red. Ejemplo: `"hola".encode()` → `b"hola"` |
| **`connection_made`** | Callback llamado cuando la conexión TCP se establece |
| **`data_received`** | Callback llamado cada vez que llegan bytes por el socket; puede llamarse varias veces para un mismo mensaje si la red lo trocea en paquetes |
| **`eof_received`** | Callback llamado cuando el otro extremo cierra la conexión; señal de que no llegarán más datos |
| **`connection_lost`** | Callback llamado cuando la conexión se pierde (con o sin error) |
| **`create_connection`** | Método del event loop que crea una conexión TCP y la vincula a un protocolo |
| **`protocol_factory`** | Función (callable) que devuelve una nueva instancia del protocolo; usada por asyncio internamente |
| **Boilerplate** | Código repetitivo y tedioso que debe escribirse para hacer funcionar algo básico |
| **`BaseTransport`** | Clase base de todos los transports; define la interfaz común |
| **`ReadTransport`** | Transport de solo lectura |
| **`WriteTransport`** | Transport de solo escritura |
| **`DatagramTransport`** | Transport para conexiones UDP (sin conexión) |

---

## 8.3 Stream Readers y Stream Writers

Los transportes y protocolos son APIs de bajo nivel, útiles cuando necesitamos control muy fino (por ejemplo, al diseñar un framework de red). Pero para la mayoría de aplicaciones, escribir con ellos implica mucho código repetitivo. Por eso, asyncio incluye las clases de alto nivel **`StreamReader`** y **`StreamWriter`**.

### ¿Qué hace cada uno?

- **`StreamReader`** — gestiona la lectura de datos. Tiene métodos muy cómodos:
  - `readline()` — coroutine que espera hasta que llega una línea completa de datos (terminada en `\n`).
  - `read(n)` — coroutine que espera hasta que llegan `n` bytes.
  - `readexactly(n)` — coroutine que espera exactamente `n` bytes o lanza `IncompleteReadError`.
  - `read(-1)` — lee hasta EOF.

- **`StreamWriter`** — gestiona la escritura de datos. Su método `write()` **no** es una coroutine; intenta escribir al buffer del socket inmediatamente. Como el buffer puede llenarse, existe el método `drain()` (este sí es una coroutine) que espera hasta que todos los datos en cola han sido enviados al socket. Es buena práctica llamar `await writer.drain()` después de cada `write()`.

> **¿Por qué importa `drain()`?** Imagina que tu red envía 1 KB/s pero tu aplicación escribe 1 MB/s. El buffer interno se llenará rápidamente y acabarás sin memoria. `drain()` actúa como freno de mano: bloquea hasta que el buffer se vacía, evitando ese problema. También devuelve el control al event loop mientras espera, permitiendo que otras tareas se ejecuten.

Para crear un `StreamReader` y un `StreamWriter` a la vez, asyncio proporciona la coroutine `open_connection(host, port)`, que devuelve ambos como una tupla.

---

### Listing 8.3 — Petición HTTP con stream readers y writers

> **Objetivo:** Reescribir el mismo cliente HTTP del Listing 8.1 pero usando la API de alto nivel (`open_connection`, `StreamReader`, `StreamWriter`). La comparación directa muestra cuánto código boilerplate elimina esta API y por qué se recomienda sobre transportes/protocolos. También introduce los **generadores asíncronos** (`async def` + `yield`) para iterar líneas de respuesta.

```python
import asyncio
from asyncio import StreamReader
from typing import AsyncGenerator

async def read_until_empty(stream_reader: StreamReader) -> AsyncGenerator[str, None]:
    while response := await stream_reader.readline():   # ❶
        yield response.decode()

async def main():
    host: str = 'www.example.com'
    request: str = f"GET / HTTP/1.1\r\n" \
                   f"Connection: close\r\n" \
                   f"Host: {host}\r\n\r\n"

    stream_reader, stream_writer = await asyncio.open_connection('www.example.com', 80)

    try:
        stream_writer.write(request.encode())           # ❷
        await stream_writer.drain()

        responses = [response async for response in read_until_empty(stream_reader)]  # ❸

        print(''.join(responses))
    finally:
        stream_writer.close()                           # ❹
        await stream_writer.wait_closed()

asyncio.run(main())
```

**Explicación de los puntos clave:**

- **❶** `readline()` devuelve `b''` (bytes vacíos) cuando se alcanza EOF. El walrus operator (`:=`) asigna y comprueba en una sola expresión: cuando no haya más datos, el while termina.
- **❷** `write()` no es coroutine; escribe al buffer interno. `drain()` espera a que el buffer se vacíe realmente, cediendo el control al event loop mientras tanto.
- **❸** `async for` itera sobre el generador asíncrono línea a línea. La list comprehension asíncrona recopila todas las líneas.
- **❹** `close()` inicia el cierre pero no lo completa. `wait_closed()` espera a que el cierre sea efectivo, capturando posibles excepciones tardías. Siempre usar ambos juntos.

> **Comparación con Listing 8.1:** el mismo resultado con ~50% menos código. No hay que gestionar futures manualmente, no hay callbacks, no hay buffer propio. `open_connection` hace toda la fontanería por nosotros.

> **Caso de uso real:** Un monitor de disponibilidad que comprueba cada minuto si varios servidores web responden. Con `open_connection` puedes lanzar 50 peticiones HTTP concurrentes en un solo hilo — cada una hace `await readline()` sin bloquear las demás. Si un servidor no responde, `asyncio.wait_for` lanza timeout y lo marcas como caído.

### Glosario — 8.3

| Término | Definición |
|---|---|
| **`StreamReader`** | Clase asyncio de alto nivel para leer datos de red de forma asíncrona |
| **`StreamWriter`** | Clase asyncio de alto nivel para escribir datos de red de forma asíncrona |
| **`open_connection`** | Coroutine que abre una conexión TCP y devuelve `(StreamReader, StreamWriter)` |
| **`readline()`** | Coroutine que espera hasta recibir una línea completa (terminada en `\n`) |
| **`read(n)`** | Coroutine que espera hasta recibir `n` bytes |
| **`write(data)`** | Método síncrono que escribe al buffer interno del socket |
| **`drain()`** | Coroutine que espera hasta que el buffer de escritura se vacía; previene saturación de memoria |
| **`close()`** | Inicia el cierre del writer (no bloqueante) |
| **`wait_closed()`** | Coroutine que espera a que el cierre sea completo |
| **Walrus operator** | Operador `:=` de Python 3.8+ que asigna y evalúa en una sola expresión |
| **Generador asíncrono** | Función con `async def` y `yield` que produce valores de forma asíncrona |
| **`async for`** | Bucle que itera sobre un generador/iterable asíncrono |
| **EOF** | *End Of File* — señal que indica que no hay más datos |

---

## 8.4 Creando una Interfaz de Línea de Comandos con Stdin Streams

Para construir el cliente de chat del apartado 8.6 necesitamos leer la entrada del teclado (stdin) de forma **no bloqueante**. El problema: `input()` de Python es síncrono y bloquea el event loop. La solución: envolver stdin en un `StreamReader` asíncrono usando `connect_read_pipe`.

Además, el cliente de chat necesita mostrar mensajes entrantes en la parte superior de la pantalla mientras el usuario escribe en la parte inferior. Esto requiere **control del cursor del terminal** mediante secuencias de escape ANSI.

Esta sección presenta las utilidades que el cliente de chat (Listing 8.14) usa internamente.

---

### Listing 8.4 — Demo básica de stdin asíncrono

> **Objetivo:** Mostrar el patrón fundamental para conectar stdin al sistema de streams de asyncio. `connect_read_pipe` envuelve cualquier pipe del sistema operativo (incluyendo stdin) en un `StreamReader`, haciendo que la lectura sea no bloqueante y compatible con el event loop.

```python
import asyncio
import sys
from asyncio import StreamReader

async def create_stdin_reader() -> StreamReader:
    stream_reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(stream_reader)
    loop = asyncio.get_running_loop()
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    return stream_reader

async def main():
    stdin_reader = await create_stdin_reader()
    print('Escribe algo y pulsa Enter (Ctrl+C para salir):')
    while True:
        line = await stdin_reader.readline()
        if not line:
            break
        print(f'Leído: {line.decode().strip()}')

asyncio.run(main())
```

**Explicación:**

- `StreamReaderProtocol` es un protocolo interno de asyncio que alimenta un `StreamReader` con los datos que llegan por el pipe.
- `connect_read_pipe` conecta stdin (o cualquier fd de lectura) al protocolo, de modo que los datos de teclado fluyen hacia el `StreamReader`.
- El resultado: `stdin_reader.readline()` es no bloqueante — mientras esperas la entrada, el event loop puede atender otras tareas.

> **Caso de uso real:** Un gestor de descargas en terminal que muestra el progreso de varios archivos descargándose a la vez y, al mismo tiempo, acepta comandos del usuario (`pause`, `cancel`, `status`). Con stdin síncrono (`input()`), el programa se congelaría esperando que escribas. Con stdin asíncrono, las descargas siguen avanzando mientras espera tu comando.

---

### Listing 8.5 — Función `create_stdin_reader`

> **Objetivo:** Extraer el patrón de creación del stdin reader en una función reutilizable que se importa desde el cliente de chat. Encapsula la complejidad de `connect_read_pipe` en una interfaz sencilla.

```python
import asyncio
import sys
from asyncio import StreamReader

async def create_stdin_reader() -> StreamReader:
    stream_reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(stream_reader)
    loop = asyncio.get_running_loop()
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    return stream_reader
```

> **Caso de uso real:** Esta función es la base de cualquier herramienta CLI interactiva construida con asyncio — un REPL asíncrono, un cliente de chat, un debugger de red. Se importa una vez y se reutiliza en cualquier proyecto que necesite leer del teclado sin bloquear el event loop.

---

### Listing 8.7 — Utilidades de terminal (secuencias ANSI)

> **Objetivo:** Proporcionar funciones para controlar el cursor del terminal usando **secuencias de escape ANSI**. Estas funciones permiten al cliente de chat dividir la pantalla en dos zonas: mensajes arriba, input abajo, sin que interfieran entre sí. Son puramente síncronas (solo escriben a stdout) porque las secuencias ANSI son instantáneas.

```python
import shutil
import sys

def save_cursor_position():
    """Guarda la posición actual del cursor (secuencia ESC 7)."""
    sys.stdout.write('\0337')
    sys.stdout.flush()

def restore_cursor_position():
    """Restaura el cursor a la posición guardada (secuencia ESC 8)."""
    sys.stdout.write('\0338')
    sys.stdout.flush()

def move_to_top_of_screen():
    """Mueve el cursor a la esquina superior izquierda (fila 1, columna 1)."""
    sys.stdout.write('\033[H')
    sys.stdout.flush()

def delete_line():
    """Borra la línea actual y mueve el cursor al inicio de la línea."""
    sys.stdout.write('\033[2K\r')
    sys.stdout.flush()

def move_to_bottom_of_screen() -> int:
    """Mueve el cursor a la última fila. Devuelve el número de filas del terminal."""
    rows, _ = shutil.get_terminal_size()
    sys.stdout.write(f'\033[{rows};0H')
    sys.stdout.flush()
    return rows
```

**Secuencias ANSI usadas:**

| Secuencia | Efecto |
|---|---|
| `\0337` | Guarda posición del cursor |
| `\0338` | Restaura posición del cursor |
| `\033[H` | Mueve cursor a fila 1, columna 1 |
| `\033[2K` | Borra toda la línea actual |
| `\033[{n};0H` | Mueve cursor a fila `n`, columna 0 |

> **Caso de uso real:** Un dashboard de monitorización en terminal que muestra en tiempo real el estado de varios servicios (CPU, memoria, red) en la mitad superior de la pantalla, mientras en la mitad inferior el operador puede escribir comandos. Las funciones ANSI permiten actualizar solo las líneas de arriba sin borrar el área de input del usuario.

---

### Listing 8.8 — Función `read_line`

> **Objetivo:** Leer una línea del `StreamReader` de stdin **carácter a carácter**, sin esperar a `\n`. Esto es necesario en modo "raw" del terminal (cuando se ha desactivado el procesamiento de línea con `tty.setcbreak`), donde los caracteres llegan uno a uno al programa en cuanto se pulsa la tecla, sin necesidad de pulsar Enter.

```python
from asyncio import StreamReader

async def read_line(stdin_reader: StreamReader) -> str:
    line = b''
    while True:
        char = await stdin_reader.read(1)
        if char == b'\n':
            break
        line += char
    return line.decode()
```

**¿Por qué no usar `readline()`?** En modo `setcbreak`, el terminal no procesa `\n` antes de enviar los caracteres. `readline()` nunca vería el terminador de línea. Leer carácter a carácter y parar en `\n` es la forma correcta.

> **Caso de uso real:** Un formulario de login en terminal (usuario + contraseña) dentro de una aplicación asyncio. Al pedir la contraseña, el modo `setcbreak` ya está activo — necesitas `read_line` para capturar correctamente lo que escribe el usuario carácter a carácter antes del Enter, sin que el terminal lo procese por su cuenta.

---

### Listing 8.9 — Clase `MessageStore`

> **Objetivo:** Gestionar la lista de mensajes del chat con un tamaño máximo (para no desbordar la pantalla) y llamar automáticamente a un **callback de redibujado** cada vez que se añade un mensaje. Esto desacopla el almacenamiento de mensajes de la lógica de presentación.

```python
import asyncio
from collections import deque
from typing import Callable

class MessageStore:
    def __init__(self, callback: Callable, max_size: int):
        self._messages: deque = deque(maxlen=max_size)
        self._callback = callback

    async def append(self, message: str):
        self._messages.append(message)
        await self._callback(self._messages)
```

**Detalles importantes:**

- `deque(maxlen=max_size)` descarta automáticamente el mensaje más antiguo cuando se supera el tamaño máximo, evitando que los mensajes se salgan de la zona visible.
- `callback` es una coroutine asíncrona (`async def`) que recibe el deque de mensajes y los dibuja en pantalla.
- El patrón "almacén + callback de actualización" es común en UIs asíncronas: separa estado de presentación.

> **Caso de uso real:** Un visor de logs en vivo que muestra las últimas 20 líneas de un fichero de log en la parte superior del terminal. Cada vez que llega una línea nueva, `MessageStore.append()` la añade y llama automáticamente al callback que redibuja las 20 líneas. Las líneas más antiguas desaparecen solas gracias a `deque(maxlen=20)` — sin código extra.

### Glosario — 8.4

| Término | Definición |
|---|---|
| **stdin** | Entrada estándar del proceso; normalmente el teclado |
| **`connect_read_pipe`** | Método del event loop que envuelve un file descriptor de lectura en un stream asíncrono |
| **`StreamReaderProtocol`** | Protocolo interno de asyncio que alimenta un `StreamReader` con datos de un pipe |
| **`tty.setcbreak`** | Pone el terminal en modo "cbreak": los caracteres se envían uno a uno sin esperar Enter |
| **Secuencia de escape ANSI** | Código especial (`\033[...`) que controla el cursor, colores y otros atributos del terminal |
| **`deque`** | Cola de doble extremo de Python (`collections.deque`); con `maxlen` descarta automáticamente los elementos más antiguos |
| **Modo raw / cbreak** | Modo del terminal donde los caracteres se procesan de forma inmediata, sin buffering de línea |
| **`shutil.get_terminal_size()`** | Función que devuelve `(columnas, filas)` del terminal actual |

---

## 8.5 Creando Servidores

Hasta ahora hemos visto cómo crear **clientes**. Pero asyncio también nos permite crear **servidores** sin preocuparnos por gestionar sockets a mano.

### `asyncio.start_server`

La coroutine `asyncio.start_server` crea un servidor de forma sencilla. Sus parámetros principales son:

- `client_connected_cb` — una función o coroutine que se llama **cada vez que un cliente se conecta**. Recibe un `StreamReader` y un `StreamWriter` como parámetros.
- `host` — dirección en la que el servidor escucha (ej. `'127.0.0.1'`).
- `port` — puerto en el que escucha (ej. `8000`).

Cuando ejecutamos `await start_server(...)`, obtenemos un objeto `AbstractServer`. Lo usamos con `async with server:` (context manager asíncrono) para garantizar que el servidor se cierre limpiamente al terminar. El método `serve_forever()` mantiene el bucle activo indefinidamente, esperando conexiones entrantes.

> **¿Por qué es mejor que un servidor síncrono?** Un servidor síncrono tradicional atiende a un cliente, espera a que termine, y solo entonces acepta el siguiente — como una caja única en el supermercado. Con asyncio y `start_server`, cada cliente recibe su propia coroutine y todas avanzan intercaladas en un solo hilo: mientras un cliente espera su respuesta, el servidor ya está atendiendo al siguiente. Sin hilos extra, sin bloqueos.

---

### Listing 8.12 — Servidor echo con estado del servidor

> **Objetivo:** Demostrar un servidor más complejo que mantiene **estado compartido entre conexiones**. El servidor informa a cada cliente del número de usuarios conectados y notifica a todos cuando alguien entra o sale. Este patrón muestra cómo gestionar múltiples clientes concurrentes con una lista de writers compartida, y cómo usar `asyncio.create_task` para procesar cada cliente de forma independiente.

```python
import asyncio
import logging
from asyncio import StreamReader, StreamWriter

class ServerState:

    def __init__(self):
        self._writers = []

    async def add_client(self, reader: StreamReader, writer: StreamWriter):  # ❶
        self._writers.append(writer)
        await self._on_connect(writer)
        asyncio.create_task(self._echo(reader, writer))

    async def _on_connect(self, writer: StreamWriter):                       # ❷
        writer.write(f'Welcome! {len(self._writers)} user(s) are online!\n'.encode())
        await writer.drain()
        await self._notify_all('New user connected!\n')

    async def _echo(self, reader: StreamReader, writer: StreamWriter):       # ❸
        try:
            while data := await reader.readline() != b'':
                writer.write(data)
                await writer.drain()
            self._writers.remove(writer)
            await self._notify_all(f'Client disconnected. {len(self._writers)} user(s) are online!\n')
        except Exception as e:
            logging.exception('Error reading from client.', exc_info=e)
            self._writers.remove(writer)

    async def _notify_all(self, message: str):                               # ❹
        for writer in self._writers:
            try:
                writer.write(message.encode())
                await writer.drain()
            except ConnectionError as e:
                logging.exception('Could not write to client.', exc_info=e)
                self._writers.remove(writer)

async def main():
    server_state = ServerState()

    async def client_connected(reader: StreamReader, writer: StreamWriter) -> None:  # ❺
        await server_state.add_client(reader, writer)

    server = await asyncio.start_server(client_connected, '127.0.0.1', 8000)  # ❻

    async with server:
        await server.serve_forever()

asyncio.run(main())
```

**Explicación de los puntos clave:**

- **❶** `add_client` añade el writer a la lista compartida, informa al nuevo cliente y lanza una tarea independiente (`create_task`) para hacer echo de sus mensajes. La tarea es no bloqueante: `add_client` retorna de inmediato y el servidor puede aceptar más conexiones.
- **❷** `_on_connect` envía el mensaje de bienvenida con el conteo actual de usuarios y luego notifica a todos los demás.
- **❸** `_echo` lee líneas del cliente en bucle. Cuando `readline()` devuelve `b''`, el cliente se desconectó. Se elimina de la lista y se notifica a todos.
- **❹** `_notify_all` itera sobre todos los writers y envía el mensaje. Si falla (cliente desconectado abruptamente), lo elimina de la lista.
- **❺** `client_connected` es el callback de `start_server`. Solo delega en `server_state` para mantener el código organizado.
- **❻** `start_server` crea el servidor. `async with server` garantiza que se cierre limpiamente. `serve_forever()` mantiene el bucle activo indefinidamente.

> **Pruébalo:** Inicia el servidor y conecta múltiples clientes con `nc 127.0.0.1 8000` o `telnet 127.0.0.1 8000`. Escribe texto en uno y verás el eco. Conecta otro y verás el mensaje "New user connected!".

> **Caso de uso real:** Un servidor de resultados deportivos en directo. Cada vez que llega un gol, el servidor llama a `_notify_all("Gol de España! 1-0\n")` y todos los clientes conectados (apps móviles, navegadores web, dashboards) reciben la actualización al instante. El contador de usuarios conectados en `_on_connect` funciona como el contador de espectadores en vivo.

### Glosario — 8.5

| Término | Definición |
|---|---|
| **`ServerState`** | Clase que centraliza el estado compartido del servidor: la lista de writers de todos los clientes conectados. Al tenerlo en un objeto separado, varias conexiones concurrentes pueden acceder y modificar esa lista sin que el código se mezcle con la lógica de red |
| **`start_server`** | Coroutine de asyncio que crea un servidor TCP y llama a un callback por cada cliente conectado |
| **`AbstractServer`** | Objeto devuelto por `start_server`; representa el servidor en ejecución |
| **`serve_forever()`** | Coroutine que mantiene el servidor activo hasta que se cancela o se cierra |
| **`client_connected_cb`** | Callback (función o coroutine) llamado por asyncio cada vez que un cliente se conecta |
| **`create_task`** | Función de asyncio que programa una coroutine para ejecutarse de forma concurrente (sin bloquear) |
| **Estado compartido** | Datos (como la lista de writers) accesibles y modificables por múltiples conexiones concurrentes |
| **Echo server** | Servidor que devuelve exactamente los mismos datos que recibe |
| **Context manager asíncrono** | Objeto usado con `async with` que gestiona recursos asíncronos; su `__aenter__` y `__aexit__` son coroutines |

---

## 8.6 Creando un Servidor y Cliente de Chat

Ahora combinamos todo lo aprendido para crear algo más real: **un servidor de chat y un cliente de chat**. Este es el ejemplo más completo del capítulo.

### Requisitos del servidor

1. Un cliente de chat debe poder conectarse proporcionando un nombre de usuario.
2. Una vez conectado, puede enviar mensajes que serán recibidos por todos los demás usuarios conectados.
3. Si un usuario está inactivo más de un minuto, el servidor lo desconecta.

### Requisitos del cliente

1. Al iniciar, el cliente pide un nombre de usuario y se conecta al servidor.
2. Una vez conectado, los mensajes de otros usuarios aparecen en la parte superior de la pantalla.
3. El campo de entrada está en la parte inferior; al pulsar Enter, el mensaje se envía al servidor.

### Protocolo de comunicación

Para distinguir entre "conectarse con un nombre de usuario" y "enviar un mensaje", se usa un protocolo sencillo: el primer mensaje del cliente al servidor debe tener el formato `CONNECT <username>`. Por ejemplo: `CONNECT MissIslington`.

Este es un ejemplo de **protocolo de aplicación**: una convención que el cliente y el servidor acuerdan para estructurar sus mensajes.

---

### Listing 8.13 — El servidor de chat

> **Objetivo:** Implementar un servidor de chat completo que gestiona usuarios por nombre, distribuye mensajes entre todos los conectados y desconecta automáticamente a usuarios inactivos usando `asyncio.wait_for` con timeout. Este listing integra todos los conceptos del capítulo: `start_server`, `StreamReader`/`StreamWriter`, estado compartido y manejo de timeouts.

> **Corrección aplicada:** En la línea de `command.split(...)`, se elimina `b' '` como argumento. `split()` sin argumentos divide por cualquier espacio en blanco, que es el comportamiento correcto.

```python
import asyncio
import logging
from asyncio import StreamReader, StreamWriter

class ChatServer:

    def __init__(self):
        self._username_to_writer = {}

    async def start_chat_server(self, host: str, port: int):
        server = await asyncio.start_server(self.client_connected, host, port)

        async with server:
            await server.serve_forever()

    async def client_connected(self, reader: StreamReader, writer: StreamWriter):  # ❶
        command = await reader.readline()
        print(f'CONNECTED {reader} {writer}')
        command, args = command.split()
        if command == b'CONNECT':
            username = args.replace(b'\n', b'').decode()
            self._add_user(username, reader, writer)
            await self._on_connect(username, writer)
        else:
            logging.error('Got invalid command from client, disconnecting.')
            writer.close()
            await writer.wait_closed()

    def _add_user(self, username: str, reader: StreamReader, writer: StreamWriter):  # ❷
        self._username_to_writer[username] = writer
        asyncio.create_task(self._listen_for_messages(username, reader))

    async def _on_connect(self, username: str, writer: StreamWriter):               # ❸
        writer.write(f'Welcome! {len(self._username_to_writer)} user(s) are online!\n'.encode())
        await writer.drain()
        await self._notify_all(f'{username} connected!\n')

    async def _remove_user(self, username: str):
        writer = self._username_to_writer[username]
        del self._username_to_writer[username]
        try:
            writer.close()
            await writer.wait_closed()
        except Exception as e:
            logging.exception('Error closing client writer, ignoring.', exc_info=e)

    async def _listen_for_messages(self, username: str, reader: StreamReader):      # ❹
        try:
            while (data := await asyncio.wait_for(reader.readline(), 60)) != b'':
                await self._notify_all(f'{username}: {data.decode()}')
            await self._notify_all(f'{username} has left the chat\n')
        except Exception as e:
            logging.exception('Error reading from client.', exc_info=e)
            await self._remove_user(username)

    async def _notify_all(self, message: str):                                      # ❺
        inactive_users = []
        for username, writer in self._username_to_writer.items():
            try:
                writer.write(message.encode())
                await writer.drain()
            except ConnectionError as e:
                logging.exception('Could not write to client.', exc_info=e)
                inactive_users.append(username)
        [await self._remove_user(username) for username in inactive_users]

async def main():
    chat_server = ChatServer()
    await chat_server.start_chat_server('127.0.0.1', 8000)

asyncio.run(main())
```

**Explicación línea por línea:**

```python
class ChatServer:
```
Clase que encapsula todo el estado y la lógica del servidor. Tener el servidor en una clase permite que `_username_to_writer` sea accesible desde todos los métodos sin usar variables globales.

```python
    def __init__(self):
        self._username_to_writer = {}
```
Diccionario que mapea `nombre_usuario → StreamWriter`. Es el estado central del servidor: saber a quién escribir para enviar un mensaje.

```python
    async def start_chat_server(self, host: str, port: int):
        server = await asyncio.start_server(self.client_connected, host, port)
        async with server:
            await server.serve_forever()
```
Arranca el servidor. `self.client_connected` es el callback — asyncio lo llamará automáticamente cada vez que llegue un cliente. `async with server` garantiza cierre limpio. `serve_forever()` bloquea hasta que el servidor se cancele.

```python
    async def client_connected(self, reader: StreamReader, writer: StreamWriter):
        command = await reader.readline()
```
Primer contacto con el cliente. Se espera la primera línea — que debe ser el handshake `CONNECT <username>`. `await` cede el control al event loop mientras espera; el resto de clientes siguen siendo atendidos.

```python
        command, args = command.split()
```
Divide la línea en dos partes. Si el cliente envió `b'CONNECT Alice\n'`, `command = b'CONNECT'` y `args = b'Alice\n'`.

```python
        if command == b'CONNECT':
            username = args.replace(b'\n', b'').decode()
```
Verifica el protocolo. Elimina el `\n` del final y convierte bytes a texto. Si el comando no es `CONNECT`, el servidor cierra la conexión inmediatamente.

```python
            self._add_user(username, reader, writer)
            await self._on_connect(username, writer)
```
Registra al usuario y le envía el mensaje de bienvenida. Orden importante: primero registrar, luego notificar (para que el contador de `_on_connect` sea correcto).

```python
    def _add_user(self, username, reader, writer):
        self._username_to_writer[username] = writer
        asyncio.create_task(self._listen_for_messages(username, reader))
```
Guarda el writer en el diccionario para poder enviarle mensajes. `create_task` lanza `_listen_for_messages` como tarea independiente — no bloqueante. `client_connected` retorna inmediatamente y el servidor puede aceptar el próximo cliente.

```python
    async def _on_connect(self, username, writer):
        writer.write(f'Welcome! {len(self._username_to_writer)} user(s) are online!\n'.encode())
        await writer.drain()
        await self._notify_all(f'{username} connected!\n')
```
Envía bienvenida al nuevo usuario con el conteo actual. `drain()` vacía el buffer antes de continuar. Luego notifica a todos los demás del nuevo usuario.

```python
    async def _remove_user(self, username):
        writer = self._username_to_writer[username]
        del self._username_to_writer[username]
        try:
            writer.close()
            await writer.wait_closed()
        except Exception as e:
            logging.exception(...)
```
Elimina al usuario del diccionario y cierra su writer. El `try/except` evita que un error al cerrar (writer ya cerrado, por ejemplo) mate el servidor entero.

```python
    async def _listen_for_messages(self, username, reader):
        try:
            while (data := await asyncio.wait_for(reader.readline(), 60)) != b'':
                await self._notify_all(f'{username}: {data.decode()}')
            await self._notify_all(f'{username} has left the chat\n')
        except Exception as e:
            logging.exception(...)
            await self._remove_user(username)
```
Bucle principal de escucha. `wait_for(..., 60)` añade timeout: si el usuario no escribe en 60 segundos, lanza `TimeoutError` → se captura → se elimina al usuario. Si `readline()` devuelve `b''` el cliente cerró la conexión limpiamente. El walrus operator `:=` asigna y comprueba en una sola expresión.

```python
    async def _notify_all(self, message):
        inactive_users = []
        for username, writer in self._username_to_writer.items():
            try:
                writer.write(message.encode())
                await writer.drain()
            except ConnectionError as e:
                inactive_users.append(username)
        [await self._remove_user(username) for username in inactive_users]
```
Envía el mensaje a todos los usuarios. No se puede eliminar del diccionario mientras se itera sobre él (`RuntimeError`), así que los usuarios con error se acumulan en `inactive_users` y se eliminan después del bucle.

```python
async def main():
    chat_server = ChatServer()
    await chat_server.start_chat_server('127.0.0.1', 8000)

asyncio.run(main())
```
Punto de entrada: crea el servidor y lo arranca. `asyncio.run` gestiona el event loop completo.

---

**Explicación por función — qué hace cada una:**

| Función | Quién la llama | Qué hace |
|---|---|---|
| `start_chat_server` | `main()` | Arranca el servidor y lo mantiene activo indefinidamente |
| `client_connected` | asyncio (automáticamente) | Valida el handshake inicial y registra al usuario |
| `_add_user` | `client_connected` | Guarda el writer y lanza la tarea de escucha del usuario |
| `_on_connect` | `client_connected` | Envía bienvenida al nuevo usuario y notifica a los demás |
| `_remove_user` | `_listen_for_messages`, `_notify_all` | Elimina al usuario del diccionario y cierra su conexión |
| `_listen_for_messages` | Tarea independiente (`create_task`) | Bucle infinito que lee mensajes del usuario con timeout de 60s |
| `_notify_all` | `_on_connect`, `_listen_for_messages` | Envía un mensaje a todos los usuarios conectados |
| `main` | `asyncio.run` | Crea el servidor y lanza el event loop |

**Flujo completo cuando Alice se conecta y escribe "hola":**

```
1. asyncio detecta conexión → llama client_connected(reader_alice, writer_alice)
2. client_connected lee "CONNECT Alice\n" → llama _add_user + _on_connect
3. _add_user guarda writer_alice en el diccionario y lanza _listen_for_messages como tarea
4. _on_connect envía "Welcome! 1 user(s)..." a Alice y "Alice connected!" a todos
5. [Alice escribe "hola"]
6. _listen_for_messages recibe "hola\n" → llama _notify_all("Alice: hola\n")
7. _notify_all itera el diccionario y escribe "Alice: hola\n" a cada writer conectado
```

> **Caso de uso real:** El backend de un soporte al cliente en tiempo real. Varios agentes de soporte conectados al servidor reciben los mensajes de los clientes. El timeout de 60 segundos desconecta automáticamente a los clientes que pierden la conexión sin avisar (cierre de pestaña, corte de red), liberando recursos del servidor sin intervención manual.

---

### Listing 8.14 — El cliente de chat

> **Objetivo:** Implementar un cliente de chat con interfaz de terminal dividida en dos zonas: mensajes entrantes arriba, campo de input abajo. Para lograrlo, se ejecutan **dos tareas en paralelo**: una que escucha mensajes del servidor (`listen_for_messages`) y otra que lee input del usuario (`read_and_send`). `asyncio.wait` con `FIRST_COMPLETED` garantiza que el cliente termine limpiamente en cuanto cualquiera de las dos tareas acabe (por desconexión del servidor o error).

```python
import asyncio
import logging
import sys
import tty
from asyncio import StreamReader, StreamWriter
from collections import deque
from chapter_08.listing_8_5 import create_stdin_reader
from chapter_08.listing_8_7 import (save_cursor_position, restore_cursor_position,
                                     move_to_top_of_screen, delete_line,
                                     move_to_bottom_of_screen)
from chapter_08.listing_8_8 import read_line
from chapter_08.listing_8_9 import MessageStore

async def send_message(message: str, writer: StreamWriter):
    writer.write((message + '\n').encode())
    await writer.drain()

async def listen_for_messages(reader: StreamReader,
                               message_store: MessageStore):      # ❶
    while (message := await reader.readline()) != b'':
        await message_store.append(message.decode())
    await message_store.append('Server closed connection.')

async def read_and_send(stdin_reader: StreamReader,
                        writer: StreamWriter):                     # ❷
    while True:
        message = await read_line(stdin_reader)
        await send_message(message, writer)

async def main():
    async def redraw_output(items: deque):
        save_cursor_position()
        move_to_top_of_screen()
        for item in items:
            delete_line()
            sys.stdout.write(item)
        restore_cursor_position()

    tty.setcbreak(0)
    # Limpia la pantalla del terminal antes de iniciar la UI del chat
    sys.stdout.write('\033[2J\033[H')
    sys.stdout.flush()
    rows = move_to_bottom_of_screen()

    messages = MessageStore(redraw_output, rows - 1)

    stdin_reader = await create_stdin_reader()
    sys.stdout.write('Enter username: ')
    username = await read_line(stdin_reader)

    reader, writer = await asyncio.open_connection('127.0.0.1', 8000)  # ❸

    writer.write(f'CONNECT {username}\n'.encode())
    await writer.drain()

    message_listener = asyncio.create_task(listen_for_messages(reader, messages))  # ❹
    input_listener = asyncio.create_task(read_and_send(stdin_reader, writer))

    try:
        await asyncio.wait([message_listener, input_listener],
                           return_when=asyncio.FIRST_COMPLETED)
    except Exception as e:
        logging.exception(e)
        writer.close()
        await writer.wait_closed()

asyncio.run(main())
```

**Explicación ordenada del código:**

---

**Paso 1 — Imports: qué necesita el cliente**

```python
import tty
from chapter_08.listing_8_5 import create_stdin_reader
from chapter_08.listing_8_7 import (save_cursor_position, ...)
from chapter_08.listing_8_8 import read_line
from chapter_08.listing_8_9 import MessageStore
```

`tty` — módulo estándar para poner el terminal en modo raw (sin buffering de línea). Los demás imports son las utilidades construidas en listings anteriores. El cliente de chat es la integración de todo lo visto en la sección 8.4.

---

**Paso 2 — `send_message`: enviar un mensaje al servidor**

```python
async def send_message(message: str, writer: StreamWriter):
    writer.write((message + '\n').encode())
    await writer.drain()
```

Añade `\n` al final (el servidor usa `readline()`, que necesita ese terminador para saber dónde acaba el mensaje), convierte a bytes y vacía el buffer con `drain()`.

---

**Paso 3 — `listen_for_messages`: recibir mensajes del servidor (Tarea A)**

```python
async def listen_for_messages(reader: StreamReader, message_store: MessageStore):
    while (message := await reader.readline()) != b'':
        await message_store.append(message.decode())
    await message_store.append('Server closed connection.')
```

Bucle infinito que espera líneas del servidor. Cada línea recibida se añade al `MessageStore`, que llama automáticamente a `redraw_output` y refresca la zona de mensajes en pantalla. Cuando el servidor cierra la conexión, `readline()` devuelve `b''` y el bucle termina — añadiendo el aviso de desconexión.

---

**Paso 4 — `read_and_send`: leer input del usuario y enviarlo (Tarea B)**

```python
async def read_and_send(stdin_reader: StreamReader, writer: StreamWriter):
    while True:
        message = await read_line(stdin_reader)
        await send_message(message, writer)
```

Bucle infinito que lee lo que escribe el usuario carácter a carácter (con `read_line` del Listing 8.8 — necesario porque el terminal está en modo `setcbreak`) y lo envía al servidor. Nunca termina por sí solo — solo se para cuando `asyncio.wait` cancela esta tarea.

---

**Paso 5 — `main`: preparar la pantalla y conectarse**

```python
tty.setcbreak(0)
sys.stdout.write('\033[2J\033[H')   # limpia pantalla completa
rows = move_to_bottom_of_screen()   # mueve cursor a la última fila
messages = MessageStore(redraw_output, rows - 1)
```

Pone el terminal en modo raw (`setcbreak`), limpia la pantalla y posiciona el cursor abajo. `MessageStore` se crea con el callback `redraw_output` (que sabe cómo dibujar mensajes arriba) y el número máximo de mensajes visibles (`rows - 1`).

```python
stdin_reader = await create_stdin_reader()
username = await read_line(stdin_reader)
```

Conecta stdin al event loop de asyncio y pide el nombre de usuario. Este es el único `input()` asíncrono del cliente.

```python
reader, writer = await asyncio.open_connection('127.0.0.1', 8000)
writer.write(f'CONNECT {username}\n'.encode())
await writer.drain()
```

Abre la conexión TCP al servidor y envía el handshake. El servidor espera exactamente este formato como primer mensaje.

---

**Paso 6 — Lanzar las dos tareas en paralelo**

```python
message_listener = asyncio.create_task(listen_for_messages(reader, messages))
input_listener   = asyncio.create_task(read_and_send(stdin_reader, writer))

await asyncio.wait([message_listener, input_listener],
                   return_when=asyncio.FIRST_COMPLETED)
```

Las dos tareas corren simultáneamente en el mismo hilo:
- `message_listener` — escucha el servidor, actualiza la pantalla
- `input_listener` — escucha el teclado, envía al servidor

`asyncio.wait` con `FIRST_COMPLETED` retorna en cuanto **cualquiera** de las dos termina. Si el servidor cae, `message_listener` termina → `wait` retorna → el cliente cierra limpiamente. Sin esto, `input_listener` seguiría en bucle intentando enviar mensajes a un servidor que ya no existe.

---

**Explicación por función — resumen:**

| Función | Rol | Cómo termina |
|---|---|---|
| `send_message` | Envía un mensaje al servidor con `\n` y `drain()` | Cuando `write` + `drain` completan |
| `listen_for_messages` | **Tarea A**: recibe mensajes del servidor y refresca pantalla | Cuando el servidor cierra la conexión (`b''`) |
| `read_and_send` | **Tarea B**: lee teclado y envía cada mensaje al servidor | Solo cuando `asyncio.wait` la cancela |
| `redraw_output` (interna) | Callback de `MessageStore`: redibuja la zona de mensajes | Cada vez que llega un mensaje nuevo |
| `main` | Configura terminal, conecta, lanza tareas, gestiona cierre | Cuando `FIRST_COMPLETED` retorna |

---

**Flujo completo — desde que el usuario arranca el cliente:**

```
1. main() limpia pantalla, mueve cursor abajo
2. Pide username → usuario escribe "Alice" + Enter
3. open_connection → TCP conectado al servidor
4. Envía "CONNECT Alice\n" → handshake completado
5. Lanza Tarea A (listen_for_messages) y Tarea B (read_and_send)
6. [Servidor envía "Welcome! 1 user(s) are online!\n"]
   → Tarea A recibe línea → MessageStore.append → redraw_output dibuja arriba
7. [Usuario escribe "hola" + Enter]
   → Tarea B lee "hola" con read_line → send_message envía "hola\n"
8. [Servidor desconecta]
   → Tarea A: readline() devuelve b'' → termina → asyncio.wait retorna
9. main() cierra writer y termina
```

### Resultado esperado

```
Welcome! 1 user(s) are online!
MissIslington connected!
SirBedevere connected!
SirBedevere: Is that your nose?
MissIslington: No, it's a false one!
```

El chat funciona con **un solo hilo**, gracias a la concurrencia cooperativa de asyncio.

> **Caso de uso real:** Una sala de chat para un equipo de desarrollo durante un incident de producción. Varios ingenieros se conectan desde sus terminales, coordinan la respuesta en tiempo real y el servidor los desconecta automáticamente si pierden la conexión. Todo el sistema corre en un solo proceso Python ligero — sin necesidad de Redis, WebSockets ni infraestructura extra.

### Glosario — 8.6

| Término | Definición |
|---|---|
| **Protocolo de aplicación** | Convención de mensajes que cliente y servidor acuerdan; aquí: primer mensaje = `CONNECT <username>` |
| **Handshake** | Proceso de establecimiento inicial de comunicación; ambas partes se identifican antes de intercambiar datos reales |
| **`asyncio.wait`** | Coroutine que espera a que un conjunto de tareas complete; admite `return_when` para controlar cuándo retorna |
| **`FIRST_COMPLETED`** | Modo de `asyncio.wait` que retorna en cuanto la primera tarea del conjunto termina |
| **`asyncio.wait_for`** | Coroutine que ejecuta otra coroutine con un timeout; lanza `TimeoutError` si supera el límite |
| **`asyncio.TimeoutError`** | Excepción lanzada cuando `wait_for` supera su timeout |
| **Tarea en paralelo** | Coroutine ejecutada con `create_task` que corre concurrentemente con otras tareas en el mismo event loop |
| **`MessageStore`** | Clase que almacena mensajes con tamaño máximo y notifica a un callback cuando hay cambios |
| **Timeout de inactividad** | Mecanismo para desconectar clientes que no han enviado datos en un tiempo determinado |

---

## Exercicis Pràctics

---

### Exercici 1 — Servidor de Telemetria de Sensors de Planta (`servidor_telemetria.py`)

**Context:** En una planta industrial, sensors de temperatura i pressió envien dades a un servidor central. El servidor ha de gestionar múltiples sensors simultanis, processar les dades i confirmar la recepció a cada sensor.

**Comportament del servidor:**
- Escolta al port `8888`.
- Per cada sensor connectat, llegeix dades línia a línia.
- Si la dada conté `"ALERTA"` → respon `"PROTOCO_EMERGENCIA_ACTIVAT"`.
- Qualsevol altra dada → respon `"DADA_REBUDA"`.
- Gestiona desconnexions i errors sense caure.

**Com provar-ho:**

> `nc` no està disponible a Windows. Usa `test_sensor.py` (inclòs a la carpeta) com a substitut interactiu.

```
# Terminal 1 — inicia el servidor
python servidor_telemetria.py

# Terminal 2 — simula el primer sensor
python test_sensor.py
Sensor > Temperatura: 25C          →  Servidor: DADA_REBUDA
Sensor > ALERTA: Pressió alta      →  Servidor: PROTOCO_EMERGENCIA_ACTIVAT

# Terminal 3 — segon sensor simultani (verifica concurrència)
python test_sensor.py
Sensor > Pressió: 1.2 bar          →  Servidor: DADA_REBUDA
```

A la Terminal 1 veuràs els logs dels dos sensors intercalats amb ports diferents:
```
Sensor connectat: ('127.0.0.1', 52341)
Sensor connectat: ('127.0.0.1', 52342)
[('127.0.0.1', 52341)] Dada rebuda: Temperatura: 25C
[('127.0.0.1', 52342)] Dada rebuda: Pressió: 1.2 bar
```
Això confirma que el servidor atén els dos sensors en paral·lel sense bloquejar-se. `Ctrl+C` per tancar cada `test_sensor.py`.

**Explicació del codi:**

`handle_sensor(reader, writer)` — coroutine que gestiona **un sensor**. asyncio en crea una instància per cada connexió entrant, de manera que tots els sensors s'atenen en paral·lel sense bloquejar-se mútuament.

```python
async def handle_sensor(reader: StreamReader, writer: StreamWriter) -> None:
```

Bucle principal: llegeix línies fins que el sensor es desconnecta (`readline()` retorna `b''`):
```python
while True:
    data = await reader.readline()   # espera dades sense bloquejar
    if not data:
        break                        # sensor desconnectat (EOF)
```

Lògica de resposta: comprova si el missatge conté `"ALERTA"` i escriu la resposta corresponent. `drain()` garanteix que els bytes surten realment del buffer abans de continuar:
```python
writer.write(response.encode())
await writer.drain()
```

Tancament net en el bloc `finally`: s'executa sempre, fins i tot si hi ha una excepció, evitant que els recursos quedin oberts:
```python
writer.close()
await writer.wait_closed()
```

`main()` — crea el servidor i el manté actiu indefinidament:
```python
server = await asyncio.start_server(handle_sensor, '127.0.0.1', 8888)
async with server:
    await server.serve_forever()
```

**Conceptes aplicats:** `start_server`, `StreamReader`/`StreamWriter`, `drain()`, `close()` + `wait_closed()`, gestió d'excepcions per connexió.

---

### Exercici 2 — Prova de Càrrega (`carregues_telemetria.py`)

**Context:** Volem mesurar quantes peticions per segon pot atendre el servidor de telemetria, simulant múltiples sensors concurrents — com fa l'eina `wrk` per a servidors HTTP.

**Mètriques calculades:**

| Mètrica | Descripció |
|---|---|
| Total peticions | Quants missatges s'han enviat i rebut correctament |
| Errors | Connexions fallides o respostes incorrectes |
| Temps total | Durada real de la prova en segons |
| Peticions/segon | Throughput = total peticions ÷ temps total |

**Com executar-ho:**
```
# Terminal 1 — servidor en marxa
python servidor_telemetria.py

# Terminal 2 — prova de càrrega (paràmetres per defecte: 10 connexions, 5 segons)
python carregues_telemetria.py

# Exemple de sortida:
# Iniciant prova de càrrega: 10 connexions durant 5s
# --- Resultats ---
# Temps total:        5.01s
# Total peticions:    4832
# Errors:             0
# Peticions/segon:    964.5
```

**Explicació del codi:**

`sensor_worker(duration, results)` — simula **un sensor** que envia peticions en bucle durant `duration` segons. Acumula resultats en el diccionari compartit `results`:

```python
async def sensor_worker(duration: float, results: dict) -> None:
    end_time = time.monotonic() + duration   # marca el moment de parada
    ...
    while time.monotonic() < end_time:       # envia fins que s'acabi el temps
        writer.write(b'Temperatura: 25C\n')
        await writer.drain()
        response = await reader.readline()
        results['requests'] += 1
```

Per què `time.monotonic()` i no `time.time()`? `monotonic()` mai va enrere (no es veu afectat per canvis d'hora del sistema), ideal per mesurar durades.

`main()` — llança totes les tasques de sensor en paral·lel amb `create_task` i espera que acabin totes amb `gather`:
```python
tasks = [
    asyncio.create_task(sensor_worker(DURATION_SECONDS, results))
    for _ in range(MAX_CONNECTIONS)
]
await asyncio.gather(*tasks)
```

**Experiments recomanats:**

Per a cada experiment, canvia els paràmetres a `carregues_telemetria.py`, guarda i executa. Compara els resultats.

---

**Experiment 1 — Línia base (valors per defecte)**
```python
MAX_CONNECTIONS = 10
DURATION_SECONDS = 5
```
Estableix el punt de referència. Anota el throughput. Tots els experiments posteriors es comparen amb aquest valor.

Resultat esperat:
```
Peticions/segon: ~800-1200   (depèn de la màquina)
Errors: 0
```

---

**Experiment 2 — Augmentar connexions (escala lineal)**
```python
MAX_CONNECTIONS = 50
DURATION_SECONDS = 5
```
Amb 5x més workers, el throughput hauria d'augmentar — però no 5x. Per què? Cada worker fa `await drain()` i `await readline()`, cedint el control. El bottleneck passa a ser el servidor processant 50 connexions. Observa si el throughput escala o s'estabilitza.

Resultat esperat:
```
Iniciant prova de càrrega: 50 connexions durant 5s
--- Resultats ---
Temps total:        5.02s
Total peticions:    3800-5500     ← més que exp.1 però no 5x
Errors:             0
Peticions/segon:    760-1100      ← per connexió: menys que exp.1
```
El throughput total puja però el rendiment per connexió baixa — el servidor reparteix el temps entre 50 clients.

---

**Experiment 3 — Connexions molt altes (límit del sistema)**
```python
MAX_CONNECTIONS = 200
DURATION_SECONDS = 5
```
A partir d'un cert punt, afegir més connexions no millora el throughput — el servidor és el coll d'ampolla. Pots veure errors si el sistema operatiu arriba al límit de sockets oberts. En Windows el límit per defecte és ~1000 file descriptors.

Resultat esperat:
```
Iniciant prova de càrrega: 200 connexions durant 5s
--- Resultats ---
Temps total:        5.08s
Total peticions:    4000-6000     ← similar o inferior a exp.2
Errors:             0-5           ← possibles errors de connexió
Peticions/segon:    800-1200      ← estabilitzat, no escala més
```
Si el servidor no pot atendre 200 connexions simultànies, alguns workers esperen i el throughput per connexió cau molt. Errors > 0 indica que el SO ha rebutjat alguna connexió.

---

**Experiment 4 — Durada curta (mesura inestable)**
```python
MAX_CONNECTIONS = 10
DURATION_SECONDS = 2
```
Amb poc temps, el cost d'obrir les connexions TCP (handshake) pesa molt sobre el total. El throughput mesurat serà inferior a la línia base perquè inclou el temps d'establir connexió. Les mesures curtes no són representatives.

Resultat esperat:
```
Iniciant prova de càrrega: 10 connexions durant 2s
--- Resultats ---
Temps total:        2.01s
Total peticions:    250-500       ← molt menys que exp.1
Errors:             0
Peticions/segon:    125-250       ← ~6x menys que exp.1
```
Executa 3 vegades seguits — veuràs valors molt diferents cada cop. Això demostra que 2s és massa poc per obtenir una mesura estable.

---

**Experiment 5 — Durada llarga (mesura estable)**
```python
MAX_CONNECTIONS = 10
DURATION_SECONDS = 30
```
Amb 30 segons, el cost inicial de connexió és negligible. La mesura reflecteix el rendiment real en estat estacionari. Ideal per comparar servidors o configuracions.

Resultat esperat:
```
Iniciant prova de càrrega: 10 connexions durant 30s
--- Resultats ---
Temps total:        30.02s
Total peticions:    24000-36000   ← ~6x exp.1 (30s vs 5s)
Errors:             0
Peticions/segon:    800-1200      ← molt consistent, igual que exp.1
```
Executa 3 vegades — els valors de `Peticions/segon` seran molt similars entre sí, confirmant que la mesura és estable.

---

**Experiment 6 — Servidor aturat (prova d'errors)**
```python
MAX_CONNECTIONS = 10
DURATION_SECONDS = 5
```
Para el servidor (`Ctrl+C` a Terminal 1) i executa la prova. Tots els workers intenten connectar-se i fallen immediatament.

Resultat esperat:
```
Total peticions: 0
Errors: 10
Peticions/segon: 0.0
```
Confirma que la gestió d'errors del `sensor_worker` funciona correctament — cap excepció no capturada, el programa acaba net.

---

**Resum visual dels experiments:**

| Experiment | `MAX_CONNECTIONS` | `DURATION_SECONDS` | Què mesura |
|---|---|---|---|
| 1 — Línia base | 10 | 5 | Punt de referència |
| 2 — Escala | 50 | 5 | Guany amb més connexions |
| 3 — Límit | 200 | 5 | Saturació del servidor |
| 4 — Durada curta | 10 | 2 | Impacte del handshake TCP |
| 5 — Durada llarga | 10 | 30 | Rendiment en estat estacionari |
| 6 — Sense servidor | 10 | 5 | Gestió correcta d'errors |

**Conceptes aplicats:** `time.monotonic()`, `create_task`, `gather`, `drain()`, mesura de rendiment asíncron.

---

## Resumen del Capítulo

| Concepto | Nivel | Para qué se usa |
|---|---|---|
| Transports | Bajo nivel | Abstraen el envío/recepción de bytes sobre sockets |
| Protocols | Bajo nivel | Definen callbacks para eventos de conexión y datos |
| `StreamReader` | Alto nivel | Leer datos de forma asíncrona con `readline()` / `read()` |
| `StreamWriter` | Alto nivel | Escribir datos con `write()` + `drain()` |
| `open_connection` | Alto nivel | Abre una conexión y devuelve reader + writer |
| `start_server` | Alto nivel | Crea un servidor que acepta conexiones entrantes |
| `connect_read_pipe` | Bajo/medio nivel | Conecta un file descriptor (stdin) a un StreamReader |
| `asyncio.wait_for` | Utilidad | Añade timeout a cualquier coroutine |
| `asyncio.wait` | Utilidad | Espera múltiples tareas con control sobre cuándo retornar |

**Lo más importante a recordar:**

- Los transportes y protocolos son la **base** de los streams pero **no** se recomienda usarlos directamente en aplicaciones normales.
- `StreamReader` y `StreamWriter` son la forma **recomendada** de trabajar con streams en asyncio.
- Siempre hacer `await writer.drain()` después de `writer.write()` para evitar problemas de memoria.
- Siempre hacer `await writer.wait_closed()` después de `writer.close()` para asegurarse de que el cierre se completa.
- `asyncio.start_server` es la forma recomendada de crear servidores, mucho más simple que gestionar sockets manualmente.
- `asyncio.wait_for` añade timeout a cualquier coroutine; `asyncio.wait` con `FIRST_COMPLETED` permite terminar limpiamente cuando la primera tarea acaba.

---

## Test — 26 Preguntas sobre Streams en asyncio

> Algunas preguntas tienen **más de una respuesta correcta** — se indica con *(una o más correctas)*.

### Preguntas

**1.** ¿Qué diferencia existe entre `StreamReader`/`StreamWriter` y Transportes/Protocolos? *(una o más correctas)*
- A) `StreamReader`/`StreamWriter` son más rápidos porque usan menos memoria
- B) `StreamReader`/`StreamWriter` son la API de alto nivel, más simple y recomendada para aplicaciones normales
- C) Transportes y Protocolos se basan en callbacks; `StreamReader`/`StreamWriter` son compatibles con `await`
- D) Transportes y Protocolos son obsoletos y no deben usarse nunca

**2.** ¿Por qué es importante llamar `await writer.drain()` después de `writer.write(data)`? *(una o más correctas)*
- A) Porque `write()` no envía datos — solo `drain()` los envía realmente
- B) Porque si el buffer se llena, escribir sin `drain()` consume cada vez más memoria
- C) Porque `drain()` cede el control al event loop, permitiendo que otras tareas se ejecuten
- D) Porque sin `drain()`, los datos se envían en orden incorrecto

**3.** ¿Qué devuelve `await asyncio.open_connection('host', port)`?
- A) Un objeto `AbstractServer`
- B) Una tupla `(StreamReader, StreamWriter)`
- C) Un `Future` con la respuesta del servidor
- D) Una instancia de `asyncio.Protocol`

**4.** ¿Qué hace `eof_received()` en un protocolo? *(una o más correctas)*
- A) Cierra automáticamente la conexión TCP
- B) Se llama cuando el otro extremo cierra su lado de la conexión
- C) Indica que no se recibirán más datos
- D) Se llama cuando se produce un error de red

**5.** ¿Por qué se usa un `Future` en `HTTPGetClientProtocol` del Listing 8.1?
- A) Para acelerar la transmisión de datos
- B) Como puente entre el mundo de callbacks y el mundo de coroutines con `await`
- C) Para almacenar los datos recibidos en el buffer
- D) Porque `readline()` no está disponible en la API de protocolos

**6.** ¿Qué es una `protocol_factory`? *(una o más correctas)*
- A) Una clase que hereda de `asyncio.Protocol`
- B) Una función que devuelve una nueva instancia del protocolo cada vez que se llama
- C) Un método interno de asyncio que gestiona conexiones TCP
- D) asyncio la usa para poder crear múltiples instancias del protocolo si es necesario

**7.** En el Listing 8.3, ¿qué ocurre cuando `stream_reader.readline()` devuelve `b''`? *(una o más correctas)*
- A) El servidor ha enviado una línea vacía — el bucle continúa
- B) Ha ocurrido un error de red — se lanza una excepción
- C) Se ha alcanzado EOF — el servidor ha cerrado la conexión
- D) El bucle `while` termina y el generador se agota

**8.** ¿Por qué `writer.close()` por sí solo no es suficiente? *(una o más correctas)*
- A) Porque `close()` no cierra el socket TCP, solo el writer de Python
- B) Porque puede haber datos en el buffer pendientes de enviar
- C) `wait_closed()` espera a que el cierre sea completo y captura excepciones tardías
- D) Porque `close()` es síncrono y bloquea el event loop

**9.** ¿Qué hace `asyncio.start_server` cuando un cliente se conecta? *(una o más correctas)*
- A) Crea un nuevo hilo para atender al cliente
- B) Llama al `client_connected_cb` pasándole un `StreamReader` y `StreamWriter`
- C) Si el callback es una coroutine, asyncio la envuelve automáticamente en una tarea
- D) Bloquea hasta que el cliente se desconecte

**10.** ¿Por qué se usa `asyncio.wait_for(reader.readline(), 60)` en Listing 8.13? *(una o más correctas)*
- A) Para limitar el tamaño de los mensajes a 60 bytes
- B) Para implementar un timeout de inactividad de 60 segundos
- C) Si el cliente no envía nada en 60 segundos, se lanza `TimeoutError` y se elimina al usuario
- D) Para leer exactamente 60 caracteres del cliente

**11.** ¿Por qué en `_notify_all` se usan dos pasos para eliminar usuarios inactivos?
- A) Para mejorar el rendimiento evitando llamadas innecesarias
- B) Porque eliminar del diccionario mientras se itera lanza `RuntimeError`
- C) Para poder notificar a los usuarios antes de eliminarlos
- D) Porque `_remove_user` es asíncrona y no puede llamarse dentro del bucle for

**12.** ¿Qué hace `tty.setcbreak(0)`? *(una o más correctas)*
- A) Activa el modo de colores en el terminal
- B) Los caracteres se envían al programa uno a uno sin esperar a Enter
- C) Desactiva el eco del terminal — el usuario no ve lo que escribe
- D) Es necesario para que `read_line` funcione correctamente en el cliente de chat

**13.** ¿Para qué sirve `connect_read_pipe` en el cliente de chat? *(una o más correctas)*
- A) Para leer archivos del disco de forma asíncrona
- B) Envuelve stdin en un stream asíncrono compatible con `await`
- C) Sin esto, `input()` bloquearía el event loop entero
- D) Para conectar el teclado al servidor directamente

**14.** ¿Por qué el cliente usa `asyncio.wait` con `FIRST_COMPLETED` en lugar de `gather`? *(una o más correctas)*
- A) Porque `gather` no puede manejar más de una tarea
- B) `gather` esperaría indefinidamente a `read_and_send` (bucle infinito) si el servidor cierra
- C) `FIRST_COMPLETED` permite terminar limpiamente cuando cualquier tarea acaba
- D) Porque `gather` lanza excepciones que no se pueden capturar

**15.** ¿Qué ventaja tiene `deque(maxlen=n)` frente a una lista normal? *(una o más correctas)*
- A) Es más rápida para acceso por índice
- B) Descarta automáticamente el elemento más antiguo al superar `maxlen`
- C) `list.pop(0)` es O(n); `deque` mantiene el límite en O(1)
- D) Permite almacenar más mensajes que una lista normal

**16.** ¿Por qué se usa `read_line` en lugar de `readline()` con `setcbreak`? *(una o más correctas)*
- A) Porque `readline()` es más lenta que `read_line`
- B) Con `setcbreak`, los caracteres llegan uno a uno sin el `\n` que `readline()` necesita
- C) `read_line` lee byte a byte y para cuando encuentra `\n`
- D) Porque `readline()` no funciona con `StreamReader`

**17.** ¿Cuál es la diferencia entre `asyncio.wait` y `asyncio.wait_for`? *(una o más correctas)*
- A) `wait_for` aplica timeout a una única coroutine; `wait` espera un conjunto de tareas
- B) `wait` admite `return_when` con modos como `FIRST_COMPLETED`
- C) `wait_for` lanza `TimeoutError` si se supera el límite
- D) `wait` y `wait_for` son intercambiables

**18.** ¿Qué secuencia ANSI mueve el cursor a la esquina superior izquierda?
- A) `\033[2K`
- B) `\0337`
- C) `\033[H`
- D) `\0338`

**19.** ¿Qué hace el servidor de chat si recibe un comando diferente a `CONNECT`?
- A) Ignora el mensaje y espera el siguiente
- B) Reenvía el mensaje a todos los usuarios conectados
- C) Registra el error y cierra la conexión inmediatamente
- D) Devuelve un mensaje de error al cliente y espera un comando válido

**20.** ¿Por qué el chat puede gestionar múltiples clientes con un solo hilo? *(una o más correctas)*
- A) Porque Python tiene un GIL que optimiza el I/O concurrente
- B) asyncio usa concurrencia cooperativa: las coroutines ceden el control en cada `await`
- C) Mientras una coroutine espera I/O, el event loop atiende a otras
- D) Porque los sockets son inherentemente thread-safe en Python

**21.** ¿Para qué sirve `writer.get_extra_info('peername')` en `servidor_telemetria.py`? *(una o más correctas)*
- A) Para obtener el nombre de host del sensor mediante DNS
- B) Devuelve la IP y puerto del sensor conectado, útil para identificarlo en logs
- C) Para verificar que la conexión es segura (SSL)
- D) Sin él, los logs no distinguirían entre sensores diferentes

**22.** ¿Qué problema evita el bloque `finally` en `servidor_telemetria.py`? *(una o más correctas)*
- A) Evita que el servidor procese mensajes duplicados
- B) Garantiza que el socket se cierra aunque ocurra una excepción
- C) Sin `finally`, el puerto quedaría ocupado indefinidamente si el sensor falla
- D) Evita que el servidor se reinicie automáticamente

**23.** Si dos sensores envían `"ALERTA"` al mismo tiempo, ¿el servidor responde correctamente? *(una o más correctas)*
- A) No — el servidor solo puede procesar una alerta a la vez con un único hilo
- B) Sí — cada sensor tiene su propia coroutine `handle_sensor` independiente
- C) Sí — cuando una coroutine hace `await`, la otra puede ejecutarse
- D) Depende — solo si el servidor tiene más de un hilo activo

**24.** ¿Por qué se usa `time.monotonic()` en `carregues_telemetria.py`? *(una o más correctas)*
- A) Porque es más preciso que `time.time()` a nivel de nanosegundos
- B) `monotonic()` nunca va hacia atrás — no se ve afectado por cambios de hora del sistema
- C) `time.time()` podría dar duraciones negativas si el sistema sincroniza el reloj durante la prueba
- D) Porque `time.time()` no está disponible en asyncio

**25.** ¿Es seguro modificar el diccionario `results` sin locks en `carregues_telemetria.py`? *(una o más correctas)*
- A) No — siempre hay riesgo de condición de carrera con coroutines
- B) Sí — asyncio usa un único hilo, nunca dos coroutines ejecutan código Python al mismo tiempo
- C) Solo es seguro porque `+=` es una operación atómica en Python
- D) Sí — las modificaciones ocurren cuando la coroutine tiene el control del event loop

**26.** ¿Qué ocurre si se aumenta `MAX_CONNECTIONS` a 500? *(una o más correctas)*
- A) El throughput escala linealmente — 500x más peticiones por segundo
- B) El sistema operativo puede limitar los sockets abiertos (límite de file descriptors)
- C) A partir de cierto punto, el servidor se convierte en el cuello de botella
- D) El throughput total se estabiliza o baja porque cada conexión espera más tiempo

---

### Respuestas

**1. B, C** — B: son la API recomendada para aplicaciones normales. C: la diferencia clave es callbacks vs `await`. A es falso (no son más rápidos). D es falso (se usan para frameworks de red).

**2. B, C** — B: sin `drain()` el buffer crece sin límite. C: `drain()` cede el control al event loop. A es falso — `write()` sí escribe al buffer; `drain()` vacía ese buffer hacia la red.

**3. B** — Devuelve exactamente `(StreamReader, StreamWriter)`.

**4. B, C** — B: se llama cuando el otro extremo cierra su lado. C: señal de que no hay más datos. A es falso (no cierra automáticamente). D es falso (eso es `connection_lost`).

**5. B** — El `Future` es el puente entre callbacks (síncronos) y coroutines (`await`). Sin él no habría forma de conectar los dos mundos.

**6. B, D** — B: es una función que devuelve instancias. D: permite crear múltiples instancias para múltiples conexiones. A es falso (no hereda de Protocol). C es falso (no es interno de asyncio).

**7. C, D** — C: `b''` significa EOF, el servidor cerró la conexión. D: eso provoca que el `while` y el generador terminen. A y B son incorrectos.

**8. B, C** — B: puede haber datos en buffer pendientes. C: `wait_closed()` espera el cierre completo. A es falso (`close()` sí cierra el socket). D es falso (`close()` no bloquea).

**9. B, C** — B: llama al callback con reader + writer. C: si es coroutine, asyncio la envuelve en tarea automáticamente. A es falso (no crea hilos). D es falso (no bloquea).

**10. B, C** — B: timeout de inactividad de 60s. C: si supera el límite, `TimeoutError` → usuario eliminado. A y D son incorrectos.

**11. B** — Modificar un diccionario durante iteración lanza `RuntimeError` en Python. Solo B es la razón correcta.

**12. B, D** — B: caracteres van uno a uno sin esperar Enter. D: necesario para que `read_line` funcione. A es falso. C es falso (no desactiva el eco).

**13. B, C** — B: envuelve stdin en stream asíncrono. C: sin esto `input()` bloquea el event loop. A y D son incorrectos.

**14. B, C** — B: `gather` quedaría esperando `read_and_send` para siempre. C: `FIRST_COMPLETED` sale en cuanto una termina. A es falso (`gather` puede manejar N tareas). D es falso.

**15. B, C** — B: descarte automático del más antiguo. C: `list.pop(0)` es O(n), `deque` es O(1). A es falso (lista es más rápida por índice). D es falso.

**16. B, C** — B: con `setcbreak` no llega `\n` hasta pulsar Enter, `readline()` nunca termina. C: `read_line` resuelve esto leyendo byte a byte. A y D son incorrectos.

**17. A, B, C** — Las tres son correctas. D es falso — no son intercambiables.

**18. C** — `\033[H` mueve a fila 1, columna 1. `\0337` guarda posición, `\0338` restaura, `\033[2K` borra línea.

**19. C** — Registra el error y cierra inmediatamente. No ignora, no reenvía, no espera otro comando.

**20. B, C** — B: concurrencia cooperativa con `await`. C: el event loop atiende a otros mientras uno espera I/O. A es falso (el GIL no optimiza I/O). D es falso.

**21. B, D** — B: devuelve IP + puerto. D: sin él los logs no distinguen sensores. A es falso (no hace DNS). C es falso (no verifica SSL).

**22. B, C** — B: el socket se cierra siempre. C: sin `finally` el puerto quedaría ocupado indefinidamente. A y D son incorrectos.

**23. B, C** — B: cada sensor tiene su propia coroutine independiente. C: cuando una hace `await`, la otra puede ejecutarse. A y D son incorrectos — un hilo es suficiente con concurrencia cooperativa.

**24. B, C** — B: `monotonic()` no va hacia atrás. C: `time.time()` puede dar duraciones negativas con ajustes NTP. A es falso (la precisión es similar). D es falso (`time.time()` sí existe en asyncio).

**25. B, D** — B: un único hilo, nunca dos coroutines al mismo tiempo. D: las modificaciones ocurren cuando la coroutine tiene el control. A es falso. C es trampa — en CPython `+=` sobre enteros puede ser atómico, pero no es la razón correcta aquí.

**26. B, C, D** — B: límite de file descriptors del SO. C: el servidor es el cuello de botella. D: throughput se estabiliza o baja. A es falso — nunca escala linealmente.
