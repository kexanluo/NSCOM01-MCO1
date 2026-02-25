import socket
import struct
import os
import hashlib
import threading
import time   
import config
import sys
import json
from tkinter import Tk, filedialog
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ===============================
# Protocol Constants
# ===============================
DEFAULT_PORT = 5555
HEADER_FORMAT = "!B I H 32s"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
BUFFER_SIZE = 1052 # Size for Encrypted packet
MAX_PAYLOAD = 1024
CHUNK_SIZE = MAX_PAYLOAD - HEADER_SIZE
TIMEOUT = 0.5
MAX_RETRIES = 5
HASH_SIZE = 32  # SHA-256 digest size
EMPTY_HASH = b"\x00" * 32
KEY = b"f83kL9x2Qa7mZpR1tY6vBn4cHd8sW0eJ"


packet_buffer = None # Used for storing any buffer received by background listener that is not intended for FIN/FIN-ACK
FIN_ACK = False # Server ack for FIN flag
listener_event = threading.Event() # Listener event for threading (background_listener)

# ===============================
# Packet Format with SHA-256
# ===============================
def make_packet(msg_type, seq, payload=b""): # Makes the packet
    plen = len(payload)
    # If payload exists, hash it
    if plen > 0:
        hash_value = hashlib.sha256(payload).digest()
    else:
        hash_value = b"\x00" * 32   # Empty hash for handshake

    header = struct.pack(
        HEADER_FORMAT,
        msg_type,
        seq,
        plen,
        hash_value
    )
    return header + payload

def encrypt(data): # Encrypts packet
    nonce = os.urandom(12)
    aesgcm = AESGCM(KEY)
    ciphertext = aesgcm.encrypt(nonce, data, None)
    return nonce + ciphertext


def decrypt(data): # Decrypts packet
    nonce = data[:12]
    ciphertext = data[12:]
    aesgcm = AESGCM(KEY)
    return aesgcm.decrypt(nonce, ciphertext, None)

def parse_packet(packet): # Parses the packet
    if len(packet) < HEADER_SIZE:
        return None, None, None
    msg_type, seq, plen, hash_value = struct.unpack(
        HEADER_FORMAT,
        packet[:HEADER_SIZE]
    )
    payload = packet[HEADER_SIZE:HEADER_SIZE + plen]
    # Verify hash only if payload exists
    if plen > 0:
        calc_hash = hashlib.sha256(payload).digest()
        if calc_hash != hash_value:
            return None, None, None
    return msg_type, seq, payload

def request_upload(self): # Used for requesting upload to server
        file_path, filename, file_size = self.select_file()
        if file_path is None:
            print("File selection cancelled.")
            input("\n\nPRESS [ENTER] TO GO BACK TO MAIN MENU")
            return None, None, None

        payload = f"{file_size}?{filename}".encode()
        header = struct.pack(
            HEADER_FORMAT,
            8,
            self.seq,
            len(payload),
            EMPTY_HASH
        )

        packet = header + payload
        self.sock.sendto(encrypt(packet), self.server_addr)
        print(f"Upload request sent. SEQ: {self.seq}")

        # Increment seq after sending
        self.seq += 1

        # wait for an ACK from server
        try:
            data, addr = self.sock.recvfrom(BUFFER_SIZE)
            data = decrypt(data)
            msg_type, seq, plen, hash_value = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
            if msg_type == 9:  # 9 means ACK signaling client can start sending file chunks
                print("Server acknowledged upload request.\n")
                return file_path, filename, file_size
            elif msg_type == 10: # 10 means server acknowledged the upload but refused to accept because file name exists inside server's directory
                self.seq += 1
                print("Server refused to accept the upload request due to possible duplication of file. Rename the file and try again later.\n")
                input("\n\nPRESS [ENTER] TO GO BACK TO MAIN MENU")
                return None, None, None
        except (socket.timeout, ConnectionResetError): # Handles Error
            print("No ACK received from server for upload request.")
            input("\n\nPRESS [ENTER] TO GO BACK TO MAIN MENU")
            return None, None, None

