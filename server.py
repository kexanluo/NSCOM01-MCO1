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
folder = Path(__file__).resolve().parent / "nscomServer"

HEADER_FORMAT = "!BIH32s"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
EMPTY_HASH = b"\x00" * 32

UPLOAD_PLEN = 0
RECEIVED_STATE = False
SEQ = 0

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

def hashDigest(content):
    return hashlib.sha256(content).digest()

def receive_message():
    while True:
        data, client_addr = sock.recvfrom(BUFFER_SIZE)

        message_type, seq, plen, hash_value = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
        payload = data[HEADER_SIZE:HEADER_SIZE + plen]
        SEQ = seq

        if message_type == 1:
            print(f"[SERVER] HANDSHAKE REQUEST from {client_addr[0]} | SEQ: {SEQ}")
            header = struct.pack(HEADER_FORMAT, 2, seq + 1, 0, EMPTY_HASH)
            sock.sendto(header, client_addr)
            SEQ = seq + 1
            print(f"[SERVER] HANDSHAKE RESPONSE sent to {client_addr[0]} | SEQ: {SEQ}")
        elif message_type == 3:
            print(f"[SERVER] FILE LIST REQUEST from {client_addr[0]} | SEQ: {SEQ}")
            files = [f.name for f in folder.iterdir() if f.is_file()]
            payload = json.dumps(files).encode()
            header = struct.pack(HEADER_FORMAT, 4, seq + 1, len(payload), hashDigest(payload))
            SEQ = seq + 1
            sock.sendto(header + payload, client_addr)
            print(f"[SERVER] FILE LIST RESPONSE sent to {client_addr[0]} | SEQ: {SEQ}")
        elif message_type == 444:
            if checkFileExist(payload):
                print(f"[SERVER] DOWNLOAD REQUEST from %s (%s) ACKNOWLEDGED", client_addr[0], payload)
                CLIENT_ACK = 0
                RECEIVED_STATE = False
                header = struct.pack(HEADER_FORMAT, 4, seq + 1, 0, EMPTY_HASH)
                sock.sendto(header, client_addr)
            else:
                print(f"[SERVER] DOWNLOAD REQUEST ERROR from %s (%s) file does not exist", client_addr[0], payload)
                header = struct.pack(HEADER_FORMAT, 5, seq + 1, 0, EMPTY_HASH)
                sock.sendto(header, client_addr)
        elif message_type == "DOWNLOAD_CHR": # Chunk Received
            print(f"[SERVER] DOWNLOAD RECEIVED by %s (%s)", client_addr[0], hash_value)
            RECEIVED_STATE = True
            CLIENT_ACK = payload
        elif message_type == "UPLOAD_REQ":
            print(f"[SERVER] UPLOAD REQUEST from %s (%s) ACKNOWLEDGED", client_addr[0], payload)
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
receive_message()