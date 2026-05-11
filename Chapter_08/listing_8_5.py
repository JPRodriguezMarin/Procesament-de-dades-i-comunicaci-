"""
Listing 8.5 - Función create_stdin_reader (utilidad reutilizable)

Objetivo:
    Extraer el patrón del Listing 8.4 en una función reutilizable que el
    cliente de chat (Listing 8.14) puede importar. Encapsula la complejidad
    de connect_read_pipe en una interfaz de una sola línea.
"""
import asyncio
import sys
from asyncio import StreamReader


async def create_stdin_reader() -> StreamReader:
    """Crea y devuelve un StreamReader conectado a stdin."""
    stream_reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(stream_reader)
    loop = asyncio.get_running_loop()
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    return stream_reader
