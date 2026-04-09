from io import BytesIO
from mss import mss
from PIL import Image
import cv2
import numpy as np
import PILutils  # savetobytes
import socket
import sockutils

initialResizeRatio =  1.5
IframeInterval = 10

def differences(img, prv):
    im0 = np.array(img, dtype=np.uint8).view(np.uint32)
    im1 = np.array(prv, dtype=np.uint8).view(np.uint32)
    dif = (im0 != im1).view(np.uint8)

    contours, _ = cv2.findContours(dif, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rectangles = [cv2.boundingRect(contour) for contour in contours]  # as x, y, w, h

    img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
    crops = [img.crop((x, y, (x+w), (y+h))) for (x, y, w, h) in rectangles]
    crops = [PILutils.resize(i, 1/initialResizeRatio) for i in crops]
    return rectangles, crops


def retreive_screenshots():
    with mss() as sct:
        mon = sct.monitors[0]
        img = sct.grab(mon)
        size = round(img.width / initialResizeRatio), round(img.height / initialResizeRatio)
        prvImg = type('MyObject', (object,), {'bgra': 0})()
        IframeCounter = 0  # when this reaches 0 an I-frame is sent, otherwise non-I-frames are sent and it is decremented

        for i in size:
            sock.sendall(i.to_bytes(2, "big"))
            print('2 bytes sent.')  # DEBUG

        while True:
            signal = sock.recv(1)
            # input('continue?')
            if signal == b'':
                break
            if signal[0] == 255: # wait for return signal
                # size has been changed
                size = int.from_bytes(sock.recv(2), "big"), int.from_bytes(sock.recv(2), "big")
                #print('Resized to', size)

            img = sct.grab(mon)  # get screenshot

            if prvImg.bgra == img.bgra:
                sock.sendall(b'\xff\xff\xff')
                print('3 bytes sent.')  # DEBUG
                print('\\xFF sent', flush=True)

            else:
                if IframeCounter:  # != 0 so sending a diff frame
                    print('IframeCounter =', IframeCounter, flush=True)
                    IframeCounter -= 1

                    rectangles, crops = differences(img, prvImg)
                    print(len(rectangles), 'rectangles')
                    crops = [PILutils.savetobytes(i, format="jpeg") for i in crops]
                    buffer_temp = []
                    for rect, bs in zip(rectangles, crops):
                        buffer_temp.append(len(bs).to_bytes(length=3))   # length
                        # print('Sent length')
                        buffer_temp.extend([round(i/initialResizeRatio).to_bytes(length=2) for i in rect[:2]])  # rect
                        # print('Sent rect')
                        buffer_temp.append(bs)  # bytes
                        # print('Sent bytes')

                    sock.sendall(b''.join(buffer_temp))
                    print(sum([len(i) for i in buffer_temp]), 'bytes sent.')  # DEBUG

                    for i in range(len(rectangles) - 1):
                        signal = sock.recv(1)
                        if signal == b'':
                            return
                        if signal[0] == 255: # wait for return signal
                            # size has been changed
                            size = int.from_bytes(sock.recv(2), "big"), int.from_bytes(sock.recv(2), "big")
                            #print('Resized to', size)

                    prvImg = img

                else:  # IframeCounter has reached 0
                    IframeCounter = IframeInterval  # reset IframeCounter
                    print('I-frame sent.', flush=True)

                    prvImg = img
                    img = Image.frombytes(
                        "RGB", img.size, img.bgra, "raw", "BGRX"
                    ).resize(size, Image.LANCZOS)
                    bs = PILutils.savetobytes(img, format="jpeg")
                    sock.sendall(len(bs).to_bytes(length=3, byteorder="big") + b'0000' + bs)  # length[3], rect[4], bytes[length]
                    print(3 + 4 + len(bs), 'bytes sent.')  # DEBUG


try:
    serv1 = socket.socket()  # display OUT and mouse IN
    serv2 = socket.socket()  # mouse clicks and key presses IN

    serv1.bind(("", 16247))
    serv2.bind(("", 16248))
    serv1.listen()
    serv2.listen()
    print("Server started.")
    sock, addr = serv1.accept()
    sock2, addr = serv2.accept()
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock2.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    print("Recieved connection from:", addr)

    retreive_screenshots()

finally:
    sock.close()
    sock2.close()
    serv1.close()
    serv2.close()
