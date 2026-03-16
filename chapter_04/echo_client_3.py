import asyncio
import socket
import sys
from util import async_timed

# Versió final amb gather, wait_for i return_exceptions=True
# Progressió de l'exercici:
# 1) gather bàsic: rep() retorna dades, gather retorna [None, 'missatge']
# 2) retard post-enviament: envia() acaba després de rep(), gather espera el més lent
# 3) wait_for(envia_t, 3): timeout entre els dos retards → TimeoutError propaga
# 4) return_exceptions=True: l'excepció es captura com a resultat en lloc de propagar-se

@async_timed()
async def envia(loop: asyncio.AbstractEventLoop, sock: socket.socket, missatge: str) -> None:
    print('Afegim un retard a l\'enviament')
    await asyncio.sleep(2)
    print(f'A punt d\'enviar: {missatge}')
    await loop.sock_sendall(sock, missatge.encode())
    print(f'Enviat: {missatge}')
    print('Afegim un retard després de l\'enviament')
    await asyncio.sleep(2)

@async_timed()
async def rep(loop: asyncio.AbstractEventLoop, sock: socket.socket, nbytes: int) -> str:
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
    await loop.sock_connect(sock, ('127.0.0.1', 8000))

    envia_t = asyncio.create_task(envia(loop, sock, missatge))
    rep_t = asyncio.create_task(rep(loop, sock, len(missatge)))

    # wait_for aplica un timeout de 3s a envia_t (entre el 1r retard=2s i la suma=4s)
    # return_exceptions=True fa que TimeoutError es retorni com a resultat en lloc de propagar-se
    r = await asyncio.gather(asyncio.wait_for(envia_t, 3), rep_t, return_exceptions=True)
    print(f'Resultat de gather(envia, rep): {r}')

    sock.close()

asyncio.run(main())
