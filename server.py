import config # Initial Configuration (Checking for directory)
import socket
import threading
import json
import os
import sys
import struct
import hashlib
from datetime import datetime
from pathlib import Path

PORT = 5555
MAX_RETRIES = 3
BUFFER_SIZE = 1024
folder = Path(__file__).resolve().parent / "nscomServer"

HEADER_FORMAT = "!BIH32s"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
EMPTY_HASH = b"\x00" * 32

UPLOAD_LEN = 0
UPLOAD_FNAME = ""
RECEIVED_STATE = False
SEQ = 0

file_chunks = {}

def display_message(message):
    sys.stdout.write('\r\033[K')
    sys.stdout.flush()
    print(message)
    sys.stdout.write(f"[server_command]: ")
    sys.stdout.flush()

def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def startSocket():
    global sock

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", PORT))
    display_message(f"[SERVER] {timestamp()} SOCKET - Server Listening...")

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
            display_message(f"[SERVER] {timestamp()} HANDSHAKE REQUEST from {client_addr[0]} | SEQ: {SEQ}")
            header = struct.pack(HEADER_FORMAT, 2, seq + 1, 0, EMPTY_HASH)
            sock.sendto(header, client_addr)
            SEQ = seq + 1
            display_message(f"[SERVER] {timestamp()} HANDSHAKE RESPONSE sent to {client_addr[0]} | SEQ: {SEQ}")
        elif message_type == 3:
            display_message(f"[SERVER] {timestamp()} FILE LIST REQUEST from {client_addr[0]} | SEQ: {SEQ}")
            files = [f.name for f in folder.iterdir() if f.is_file()]
            payload = json.dumps(files).encode()
            header = struct.pack(HEADER_FORMAT, 4, seq + 1, len(payload), hashDigest(payload))
            SEQ = seq + 1
            sock.sendto(header + payload, client_addr)
            display_message(f"[SERVER] {timestamp()} FILE LIST RESPONSE sent to {client_addr[0]} | SEQ: {SEQ}")
        elif message_type == 5:
            if checkFileExist(payload.strip()):
                display_message(f"[SERVER] {timestamp()} DOWNLOAD REQUEST from %s (%s) ACKNOWLEDGED", client_addr[0], payload.strip())
                RECEIVED_STATE = False
                #payload = #total size of the file
                header = struct.pack(HEADER_FORMAT, 5, seq + 1, 0, EMPTY_HASH)
                sock.sendto(header, client_addr)
            else:
                display_message(f"[SERVER] {timestamp()} DOWNLOAD REQUEST ERROR from %s (%s) file does not exist", client_addr[0], payload)
                header = struct.pack(HEADER_FORMAT, 5, seq + 1, 0, EMPTY_HASH)
                sock.sendto(header, client_addr)
        elif message_type == "DOWNLOAD_CHR": # Chunk Received
            print(f"[SERVER] {timestamp()} DOWNLOAD RECEIVED by %s (%s)", client_addr[0], hash_value)
            RECEIVED_STATE = True
            CLIENT_ACK = payload
        elif message_type == 7:
            payload = payload.decode()
            payload_parts = payload.split(" ")
            UPLOAD_LEN = int(payload_parts[0])
            UPLOAD_FNAME = payload_parts[1]
            print(f"[SERVER] {timestamp()} UPLOAD REQUEST from {client_addr[0]} ({UPLOAD_FNAME} - {UPLOAD_LEN} bytes)")
            header = struct.pack(HEADER_FORMAT, 8, seq + 1, 0, EMPTY_HASH)
            sock.sendto(header, client_addr)
        elif message_type == 9:
            #Start uploading ... To be continued ...

# MAIN PROGRAM
os.system('cls')
print(f"Simple File Transfer Application (UDP)")
print("        SERVER INTERFACE")
print(f"\nCreated by: Ke, Xan Luo and Mojica, Maurienne Marie\n\n")
input("PRESS [ENTER] TO START THE SERVER")
os.system('cls')

config.checkDirectory("Server")
startSocket()
threading.Thread(target=receive_message, daemon=True).start()

command = ""
while not command == "CLOSE_SERVER":
    command = input()
    if command == "CLOSE_SERVER":
        print(f"[SERVER] {timestamp()} Listening stopped. All pending processes stopped.")
    else:
        display_message(f"[SERVER] {timestamp()} Invalid server command. (command: {command})")