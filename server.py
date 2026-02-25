import config # Initial Configuration (Checking for directory)
import socket
import threading
import json
import os
import time
import sys
import struct
import hashlib
from datetime import datetime
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY = b"f83kL9x2Qa7mZpR1tY6vBn4cHd8sW0eJ" # Key used for encryption

PORT = 5555
MAX_RETRIES = 3
BUFFER_SIZE = 1052 # Max Packet Size is 1024 but with encryption, it becomes 1052
MAX_PAYLOAD = 1024
folder = Path(__file__).resolve().parent / "nscomServer" # Directory Path of Server

HEADER_FORMAT = "!BIH32s"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
CHUNK_SIZE = MAX_PAYLOAD - HEADER_SIZE
EMPTY_HASH = b"\x00" * 32
SESSION_TIMEOUT = 180
CURRENT_CLIENT = None # Saves the addr of the connected client
CLIENT_CONNECTED = False
SEQ = 0

TEST_MODE = False # Triggers test mode when turned on
delay_packet = 0 # Index used for test mode (which packet to delay)

# Temporary Holder for Upload and Download
HOLDER_LEN = 0
HOLDER_FNAME = ""

def noServerActive(): # Checks for any active server. Used by server to check for any active server within the network
    temp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    temp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    temp_sock.settimeout(0.5)
    try:
        header = struct.pack(HEADER_FORMAT, 255, 0, 0, EMPTY_HASH)
        temp_sock.sendto(encrypt(header), ("255.255.255.255", 5555))
        data, addr = temp_sock.recvfrom(BUFFER_SIZE)
        data = decrypt(data)
        print("[ERROR] There is an active server listening. Terminating program ...")
        sys.exit()
    except socket.timeout:
        return
    finally:
        temp_sock.close()

def display_message(message): # Properly prints server message without removing [server_command]
    sys.stdout.write('\r\033[K')
    sys.stdout.flush()
    print(message)
    sys.stdout.write(f"[server_command]: ")
    sys.stdout.flush()

def timestamp(): # Timestamp getter
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def startSocket(): # Creates the socket for server
    global sock

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", PORT))
    display_message(f"[SERVER] {timestamp()} SOCKET - Server Listening...")

def checkFileExist(filename): # It is used to check if the file exists inside the server directory.
    file_path = folder / filename

    if file_path.exists():
        return 1
    else:
        return 0

def hashDigest(content): # Used to hash payload
    return hashlib.sha256(content).digest()

def encrypt(data): # Used to encrypt packet
    nonce = os.urandom(12)
    aesgcm = AESGCM(KEY)
    ciphertext = aesgcm.encrypt(nonce, data, None)
    return nonce + ciphertext


def decrypt(data): # Used to decrypt packet
    nonce = data[:12]
    ciphertext = data[12:]
    aesgcm = AESGCM(KEY)
    return aesgcm.decrypt(nonce, ciphertext, None)

def send_file(client_addr): # Used for sending file. (Client Download)
    global SEQ
    index = 0 # Used in TEST_MODE

    display_message(f"[SERVER] {timestamp()} Starting to send file chunks to {client_addr[0]}.")
    with open(folder/HOLDER_FNAME, "rb") as f:
        while True:
            retry = 0
            payload = f.read(CHUNK_SIZE)

            if TEST_MODE == True and index <= delay_packet: # If TEST_MODE is activated and index == delay_packet, it will simulate packet loss.
                if index == delay_packet:
                    display_message(f"[SERVER] {timestamp()} TEST MODE - Simulating packet loss.")
                    time.sleep(0.7)
                    index += 1
                else:
                    index += 1

            if not payload:
                display_message(f"[SERVER] {timestamp()} DOWNLOAD COMPLETED File ({HOLDER_FNAME}) is successfully received by {client_addr[0]}.")
                break

            SEQ += 1
            hash_value = hashDigest(payload)
            header = struct.pack(HEADER_FORMAT, 13, SEQ, len(payload), hash_value)
            sock.sendto(encrypt(header + payload), client_addr)
            display_message(f"[SERVER] {timestamp()} DOWNLOAD in progress. File Chunk of ({HOLDER_FNAME}) sent to {client_addr[0]}. {hash_value.hex()} | SEQ: {SEQ}")

            sock.settimeout(0.5) # Timeout for sending file
            while retry < MAX_RETRIES:
                try:
                    data, client_addr = sock.recvfrom(BUFFER_SIZE)
                    data = decrypt(data)
                    message_type, seq, plen, hash_value = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
                    ack_payload = data[HEADER_SIZE:HEADER_SIZE + plen]

                    if message_type == 14 and int(ack_payload.decode()) == SEQ:
                        display_message(f"[SERVER] {timestamp()} FILE CHUNK RECEIVED by {client_addr[0]} ACK: {ack_payload.decode()} | SEQ: {seq}")
                        SEQ += 1
                        break
                    elif message_type == 255: # Handles Another Session Checking for Active Server
                        sock.sendto(encrypt(b""), client_addr)
                        continue
                    else:
                        continue
                except (socket.timeout, ConnectionResetError): # Error handling
                    sock.sendto(encrypt(header + payload), client_addr)
                    display_message(f"[SERVER] {timestamp()} File Chunk SEQ: {SEQ} not ACKNOWLEDGED by {client_addr[0]}. Resending SEQ: {SEQ} {retry + 1}/3")
                    retry += 1
            else: # Triggered when maximun retries reached.
                display_message(f"[SERVER] {timestamp()} DOWNLOAD ERROR - Maximum 3 retries sent with no ACKNOWLEDGEMENT from {client_addr[0]}. Download Failed.")
                return

