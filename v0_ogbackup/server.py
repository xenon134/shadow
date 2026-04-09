import socket
from io import BytesIO
from PIL import Image
from mss import mss

initialResizeRatio = 1.4059068448023426

def retreive_screenshots():
    with mss() as sct:
        mon = sct.monitors[0]
        img = sct.grab(mon)
        prvImg = None
        size = round(img.width / initialResizeRatio), round(img.height / initialResizeRatio)
        for i in size:
            sock.sendall(i.to_bytes(2, "big"))
        while True:
            signal = sock.recv(1)
            if signal == b'':
                break
            if signal[0]: # wait for return signal
                # size has been changed
                size = int.from_bytes(sock.recv(2), "big"), int.from_bytes(sock.recv(2), "big")
                #print('Resized to', size)
            img = sct.grab(mon)  # get screenshot
            img = Image.frombytes(
                "RGB", img.size, img.bgra, "raw", "BGRX"
            ).resize(size, Image.LANCZOS)
            if prvImg == img:
                sock.sendall(b'\xff\xff\xff')
            else:
                prvImg = img
                bs = BytesIO()
                img.save(bs, format="jpeg")
                bs = bs.getvalue()
                sock.sendall(len(bs).to_bytes(length=3, byteorder="big") + bs)

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as serv:
    serv.bind(("", 16247))
    serv.listen()
    print("Server started at port 16247")
    sock, addr = serv.accept()
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    print("Recieved connection from:", addr)

    retreive_screenshots()
