"""
Listing 8.8 - Función read_line (lectura carácter a carácter)

Objetivo:
    Leer una línea de stdin carácter a carácter desde un StreamReader.
    Necesario en modo tty.setcbreak donde el terminal no procesa líneas:
    los caracteres llegan uno a uno, sin buffering. readline() no funciona
    en este modo porque nunca ve el terminador de línea del sistema.
    read_line acumula bytes hasta encontrar '\\n' y devuelve el string.
"""
from asyncio import StreamReader


async def read_line(stdin_reader: StreamReader) -> str:
    """Lee carácter a carácter hasta encontrar newline. Devuelve la línea decodificada."""
    line = b''
    while True:
        char = await stdin_reader.read(1)
        if char == b'\n':
            break
        line += char
    return line.decode()
