# Chapter 04 — gather, as_completed i wait amb Asyncio

> **Prerequisit**: Antes de leer esto, asegúrate de haber entendido el Chapter 03 (`explicacion_asyncio_echo.md`). Aquí asumimos que ya sabes qué son las corrutinas, el event loop, `asyncio.create_task()` y el cliente/servidor echo.

---

## ¿Qué se trabaja en este capítulo?

En el Chapter 03 aprendimos a lanzar tareas concurrentes con `asyncio.gather()` de forma básica. En este capítulo profundizamos en **tres formas distintas de coordinar múltiples tareas**:

| Herramienta | ¿Qué hace? | ¿Cancela en timeout? |
|---|---|---|
| `asyncio.gather()` | Espera TODAS, devuelve lista ordenada | Sí (propaga excepción o la captura con `return_exceptions`) |
| `asyncio.as_completed()` | Itera resultados en orden de finalización | Sí (lanza `TimeoutError` en el `await`) |
| `asyncio.wait()` | Devuelve conjuntos `done`/`pending` | **No** — el programador decide qué hacer |

---

## Contexto: el cliente echo de base (`echo_client_2.py`)

Partimos del cliente echo del Chapter 03. Recuerda su estructura:

```python
envia_t = asyncio.create_task(envia(loop, sock, missatge))
rep_t   = asyncio.create_task(rep(loop, sock, len(missatge)))
await asyncio.gather(envia_t, rep_t)
```

- `envia()`: espera 2 segundos, envía el mensaje al servidor.
- `rep()`: espera a recibir la respuesta del servidor (el eco).
- Ambas tareas corren concurrentemente: mientras `envia` duerme 2 segundos, `rep` ya está lista para recibir.

En los ejercicios de este capítulo añadimos un **segundo retardo de 2 segundos dentro de `envia`** (después de enviar), para que `envia` tarde 4 segundos en total y `rep` solo 2. Esto nos permite experimentar con timeouts entre los dos tiempos.

```
Tiempo:  0s       2s       4s
         |--------|--------|
envia:   [sleep1][envía][sleep2]   → acaba a 4s
rep:     [esperando eco  ]         → acaba a 2s (cuando recibe la respuesta)
timeout: --------|-----|            → 3s (entre 2s y 4s)
```

---

## `echo_client_3.py` — gather con wait_for y return_exceptions

### ¿Qué hace?

Usa `asyncio.gather()` para esperar las dos tareas concurrentemente, pero con dos variantes importantes respecto a la versión anterior:

1. **`rep()` devuelve datos**: la función `rep` ahora hace `return resultat`, así que `gather` puede incluir ese valor en su lista de resultados.
2. **`asyncio.wait_for(envia_t, 3)`**: aplica un timeout de 3 segundos solo a la tarea `envia`. Como `envia` necesita 4 segundos (2+2), expirará.
3. **`return_exceptions=True`**: en lugar de propagar la excepción `TimeoutError`, `gather` la captura y la devuelve como un elemento más de la lista.

### Código clave

```python
r = await asyncio.gather(
    asyncio.wait_for(envia_t, 3),   # timeout de 3s sobre envia
    rep_t,                           # rep sin timeout
    return_exceptions=True           # captura excepciones como resultados
)
print(f'Resultat de gather(envia, rep): {r}')
```

### ¿Qué imprime?

```
Resultat de gather(envia, rep): [TimeoutError(), 'Lluitem aquí, en el nostre temps, i espai petit,']
```

El resultado es siempre una **lista ordenada por posición de argumento**:
- `r[0]` → resultado de `wait_for(envia_t, 3)` → `TimeoutError()` (expiró)
- `r[1]` → resultado de `rep_t` → el string recibido del servidor

### ¿Por qué es útil gather?

> **Analogía**: Imagina que mandas a dos personas a hacer recados. Con `gather` esperas a que vuelvan los dos y te traen los resultados en orden (persona 1 primero, persona 2 después), aunque la persona 2 haya vuelto antes.

Sin `return_exceptions=True`, si una tarea falla, `gather` lanza la excepción inmediatamente y **no informa del resultado de las demás tareas**.

Con `return_exceptions=True`, todas las tareas completan (o expiran) y tienes el control total de qué salió bien y qué falló.

### Progresión del ejercicio (pasos intermedios)

