"""
Listing 8.1 - Cliente HTTP con Transportes y Protocolos (bajo nivel)

Objetivo:
    Demostrar la API de bajo nivel de asyncio: implementar un cliente HTTP GET
    usando callbacks de Protocol. Muestra el patrón Future como puente entre
    callbacks síncronos y el mundo async/await.

Concepto clave:
    Transport gestiona el canal (bytes in/out).
    Protocol define qué hacer cuando ocurren eventos (conexión, datos, EOF).
    Future conecta callbacks con coroutines: eof_received completa el future,
    get_response lo espera con await.
"""
import asyncio
from asyncio import Transport, Future, AbstractEventLoop
from typing import Optional


class HTTPGetClientProtocol(asyncio.Protocol):

    def __init__(self, host: str, loop: AbstractEventLoop):
        self._host: str = host
        self._future: Future = loop.create_future()
        self._transport: Optional[Transport] = None
        self._response_buffer: bytes = b''

    async def get_response(self):
        """Espera el future hasta recibir la respuesta completa."""
        return await self._future

    def _get_request_bytes(self) -> bytes:
        """Construye la petición HTTP GET en bytes."""
        request = (
            f"GET / HTTP/1.1\r\n"
            f"Connection: close\r\n"
            f"Host: {self._host}\r\n\r\n"
        )
        return request.encode()

    def connection_made(self, transport: Transport):
        """Callback: la conexión TCP está establecida. Envía la petición."""
        print(f'Connection made to {self._host}')
        self._transport = transport
        self._transport.write(self._get_request_bytes())

    def data_received(self, data: bytes):
        """Callback: llegaron más bytes. Acumula en el buffer."""
        print('Data received!')
        self._response_buffer += data

    def eof_received(self) -> Optional[bool]:
        """Callback: el servidor cerró su extremo. Completa el future."""
        self._future.set_result(self._response_buffer.decode())
        return False

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Callback: conexión cerrada. Si hay error, lo propaga al future."""
        if exc is None:
            print('Connection closed without error.')
        else:
            self._future.set_exception(exc)