def handle_upload(self, file_path, fname, fsize): # Handles Upload
    print(f"\n[CLIENT] Uploading file '{fname}' ({fsize} bytes)...")
    bytes_sent = 0
    with open(file_path, "rb") as f:
        while True:
            retry = 0
            payload = f.read(CHUNK_SIZE)

            if not payload: # This block will run if there is no chunk left
                self.seq += 1
                print(f"\n[Client] File uploaded successfully !")
                input("\n\nPRESS [ENTER] TO GO BACK TO MAIN MENU")
                break

            self.seq += 1
            packet = make_packet(11, self.seq, payload) # Creates the packet
            self.sock.sendto(encrypt(packet), self.server_addr) # Sends the packet after encryption
            bytes_sent += len(payload)
            print(f"\rSent {bytes_sent}/{fsize} bytes", end="")

            self.sock.settimeout(0.5) # Sets the timeout
            while retry < MAX_RETRIES:
                try:
                    data, server_addr = self.sock.recvfrom(BUFFER_SIZE)
                    data = decrypt(data)
                    message_type, seq, ack_payload = parse_packet(data)

                    if message_type == 12 and int(ack_payload.decode()) == self.seq:
                        self.seq = seq
                        break
                    else:
                        continue
                except (socket.timeout, ConnectionResetError): # Handles Error
                    self.sock.sendto(encrypt(packet), self.server_addr)
                    print(f"\n[Client] File Chunk SEQ: {self.seq} not acknowledged. Resending SEQ: {self.seq} {retry + 1}/5")
                    retry += 1
            else:
                print(f"\n[Client] Upload error. Maximum 5 retries sent with no acknowledgement from server. Upload failed.")
                input("\n\nPRESS [ENTER] TO GO BACK TO MAIN MENU")
                return
        
def handle_download(client): # Handles Download
        os.system('cls')
        print("Files Available (Server):\n")
        files = client.request_list_files() # Requests List of Files Available inside nscomServer directory
        if not files:
            print("No files received from server.")
            input("PRESS [ENTER] TO GO BACK TO MAIN MENU")
            return

        for i, f in enumerate(files, 1):
            print(f"{i}. {f}")
        fname = input("\nEnter filename to download [filename.ext]: ")
        client_folder = Path(__file__).resolve().parent / "nscomClient"
        client_folder.mkdir(exist_ok=True)
        file_path = client_folder / fname
        if fname == "":
            print(f"\nERROR: No filename entered.")
            input("PRESS [ENTER] TO GO BACK TO MAIN MENU")
            return

        if file_path.exists():
            print(f"\nERROR: '{fname}' already exists in nscomClient.")
            print("Download cancelled to avoid overwrite.\n")
            input("PRESS [ENTER] TO GO BACK TO MAIN MENU")
            return
        # Proceeds if the file does not exists inside nscomClient directory
        client.request_download(fname)

