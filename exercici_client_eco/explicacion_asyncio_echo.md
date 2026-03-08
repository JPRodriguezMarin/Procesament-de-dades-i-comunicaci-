# Clientes Echo con Asyncio — Explicación Completa

---

## 1. ¿Qué problema resuelve asyncio?

Imagina que tienes un servidor de chat. Cuando el usuario A escribe un mensaje, el servidor tiene que esperar a que lleguen los datos por la red. Durante esa espera, ¿puede atender al usuario B?

Con **programación tradicional (síncrona)**, no: el programa se bloquea esperando al usuario A y el usuario B tiene que esperar.

Con **asyncio**, el programa puede decir: *"mientras espero datos del usuario A, voy a hacer otras cosas"*. Esto se llama **programación asíncrona**.

> **Analogía**: Es como un camarero que atiende varias mesas. No se queda parado esperando que cocina prepare un plato — mientras espera, toma el pedido de otra mesa.

---

## 2. Conceptos fundamentales de Python que necesitas

### 2.1 Funciones normales vs corrutinas

Una **función normal** en Python:
```python
def saludar():
    return "Hola"
```

Una **corrutina** en Python (con `async def`):
```python
async def saludar():
    return "Hola"
```

La diferencia clave: una corrutina puede **pausarse** en medio de su ejecución con `await` y ceder el control a otras corrutinas. Una función normal no puede hacer eso.

### 2.2 La palabra clave `await`

`await` solo se puede usar dentro de una corrutina (`async def`). Significa:
> *"Espera a que esto termine, pero mientras esperas, deja que otras corrutinas corran."*

```python
async def ejemplo():
    await asyncio.sleep(2)  # Pausa 2 segundos, pero el programa no se bloquea
    print("Han pasado 2 segundos")
```

Sin `await`, el programa se bloquea completamente. Con `await`, el event loop puede ejecutar otras tareas durante la espera.

---

## 3. El Event Loop (Bucle de Eventos)

El **event loop** es el corazón de asyncio. Es un bucle infinito que:

1. Mira qué tareas están listas para ejecutarse
2. Ejecuta una tarea hasta que encuentra un `await`
3. Guarda el estado de esa tarea y pasa a la siguiente
4. Cuando la operación de espera termina (datos de red, timer, etc.), reanuda la tarea

```
Event Loop:
┌─────────────────────────────────────────┐
│  1. Tarea A empieza                      │
│  2. Tarea A llega a await → se pausa    │
│  3. Tarea B empieza                      │
│  4. Tarea B llega a await → se pausa    │
│  5. Tarea A está lista → reanuda        │
│  6. ... y así indefinidamente            │
└─────────────────────────────────────────┘
```

> **Importante**: El event loop es **monohilo** (single-thread). No corre varias cosas a la vez literalmente, sino que alterna entre tareas tan rápido que parece simultáneo. Esto es **concurrencia**, no paralelismo.

`asyncio.run(main())` crea el event loop, ejecuta la corrutina `main()` y lo cierra al terminar.

---

## 4. Sockets — ¿Qué son?

Un **socket** es un punto de comunicación entre dos programas a través de la red (o en la misma máquina). Es como un "enchufe" al que conectas dos extremos para que se comuniquen.

Para comunicación TCP:
- Uno actúa como **servidor**: escucha conexiones entrantes (`bind` + `listen` + `accept`)
- Otro actúa como **cliente**: se conecta al servidor (`connect`)

Un socket **bloqueante** (el modo por defecto) pausa el programa mientras espera. Un socket **no bloqueante** devuelve el control inmediatamente aunque no haya datos.

asyncio necesita sockets **no bloqueantes**: `sock.setblocking(False)`.

---

## 5. API de bajo nivel de asyncio para sockets

En vez de la API de alto nivel (`asyncio.open_connection()`), este ejercicio usa la **API de bajo nivel**, que trabaja directamente con sockets del sistema operativo:

| Función | Qué hace |
|---|---|
| `loop.sock_connect(sock, addr)` | Conecta el socket a la dirección |
| `loop.sock_sendall(sock, data)` | Envía todos los datos |
| `loop.sock_recv(sock, nbytes)` | Recibe hasta `nbytes` bytes |
| `loop.sock_accept(server_sock)` | Acepta una conexión entrante |

