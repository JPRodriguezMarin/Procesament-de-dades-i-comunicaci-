"""
Listing 8.2 - Usando el protocolo con loop.create_connection

Objetivo:
    Mostrar cómo usar HTTPGetClientProtocol con create_connection.
    Introduce el patrón protocol_factory: asyncio recibe una función (no
    una instancia) para poder crear el protocolo cuando establezca la conexión.

Requiere ejecutar desde la raíz del proyecto para que los imports funcionen:
    python -m Chapter_08.listing_8_2
"""
import asyncio
from asyncio import AbstractEventLoop

from Chapter_08.listing_8_1 import HTTPGetClientProtocol


async def make_request(host: str, port: int, loop: AbstractEventLoop) -> str:
    def protocol_factory():
        """Crea una nueva instancia del protocolo por cada conexión."""
        return HTTPGetClientProtocol(host, loop)

    # create_connection devuelve (transport, protocol); ignoramos el transport
    # porque el protocolo ya lo guarda internamente en connection_made.
    _, protocol = await loop.create_connection(protocol_factory, host=host, port=port)

    return await protocol.get_response()


async def main():
    loop = asyncio.get_running_loop()
    result = await make_request('www.example.com', 80, loop)
    print(result)


asyncio.run(main())
