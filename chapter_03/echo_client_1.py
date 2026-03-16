import asyncio
import socket
import sys

async def envia(loop: asyncio.AbstractEventLoop, sock: socket.socket, missatge: str) -> None:
    print('Afegim un retard a l\'enviament')
    await asyncio.sleep(2)
    print(f'A punt d\'enviar: {missatge}')
    await loop.sock_sendall(sock, missatge.encode())
    print(f'Enviat: {missatge}')

async def rep(loop: asyncio.AbstractEventLoop, sock: socket.socket, nbytes: int) -> str:
    print('A punt per rebre')
    dades = await loop.sock_recv(sock, nbytes)
    resultat = dades.decode()
    print(f'Rebut: {resultat}')
    return resultat

async def main():
    missatge = ' '.join(sys.argv[1:])
    loop = asyncio.get_event_loop()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    await loop.sock_connect(sock, ('127.0.0.1', 8000))

    task_envia = asyncio.create_task(envia(loop, sock, missatge))
    task_rep = asyncio.create_task(rep(loop, sock, len(missatge)))

    await asyncio.gather(task_envia, task_rep)

    sock.close()

asyncio.run(main())
