"""
Listing 8.9 - Clase MessageStore

Objetivo:
    Almacenar mensajes del chat con tamaño máximo fijo y notificar a un
    callback asíncrono cada vez que se añade un mensaje. Desacopla el
    almacenamiento de mensajes (estado) de la lógica de redibujado (UI).

    deque(maxlen) descarta automáticamente los mensajes más antiguos cuando
    se supera el límite, evitando que los mensajes se salgan de la zona
    visible del terminal sin necesidad de lógica extra.
"""
from collections import deque
from typing import Callable


class MessageStore:
    def __init__(self, callback: Callable, max_size: int):
        self._messages: deque = deque(maxlen=max_size)
        self._callback = callback

    async def append(self, message: str):
        """Añade un mensaje y dispara el callback de redibujado."""
        self._messages.append(message)
        await self._callback(self._messages)