Todas son **awaitables**: al hacer `await loop.sock_recv(...)`, el event loop puede ejecutar otras tareas mientras espera datos de la red.

---

## 6. Tasks — ¿Qué son y para qué sirven?

Una **Task** es una corrutina envuelta para que el event loop pueda ejecutarla de forma independiente (como un "hilo ligero").

```python
task = asyncio.create_task(mi_corrutina())
```

Al crear una Task, el event loop la registra y empieza a ejecutarla en cuanto pueda (es decir, cuando la corrutina actual llega a un `await`).

### `asyncio.gather()`

```python
await asyncio.gather(task1, task2)
```

Espera a que **todas** las tasks terminen, pero las ejecuta **concurrentemente**. Si task1 se pausa (por un `await`), task2 avanza, y viceversa.

> **Diferencia crucial**:
> - `await tarea1` + `await tarea2` → secuencial (tarea2 espera a que tarea1 termine)
> - `asyncio.gather(tarea1, tarea2)` → concurrente (corren "a la vez")

---

## 7. El decorador `async_timed` — Explicación paso a paso

```python
def async_timed():                          # Función exterior
    def wrapper(func):                      # Recibe la función a decorar
        @functools.wraps(func)
        async def wrapped(*args, **kwargs): # La función envuelta
            print(f'starting {func}...')
            start = time.time()
            try:
                return await func(*args, **kwargs)  # Ejecuta la función original
            finally:
                total = time.time() - start
                print(f'finished {func} in {total:.4f} second(s)')
        return wrapped
    return wrapper
```

**¿Cómo funciona un decorador?**

Un decorador es una función que *envuelve* otra función para añadirle comportamiento extra sin modificar su código.

```python
@async_timed()
async def envia(...):
    ...
```

Es equivalente a escribir:
```python
async def envia(...):
    ...
envia = async_timed()(envia)
```

El `@functools.wraps(func)` preserva el nombre y docstring de la función original.

**¿Por qué `async_timed()` y no `@async_timed`?**
Porque `async_timed` es una función que *retorna* el decorador (`wrapper`). Los paréntesis `()` la ejecutan para obtener el decorador real.

---

## 8. El servidor de eco (`listing_3_10.py`)

### ¿Qué significa "eco"?

Un **servidor de eco** es el programa más sencillo que existe en comunicación de red: recibe lo que le envías y te lo devuelve exactamente igual, sin modificarlo.

Es como gritar en una cueva y escuchar tu propia voz de vuelta. No hace nada útil con los datos — simplemente los refleja.

Se usa como ejercicio de aprendizaje porque permite verificar que la comunicación entre cliente y servidor funciona correctamente: si recibes lo mismo que enviaste, el canal de comunicación está bien establecido. En este ejercicio, lo que importa no es lo que hace el servidor, sino cómo el cliente maneja el envío y la recepción de forma concurrente.

---

### Código completo del servidor con explicación línea a línea

```python
import asyncio      # Librería para programación asíncrona en Python
import socket       # Librería para trabajar con sockets de red
```

```python
async def echo(connection: socket.socket, loop: asyncio.AbstractEventLoop) -> None:
```
- `async def` → es una corrutina (puede pausarse con `await`)
- `connection` → el socket que representa la conexión con UN cliente concreto
- `loop` → referencia al event loop, necesaria para usar `loop.sock_*`

```python
    try:
        while data := await loop.sock_recv(connection, 1024):
            await loop.sock_sendall(connection, data)
```

Esta es la línea más densa del servidor. Vamos parte a parte:

- `loop.sock_recv(connection, 1024)` → intenta recibir hasta 1024 bytes del cliente. Es un `await`, así que el event loop puede hacer otras cosas mientras espera que lleguen datos.
- `:=` → el **operador walrus** (llamado así porque parece unos ojos y colmillos de morsa). Hace DOS cosas a la vez: asigna el resultado a `data` Y lo evalúa como condición del `while`.

  Sin el operador walrus, habría que escribirlo así (más largo):
  ```python
  data = await loop.sock_recv(connection, 1024)
  while data:
      await loop.sock_sendall(connection, data)
      data = await loop.sock_recv(connection, 1024)
  ```

  Con el operador walrus, se compacta en un solo `while` elegante.

