"""
Listing 8.14 - Cliente de chat con UI de terminal dividida

Objetivo:
    Implementar un cliente de chat con dos zonas visuales: mensajes arriba,
    input abajo. Dos tareas corren en paralelo:
      - listen_for_messages: lee mensajes del servidor y refresca la pantalla
      - read_and_send: lee input del usuario y lo envía al servidor

    asyncio.wait con FIRST_COMPLETED garantiza que el cliente termine limpiamente
    en cuanto cualquiera de las dos tareas acabe (desconexión del servidor, error).

Requisitos:
    - Python 3.8+
    - Sistema Unix/Linux/macOS (tty.setcbreak no disponible en Windows)
    - Servidor de chat del Listing 8.13 en ejecución en 127.0.0.1:8000

Para ejecutar desde la raíz del proyecto:
    python -m Chapter_08.listing_8_14
"""
import asyncio
import logging
import sys
import tty
from asyncio import StreamReader, StreamWriter
from collections import deque

from Chapter_08.listing_8_5 import create_stdin_reader
from Chapter_08.listing_8_7 import (
    save_cursor_position,
    restore_cursor_position,
    move_to_top_of_screen,
    delete_line,
    move_to_bottom_of_screen,
)
from Chapter_08.listing_8_8 import read_line
from Chapter_08.listing_8_9 import MessageStore


async def send_message(message: str, writer: StreamWriter):
    writer.write((message + '\n').encode())
    await writer.drain()


async def listen_for_messages(reader: StreamReader, message_store: MessageStore):
    """Escucha mensajes del servidor y los añade al MessageStore."""
    while (message := await reader.readline()) != b'':
        await message_store.append(message.decode())
    await message_store.append('Server closed connection.')


async def read_and_send(stdin_reader: StreamReader, writer: StreamWriter):
    """Lee input del usuario carácter a carácter y lo envía al servidor."""
    while True:
        message = await read_line(stdin_reader)
        await send_message(message, writer)


async def main():
    async def redraw_output(items: deque):
        """Callback que redibuja todos los mensajes en la zona superior."""
        save_cursor_position()
        move_to_top_of_screen()
        for item in items:
            delete_line()
            sys.stdout.write(item)
        restore_cursor_position()

    tty.setcbreak(0)
    # Limpia pantalla con secuencias ANSI: ESC[2J = borrar pantalla, ESC[H = cursor inicio
    sys.stdout.write('\033[2J\033[H')
    sys.stdout.flush()
    rows = move_to_bottom_of_screen()

    messages = MessageStore(redraw_output, rows - 1)

    stdin_reader = await create_stdin_reader()
    sys.stdout.write('Enter username: ')
    username = await read_line(stdin_reader)

    reader, writer = await asyncio.open_connection('127.0.0.1', 8000)

    # Handshake: primer mensaje = CONNECT <username>
    writer.write(f'CONNECT {username}\n'.encode())
    await writer.drain()

    # Dos tareas concurrentes en el mismo event loop (un solo hilo)
    message_listener = asyncio.create_task(listen_for_messages(reader, messages))
    input_listener = asyncio.create_task(read_and_send(stdin_reader, writer))

    try:
        # FIRST_COMPLETED: salir en cuanto cualquiera de las dos tareas termine
        await asyncio.wait(
            [message_listener, input_listener],
            return_when=asyncio.FIRST_COMPLETED,
        )
    except Exception as e:
        logging.exception(e)
        writer.close()
        await writer.wait_closed()


asyncio.run(main())
