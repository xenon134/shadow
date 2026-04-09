print('Initialising ... ')
from PIL import Image
import PILutils
import numpy as np

import collections
import pygame
import queue
import socket
import sockutils  # recvall, firstconnect
import threading
import time

addrs = 'veteran.local', '192.168.0.147'

print('taskkill -f -im', __import__('os').getpid())


eventsqueue = queue.Queue()
image_to_blit = None
image_to_blit_lock = threading.Lock()
def pygamedisplay():
    global clock
    global image_to_blit

    pygame.init()
    screen = pygame.display.set_mode(currentSize, pygame.RESIZABLE)
    clock = pygame.time.Clock()

    lagmeter = collections.deque([time.time()], maxlen=10)
    while watching:
        was_blit = False
        with image_to_blit_lock:
            if image_to_blit is not None:
                screen.blit(pygame.image.fromstring(img.tobytes(), img.size, img.mode), (0, 0))
                pygame.display.flip()
                clock.tick(10)
                image_to_blit = None
                was_blit = True

        for event in pygame.event.get():
            eventsqueue.put(event)

        if was_blit:
            # print('blitted')
            lagmeter.append(time.time())
            fps = len(lagmeter)/(lagmeter[-1] - lagmeter[0])
            # print("\r\t\tFPS =", round(fps, 1), end=" "*8)
        time.sleep(0.1)


sock1 = sockutils.firstconnect(addrs, 16247)  # display and mouse
sock2 = sockutils.firstconnect(addrs, 16248)  # mouse clicks and key presses
sock1.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
sock2.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

initialResizeRatio = 65535 / sockutils.recvint(sock1, 2)
maxsize = sockutils.recvint(sock1, 2), sockutils.recvint(sock1, 2)
currentSize = (round(maxsize[0]/initialResizeRatio), round(maxsize[1]/initialResizeRatio))

watching = True  # running
t1 = 0
threading.Thread(target=pygamedisplay, daemon=True).start()


def handlemouseclick(event, down):
    global sock2_buffer
    sock2_buffer += bytes((event.button*2 + down,))  # button = 1, 2, 3 for left, middle, right
    x, y = event.pos
    x = round(x*(currentSize[0]/maxsize[0]))
    y = round(y*(currentSize[1]/maxsize[1]))
    sock2_buffer += x.to_bytes(2) + y.to_bytes(2)

def handlekeypress(event, down):
    print(event.key, event.mod, event.unicode, event.scancode)


prvImg = None

while watching:
    newSize = None
    sock2_buffer = b''
    sock1_buffer = b''

    while True:
        try:
            event = eventsqueue.get_nowait()
        except queue.Empty:
            break

        else:
            if event.type == pygame.QUIT:
                watching = False
                break

            elif event.type == pygame.WINDOWRESIZED:
                newSize = min(event.x, maxsize[0]), min(event.y, maxsize[1])
                currentSize = newSize

            # elif event.type == pygame.MOUSEMOTION:
            #     mousex, mousey = event.pos

            elif event.type == pygame.MOUSEBUTTONDOWN:
                handlemouseclick(event, 1)
            elif event.type == pygame.MOUSEBUTTONUP:
                handlemouseclick(event, 0)

            # elif event.type == pygame.KEYDOWN:
            #     handlekeypress(event, 1)
            # elif event.type == pygame.KEYUP:
            #     handlekeypress(event, 0)
            #     pass

    sock2.sendall(sock2_buffer)

    if newSize:
        sock1_buffer += b'\xff'
        for i in newSize:
            sock1_buffer += i.to_bytes(2)
        print(f'\rResized to {newSize[0]}x{newSize[1]}   \t\t')
    else:
        sock1_buffer += b'\x00'

    sock1.sendall(sock1_buffer)

    leng = sockutils.recvint(sock1, 3)  # recieve a 3 byte integer
    if (leng & (1 << 23)):  # xor frame (check highest (24th) bit)
        # print('diff!')
        leng = leng - (1 << 23)
        xor_bs = sockutils.recvall(sock1, leng)
        recievedImg = PILutils.openfrombytes(xor_bs)
        img = Image.fromarray(np.asarray(prvImg) ^ np.asarray(recievedImg))

    else:
        # print('i-frame!!')
        img_bs = sockutils.recvall(sock1, leng)
        try:
            img = PILutils.openfrombytes(img_bs)
        except:
            print('Cannot recogzize bytes of length', leng, len(img_bs))

    prvImg = img
    with image_to_blit_lock:
        assert (image_to_blit is None) or not watching  # if watching: assert image_to_blit is None
        image_to_blit = img

print()