- ¿Cuándo termina el bucle? Cuando el cliente cierra la conexión. En ese momento, `sock_recv` devuelve `b""` (una cadena de bytes vacía). En Python, una cadena vacía es `False`, así que el `while` termina.

- `loop.sock_sendall(connection, data)` → envía todos los bytes recibidos de vuelta al cliente. Aquí es donde el servidor "hace eco": devuelve exactamente lo que recibió.

```python
    except ConnectionResetError:
        pass
```
- En Windows, cuando el cliente cierra la conexión abruptamente, el sistema operativo lanza `ConnectionResetError` en vez de devolver `b""`. Capturamos el error y no hacemos nada (`pass`), porque es un cierre normal.

```python
    finally:
        connection.close()
```
- `finally` se ejecuta siempre, haya error o no. Cerramos el socket para liberar recursos del sistema operativo. Si no lo hiciéramos, cada conexión dejaría un socket "abierto" que consume memoria.

---

```python
async def listen_for_connections(server_socket: socket.socket, loop: asyncio.AbstractEventLoop):
    while True:                                                    # Bucle infinito: el servidor nunca para
        connection, address = await loop.sock_accept(server_socket)  # Espera a que alguien se conecte
        connection.setblocking(False)                              # Lo hace no bloqueante (necesario para asyncio)
        print(f"Got a connection from {address}")                  # Imprime la IP y puerto del cliente
        asyncio.ensure_future(echo(connection, loop))              # Lanza echo() sin esperar que termine
```

**¿Por qué `asyncio.ensure_future()` y no `await echo(...)`?**

Imagina que usáramos `await`:
```python
# MAL — con await:
while True:
    connection, address = await loop.sock_accept(server_socket)
    await echo(connection, loop)   # ← el servidor se QUEDA AQUÍ hasta que el cliente se desconecte
    # Solo entonces vuelve al accept para aceptar otro cliente
```
Con `await echo(...)`, el servidor atendería a UN cliente y no aceptaría a nadie más hasta que ese cliente terminara. Si tienes 3 clientes, el segundo y el tercero tendrían que esperar en cola.

Con `asyncio.ensure_future()`:
```python
# BIEN — con ensure_future:
while True:
    connection, address = await loop.sock_accept(server_socket)
    asyncio.ensure_future(echo(connection, loop))  # ← registra echo() como tarea y SIGUE ADELANTE
    # Vuelve inmediatamente al accept para aceptar el siguiente cliente
```
`ensure_future()` dice al event loop: *"ejecuta `echo()` cuando puedas, pero no me hagas esperar"*. Así el servidor vuelve inmediatamente al `await sock_accept()` para atender al siguiente cliente, mientras `echo()` corre como tarea independiente en segundo plano.

**Flujo completo del servidor:**
```
main() → crea socket → listen_for_connections()
    → await sock_accept() ... cliente A se conecta
    → ensure_future(echo(A))   → echo(A) queda registrado como tarea
    → await sock_accept() ... cliente B se conecta
    → ensure_future(echo(B))   → echo(B) queda registrado como tarea
    → await sock_accept() ... cliente C se conecta
    → ensure_future(echo(C))   → echo(C) queda registrado como tarea
    → ...

El event loop ejecuta echo(A), echo(B), echo(C) de forma concurrente
mientras listen_for_connections() sigue aceptando nuevas conexiones
```

---

## 9. Los tres clientes — Análisis comparativo

Los tres clientes hacen esencialmente lo mismo: conectarse al servidor de eco, enviar un mensaje y recibir la respuesta. La diferencia entre ellos es pedagógica: cada uno añade una capa para demostrar un concepto diferente sobre la concurrencia.

---

### `echo_client_0.py` — Propósito: establecer la base

**¿Para qué existe este cliente?**

Este primer cliente establece la estructura base: dos corrutinas (`envia` y `rep`) ejecutándose como Tasks con `asyncio.gather()`. El objetivo es mostrar la arquitectura correcta de un cliente asíncrono. Sin embargo, tiene un "problema" de visibilidad: el envío ocurre tan rápido que no podemos ver a simple vista si realmente hay concurrencia o si todo es secuencial.

**Código con explicación línea a línea:**

```python
import asyncio   # Librería para programación asíncrona
import socket    # Librería para sockets de red
import sys       # Para acceder a los argumentos de línea de comandos (sys.argv)
```

