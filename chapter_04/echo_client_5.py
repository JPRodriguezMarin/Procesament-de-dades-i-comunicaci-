import asyncio
import socket
import sys
from util import async_timed

# Versió amb wait i timeout=3
# asyncio.wait retorna dos conjunts: (done, pending)
# A diferència de gather i as_completed, wait NO cancel·la les tasques pendents quan expira el timeout.
# El programador ha de decidir explícitament si reprendre-les o cancel·lar-les.

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

    # wait retorna (done, pending) quan expira el timeout o acaben totes les tasques
    # timeout=3: entre el 1r retard (2s) i la suma (4s)
    # → rep acaba a ~2s (done), envia no acaba a temps (pending)
    done, pending = await asyncio.wait([envia_t, rep_t], timeout=3)

    print(f'Nombre de tasques acabades: {len(done)}')
    print(f'Nombre de tasques pendents: {len(pending)}')

    for t in done:
        print(f'Resultat de la tasca {t}: {t.result()}')

    # Les tasques pendents es cancel·len explícitament (wait no ho fa automàticament)
    for t in pending:
        t.cancel()

    sock.close()

asyncio.run(main())