| Paso | Modificación | Resultado de gather |
|---|---|---|
| 1 | gather básico, rep devuelve datos | `[None, 'missatge']` |
| 2 | envia tiene retard post-enviament (4s total) | `[None, 'missatge']` (gather espera 4s) |
| 3 | `wait_for(envia_t, 3)` sin `return_exceptions` | `TimeoutError` se propaga, crash |
| 4 | Añadir `return_exceptions=True` | `[TimeoutError(), 'missatge']` |

---

## `echo_client_4.py` — as_completed

### ¿Qué hace?

`asyncio.as_completed()` recibe una lista de awaitables y devuelve un **iterador de futures** que se resuelven **en orden de finalización** (el que termina primero, primero).

```python
for t in asyncio.as_completed([envia_t, rep_t], timeout=3):
    print(f'Resultat de {t}: {await t}')
```

### Diferencia clave con gather

Con `gather`, el orden de resultados sigue el orden de los argumentos. Con `as_completed`, el orden sigue el **tiempo de finalización real**.

> **Analogía**: Es como esperar en la cola de un supermercado. Con `gather` esperas a que todos los cajeros terminen y luego recoges los resultados en el orden que estaban en la cola. Con `as_completed`, vas recogiendo el resultado de cada cajero en cuanto termina, sea cual sea.

### ¿Qué imprime (con timeout=3)?

```
Resultat de <coroutine ...>: Lluitem aquí, en el nostre temps, i espai petit,   ← rep termina a 2s
... (a los 3s, envia no ha terminado aún) ...
TimeoutError    ← el segundo await lanza excepción
```

### Comportamiento con timeout

- `rep` termina a ~2s → primera iteración del for: `await t` devuelve el string.
- `envia` necesitaría 4s → segunda iteración: el timeout de 3s expira → `await t` lanza `TimeoutError`.

A diferencia de `gather` con `return_exceptions`, aquí la excepción **se lanza directamente** en el `await t`. Si quieres capturarla, necesitas un bloque `try/except` dentro del bucle.

### ¿Cuándo usar as_completed?

Cuando tienes tareas independientes y quieres **procesar cada resultado en cuanto esté disponible**, sin esperar a que terminen todas. Útil para búsquedas paralelas donde la primera respuesta válida es suficiente.

---

## `echo_client_5.py` — wait

### ¿Qué hace?

`asyncio.wait()` es la herramienta de más **bajo nivel y más control**. Devuelve dos conjuntos de tareas:

- `done`: tareas que han **terminado** (correctamente o con error) antes del timeout.
- `pending`: tareas que **no han terminado** cuando expiró el timeout.

```python
done, pending = await asyncio.wait([envia_t, rep_t], timeout=3)

print(f'Nombre de tasques acabades: {len(done)}')    # → 1
print(f'Nombre de tasques pendents: {len(pending)}')  # → 1

for t in done:
    print(f'Resultat de la tasca {t}: {t.result()}')

# Decisión explícita: cancelar las pendientes
for t in pending:
    t.cancel()
```

### Diferencia CRÍTICA respecto a gather y as_completed

> **`asyncio.wait` NO cancela las tareas pendientes cuando expira el timeout.**

Cuando el timeout expira, `wait` simplemente **retorna** con los conjuntos `done` y `pending`. Las tareas pendientes siguen ejecutándose en el event loop hasta que tú decidas qué hacer con ellas.

Tienes tres opciones:
1. **Cancelarlas**: `t.cancel()`
2. **Esperarlas**: volver a hacer `await asyncio.wait(pending)` sin timeout
3. **Ignorarlas**: dejarlas correr (mala práctica, pueden causar warnings)

### ¿Qué imprime (con timeout=3)?

```
Nombre de tasques acabades: 1
Nombre de tasques pendents: 1
Resultat de la tasca <Task finished ... rep() ... result='Lluitem...'>: Lluitem aquí, en el nostre temps, i espai petit,
```

### ¿Por qué los resultados de done no tienen orden?

`done` es un **conjunto** (`set`), no una lista. Los conjuntos no tienen orden garantizado. Si necesitas procesar los resultados en un orden específico, tendrás que ordenarlos tú mismo.

### ¿Cuándo usar wait?

Cuando necesitas **control total** sobre qué hacer con las tareas que no han terminado. Por ejemplo:
- En un servidor que quiere intentar reconectar las tareas pendientes antes de cancelarlas.
- En un sistema donde algunas tareas son opcionales y otras obligatorias.

---

## Comparación de las tres herramientas

