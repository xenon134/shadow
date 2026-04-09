print('Initialising ... ')
from io import BytesIO
from PIL import Image
import  collections  # deque
import pygame
import socket
import sockutils  # recvall
import threading
import time

# addr = "192.168.0.147"
addr = 'localhost'


lags = collections.deque([float('inf')], maxlen=10)
def displayFpsFunc():
    mt = threading.main_thread()
    while mt.is_alive():
        avglag = sum(lags)/len(lags)
        print("\r\t\tFPS =", round(1/avglag), end=" "*8)
        #pygame.display.set_caption('FPS: ' + str(round(1/lag, 3)))
        time.sleep(0.1) # 200 ms


with socket.socket() as sock:
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.connect((addr, 16247))

    size = int.from_bytes(sock.recv(2), "big"), int.from_bytes(sock.recv(2), "big")
    pygame.init()
    screen = pygame.display.set_mode(size, pygame.RESIZABLE)
    clock = pygame.time.Clock()
    watching = True
    t1 = 0
    threading.Thread(target=displayFpsFunc).start()

    while watching:
        now = time.time()
        lags.append(now - t1)
        t1 = now
        newSize = None

        for event in pygame.event.get():
            #print(event)
            if event.type == pygame.QUIT:
                watching = False
                break
            elif event.type == pygame.WINDOWRESIZED:
                newSize = event.x, event.y

        if newSize:
            sock.sendall(b'\xff')
            for i in newSize:
                sock.sendall(i.to_bytes(2, "big"))
            print(f'\rResized to {newSize[0]}x{newSize[1]}   \t\t')
        else:
            sock.sendall(b'\x00')
        leng = sockutils.recvall(sock, 3)
        if leng != b'\xff\xff\xff': # screen same as before
            leng = int.from_bytes(leng, byteorder="big")
            bs = sockutils.recvall(sock, leng)
            img = Image.open(BytesIO(bs), formats=['jpeg'])
            img = pygame.image.fromstring(img.tobytes(), img.size, img.mode)
            screen.blit(img, (0, 0))
            pygame.display.flip()
        
        clock.tick(60)

print()