```python
async def envia(loop, sock, missatge):
    # Corrutina que gestiona el ENVÍO de datos al servidor
```
```python
    print(f'A punt d\'enviar: {missatge}')
    # Avisa por pantalla de que está a punto de enviar
```
```python
    await loop.sock_sendall(sock, missatge.encode())
    # .encode() convierte el texto (str) a bytes, porque los sockets solo trabajan con bytes
    # await → cede el control al event loop mientras el sistema operativo envía los datos
    # sock_sendall garantiza que se envían TODOS los bytes, no solo una parte
```
```python
    print(f'Enviat: {missatge}')
    # Confirma que los datos se han enviado correctamente
```

```python
async def rep(loop, sock, nbytes):
    # Corrutina que gestiona la RECEPCIÓN de datos del servidor
```
```python
    print('A punt per rebre')
    # Avisa que está esperando recibir datos
```
```python
    dades = await loop.sock_recv(sock, nbytes)
    # Espera recibir exactamente nbytes bytes del servidor
    # await → se pausa aquí hasta que lleguen datos, cediendo el control al event loop
    # nbytes = len(missatge) → sabemos cuántos bytes esperar porque el eco devuelve lo mismo
```
```python
    resultat = dades.decode()
    # .decode() convierte los bytes recibidos de vuelta a texto legible (str)
```
```python
    print(f'Rebut: {resultat}')
    # Muestra los datos recibidos por pantalla
    return resultat
```

```python
async def main():
```
```python
    missatge = ' '.join(sys.argv[1:])
    # sys.argv es la lista de argumentos pasados al script
    # sys.argv[0] es el nombre del script, sys.argv[1:] son los argumentos del usuario
    # ' '.join(...) une todos los argumentos con espacios
    # Ejemplo: python echo_client_0.py Lluitem aquí → missatge = "Lluitem aquí"
```
```python
    loop = asyncio.get_event_loop()
    # Obtiene la referencia al event loop activo (el que gestiona las corrutinas)
    # Necesitamos esta referencia para pasarla a las funciones loop.sock_*
```
```python
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Crea un socket TCP:
    # AF_INET → familia de direcciones IPv4 (direcciones como 192.168.x.x)
    # SOCK_STREAM → tipo TCP (conexión fiable, con confirmación de entrega)
```
```python
    sock.setblocking(False)
    # Configura el socket como NO bloqueante
    # Sin esto, las operaciones de red pararían el event loop entero
```
```python
    await loop.sock_connect(sock, ('127.0.0.1', 8000))
    # Conecta el socket al servidor en la dirección 127.0.0.1 (localhost) puerto 8000
    # 127.0.0.1 significa "esta misma máquina"
    # await → espera a que se establezca la conexión TCP
```
```python
    task_envia = asyncio.create_task(envia(loop, sock, missatge))
    # Crea una Task para la corrutina envia()
    # La Task queda registrada en el event loop pero NO empieza aún
```
```python
    task_rep = asyncio.create_task(rep(loop, sock, len(missatge)))
    # Crea una Task para la corrutina rep()
    # len(missatge) → número de bytes a esperar (el eco devuelve exactamente los mismos bytes)
```
```python
    await asyncio.gather(task_envia, task_rep)
    # Espera a que AMBAS tasks terminen, ejecutándolas concurrentemente
    # El event loop alterna entre task_envia y task_rep cada vez que alguna llega a un await
```
```python
    sock.close()
    # Cierra el socket y libera los recursos de red
```

**Salida típica:**
```
A punt d'enviar: Lluitem aquí en el nostre temps
Enviat: Lluitem aquí en el nostre temps
A punt per rebre
Rebut: Lluitem aquí en el nostre temps
```

**¿Por qué no se ve claramente la concurrencia?**

El envío por red local es tan rápido (microsegundos) que `envia()` termina completamente antes de que el event loop tenga tiempo de ceder el control a `rep()`. La concurrencia existe, pero no es observable. Este cliente nos sirve de base para el siguiente.

---

### `echo_client_1.py` — Propósito: hacer visible la concurrencia

**¿Para qué existe este cliente?**

