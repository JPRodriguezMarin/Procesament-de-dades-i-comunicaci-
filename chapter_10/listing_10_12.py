# =============================================================================
# listing_10_12.py — CircuitBreaker Demo
# =============================================================================
# Objetivo:
#   Script de demostración que muestra el comportamiento completo del
#   CircuitBreaker (listing_10_11.py) con una corutina que siempre
#   supera el timeout, para observar las tres fases del ciclo:
#
#   Fase 1 — Circuito cerrándose (CLOSED):
#     Los dos primeros intentos hacen la petición real y fallan por
#     timeout (1s cada uno). Tras el segundo fallo, current_failures
#     alcanza max_failures=2 y el circuito se abre.
#
#   Fase 2 — Circuito abierto (OPEN):
#     Los dos intentos siguientes fallan instantáneamente con
#     CircuitOpenException, sin esperar ningún timeout. El ahorro
#     de tiempo es la motivación principal del patrón.
#
#   Pausa de 5s (reset_interval):
#     Se espera el tiempo necesario para que el circuito pueda
#     intentar cerrarse en la siguiente petición.
#
#   Fase 3 — Intento de cierre y reapertura:
#     La primera petición después de la pausa resetea el circuito
#     y hace una petición de prueba (que falla de nuevo por timeout).
#     El ciclo se repite exactamente igual que en las fases 1 y 2.
#
#   Configuración del demo:
#     slow_callback tarda siempre 2s → timeout=1s → siempre falla
#     max_failures=2, time_window=5s, reset_interval=5s
# =============================================================================

import asyncio                                      # Proporciona sleep() y run() para el demo
from chapter_10.listing_10_11 import CircuitBreaker  # Importa la clase CircuitBreaker del listing anterior


async def main():
    async def slow_callback():
        await asyncio.sleep(2)          # Siempre tarda 2 segundos → siempre supera el timeout de 1s del CircuitBreaker

    cb = CircuitBreaker(
        slow_callback,                  # Callback que será protegido por el circuit breaker
        timeout=1.0,                    # Cada petición tiene máximo 1 segundo → slow_callback siempre fallará
        time_window=5,                  # Los fallos se acumulan durante una ventana de 5 segundos
        max_failures=2,                 # Después de 2 fallos el circuito se abre
        reset_interval=5                # El circuito abierto espera 5 segundos antes de intentar cerrarse
    )

    for _ in range(4):                  # Primer bloque: 4 intentos seguidos
        try:
            await cb.request()          # Intento 1 y 2: fallan por timeout (1s < 2s) → current_failures sube a 2 → circuito abre
                                        # Intento 3 y 4: fallan inmediatamente con CircuitOpenException (circuito abierto)
        except Exception:
            pass                        # Captura tanto TimeoutError como CircuitOpenException para que el bucle continúe

    print('Sleeping for 5 seconds so breaker closes...')
    await asyncio.sleep(5)              # Espera reset_interval segundos para que el circuito pueda intentar cerrarse

    for _ in range(4):                  # Segundo bloque: misma secuencia de 4 intentos
        try:
            await cb.request()          # Intento 1: reset_interval ha pasado → circuito se cierra y hace petición de prueba (falla por timeout)
                                        # Intento 2: circuito cerrado, falla por timeout → current_failures = 2 → circuito abre de nuevo
                                        # Intentos 3 y 4: fallan inmediatamente con CircuitOpenException
        except Exception:
            pass


asyncio.run(main())                     # Crea el event loop, ejecuta main() y lo cierra al terminar
