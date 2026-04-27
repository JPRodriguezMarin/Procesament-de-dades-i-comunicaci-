# =============================================================================
# listing_10_11.py — CircuitBreaker Class
# =============================================================================
# Objetivo:
#   Implementa el patrón Circuit Breaker (interruptor de circuito),
#   un mecanismo de resiliencia para proteger llamadas a servicios
#   externos que pueden fallar o tardar demasiado.
#
#   Problema que resuelve: si un microservicio empieza a fallar, seguir
#   enviándole peticiones desperdicia tiempo (esperando el timeout) y
#   recursos (conexiones abiertas). El circuit breaker detecta los fallos
#   acumulados y "abre el circuito": a partir de ese momento, falla
#   inmediatamente (fail fast) sin ni siquiera intentar la petición,
#   dando tiempo al servicio a recuperarse.
#
#   Tres conceptos de tiempo que gestiona la clase:
#     - timeout:        límite por petición individual (via asyncio.wait_for)
#     - time_window:    ventana en la que se acumulan los fallos; si el
#                       primer fallo fue hace más de time_window segundos,
#                       los fallos anteriores ya no cuentan
#     - reset_interval: tiempo que espera el circuito abierto antes de
#                       intentar cerrarse con una petición de prueba
#
#   Dos clases exportadas:
#     - CircuitOpenException: excepción que indica circuito abierto
#     - CircuitBreaker: clase principal con métodos request() y _do_request()
#
#   Usado en listing_10_12.py para demostrar su comportamiento.
# =============================================================================

import asyncio                          # Proporciona wait_for() para aplicar timeout a cada petición
from datetime import datetime, timedelta  # Usados para calcular si han pasado los intervalos de tiempo


class CircuitOpenException(Exception):  # Excepción personalizada que se lanza cuando el circuito está abierto
    pass


class CircuitBreaker:
    def __init__(self, callback, timeout: float, time_window: float,
                 max_failures: int, reset_interval: float):
        self.callback = callback               # Corutina que se ejecutará en cada petición
        self.timeout = timeout                 # Segundos máximos que puede tardar cada llamada al callback
        self.time_window = time_window         # Ventana de tiempo (s) en la que se acumulan los fallos
        self.max_failures = max_failures       # Número de fallos necesarios para abrir el circuito
        self.reset_interval = reset_interval   # Segundos que debe esperar el circuito abierto antes de intentar cerrarse
        self.last_request_time = None          # Momento de la última petición real (actualizado en _do_request)
        self.last_failure_time = None          # Momento del primer fallo dentro de la ventana actual
        self.current_failures = 0              # Contador de fallos acumulados en la ventana actual

    async def request(self, *args, **kwargs):
        if self.current_failures >= self.max_failures:
            # Circuito ABIERTO: se han superado los fallos permitidos
            if datetime.now() > self.last_request_time + timedelta(seconds=self.reset_interval):
                # Ha pasado el reset_interval desde la última petición → intentar cerrar el circuito
                self._reset('Circuit is going from open to closed, resetting!')
                return await self._do_request(*args, **kwargs)  # Petición de prueba para ver si el servicio se recuperó
            else:
                # Aún no ha pasado el reset_interval → fallar inmediatamente sin llamar al callback
                print('Circuit is open, failing fast!')
                raise CircuitOpenException()
        else:
            # Circuito CERRADO: los fallos están por debajo del umbral
            if self.last_failure_time and \
               datetime.now() > self.last_failure_time + timedelta(seconds=self.time_window):
                # Ha pasado la ventana de tiempo desde el primer fallo → los fallos anteriores ya no cuentan
                self._reset('Interval since first failure elapsed, resetting!')
            print('Circuit is closed, requesting!')
            return await self._do_request(*args, **kwargs)  # Ejecuta la petición normalmente

    def _reset(self, msg: str):
        print(msg)
        self.last_failure_time = None   # Borra el timestamp del primer fallo de la ventana actual
        self.current_failures = 0       # Reinicia el contador de fallos a cero

    async def _do_request(self, *args, **kwargs):
        try:
            print('Making request!')
            self.last_request_time = datetime.now()  # Registra el momento de esta petición para calcular reset_interval
            return await asyncio.wait_for(self.callback(*args, **kwargs), timeout=self.timeout)
            # ↑ Ejecuta el callback con un timeout; lanza asyncio.TimeoutError si supera self.timeout segundos
        except Exception as e:
            self.current_failures += 1                      # Incrementa el contador de fallos ante cualquier excepción
            if self.last_failure_time is None:
                self.last_failure_time = datetime.now()     # Marca el inicio de la ventana de fallos con el primer error
            raise                                           # Re-lanza la excepción para que el llamador la gestione
