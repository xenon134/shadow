import socket
import struct
import time
import json
import select

import numpy as np  # pip install numpy
from PIL import ImageGrab  # pip install Pillow
import av  # pip install av

import stringutils

# 1. Network Setup
class Connection:
    def __init__(self, host='0.0.0.0', port=45914):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Allow quick restart and prefer low-latency behavior
        try:
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception:
            pass
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(1)
        print(f"Listening on {self.port}...")
        self.conn, self.addr = self.server_socket.accept()
        print(f"Connected to {self.addr}")
        
        # Disable Nagle for low latency and adjust buffers
        self.conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        # Reasonable send/recv buffers for low-latency streaming
        self.conn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
        self.conn.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)

    def recvall(self, count):
        """Read exactly `count` bytes from the connected socket or return None on EOF."""
        buf = b''
        while count:
            newbuf = self.conn.recv(count)
            if not newbuf:
                return None
            buf += newbuf
            count -= len(newbuf)
        return buf

    def send_packet(self, data):
        size_header = struct.pack('<L', len(data))
        self.conn.sendall(size_header + data)

    def send_metadata(self, obj):
        """JSON-serialize `obj` and send with MSB of header set to 1."""
        data = json.dumps(obj).encode('utf-8')
        size = len(data)
        size_with_flag = size | (1 << 31)
        header = struct.pack('<L', size_with_flag)
        self.conn.sendall(header + data)

    def recv_metadata(self):
        """Receive a metadata packet, assert header MSB==1, and return the deserialized object.

        Returns None if the connection was closed while reading.
        """
        header = self.recvall(4)
        if not header:
            return None
        size_with_flag = struct.unpack('<L', header)[0]
        # MSB should be 1 for metadata
        msb = (size_with_flag >> 31) & 1
        assert msb == 1, "Header MSB not set; not a metadata packet"
        size = size_with_flag & 0x7FFFFFFF
        payload = self.recvall(size)
        if payload is None:
            return None
        return json.loads(payload.decode('utf-8'))

    def has_data(self):
        """Check if there is data waiting to be read on the socket, non-blocking."""
        ready, _, _ = select.select([self.conn], [], [], 0)
        return bool(ready)

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
        try:
            self.server_socket.close()
        except Exception:
            pass

connection = Connection()

# Get initial screen dimensions to configure the encoder
# H.264 requires width and height to be divisible by 2.
sample_img = ImageGrab.grab()
width, height = sample_img.size
width = (width // 2) * 2
height = (height // 2) * 2

# 2. Encoder Setup (The Black Box)
encoder = av.CodecContext.create('libx264', 'w')
encoder.width = width
encoder.height = height
encoder.pix_fmt = 'yuv420p'
# Optimize for real-time streaming over file size
encoder.options = {'preset': 'ultrafast', 'tune': 'zerolatency', 'bframes': '0'}

MAX_IN_FLIGHT_FRAMES = 1
in_flight_frames = 0

try:
    while True:
        # Check for any pending metadata (specifically acknowledgments)
        while connection.has_data():
            metadata = connection.recv_metadata()
            if metadata and metadata.get("type") == "ack":
                in_flight_frames = max(0, in_flight_frames - 1)
            elif metadata is None:
                raise ConnectionResetError("Client disconnected cleanly")

        # Don't send a new frame if we've reached the limit
        if in_flight_frames >= MAX_IN_FLIGHT_FRAMES:
            time.sleep(0.001)  # small sleep to avoid busy-waiting 100% CPU
            continue

        start_time = time.time()

        # Capture screen and convert to a numpy array (RGB -> BGR for consistency)
        img = ImageGrab.grab(bbox=(0, 0, width, height))
        img_np = np.array(img)[:, :, ::-1] 

        # Pass the numpy array to PyAV. It handles the YUV conversion internally.
        frame = av.VideoFrame.from_ndarray(img_np, format='bgr24')
        
        # Encode the frame into H.264 packets
        packets = encoder.encode(frame)

        for packet in packets:
            # Use the bytes() constructor to extract the raw H.264 data
            data = bytes(packet)
            # Send via Connection helper which prefixes the length header
            connection.send_packet(data)
            in_flight_frames += 1
            print(f"Sent packet of size: {stringutils.metricunits(len(data), 'B')}, In-flight: {in_flight_frames}")

except ConnectionResetError:
    print("Client disconnected.")
finally:
    connection.close()