def receive_file(client_addr): # Used for uploading file. (Client Upload)
    global SEQ
    index = 0

    chunks = {} # Temporary holder for file chunks
    bytes_received = 0
    retry = 0
    
    sock.settimeout(0.5)
    while bytes_received < HOLDER_LEN and retry < MAX_RETRIES:
        try:
            data, addr = sock.recvfrom(BUFFER_SIZE)
            data = decrypt(data)
            message_type, seq, plen, hash_value = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
            payload = data[HEADER_SIZE:HEADER_SIZE + plen]
            
            if message_type is None: # Handles unrecognized packet
                continue

            if not client_addr == addr: # Disregard any packet not sent by current client
                continue
            
            if message_type == 11: # Correct message_type
                if not hashDigest(payload) == hash_value: # Checks if the payload is tampered. If so, disregard
                    continue

                if seq not in chunks: # Checks if the seq of chunks is already inside chunks{}, if not this block will run.
                    chunks[seq] = payload
                    bytes_received += len(payload)
                    display_message(f"[SERVER] {timestamp()} UPLOAD in progress. File Chunk of ({HOLDER_FNAME}) sent by {client_addr[0]} received. {hash_value.hex()} | SEQ: {seq}")
                    SEQ = seq + 1
                    ack_payload = str(seq).encode()
                    header = struct.pack(HEADER_FORMAT, 12, SEQ, len(ack_payload), hashDigest(ack_payload))
                    if TEST_MODE == True and index <= delay_packet: # Triggered when test run is on
                        if index == delay_packet:
                            display_message(f"[SERVER] {timestamp()} TEST MODE - Simulating packet loss by not sending ACK.")
                            time.sleep(0.7)
                            index += 1
                        else:
                            index += 1
                    sock.sendto(encrypt(header + ack_payload), client_addr)
                    display_message(f"[SERVER] {timestamp()} UPLOAD in progress. File Chunk Acknowledgement sent to {client_addr} ACK: {seq} | SEQ: {SEQ}")
                    retry = 0
        except socket.timeout: # Handles error
            display_message(f"[SERVER] {timestamp()} UPLOAD PAUSED - No new chunk received after the timeout. {client_addr[0]} disconnected or crashed. Retrying {retry + 1}/3 ...")
            retry += 1

            if retry == 3: # Maximum retries reached
                display_message(f"[SERVER] {timestamp()} UPLOAD ERROR - No new chunk received after 3 retries. {client_addr[0]} disconnected or crashed. Upload Failed.")
                return

    with open(folder/HOLDER_FNAME, "wb") as f: # If complete file chunks received. This will run
        for i in sorted(chunks.keys()):
            f.write(chunks[i])
    display_message(f"[SERVER] {timestamp()} UPLOAD SUCCESS - ({HOLDER_FNAME}) is now available inside the server directory.")