El problema del cliente anterior es que la concurrencia ocurre pero no podemos verla. Este cliente añade `await asyncio.sleep(2)` dentro de `envia()` para forzar una pausa artificial de 2 segundos. Esa pausa obliga al event loop a ejecutar `rep()` mientras `envia()` duerme, haciendo que el orden de los mensajes en pantalla demuestre visualmente que ambas corrutinas corren a la vez.

**Código con explicación línea a línea:**

Las importaciones y la función `rep()` son idénticas a `echo_client_0.py`. Solo cambia `envia()` y, en consecuencia, el comportamiento observable.

```python
async def envia(loop, sock, missatge):
```
```python
    print('Afegim un retard a l\'enviament')
    # Informa que se va a añadir un retardo artificial antes de enviar
    # La barra invertida (\') escapa el apóstrofe dentro de las comillas simples
```
```python
    await asyncio.sleep(2)
    # PAUSA ARTIFICIAL de 2 segundos
    # Punto clave: await cede el control al event loop
    # El event loop aprovecha para ejecutar rep(), que estaba esperando su turno
    # asyncio.sleep() NO bloquea el hilo — es una pausa asíncrona
    # Si fuera time.sleep(2), SÍ bloquearía el hilo entero y rep() no podría avanzar
```
```python
    print(f'A punt d\'enviar: {missatge}')
    # Este mensaje aparece DESPUÉS de los 2 segundos
    # y DESPUÉS del "A punt per rebre" de rep() — ahí está la prueba de concurrencia
```
```python
    await loop.sock_sendall(sock, missatge.encode())
    # Ahora sí se envían los datos al servidor
```
```python
    print(f'Enviat: {missatge}')
    # Confirmación de envío
```

**El resto del código (`rep()` y `main()`) es idéntico a `echo_client_0.py`.**

**Salida y explicación momento a momento:**
```
Afegim un retard a l'enviament    ← [t=0.000s] envia() empieza, imprime esto y llega a await sleep(2)
                                   ← el event loop ve que envia() está dormida → cede a rep()
A punt per rebre                   ← [t=0.001s] rep() avanza, imprime esto y llega a await sock_recv()
                                   ← rep() se pausa (no hay datos aún, envia() no ha enviado)
                                   ← (silencio durante ~2 segundos)
A punt d'enviar: Lluitem...        ← [t=2.001s] el sleep de envia() termina, reanuda y avanza
Enviat: Lluitem...                 ← [t=2.002s] envia() manda datos al servidor
Rebut: Lluitem...                  ← [t=2.003s] el servidor responde, rep() recibe y muestra
```

**¿Por qué esto demuestra concurrencia?**

"A punt per rebre" aparece ANTES que "A punt d'enviar". Esto significa que `rep()` empezó a ejecutarse ANTES de que `envia()` terminara. Si fueran secuenciales, `rep()` no hubiera podido imprimir nada hasta que `envia()` completara. El sleep forzó una situación donde la alternancia entre tareas es inconfundible.

---

### `echo_client_2.py` — Propósito: medir y probar la concurrencia con números

**¿Para qué existe este cliente?**

El cliente anterior demuestra visualmente la concurrencia por el orden de los mensajes. Este cliente va un paso más allá: usa el decorador `@async_timed()` para medir cuánto tarda cada función y comprobarlo numéricamente. Si `envia()` tarda 2s, `rep()` tarda 2s, pero `main()` también tarda ~2s (no ~4s), los números prueban matemáticamente que las dos tareas corrieron solapadas.

**Código con explicación línea a línea:**

```python
import asyncio
import socket
import sys
from util import async_timed   # Importa el decorador desde nuestro archivo util.py
```

```python
@async_timed()
async def envia(loop, sock, missatge):
    # @async_timed() envuelve envia() para que imprima cuándo empieza y cuánto tarda
    # El decorador se activa automáticamente al llamar a envia()
    # El código interior es exactamente igual que en echo_client_1.py
    print('Afegim un retard a l\'enviament')
    await asyncio.sleep(2)
    print(f'A punt d\'enviar: {missatge}')
    await loop.sock_sendall(sock, missatge.encode())
    print(f'Enviat: {missatge}')
```

```python
@async_timed()
async def rep(loop, sock, nbytes):
    # También decorada: sabremos cuándo empieza y cuánto tarda
    # rep() tarda ~2s porque espera que envia() mande datos (que tarda 2s por el sleep)
    print('A punt per rebre')
    dades = await loop.sock_recv(sock, nbytes)
    resultat = dades.decode()
    print(f'Rebut: {resultat}')
    return resultat
```

