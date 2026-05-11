"""
Exercici — Servidor de Telemetria de Sensors de Planta

Objectiu:
    Servidor asíncron que gestiona múltiples sensors industrials simultanis.
    Cada sensor envia dades línia a línia; el servidor respon:
        - "DADA_REBUDA"              per a qualsevol dada normal
        - "PROTOCO_EMERGENCIA_ACTIVAT"  si la dada conté "ALERTA"

    Conceptes clau:
        - asyncio.start_server: accepta connexions simultànies sense bloquejar
        - StreamReader / StreamWriter: lectura i escriptura asíncrona
        - await writer.drain(): garanteix que les dades s'envien abans de continuar
        - close() + wait_closed(): tancament net del stream

Per provar-ho:
    1. Executa aquest script
    2. En una altra terminal: nc localhost 8888  (o telnet localhost 8888)
       Escriu: Temperatura: 25C       → respon DADA_REBUDA
       Escriu: ALERTA: Pressió alta   → respon PROTOCO_EMERGENCIA_ACTIVAT
    3. Obre una segona terminal i connecta un altre sensor simultàniament
       per comprovar que el servidor gestiona ambdós sense bloquejar-se.
"""
import asyncio
import logging
from asyncio import StreamReader, StreamWriter

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')


async def handle_sensor(reader: StreamReader, writer: StreamWriter) -> None:
    addr = writer.get_extra_info('peername')
    logging.info(f'Sensor connectat: {addr}')

    try:
        while True:
            data = await reader.readline()
            if not data:
                break

            message = data.decode().strip()
            logging.info(f'[{addr}] Dada rebuda: {message}')

            if 'ALERTA' in message:
                response = 'PROTOCO_EMERGENCIA_ACTIVAT\n'
                logging.warning(f'[{addr}] ALERTA detectada — protocol emergència activat')
            else:
                response = 'DADA_REBUDA\n'

            writer.write(response.encode())
            await writer.drain()

    except Exception as e:
        logging.exception(f'Error amb sensor {addr}', exc_info=e)
    finally:
        logging.info(f'Sensor desconnectat: {addr}')
        writer.close()
        await writer.wait_closed()


async def main() -> None:
    server = await asyncio.start_server(handle_sensor, '127.0.0.1', 8888)
    addr = server.sockets[0].getsockname()
    logging.info(f'Servidor de telemetria escoltant a {addr}')

    async with server:
        await server.serve_forever()


asyncio.run(main())