```
┌─────────────────┬──────────────────────┬─────────────────────┬──────────────────────┐
│                 │    gather            │   as_completed      │       wait           │
├─────────────────┼──────────────────────┼─────────────────────┼──────────────────────┤
│ Retorna         │ Lista ordenada       │ Iterador de futures │ (done, pending)      │
│                 │ por argumento        │ por orden llegada   │ (conjuntos de tasks) │
├─────────────────┼──────────────────────┼─────────────────────┼──────────────────────┤
│ Orden resultats │ Igual que argumentos │ Orden finalización  │ Sin orden (set)      │
├─────────────────┼──────────────────────┼─────────────────────┼──────────────────────┤
│ Timeout         │ Via wait_for()       │ Paràmetre timeout   │ Paràmetre timeout    │
├─────────────────┼──────────────────────┼─────────────────────┼──────────────────────┤
│ Si hay timeout  │ Propaga excepció     │ Lanza TimeoutError  │ Retorna, NO cancel·la│
│                 │ (o return_exc=True)  │ en el await         │ les pendents         │
├─────────────────┼──────────────────────┼─────────────────────┼──────────────────────┤
│ Nivel control   │ Bajo (automático)    │ Medio               │ Alto (manual)        │
└─────────────────┴──────────────────────┴─────────────────────┴──────────────────────┘
```

---

## Descripción de cada fichero

### `util.py`
Mismo decorador `@async_timed()` del Chapter 03. Mide el tiempo de ejecución de cada corrutina e imprime mensajes de inicio y fin con el tiempo total. Se copia aquí para que los scripts del chapter_04 sean autónomos.

### `echo_client_2.py`
Punto de partida del capítulo. Idéntico al `echo_client_2.py` del Chapter 03. Versión instrumentada del cliente echo con `@async_timed()` y un retardo de 2 segundos en `envia()` para hacer visible la concurrencia.

### `echo_client_3.py`
**Objetivo**: experimentar con `asyncio.gather()` a fondo.

- `rep()` ahora **devuelve** el string recibido (antes solo lo imprimía).
- `envia()` tiene un segundo retardo de 2s después de enviar → total 4s.
- `asyncio.wait_for(envia_t, 3)` aplica un timeout de 3s a `envia` (entre 2s y 4s).
- `return_exceptions=True` en `gather` captura el `TimeoutError` como resultado.
- **Muestra**: cómo `gather` siempre preserva el orden de argumentos en su resultado, aunque las tareas terminen en orden diferente.

### `echo_client_4.py`
**Objetivo**: experimentar con `asyncio.as_completed()`.

- Misma lógica de delays que `echo_client_3.py`.
- Sustituye `gather` por un bucle `for t in asyncio.as_completed([...], timeout=3)`.
- **Muestra**: `rep` termina primero (~2s) y se procesa primero; `envia` no termina antes del timeout (3s) y lanza `TimeoutError` en el segundo `await t`.
- La diferencia clave con `gather`: los resultados llegan en **orden de finalización**, no de creación.

### `echo_client_5.py`
**Objetivo**: experimentar con `asyncio.wait()`.

- Misma lógica de delays que los anteriores.
- Sustituye el iterador de `as_completed` por `done, pending = await asyncio.wait([...], timeout=3)`.
- **Muestra**: cuando expira el timeout, `wait` retorna sin cancelar nada. `done` tiene las tareas acabadas, `pending` las que aún corren. El código cancela explícitamente las pendientes con `t.cancel()`.
- Diferencia clave: **el programador tiene control total** — puede inspeccionar, reintentar o cancelar cada tarea individualmente.

---

## Preguntas test por sección

### Sección gather (`echo_client_3.py`)

**1.** ¿Qué tipo devuelve `asyncio.gather()` cuando todas las tareas terminan correctamente?
- a) Un conjunto (set) con los resultados
- b) Una lista con los resultados en orden de finalización
- c) **Una lista con los resultados en el mismo orden que los argumentos** ✓
- d) Un diccionario tarea→resultado

**2.** Si `asyncio.gather(t1, t2)` se llama y `t2` termina antes que `t1`, ¿en qué posición aparece el resultado de `t2`?
- a) En la posición 0, porque terminó primero
- b) **En la posición 1, porque es el segundo argumento** ✓
- c) Depende del event loop
- d) `gather` no garantiza orden

**3.** Sin `return_exceptions=True`, si una tarea dentro de `gather` lanza una excepción, ¿qué ocurre?
- a) La excepción se ignora y `gather` devuelve los resultados de las otras tareas
- b) La excepción se almacena en la lista de resultados
- c) **La excepción se propaga inmediatamente y `gather` cancela las demás tareas** ✓
- d) `gather` espera a que todas terminen antes de lanzar la excepción

