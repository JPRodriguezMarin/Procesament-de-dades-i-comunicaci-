import asyncio
import socket
import sys
from util import async_timed

# Versió final amb gather, wait_for i return_exceptions=True
#   Per tant com es mostra al enunciat d'atenea inclou:
#   gather: la tasca rep() retorna dades, gather retorna [None, 'missatge']
#   retard post enviament: envia() acaba després de rep(), gather espera el més lent.
#   wait_for(envia_t, 3): timeout entre els dos retards i es pot veure al terminal com TimeoutError es propaga
#   return_exceptions=True: l'excepció es veu com a resultat a la primera posicio de la lista, en lloc de propagarse

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

    # ara aqui aafegeixo un wait_for que aplica un timeout de 3s a envia_t
    # return_exceptions=True fa que TimeoutError es retorni com a resultat.
    r = await asyncio.gather(asyncio.wait_for(envia_t, 3), rep_t, return_exceptions=True)
    print(f'Resultat de gather(envia, rep): {r}')

    sock.close()

asyncio.run(main())
