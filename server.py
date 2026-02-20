import config # Initial Configuration (Checking for directory)
import socket
import threading
import json
import os
import struct
from pathlib import Path

PORT = 5555
MAX_RETRIES = 3
BUFFER_SIZE = 1024
folder = Path.home() / "Desktop" / "nscomServer"

HEADER_FORMAT = "!BIH32s"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
EMPTY_HASH = b"\x00" * 32

UPLOAD_PLEN = 0
RECEIVED_STATE = False
CLIENT_ACK = 0

file_chunks = {}

def startSocket():
    global sock

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", PORT))
    print("[SERVER] SOCKET - Server Listening...")

def checkFileExist(filename):
    file_path = folder / filename

    if file_path.exists():
        return 1
    else:
        return 0

def receive_message():
    while True:
        data, client_addr = sock.recvfrom(BUFFER_SIZE)

        message_type, seq, plen, hash_value = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
        payload = data[HEADER_SIZE:HEADER_SIZE + plen]

        if message_type == 1:
            print(f"[SERVER] HANDSHAKE REQUEST from %s ACKNOWLEDGED", addr[0])
            header = struct.pack(HEADER_FORMAT, 2, seq + 1, 0, EMPTY_HASH)
            sock.sendto(header, client_addr)
        elif message_type == "DOWNLOAD_REQ":
            if checkFileExist(payload):
                print(f"[SERVER] DOWNLOAD REQUEST from %s (%s) ACKNOWLEDGED", addr[0], payload)
                CLIENT_ACK = 0
                RECEIVED_STATE = False
                header = struct.pack(HEADER_FORMAT, "DOWNLOAD_ACK", -1, 0, 0, 0)
                sock.sendto(header, client_addr)
            else:
                print(f"[SERVER] DOWNLOAD REQUEST ERROR from %s (%s) file does not exist", addr[0], payload)
                header = struct.pack(HEADER_FORMAT, "DOWNLOAD_ERROR", -1, 0, 0, 0)
                sock.sendto(header, client_addr)
        elif message_type == "DOWNLOAD_CHR": # Chunk Received
            print(f"[SERVER] DOWNLOAD RECEIVED by %s (%s)", addr[0], hash_value)
            RECEIVED_STATE = True
            CLIENT_ACK = payload
        elif message_type == "UPLOAD_REQ":
            print(f"[SERVER] UPLOAD REQUEST from %s (%s) ACKNOWLEDGED", addr[0], payload)
            UPLOAD_LEN = payload # Format: <File Size> SP <Filename>
            header = struct.pack(HEADER_FORMAT, "UPLOAD_ACK", -1, 0, 0, 0)
            sock.sendto(header, client_addr)
        elif message_type == "UPLOAD_CHUNK":
            print("hello world")

# MAIN PROGRAM
os.system('cls')
print(f"Simple File Transfer Application (UDP)")
print("        SERVER INTERFACE")
print(f"\nCreated by: Ke, Xan Luo and Mojica, Maurienne Marie\n\n")
input("PRESS [ENTER] TO START THE SERVER")
os.system('cls')

config.checkDirectory("Server")
startSocket()
threading.Thread(target=receive_message).start()