class ReliableUDPClient:

    def __init__(self, server_port):
        # Start with broadcast address (no IP needed)
        self.server_addr = ("255.255.255.255", server_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Enable broadcast sending
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.settimeout(TIMEOUT)
        self.seq = 0
        self.session_active = False

    def select_file(self): # Used for selecting file (Upload)
        root = Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(
            initialdir=os.path.join(os.path.expanduser("~"), "Downloads"),
            title="Select file to upload"
        )
        root.destroy()
        if not file_path:
            print("No file selected.")
            return None, None, None
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        print(f"\nSelected File: {filename}")
        print(f"Path: {file_path}")
        print(f"Size: {file_size} bytes")
        return file_path, filename, file_size

    def background_listener(self): # Background Listener
        global packet_buffer, FIN_ACK

        while True:
            listener_event.wait()
            try:
                data, addr = self.sock.recvfrom(BUFFER_SIZE)
                data = decrypt(data)
                msg_type, seq, payload = parse_packet(data)

                if msg_type == 254: # Servers sends 254 if it detects client is idle within server's timeout
                    os.system('cls')
                    print(f"[CLIENT] Server terminated this session to accept new client. [REASON: Long idle time]")
                    os._exit(0)
                elif msg_type == 253: # Server's FIN
                    os.system('cls')
                    print(f"[CLIENT] Server terminated this session. [REASON: Server shutdown]")
                    os._exit(0)
                elif msg_type == 252: # Server acknowledges client's FIN
                    FIN_ACK = True
                else:
                    packet_buffer = data # Catches packet that is received in this thread that is intended for the other functions.

            except (socket.timeout, ConnectionResetError):
                continue

    # ---------------------------
    # Session Establishment (Broadcast Handshake)
    # ---------------------------
    def connect(self):
        print("HANDSHAKE_REQUEST")
        for attempt in range(1, 4):   # Exactly 3 attempts
            print(f"Retry {attempt}/3...")
            syn_pkt = make_packet(1, self.seq)
            self.sock.sendto(encrypt(syn_pkt), self.server_addr)

            try:
                data, addr = self.sock.recvfrom(BUFFER_SIZE)
                data = decrypt(data)
                msg_type, seq, _ = parse_packet(data)

                if msg_type is None:
                    print("Corrupted packet ignored.")
                elif msg_type == 2: # Handshake Response
                    print(f"\nServer found at ({addr[0]})")
                    self.server_addr = addr
                    self.session_active = True
                    # Update client seq to match next expected seq
                    self.seq = seq + 1
                    return True

            except (socket.timeout, ConnectionResetError): # Handles Error
                if attempt < 3:
                    time.sleep(0.5)  # Short delay before retrying

        print("\nNo active server found or Server is currently busy. ")
        return False
    
    def request_list_files(self):
        global packet_buffer

        header = struct.pack(
            HEADER_FORMAT,
            3,              # Request File List
            self.seq,       # current client seq
            0,
            EMPTY_HASH
        )
        self.sock.sendto(encrypt(header), self.server_addr)
        # Increment seq immediately after sending
        self.seq += 1
        try:
            data, addr = self.sock.recvfrom(BUFFER_SIZE)
            data = decrypt(data)
            msg_type, seq, plen, hash_value = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
            payload = data[HEADER_SIZE:HEADER_SIZE + plen]

            if msg_type == 4: # Response File List
                self.seq += 1
                file_list = json.loads(payload.decode())
                return file_list
            else:
                print("Unexpected response type.")
                return None
        except (socket.timeout, ConnectionResetError):
            if packet_buffer: # Checks if the packet is received by the background listener
                msg_type, seq, plen, hash_value = struct.unpack(HEADER_FORMAT, packet_buffer[:HEADER_SIZE])
                payload = packet_buffer[HEADER_SIZE:HEADER_SIZE + plen]

                if msg_type == 4:
                    self.seq += 1
                    file_list = json.loads(payload.decode())
                    packet_buffer = None
                    return file_list

            print("Server did not respond.")
            return None
    
    def request_download(self, fname): # Requesting download
        # Send download request
        payload = fname.encode()
        header = struct.pack(
            HEADER_FORMAT,
            5,  # download request
            self.seq,
            len(payload),
            EMPTY_HASH
        )

        self.sock.sendto(encrypt(header + payload), self.server_addr)
        print(f"[CLIENT] Download request sent for '{fname}' | SEQ: {self.seq}")
        self.seq += 1

        try:
            data, addr = self.sock.recvfrom(BUFFER_SIZE)
            data = decrypt(data)
            msg_type, seq, plen, hash_value = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
            payload = data[HEADER_SIZE:HEADER_SIZE + plen]
            if msg_type == 6: # Download Ack
                file_size = int(payload.decode())
                print(f"[CLIENT] Server acknowledged download request | File size: {file_size} bytes")
                print("Starting file transfer...")
                self.receive_file(fname, file_size)
            elif msg_type == 7: # Error, File does not exist inside nscomServer directory
                self.seq += 1
                print(f"[CLIENT] Server reports file '{fname}' does not exist.")
                input("\n\nPRESS [ENTER] TO GO BACK TO MAIN MENU")
                return
        except (socket.timeout, ConnectionResetError): # Handles error
            print("No response from server for download request.\n")
            input("\n\nPRESS [ENTER] TO GO BACK TO MAIN MENU")

    def receive_file(self, fname, file_size): # Receives file (Download)
        client_folder = Path(__file__).resolve().parent / "nscomClient"
        client_folder.mkdir(exist_ok=True)
        file_path = client_folder / fname
        
        print(f"\nDownloading: {fname}")
        print(f"\n[CLIENT] Receiving file '{fname}' ({file_size} bytes)...")
        
        chunks = {} # Temporarily stores chunks
        bytes_received = 0
        retry = 0
        
        while bytes_received < file_size and retry < MAX_RETRIES:
            try:
                data, addr = self.sock.recvfrom(BUFFER_SIZE)
                data = decrypt(data)
                msg_type, seq, payload = parse_packet(data)
                
                if msg_type is None:
                    print("Corrupted packet received, ignored.")
                    continue
                
                if msg_type == 13: # Download File Chunk
                    if seq not in chunks:
                        chunks[seq] = payload
                        bytes_received += len(payload)
                        print(f"\rReceived {bytes_received}/{file_size} bytes", end="")
                        self.seq = seq + 1
                        
                        payload = str(seq).encode()
                        header = struct.pack(
                            HEADER_FORMAT,
                            14, # Download File Chunk Ack
                            self.seq,
                            len(payload),
                            EMPTY_HASH
                        )
                        self.sock.sendto(encrypt(header + payload), self.server_addr)
                        retry = 0
            except (socket.timeout, ConnectionResetError):
                if retry == 0:
                    print("\n\n")

                print(f"Timeout waiting for file chunk, retrying... {retry + 1}/5")
                retry += 1

                if retry == MAX_RETRIES:
                    print("No response from server ... Download Failed.\n")
                    input("PRESS [ENTER] TO GO BACK TO MAIN MENU")
                    return
        
        self.seq += 1
        with open(file_path, "wb") as f: # Runs if the file chunks is completed
            for i in sorted(chunks.keys()):
                f.write(chunks[i])
        print(f"\n[CLIENT] File '{fname}' successfully downloaded!\n")
        input("PRESS [ENTER] TO GO BACK TO MAIN MENU")
            
    def close(self): # Closes the socket
        self.sock.close()
        print("\nClient socket closed.")


# ===============================
# Main Client Program
# ===============================

if __name__ == "__main__":
    os.system('cls')
    print(f"NSCOM Reliable UDP Protocol")
    print("     CLIENT INTERFACE")
    print(f"\nCreated by: Ke, Xan Luo and Mojica, Maurienne Marie\n\n")
    config.checkDirectory("Client")
    
    input("PRESS [ENTER] TO START HANDSHAKE_REQUEST")
    os.system('cls')
 
    client = ReliableUDPClient(DEFAULT_PORT)
    if not client.connect(): # Starts connecting to server
        exit()

    threading.Thread(target=client.background_listener, daemon=True).start() # Starts background_listener thread

    while True:
        listener_event.set()
        os.system('cls')
        print("====== CLIENT MENU ======")
        print("1. Download File from Server")
        print("2. Upload File to Server")
        print("3. Exit\n")

        choice = input("Choose option: ")

        if choice == "1": # Download
            listener_event.clear()
            handle_download(client)
            listener_event.set()

        elif choice == "2": # Upload
            listener_event.clear()
            # Show local file picker and send upload request
            file_path, fname, fsize = request_upload(client)
            if(file_path):
                handle_upload(client, file_path, fname, fsize)
            listener_event.set()

        elif choice == "3": # Exit
            header = struct.pack(HEADER_FORMAT, 253, client.seq, 0, EMPTY_HASH)
            client.sock.sendto(encrypt(header), client.server_addr) # Sends FIN to Server
            
            retry = 0
            while not FIN_ACK and retry <= MAX_RETRIES: # Handles Waiting for Ack until MAX_RETRIES with shorter timeout
                time.sleep(0.1)

                if retry == MAX_RETRIES:
                    print("Server did not acknowledge this termination. Program is now terminated !")
                    break

                retry += 1
                continue

            if not retry == MAX_RETRIES:
                print("Server acknowledged this termination. Program is now terminated !")
            os._exit(0)
            break

        else: # Handles Invalid input
            print("Invalid option.")
            input("\n\nPRESS [ENTER] TO CONTINUE")