```python
@async_timed()
async def main():
    # También decorada: aquí está la clave del experimento
    # Si envia() tarda 2s y rep() tarda 2s en SECUENCIAL → main() tardaría 4s
    # Si envia() tarda 2s y rep() tarda 2s en CONCURRENTE → main() tarda ~2s
    missatge = ' '.join(sys.argv[1:])
    loop = asyncio.get_event_loop()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    await loop.sock_connect(sock, ('127.0.0.1', 8000))

    task_envia = asyncio.create_task(envia(loop, sock, missatge))
    # Crea la task de envia() — el decorador @async_timed() imprimirá "starting envia..."
```
```python
    task_rep = asyncio.create_task(rep(loop, sock, len(missatge)))
    # Crea la task de rep() — el decorador imprimirá "starting rep..."
    # Ambas tasks quedan registradas pero el event loop aún no las ha ejecutado
```
```python
    await asyncio.gather(task_envia, task_rep)
    # Aquí es donde el event loop empieza a alternar entre task_envia y task_rep
    # Al terminar cada una, @async_timed() imprime "finished ... in X second(s)"
```
```python
    sock.close()
```

**Salida típica completa:**
```
starting <function main> with args () {}           ← main() comienza, @async_timed registra t=0
starting <function envia> with args (...)          ← task_envia empieza
Afegim un retard a l'enviament                    ← envia() imprime y llega a sleep(2)
starting <function rep> with args (...)            ← event loop cede a rep(), que empieza
A punt per rebre                                   ← rep() avanza hasta sock_recv() y espera
                                                   ← (silencio ~2 segundos)
A punt d'enviar: Lluitem aquí en el nostre temps  ← envia() reanuda tras el sleep
Enviat: Lluitem aquí en el nostre temps           ← envia() envía datos al servidor
Rebut: Lluitem aquí en el nostre temps            ← rep() recibe la respuesta
finished <function rep> in 2.0031 second(s)        ← rep() terminó: tardó ~2s
finished <function envia> in 2.0035 second(s)      ← envia() terminó: tardó ~2s
finished <function main> in 2.0038 second(s)       ← main() terminó: también ~2s (¡no 4s!)
```

**La prueba definitiva de concurrencia:**

| Función | Tiempo medido | ¿Qué significa? |
|---|---|---|
| `envia()` | ~2.003s | Durmió 2s + envió datos |
| `rep()` | ~2.003s | Esperó 2s a que llegaran datos |
| `main()` | ~2.004s | Esperó a ambas concurrentemente |

Si `envia()` y `rep()` se ejecutaran **en secuencia**, `main()` tardaría `2 + 2 = 4 segundos`. Como `main()` tarda **~2 segundos**, la demostración es matemática: ambas tareas corrieron solapadas en el tiempo.

---

## 10. Resumen visual del flujo de concurrencia

```
Tiempo →  0s          1s          2s          2.003s
─────────────────────────────────────────────────────
envia():  [sleep(2)........................][send][done]
rep():    [waiting sock_recv....................][recv][done]
main():   [gather esperando ambas tasks..............][done]
```

Ambas tareas empiezan casi simultáneamente. `main()` termina cuando termina la última de las dos.

---

## 11. Diferencia Windows vs Linux (nota técnica)

En **Linux/Mac**, asyncio usa `SelectorEventLoop`. Cuando el cliente cierra la conexión, el servidor recibe `b""` y el bucle `while` termina limpiamente.

En **Windows**, asyncio usa `ProactorEventLoop`. Cuando el cliente cierra la conexión, en vez de `b""`, lanza una excepción `ConnectionResetError`. Por eso el servidor necesita el `try/except ConnectionResetError`.

---

## 12. Glosario rápido

