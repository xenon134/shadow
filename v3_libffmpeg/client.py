import socket
import struct
import sys
import json

import cv2  # pip install opencv-python
import av  # pip install av
import numpy as np  # pip install numpy

import PILutils

class Connection:
    def __init__(self):
        HOST = sys.argv[1] if len(sys.argv)>1 else 'localhost' # Change to server IP if running on a different machine
        PORT = 45914
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Prefer low-latency TCP behavior
        self.client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
        self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        self.client_socket.connect((HOST, PORT))
        print("Connected to server.")

    def close(self):
        self.client_socket.close()
        
    def send_metadata(self, obj):
        """JSON-serialize `obj` and send with MSB of header set to 1."""
        data = json.dumps(obj).encode('utf-8')
        size = len(data)
        size_with_flag = size | (1 << 31)
        header = struct.pack('<L', size_with_flag)
        self.client_socket.sendall(header + data)

    def _recv_packet_or_metadata(self):
        # Read the 4-byte header to find out the incoming packet size
        header = self.recvall(4)
        if not header:
            return None
        size_with_flag = struct.unpack('<L', header)[0]
        packet_size = size_with_flag & 0x7FFFFFFF  # Clear the MSB to get the actual size
        # Read the exact payload based on the header
        packet_data = self.recvall(packet_size)
        is_metadata = (size_with_flag >> 31) & 1
        return (is_metadata, packet_data) if packet_data else None
    
    def recv_packet(self):
        while True:
            is_metadata, payload = self._recv_packet_or_metadata()
            if is_metadata:
                metadata = json.loads(payload.decode('utf-8'))
                handle_metadata(metadata)
            else:
                return payload
     
    def recvall(self, count):
        """Helper function to read exactly 'count' bytes from the TCP stream."""
        buf = b''
        while count:
            newbuf = self.client_socket.recv(count)
            if not newbuf: return None
            buf += newbuf
            count -= len(newbuf)
        return buf


client_conn = Connection()

def handle_metadata(metadata):
    print("Received metadata:", metadata)

# 2. Decoder Setup (The Black Box)
decoder = av.CodecContext.create('h264', 'r')

try:
    while True:
        packet_data = client_conn.recv_packet()
        if packet_data is None:
            break
            
        client_conn.send_metadata({"type": "ack"})

        # Wrap the bytes into a PyAV Packet
        packet = av.Packet(packet_data)
        
        # Decode the packet into video frames
        # (One packet usually yields one frame, but we loop just in case)
        frames = decoder.decode(packet)

        for frame in frames:
            # PyAV handles the YUV back to BGR numpy array conversion
            img = PILutils.Image.fromarray(frame.to_ndarray(format='rgb24'))
            img = PILutils.resize(img, 0.5)
            img_cv2 = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)
            
            # Display the result
            cv2.imshow("Remote Desktop", img_cv2)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                raise KeyboardInterrupt

except (ConnectionResetError, KeyboardInterrupt):
    print("Connection closed.")
finally:
    client_conn.close()
    cv2.destroyAllWindows()