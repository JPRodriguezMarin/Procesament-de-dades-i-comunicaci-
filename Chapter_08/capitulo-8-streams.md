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

**Explicación de los puntos clave:**

- **❶** El primer mensaje de cada cliente debe ser `CONNECT <username>`. Si no lo es, el servidor cierra la conexión. Esto implementa la fase de "handshake" del protocolo de aplicación.
- **❷** Guarda el `StreamWriter` en un diccionario indexado por nombre de usuario. Lanza una tarea independiente para escuchar mensajes, de modo que el servidor puede seguir aceptando más conexiones.
- **❸** Informa al cliente del número de usuarios conectados y notifica a todos los demás del nuevo usuario.
- **❹** Usa `asyncio.wait_for(reader.readline(), 60)` para implementar el timeout de inactividad. Si el cliente no envía nada en 60 segundos, `wait_for` lanza `asyncio.TimeoutError`, se captura la excepción y se elimina al usuario.
- **❺** Envía el mensaje a todos los usuarios. Para evitar modificar el diccionario mientras se itera sobre él (lo cual daría `RuntimeError`), los usuarios inactivos se acumulan en una lista y se eliminan después del bucle.

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

**Explicación de los puntos clave:**

- **❶** `listen_for_messages` lee líneas del servidor en bucle. Cada línea se añade al `MessageStore`, que automáticamente llama al callback `redraw_output` para refrescar la pantalla.
- **❷** `read_and_send` lee el input del usuario carácter a carácter (usando `read_line`) y lo envía al servidor. Es un bucle infinito porque el usuario puede enviar mensajes ilimitados.
- **❸** Abre la conexión al servidor y envía el mensaje de conexión con el nombre de usuario. Este es el handshake del protocolo: primer mensaje = `CONNECT <username>`.
- **❹** Ambas tareas se crean con `create_task` y se espera con `asyncio.wait(return_when=FIRST_COMPLETED)`. Cuando cualquiera de las dos termina (desconexión del servidor o error de red), el cliente termina limpiamente. Sin este patrón, si el servidor cerrara la conexión, `read_and_send` seguiría intentando enviar mensajes y daría errores.

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

## Test — 20 Preguntas sobre Streams en asyncio

### Preguntas

**1.** ¿Qué diferencia existe entre `StreamReader`/`StreamWriter` y Transportes/Protocolos en asyncio?

**2.** ¿Por qué es importante llamar `await writer.drain()` después de `writer.write(data)`?

**3.** ¿Qué devuelve `await asyncio.open_connection('host', port)`?

**4.** ¿Qué hace `eof_received()` en un protocolo? ¿Cuándo lo llama asyncio?

**5.** ¿Por qué se usa un `Future` en el `HTTPGetClientProtocol` del Listing 8.1? ¿Qué problema resuelve?

**6.** ¿Qué es una `protocol_factory`? ¿Por qué `create_connection` recibe una función en lugar de una instancia?

**7.** En el Listing 8.3, ¿qué ocurre cuando `stream_reader.readline()` devuelve `b''`?

**8.** ¿Por qué `writer.close()` por sí solo no es suficiente? ¿Qué hace `wait_closed()`?

**9.** ¿Qué hace `asyncio.start_server` cuando un cliente se conecta?

**10.** En el servidor de chat (Listing 8.13), ¿por qué se usa `asyncio.wait_for(reader.readline(), 60)`?

**11.** ¿Por qué en `_notify_all` del Listing 8.13 se acumulan los usuarios inactivos en una lista separada en lugar de eliminarlos directamente durante el bucle?

**12.** ¿Qué hace `tty.setcbreak(0)` en el cliente de chat? ¿Por qué es necesario?

**13.** ¿Qué es `connect_read_pipe` y para qué sirve en el cliente de chat?

**14.** ¿Por qué el cliente de chat usa `asyncio.wait` con `FIRST_COMPLETED` en lugar de `asyncio.gather`?

**15.** ¿Qué ventaja tiene `deque(maxlen=n)` frente a una lista normal en el `MessageStore`?

**16.** En el Listing 8.14, ¿por qué se usa `read_line` (leer carácter a carácter) en lugar de `readline()`?

**17.** ¿Cuál es la diferencia entre `asyncio.wait` y `asyncio.wait_for`?

**18.** ¿Qué secuencia ANSI mueve el cursor a la esquina superior izquierda de la pantalla?

**19.** En el protocolo del chat, el primer mensaje del cliente debe tener el formato `CONNECT <username>`. ¿Qué hace el servidor si recibe un comando diferente?

**20.** ¿Por qué el chat del Listing 8.13/8.14 puede gestionar múltiples clientes simultáneos con un solo hilo de Python?

---

### Respuestas

**1.** `StreamReader`/`StreamWriter` son la API de **alto nivel**: más simple, menos código, recomendada para la mayoría de aplicaciones. Transportes y Protocolos son la API de **bajo nivel**: más control, basada en callbacks, adecuada para frameworks de red. Los streams se construyen sobre transportes/protocolos internamente.

**2.** `write()` escribe al buffer interno del socket, no directamente a la red. Si el buffer se llena (red lenta, cliente lento), escribir sin `drain()` consume cada vez más memoria. `drain()` espera a que el buffer se vacíe, previniendo desbordamientos de memoria y cediendo el control al event loop mientras espera.

