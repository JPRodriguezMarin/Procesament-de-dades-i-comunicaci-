"""
Exercici — Prova de Càrrega del Servidor de Telemetria

Objectiu:
    Mesurar el rendiment del servidor de telemetria simulant múltiples sensors
    concurrents durant un temps determinat. Calcula:
        - Total de peticions enviades
        - Nombre d'errors
        - Temps total d'execució
        - Peticions per segon (throughput)

    Conceptes clau:
        - time.monotonic(): rellotge monòton per mesurar durades sense deriva
        - asyncio.create_task(): connexions concurrents sense bloquejar
        - await writer.drain(): garanteix enviament real de les dades
        - asyncio.gather(): espera que totes les tasques acabin

Experiments recomanats:
    - Augmenta MAX_CONNECTIONS (10 → 50 → 100) i observa el throughput
    - Augmenta DURATION_SECONDS per obtenir mesures més estables
    - Compara el rendiment amb el servidor aturat per veure els errors

Execució:
    1. Inicia servidor_telemetria.py en una terminal
    2. Executa aquest script en una altra terminal
"""
import asyncio
import time


HOST = '127.0.0.1'
PORT = 8888
MAX_CONNECTIONS = 10   # nombre de sensors simulats en paral·lel
DURATION_SECONDS = 5   # temps que dura la prova


async def sensor_worker(duration: float, results: dict) -> None:
    """
    Un sensor simulat que envia dades al servidor en bucle durant `duration` segons.
    Acumula peticions i errors en el diccionari `results` compartit.
    """
    end_time = time.monotonic() + duration

    try:
        reader, writer = await asyncio.open_connection(HOST, PORT)
    except Exception:
        results['errors'] += 1
        return

    try:
        while time.monotonic() < end_time:
            writer.write(b'Temperatura: 25C\n')
            await writer.drain()

            response = await reader.readline()
            if response.strip() != b'DADA_REBUDA':
                results['errors'] += 1

            results['requests'] += 1
    except Exception:
        results['errors'] += 1
    finally:
        writer.close()
        await writer.wait_closed()


async def main() -> None:
    results = {'requests': 0, 'errors': 0}

    print(f'Iniciant prova de càrrega: {MAX_CONNECTIONS} connexions durant {DURATION_SECONDS}s')

    start = time.monotonic()

    tasks = [
        asyncio.create_task(sensor_worker(DURATION_SECONDS, results))
        for _ in range(MAX_CONNECTIONS)
    ]
    await asyncio.gather(*tasks)

    elapsed = time.monotonic() - start
    throughput = results['requests'] / elapsed if elapsed > 0 else 0

    print(f'\n--- Resultats ---')
    print(f'Temps total:        {elapsed:.2f}s')
    print(f'Total peticions:    {results["requests"]}')
    print(f'Errors:             {results["errors"]}')
    print(f'Peticions/segon:    {throughput:.1f}')


asyncio.run(main())
