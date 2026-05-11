"""
Listing 8.4 - Demo básica de stdin asíncrono

Objetivo:
    Mostrar el patrón para conectar stdin al sistema de streams de asyncio.
    connect_read_pipe envuelve cualquier pipe del SO (incluyendo stdin) en un
    StreamReader, haciendo que la lectura sea no bloqueante y compatible con
    el event loop. Sin este patrón, input() bloquearía el event loop entero.
"""
import asyncio
import sys
from asyncio import StreamReader


async def create_stdin_reader() -> StreamReader:
    """Envuelve stdin en un StreamReader asíncrono."""
    stream_reader = asyncio.StreamReader()
    # StreamReaderProtocol alimenta el StreamReader con datos del pipe
    protocol = asyncio.StreamReaderProtocol(stream_reader)
    loop = asyncio.get_running_loop()
    # Conecta stdin (fd 0) al protocolo; los bytes de teclado fluyen al StreamReader
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