**3.** Devuelve una tupla `(StreamReader, StreamWriter)`. El `StreamReader` se usa para leer datos del servidor; el `StreamWriter` para enviarlos.

**4.** `eof_received()` se llama cuando el otro extremo cierra su lado de la conexión (envía EOF). Indica que no se recibirán más datos. En el Listing 8.1 se usa para completar el `Future` con la respuesta acumulada en el buffer.

**5.** El `Future` es el puente entre el mundo de callbacks (donde `eof_received` completa el future con `set_result`) y el mundo de coroutines (donde `get_response` espera el future con `await`). Sin el future, no habría forma de que el código externo esperara de forma asíncrona el resultado de los callbacks.

**6.** Una `protocol_factory` es una función (callable) que devuelve una nueva instancia del protocolo cada vez que se llama. Se usa porque asyncio puede necesitar crear múltiples instancias para múltiples conexiones o reintentos. Pasar la clase o una función factory en lugar de una instancia ya creada permite esta flexibilidad.

**7.** `readline()` devuelve `b''` (bytes vacíos) cuando se alcanza EOF — es decir, cuando el servidor ha cerrado la conexión. En el generador `read_until_empty`, esto hace que el `while` termine y el generador se agote.

**8.** `writer.close()` inicia el proceso de cierre pero es asíncrono internamente; puede haber datos en el buffer que aún no se han enviado o una excepción pendiente. `await writer.wait_closed()` espera a que el cierre sea completo y permite capturar esas excepciones tardías. Usar solo `close()` puede dejar recursos sin liberar.

**9.** `start_server` llama al `client_connected_cb` (callback o coroutine que se especificó) pasándole un `StreamReader` y un `StreamWriter` para esa conexión. Si es una coroutine, asyncio la envuelve en una tarea automáticamente.

**10.** Para implementar el timeout de inactividad: si el cliente no envía ningún mensaje en 60 segundos, `wait_for` lanza `asyncio.TimeoutError`. Esto permite que el servidor detecte y desconecte clientes inactivos, liberando recursos.

**11.** Modificar un diccionario mientras se itera sobre él lanza `RuntimeError: dictionary changed size during iteration` en Python. La solución es acumular los usuarios a eliminar en una lista separada y eliminarlos después de que el bucle termine.

**12.** `tty.setcbreak(0)` pone el terminal (stdin, file descriptor 0) en modo "cbreak": los caracteres se envían al programa uno a uno en cuanto se pulsan, sin esperar a que el usuario pulse Enter. Sin esto, el cliente no podría procesar la entrada carácter a carácter ni detectar el Enter como separador de mensajes.

**13.** `connect_read_pipe` es un método del event loop que envuelve un file descriptor de lectura (en este caso stdin) en un stream asíncrono. Permite leer del teclado con `await` de forma no bloqueante, compatible con el event loop de asyncio. Sin esto, `input()` bloquearía el event loop.

**14.** `asyncio.gather` espera a que **todas** las tareas terminen. Si el servidor cierra la conexión (y `listen_for_messages` termina), `gather` esperaría indefinidamente a que `read_and_send` también termine, lo que nunca ocurriría (es un bucle infinito). `asyncio.wait` con `FIRST_COMPLETED` retorna en cuanto cualquiera de las dos tareas termina, permitiendo salir limpiamente.

**15.** `deque(maxlen=n)` descarta **automáticamente** el elemento más antiguo cuando se supera el tamaño máximo, sin necesidad de código extra. Con una lista normal habría que gestionar manualmente el límite con `list.pop(0)` (que además es O(n)). `deque` garantiza que los mensajes no excedan la zona visible de la pantalla.

**16.** Con `tty.setcbreak`, el terminal no procesa líneas: los caracteres llegan al programa uno a uno sin el terminador `\n` que `readline()` necesita para saber cuándo parar. `read_line` lee byte a byte y para cuando encuentra `\n`, que es el comportamiento correcto en este modo.

**17.** `asyncio.wait_for(coro, timeout)` ejecuta **una única coroutine** con timeout; lanza `TimeoutError` si se supera. `asyncio.wait(tasks, return_when=...)` espera un **conjunto de tareas** y retorna cuando se cumple la condición (`FIRST_COMPLETED`, `FIRST_EXCEPTION`, o `ALL_COMPLETED`); devuelve dos conjuntos: tareas completadas y tareas pendientes.

**18.** `\033[H` (escape + `[H`). En las utilidades del Listing 8.7, esto se usa en `move_to_top_of_screen()` para posicionar el cursor donde empieza el área de mensajes del chat.

**19.** El servidor registra el error con `logging.error` y cierra la conexión inmediatamente (`writer.close()` + `await writer.wait_closed()`). No añade al usuario a `_username_to_writer`.

**20.** Porque asyncio usa **concurrencia cooperativa**: cuando una coroutine espera E/S (leer un mensaje, escribir una respuesta), cede el control al event loop con `await`. El event loop aprovecha ese momento para atender a otros clientes. Todo ocurre en un solo hilo de OS, pero múltiples operaciones de I/O progresan de forma intercalada.