**4.** ¿Qué hace `asyncio.wait_for(coro, timeout=3)`?
- a) Pausa la corrutina 3 segundos antes de ejecutarla
- b) **Ejecuta la corrutina y lanza `TimeoutError` si no termina en 3 segundos** ✓
- c) Repite la corrutina hasta 3 veces si falla
- d) Limita el uso de CPU de la corrutina a 3 segundos

**5.** Con `return_exceptions=True` y timeout de 3s sobre `envia_t` (que tarda 4s), y `rep_t` (que tarda 2s), ¿cuál es el resultado de `gather`?
- a) `['missatge', TimeoutError()]`
- b) `[None, 'missatge']`
- c) **`[TimeoutError(), 'missatge']`** ✓
- d) `TimeoutError` se propaga igualmente

---

### Sección as_completed (`echo_client_4.py`)

**6.** ¿En qué orden `asyncio.as_completed()` entrega los resultados?
- a) En el orden en que se pasaron en la lista
- b) Aleatoriamente
- c) **En el orden en que las tareas van terminando** ✓
- d) Primero las que tienen error, luego las correctas

**7.** En el bucle `for t in asyncio.as_completed([envia_t, rep_t], timeout=3)`, si `rep_t` tarda 2s y `envia_t` tarda 4s con timeout=3, ¿qué ocurre en la segunda iteración?
- a) Se devuelve `None` porque `envia_t` no ha terminado
- b) El bucle termina silenciosamente
- c) Se espera indefinidamente hasta que `envia_t` termine
- d) **`await t` lanza `TimeoutError`** ✓

**8.** ¿Cuál es la principal diferencia de `as_completed` respecto a `gather`?
- a) `as_completed` es más rápido
- b) `as_completed` solo funciona con corrutinas, no con tareas
- c) **`as_completed` permite procesar cada resultado en cuanto está disponible, sin esperar a todos** ✓
- d) `as_completed` cancela automáticamente las tareas lentas

---

### Sección wait (`echo_client_5.py`)

**9.** ¿Qué ocurre con las tareas pendientes cuando `asyncio.wait()` expira su timeout?
- a) Se cancelan automáticamente
- b) Se reinician desde el principio
- c) Se convierten en corrutinas normales
- d) **Siguen ejecutándose; el programador decide qué hacer con ellas** ✓

**10.** ¿Por qué el conjunto `done` de `asyncio.wait()` no tiene un orden garantizado?
- a) Porque `asyncio.wait` es no determinista
- b) **Porque `done` es un `set` de Python, y los sets no preservan orden** ✓
- c) Porque el event loop aleatoriza el orden de finalización
- d) Porque las tareas pueden terminar en cualquier hilo

**11.** ¿Cuándo es preferible usar `asyncio.wait()` sobre `asyncio.gather()`?
- a) Cuando quieres que los resultados lleguen en orden de creación
- b) Cuando todas las tareas deben tener el mismo timeout
- c) **Cuando necesitas control manual sobre las tareas que no han terminado (reintentar, cancelar, esperar)** ✓
- d) `wait` es siempre preferible porque es más moderno

**12.** Si tienes 5 tareas y usas `asyncio.wait()` con `timeout=2`, y solo 3 terminan en 2 segundos, ¿qué contiene `pending`?
- a) Las 5 tareas (wait no modifica la lista original)
- b) Una excepción `TimeoutError`
- c) **Las 2 tareas que no terminaron a tiempo** ✓
- d) Las 3 tareas que sí terminaron (para que puedas reiniciarlas)

---

## Resumen visual del flujo de los tres clientes

```
Tiempo:  0s    1s    2s    3s    4s
         |-----|-----|-----|-----|
envia:   [sleep1   ][envía][sleep2]  → termina a 4s
rep:     [esperando eco   ]          → termina a 2s
timeout:              |              → 3s

gather:  espera hasta que TODAS terminan o hay excepción
         → a los 3s, wait_for(envia) lanza TimeoutError
         → con return_exceptions=True: [TimeoutError(), 'missatge']

as_completed: a los 2s, rep termina → procesa 'missatge'
              a los 3s, timeout → TimeoutError en el siguiente await

wait:    a los 3s retorna con done={rep_t}, pending={envia_t}
         → envia_t sigue corriendo hasta que se cancela
```