| Término | Significado |
|---|---|
| **Corrutina** | Función definida con `async def` que puede pausarse con `await` |
| **Event loop** | Bucle que gestiona y alterna la ejecución de corrutinas |
| **Task** | Corrutina registrada en el event loop para ejecutarse independientemente |
| **`await`** | Pausa la corrutina actual y cede control al event loop |
| **Concurrencia** | Varias tareas progresan "a la vez" (alternando, no en paralelo real) |
| **Paralelismo** | Varias tareas ejecutadas físicamente al mismo tiempo (múltiples CPUs) |
| **Socket** | Canal de comunicación entre dos programas a través de la red |
| **Eco** | El servidor devuelve exactamente lo que recibe |
| **Decorador** | Función que envuelve otra función para añadir comportamiento extra |
| **API de bajo nivel** | `loop.sock_*`: control directo sobre sockets, más explícito que `open_connection()` |

---

---

# Test de Autoevaluación — 10 Preguntas

---

**Pregunta 1**

¿Cuál es la diferencia principal entre una función normal (`def`) y una corrutina (`async def`) en Python?

- A) Las corrutinas son más rápidas que las funciones normales
- B) Las corrutinas pueden pausarse con `await` y ceder el control al event loop; las funciones normales no pueden
- C) Las corrutinas solo funcionan con sockets de red
- D) No hay diferencia funcional, solo es una cuestión de estilo

**Respuesta correcta: B**

> Una corrutina puede suspender su ejecución en un punto `await`, permitiendo que el event loop ejecute otras tareas mientras espera. Una función normal bloquea el hilo completamente hasta que termina.

---

**Pregunta 2**

En `echo_client_1.py`, la salida muestra "A punt per rebre" ANTES de "A punt d'enviar". ¿Por qué ocurre esto?

- A) Hay un error en el orden del código
- B) `rep()` siempre se ejecuta antes que `envia()` porque fue la segunda task creada
- C) `envia()` llega a `await asyncio.sleep(2)` y cede el control al event loop, que entonces ejecuta `rep()` hasta que esta también se pausa
- D) El servidor procesa las peticiones en orden inverso

**Respuesta correcta: C**

> `await asyncio.sleep(2)` pausa `envia()` y el event loop tiene oportunidad de avanzar `rep()`. Esta imprime "A punt per rebre" y luego se pausa en `await loop.sock_recv()` esperando datos que aún no han llegado.

---

**Pregunta 3**

En `echo_client_2.py`, si `envia()` tarda ~2s y `rep()` tarda ~2s, pero `main()` tarda ~2s en total (no ~4s), ¿qué demuestra esto?

- A) Que el decorador `async_timed` no mide bien el tiempo
- B) Que `envia()` y `rep()` se ejecutaron concurrentemente, no secuencialmente
- C) Que el servidor es muy rápido y redujo el tiempo
- D) Que Python ejecuta automáticamente todo en paralelo

**Respuesta correcta: B**

> Si fueran secuenciales, el tiempo total sería la suma (~4s). Como el tiempo total es ~2s, ambas tareas corrieron solapadas en el tiempo gracias a `asyncio.gather()`.

---

**Pregunta 4**

¿Cuál es la función de `asyncio.create_task()`?

- A) Ejecuta inmediatamente una corrutina de forma síncrona
- B) Registra una corrutina en el event loop para que se ejecute de forma independiente como una Task
- C) Crea un nuevo hilo del sistema operativo para la corrutina
- D) Pausa la ejecución hasta que la corrutina termine

**Respuesta correcta: B**

> `create_task()` envuelve la corrutina en un objeto Task y la registra en el event loop. La Task empieza a ejecutarse la próxima vez que el event loop tiene control (cuando la corrutina actual llega a un `await`).

---

**Pregunta 5**

¿Por qué es necesario llamar a `sock.setblocking(False)` antes de usar los métodos `loop.sock_*`?

- A) Para hacer el socket más rápido
- B) Para que el socket funcione en Windows
- C) Porque asyncio necesita sockets no bloqueantes: si el socket bloqueara, congelaría el event loop completo impidiendo la concurrencia
- D) Para reducir el uso de memoria

**Respuesta correcta: C**

> El event loop es monohilo. Si un socket bloqueante esperara datos, bloquearía el único hilo, y ninguna otra corrutina podría avanzar. Con sockets no bloqueantes, la operación retorna inmediatamente si no hay datos, y el event loop puede gestionar otras tareas mientras espera.

---

**Pregunta 6**

¿Cuál es la diferencia entre ejecutar dos corrutinas con `await` secuencial vs `asyncio.gather()`?

```python
# Opción A:
await envia(...)
await rep(...)

# Opción B:
await asyncio.gather(envia(...), rep(...))
```