def receive_message(): # Handles all incoming message except upload and sending transaction
    global SEQ, HOLDER_FNAME, HOLDER_LEN, CLIENT_CONNECTED, CURRENT_CLIENT

    while True:

        try:
            data, client_addr = sock.recvfrom(BUFFER_SIZE)
            data = decrypt(data)
            message_type, seq, plen, hash_value = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
            payload = data[HEADER_SIZE:HEADER_SIZE + plen]
            
            if not message_type == 255 and CLIENT_CONNECTED: # Only updates the SEQ if the message came from current client
                if CURRENT_CLIENT[0] == client_addr[0]:
                    SEQ = seq

            if message_type == 255: # Used by another server checking if any server is listening within the network
                sock.sendto(encrypt(b""), client_addr)
            elif message_type == 253: # FIN
                header = struct.pack(HEADER_FORMAT, 252, seq + 1, 0, EMPTY_HASH) # Sends FIN_ACK
                sock.sendto(encrypt(header), client_addr)
                display_message(f"[SERVER] {timestamp()} Client {CURRENT_CLIENT[0]} disconnecting. (FIN) | SEQ: {seq}")
                display_message(f"[SERVER] {timestamp()} FIN-ACK Sent to client {CURRENT_CLIENT[0]}. Server accepting new client. | SEQ: {seq + 1}")
                sock.settimeout(None)
                CURRENT_CLIENT = None
                CLIENT_CONNECTED = False
            elif message_type == 1: # HANDSHAKE_REQUEST
                if CLIENT_CONNECTED == False:
                    SEQ = seq
                    display_message(f"[SERVER] {timestamp()} HANDSHAKE REQUEST from {client_addr[0]} | SEQ: {SEQ}")
                    CURRENT_CLIENT = client_addr
                    header = struct.pack(HEADER_FORMAT, 2, seq + 1, 0, EMPTY_HASH) # Sends HANDSHAKE_RESPONSE
                    sock.sendto(encrypt(header), client_addr)
                    SEQ = seq + 1
                    display_message(f"[SERVER] {timestamp()} HANDSHAKE RESPONSE sent to {client_addr[0]} | SEQ: {SEQ}")
                    CLIENT_CONNECTED = True
                    sock.settimeout(SESSION_TIMEOUT)
                else:
                    display_message(f"[SERVER] {timestamp()} HANDSHAKE REQUEST from {client_addr[0]} Rejected. Current client is still active.") # If current client is still connected, reject any incoming handshake request
            elif message_type == 3: # FILE LIST REQUEST
                display_message(f"[SERVER] {timestamp()} FILE LIST REQUEST from {client_addr[0]} | SEQ: {SEQ}")
                files = [f.name for f in folder.iterdir() if f.is_file()] # Checks the nscomServer directory for the list of files available
                payload = json.dumps(files).encode()
                header = struct.pack(HEADER_FORMAT, 4, seq + 1, len(payload), hashDigest(payload)) # Hash the Content to ensure complete and no error
                SEQ = seq + 1
                sock.sendto(encrypt(header + payload), client_addr) # sends the header containing message_type 4 and payload containing the list of files.
                display_message(f"[SERVER] {timestamp()} FILE LIST RESPONSE sent to {client_addr[0]} | SEQ: {SEQ}")
            elif message_type == 5: # Download Request
                display_message(f"[SERVER] {timestamp()} DOWNLOAD REQUEST from {client_addr[0]} ({HOLDER_FNAME}) | SEQ: {SEQ}")

                if checkFileExist(payload.decode()): # This block will run if the file exists
                    HOLDER_FNAME = payload.decode()
                    HOLDER_LEN = os.path.getsize(folder/HOLDER_FNAME)
                    payload = f"{HOLDER_LEN}".encode() # Stores the size of the file inside the payload
                    header = struct.pack(HEADER_FORMAT, 6, seq + 1, len(payload), EMPTY_HASH) # DOWNLOAD ACK = 6
                    sock.sendto(encrypt(header + payload), client_addr) # Sends the header and payload containing the size of the file
                    SEQ = seq + 1
                    display_message(f"[SERVER] {timestamp()} DOWNLOAD ACKNOWLEDGEMENT sent to {client_addr[0]} ({HOLDER_FNAME} - {HOLDER_LEN} bytes) | SEQ: {SEQ}")
                    send_file(client_addr) # Starts sending file chunk to client.
                    sock.settimeout(SESSION_TIMEOUT) # Reset timeout
                else: # If file doesn't exists
                    SEQ = seq + 1
                    display_message(f"[SERVER] {timestamp()} DOWNLOAD REQUEST ERROR sent to {client_addr[0]} ({payload.decode()}) file does not exist | SEQ: {SEQ}")
                    header = struct.pack(HEADER_FORMAT, 7, seq + 1, 0, EMPTY_HASH) # message_type = 7
                    sock.sendto(encrypt(header), client_addr)
            elif message_type == 8: # Upload Request
                payload = payload.decode()
                payload_parts = payload.split("?", 1) # Splits the payload SIZE?FILENAME

                if not checkFileExist(payload_parts[1]): # Checks first if file is already inside the nscomServer directory. If not, this block will run
                    HOLDER_LEN = int(payload_parts[0])
                    HOLDER_FNAME = payload_parts[1]
                    display_message(f"[SERVER] {timestamp()} UPLOAD REQUEST from {client_addr[0]} ({HOLDER_FNAME} - {HOLDER_LEN} bytes) | SEQ: {SEQ}")
                    header = struct.pack(HEADER_FORMAT, 9, seq + 1, 0, EMPTY_HASH) # Upload Ack
                    SEQ = seq + 1
                    sock.sendto(encrypt(header), client_addr)
                    display_message(f"[SERVER] {timestamp()} UPLOAD ACKNOWLEDGEMENT sent to {client_addr[0]} ({HOLDER_FNAME} - {HOLDER_LEN} bytes) | SEQ: {SEQ}")
                    receive_file(client_addr) # Starts receiving file
                    sock.settimeout(SESSION_TIMEOUT) # Resets timeout
                else: # If file already exists
                    display_message(f"[SERVER] {timestamp()} UPLOAD REQUEST from {client_addr[0]} ({payload_parts[1]} - {int(payload_parts[0])} bytes) | SEQ: {SEQ}")
                    header = struct.pack(HEADER_FORMAT, 10, seq + 1, 0, EMPTY_HASH) # Upload Refused
                    SEQ = seq + 1
                    sock.sendto(encrypt(header), client_addr)
                    display_message(f"[SERVER] {timestamp()} UPLOAD REFUSED sent to {client_addr[0]} ({payload_parts[1]} - {int(payload_parts[0])} bytes) FILE EXISTS inside the server directory | SEQ: {SEQ}")
        except socket.timeout: # Handles socket timeout
            display_message(f"[SERVER] {timestamp()} SOCKET TIMEOUT - No new request received within {SESSION_TIMEOUT} seconds. Server is now accepting new client.")
            sock.settimeout(None)
            if CURRENT_CLIENT:
                header = struct.pack(HEADER_FORMAT, 254, seq + 1, 0, EMPTY_HASH)
                sock.sendto(encrypt(header), CURRENT_CLIENT)
            CLIENT_CONNECTED = False
            CURRENT_CLIENT = None
            continue
        except ConnectionResetError: # Handles connection reset error
            display_message(f"[SERVER] {timestamp()} SOCKET TIMEOUT - Connection Reset Error. Server is now accepting new client.")
            CLIENT_CONNECTED = False
            sock.settimeout(None)
            CURRENT_CLIENT = None
            continue

