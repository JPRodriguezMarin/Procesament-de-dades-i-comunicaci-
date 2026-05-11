"""
Listing 8.12 - Servidor echo con estado compartido

Objetivo:
    Demostrar un servidor asyncio que mantiene estado compartido entre
    múltiples conexiones simultáneas. El servidor notifica a todos los
    clientes cuando alguien se conecta o desconecta, e informa del número
    de usuarios activos. Muestra el patrón create_task para manejar cada
    cliente de forma independiente sin bloquear la aceptación de nuevos.

Para probarlo:
    1. Ejecuta este script
    2. En otra terminal: nc 127.0.0.1 8000
    3. Escribe texto; verás el eco. Abre otra conexión y verás "New user connected!"
"""
import asyncio
import logging
from asyncio import StreamReader, StreamWriter


class ServerState:

    def __init__(self):
        self._writers: list = []

    async def add_client(self, reader: StreamReader, writer: StreamWriter):
        """Registra el cliente, lo saluda y lanza la tarea de echo."""
        self._writers.append(writer)
        await self._on_connect(writer)
        asyncio.create_task(self._echo(reader, writer))

    async def _on_connect(self, writer: StreamWriter):
        """Informa al nuevo cliente y notifica a todos los demás."""
        writer.write(f'Welcome! {len(self._writers)} user(s) are online!\n'.encode())
        await writer.drain()
        await self._notify_all('New user connected!\n')

    async def _echo(self, reader: StreamReader, writer: StreamWriter):
        """Hace echo de los mensajes del cliente hasta que se desconecta."""
        try:
            while data := await reader.readline() != b'':
                writer.write(data)
                await writer.drain()
            self._writers.remove(writer)
            await self._notify_all(
                f'Client disconnected. {len(self._writers)} user(s) are online!\n'
            )
        except Exception as e:
            logging.exception('Error reading from client.', exc_info=e)
            self._writers.remove(writer)

    async def _notify_all(self, message: str):
        """Envía un mensaje a todos los clientes conectados."""
        for writer in self._writers:
            try:
                writer.write(message.encode())
                await writer.drain()
            except ConnectionError as e:
                logging.exception('Could not write to client.', exc_info=e)
                self._writers.remove(writer)


async def main():
    server_state = ServerState()

    async def client_connected(reader: StreamReader, writer: StreamWriter) -> None:
        await server_state.add_client(reader, writer)

    server = await asyncio.start_server(client_connected, '127.0.0.1', 8000)

    async with server:
        await server.serve_forever()


asyncio.run(main())
