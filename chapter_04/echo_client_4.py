import asyncio
import socket
import sys
from util import async_timed

# Versió amb as_completed i timeout=3

@async_timed()
async def envia(loop: asyncio.AbstractEventLoop, sock: socket.socket, missatge: str):
    print('Afegim un retard a l\'enviament')
    await asyncio.sleep(2)
    print(f'A punt d\'enviar: {missatge}')
    await loop.sock_sendall(sock, missatge.encode())
    print(f'Enviat: {missatge}')
    print('Afegim un retard després de l\'enviament')
    await asyncio.sleep(2)

@async_timed()
async def rep(loop: asyncio.AbstractEventLoop, sock: socket.socket, nbytes: int):
    print('A punt per rebre')
    dades = await loop.sock_recv(sock, nbytes)
    resultat = dades.decode()
    print(f'Rebut: {resultat}')
    return resultat

@async_timed()
async def main():
    missatge = ' '.join(sys.argv[1:])
    loop = asyncio.get_event_loop()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    await loop.sock_connect(sock, ('127.0.0.1', 32000))

    envia_t = asyncio.create_task(envia(loop, sock, missatge))
    rep_t = asyncio.create_task(rep(loop, sock, len(missatge)))

    # amb as_completed el primer a acabar és el primer iterat
    # timeout=3 que es just entre el 1r retard de envia i la suma dels dos per tant rep acaba a ~2s la primera iteracio sera sense error, envia no acaba a temps per tant la segona iteració, TimeoutError
    for t in asyncio.as_completed([envia_t, rep_t], timeout=3):
        print(f'Resultat de {t}: {await t}')

    sock.close()

asyncio.run(main())
