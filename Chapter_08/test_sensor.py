"""
Test interactivo del servidor de telemetria.
Equivalente a: nc localhost 8888

Uso:
    1. Inicia servidor_telemetria.py en otra terminal
    2. Ejecuta: python test_sensor.py
    3. Escribe mensajes y pulsa Enter
       Ejemplos:
           Temperatura: 25C        -> DADA_REBUDA
           ALERTA: Pressió alta    -> PROTOCO_EMERGENCIA_ACTIVAT
    4. Ctrl+C para salir
"""
import asyncio


async def main():
    reader, writer = await asyncio.open_connection('127.0.0.1', 8888)
    print('Conectado al servidor de telemetria (Ctrl+C para salir)\n')

    loop = asyncio.get_running_loop()

    try:
        while True:
            msg = await loop.run_in_executor(None, input, 'Sensor > ')
            writer.write((msg + '\n').encode())
            await writer.drain()
            resp = await reader.readline()
            print(f'Servidor: {resp.decode().strip()}\n')
    except (KeyboardInterrupt, EOFError):
        print('\nDesconectando...')
    finally:
        writer.close()
        await writer.wait_closed()


asyncio.run(main())
