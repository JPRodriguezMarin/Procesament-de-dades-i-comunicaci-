"""
Listing 8.3 - Cliente HTTP con StreamReader y StreamWriter (alto nivel)

Objetivo:
    Reescribir el cliente HTTP del Listing 8.1 usando open_connection.
    Demuestra cuánto código boilerplate elimina la API de alto nivel:
    sin callbacks manuales, sin Future explícito, sin buffer propio.
    Introduce generadores asíncronos (async def + yield) y async for.

Comparación:
    Listing 8.1: ~40 líneas de clase con callbacks
    Listing 8.3: ~20 líneas con open_connection
    Mismo resultado, la mitad de código.
"""
import asyncio
from asyncio import StreamReader
from typing import AsyncGenerator


async def read_until_empty(stream_reader: StreamReader) -> AsyncGenerator[str, None]:
    """Generador asíncrono: yield de cada línea hasta EOF (b'')."""
    while response := await stream_reader.readline():
        yield response.decode()


async def main():
    host: str = 'www.example.com'
    request: str = (
        f"GET / HTTP/1.1\r\n"
        f"Connection: close\r\n"
        f"Host: {host}\r\n\r\n"
    )

    stream_reader, stream_writer = await asyncio.open_connection('www.example.com', 80)

    try:
        # write() no es coroutine; drain() vacía el buffer y cede al event loop
        stream_writer.write(request.encode())
        await stream_writer.drain()

        # async for itera el generador asíncrono línea a línea
        responses = [response async for response in read_until_empty(stream_reader)]

        print(''.join(responses))
    finally:
        # close() inicia el cierre; wait_closed() espera que sea efectivo
        stream_writer.close()
        await stream_writer.wait_closed()


asyncio.run(main())
