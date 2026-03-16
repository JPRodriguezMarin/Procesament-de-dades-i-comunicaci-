import asyncio
import socket
import sys
from util import async_timed

# Versió amb wait i timeout=3
# asyncio.wait retorna done o pending per tant si hi ha una tasca pendent pel timeout no apareix un error pero done o pending
# Per tant com hem vist a clase el programador ha de decidir si reprendre o cancel·lar les tasques

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

    
    done, pending = await asyncio.wait([envia_t, rep_t], timeout=3)

    print(f'Nombre de tasques acabades: {len(done)}')
    print(f'Nombre de tasques pendents: {len(pending)}')

    for t in done:
        print(f'Resultat de la tasca {t}: {t.result()}')

    # Les tasques pendents es cancelen explicitament (wait no ho fa automàticament)
    for t in pending:
        t.cancel()

    sock.close()

asyncio.run(main())