# MAIN PROGRAM
os.system('cls')
print(f"Simple File Transfer Application (UDP)")
print("        SERVER INTERFACE")
print(f"\nCreated by: Ke, Xan Luo and Mojica, Maurienne Marie\n\n")
input("PRESS [ENTER] TO START THE SERVER")
os.system('cls')

noServerActive() # Checks if there are open server available. Terminate if there is an open server.
config.checkDirectory("Server") # Checks if nscomServer directory is available
startSocket()
threading.Thread(target=receive_message, daemon=True).start() # Threading for receive_message or listener of the server

command = ""
while not command == "CLOSE_SERVER":
    command = input().strip()

    if not command == "":
        parts = command.split()
    else:
        display_message(f"[SERVER] {timestamp()} Invalid server command. (command: {command})")
        continue

    if command == "CLOSE_SERVER": # Used to stop the server
        print(f"[SERVER] {timestamp()} Listening stopped. All pending processes stopped.")

        if CLIENT_CONNECTED:
            header = struct.pack(HEADER_FORMAT, 253, SEQ, 0, EMPTY_HASH) # If client is still connected, server sends FIN
            sock.sendto(encrypt(header), CURRENT_CLIENT)
    elif command == "TEST_ON": # Activates Test Mode
        TEST_MODE = True
        display_message(f"[SERVER] {timestamp()} TEST MODE is now ON.")
    elif command == "TEST_OFF":
        TEST_MODE = False # Deactivates Test Mode
        display_message(f"[SERVER] {timestamp()} TEST MODE is now OFF.")
    elif parts[0] == "SET_SESSION_TIMEOUT": # Used to set the timeout, handles idle client
        if len(parts) == 2 and parts[1].isdigit():
            SESSION_TIMEOUT = int(parts[1])
            sock.settimeout(int(parts[1]))
            display_message(f"[SERVER] {timestamp()} SESSION TIMEOUT updated to {int(parts[1])} seconds.")
        else:
            display_message(f"[SERVER] Usage: SET_SESSION_TIMEOUT <seconds>")
    elif parts[0] == "SET_DELAY_INDEX": # Adjusts which packet to delay
        if len(parts) == 2 and parts[1].isdigit():
            delay_packet = int(parts[1])
            display_message(f"[SERVER] {timestamp()} DELAY PACKET INDEX updated to index {int(parts[1])}.")
        else:
            display_message(f"[SERVER] Usage: SET_DELAY_INDEX <index>")
    else: # Handles invalid commands
        display_message(f"[SERVER] {timestamp()} Invalid server command. (command: {command})")