- A) No hay diferencia, ambas opciones son equivalentes
- B) La opción A ejecuta las dos concurrentemente; la opción B las ejecuta una tras otra
- C) La opción A ejecuta `rep()` solo cuando `envia()` ha terminado completamente; la opción B las ejecuta concurrentemente
- D) La opción B siempre es más lenta porque crea overhead adicional

**Respuesta correcta: C**

> Con `await` secuencial, `rep()` no empieza hasta que `envia()` termina completamente. Con `asyncio.gather()`, ambas corrutinas se crean como Tasks y el event loop las alterna, permitiendo concurrencia real.

---

**Pregunta 7**

En el servidor (`listing_3_10.py`), ¿por qué se usa `asyncio.ensure_future(echo(connection, loop))` en lugar de `await echo(connection, loop)`?

- A) `await` no funciona dentro de bucles `while`
- B) `await` bloquearía el servidor esperando que el cliente actual termine, impidiendo aceptar nuevas conexiones
- C) `asyncio.ensure_future()` es más eficiente en memoria
- D) `await` no puede recibir sockets como argumento

**Respuesta correcta: B**

> Si el servidor hiciera `await echo(connection, loop)`, se quedaría esperando hasta que ese cliente se desconectara antes de volver al bucle y aceptar otro cliente. Con `ensure_future()`, lanza `echo()` como tarea independiente y vuelve inmediatamente al `await loop.sock_accept()` para aceptar el siguiente cliente.

---

**Pregunta 8**

¿Qué hace el operador walrus (`:=`) en esta línea del servidor?

```python
while data := await loop.sock_recv(connection, 1024):
```

- A) Es un operador de comparación que verifica si `data` es igual a `loop.sock_recv`
- B) Asigna el resultado de `sock_recv` a `data` y evalúa si es verdadero (no vacío) en una sola expresión
- C) Declara `data` como variable de tipo bytes
- D) Envía datos al cliente y los almacena en `data`

**Respuesta correcta: B**

> El operador walrus (`:=`) asigna y evalúa en una sola expresión. Si el cliente se desconecta, `sock_recv` devuelve `b""` (bytes vacíos), que es falso, y el bucle termina. Es equivalente a: `data = await loop.sock_recv(...); while data: ...`

---

**Pregunta 9**

¿Qué demuestra específicamente la comparación entre los tiempos de `echo_client_0.py` (sin sleep) y `echo_client_1.py` (con sleep de 2s)?

- A) Que añadir retardos hace los programas más eficientes
- B) Que `asyncio.sleep()` es más preciso que `time.sleep()`
- C) Que `echo_client_1.py` demuestra visualmente la concurrencia porque el sleep fuerza al event loop a ejecutar `rep()` mientras `envia()` espera, algo que en `echo_client_0.py` ocurre pero no es visible porque el envío es casi instantáneo
- D) Que el servidor procesa más rápido las peticiones sin retardo

**Respuesta correcta: C**

> En `echo_client_0.py`, `envia()` es tan rápida que termina antes de que la concurrencia sea observable. El `sleep(2)` en `echo_client_1.py` fuerza una pausa artificial que hace que el event loop ejecute `rep()` visiblemente antes de que `envia()` continúe, demostrando de forma clara el mecanismo de concurrencia.

---

**Pregunta 10**

¿Por qué el servidor en Windows necesita capturar `ConnectionResetError` pero en Linux no?

- A) Windows usa una versión más antigua de Python que no soporta sockets no bloqueantes
- B) En Windows, asyncio usa `ProactorEventLoop` que lanza `ConnectionResetError` cuando el cliente cierra la conexión, mientras que en Linux el `SelectorEventLoop` simplemente devuelve `b""` (bytes vacíos)
- C) Windows tiene un firewall que interrumpe las conexiones abruptamente
- D) El cliente en Windows envía una señal de error explícita al cerrar el socket

**Respuesta correcta: B**

> Es una diferencia de implementación del event loop: `ProactorEventLoop` (Windows) y `SelectorEventLoop` (Linux/Mac) manejan el cierre de conexión de forma distinta a nivel interno. El comportamiento correcto requiere adaptar el código al sistema operativo.

---

*Fin del documento — Procesamiento de Datos y Comunicación, Q5*
