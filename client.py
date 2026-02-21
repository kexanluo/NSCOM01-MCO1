import socket
import struct
import os
import hashlib
import time   
import config
import os
from tkinter import Tk, filedialog

# ===============================
# Protocol Constants
# ===============================
DEFAULT_PORT = 5555   
HANDSHAKE_REQUEST  = 1
HANDSHAKE_RESPONSE = 2
ACK                = 3
REQUEST_LIST_FILES = 3
RESPONSE_LIST_FILES = 4
EOF                = 7
HEADER_FORMAT = "!B I H 32s"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAX_PAYLOAD = 1024
TIMEOUT = 0.5          # ✅ shorter timeout for broadcast handshake
MAX_RETRIES = 5
HASH_SIZE = 32  # SHA-256 digest size
EMPTY_HASH = b"\x00" * 32

#FOR TESTING NA CONSTANT
UPLOAD_REQ = 7     
UPLOAD_CHUNK = 8


# ===============================
# Packet Format with SHA-256
# ===============================
def make_packet(msg_type, seq, payload=b""):
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


def parse_packet(packet):
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


class ReliableUDPClient:

    def __init__(self, server_port):
        # ✅ Start with broadcast address (no IP needed)
        self.server_addr = ("255.255.255.255", server_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # ✅ Enable broadcast sending
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.settimeout(TIMEOUT)
        self.seq = 0
        self.session_active = False

    def select_file(self):
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

    # ---------------------------
    # Session Establishment (Broadcast Handshake)
    # ---------------------------
    def connect(self):
        print("\nHANDSHAKE_REQUEST")

        for attempt in range(1, 4):   # Exactly 3 attempts
            print(f"Retry {attempt}/3...")
            syn_pkt = make_packet(HANDSHAKE_REQUEST, self.seq)
            self.sock.sendto(syn_pkt, self.server_addr)

            try:
                data, addr = self.sock.recvfrom(4096)
                msg_type, seq, _ = parse_packet(data)

                if msg_type is None:
                    print("Corrupted packet ignored.")
                elif msg_type == HANDSHAKE_RESPONSE:
                    print(f"\nServer found at ({addr[0]})")
                    self.server_addr = addr
                    self.session_active = True
                    # ✅ Update client seq to match next expected seq
                    # Server response seq = client seq + 1, so client seq should also become +2
                    self.seq = seq + 1
                    return True

            except socket.timeout:
                if attempt < 3:
                    time.sleep(0.5)  # Short delay before retrying

        print("\nNo active server found.")
        return False
    
    
    def request_upload(self):
        file_path, filename, file_size = self.select_file()
        if file_path is None:
            return

        # Use the integer constant to match server
        payload = f"{file_size} {filename}".encode()
        header = struct.pack(
            HEADER_FORMAT,
            UPLOAD_REQ,   # 7 matches server check
            self.seq,
            len(payload),
            EMPTY_HASH
        )

        packet = header + payload
        self.sock.sendto(packet, self.server_addr)
        print(f"Upload request sent. SEQ: {self.seq}")

        # ✅ Increment seq after sending
        self.seq += 1

        # Optionally, wait for an ACK from server
        try:
            data, addr = self.sock.recvfrom(4096)
            msg_type, seq, plen, hash_value = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
            if msg_type == UPLOAD_REQ:  # server will echo type as integer
                print("Server acknowledged upload request.")
        except socket.timeout:
            print("No ACK received from server for upload request.")

        return file_path

    #Request and receive file list
    def request_list_files(self):
        header = struct.pack(
            HEADER_FORMAT,
            REQUEST_LIST_FILES,
            self.seq,       # current client seq
            0,
            EMPTY_HASH
        )
        self.sock.sendto(header, self.server_addr)
        
        # ✅ Increment seq immediately after sending
        self.seq += 1

        try:
            data, addr = self.sock.recvfrom(4096)
            msg_type, seq, plen, hash_value = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
            payload = data[HEADER_SIZE:HEADER_SIZE + plen]

            if msg_type == RESPONSE_LIST_FILES:
                file_string = payload.decode()
                file_list = file_string.split("\n") if file_string else []
                return file_list
            else:
                print("Unexpected response type.")
                return None
        except socket.timeout:
            print("Server did not respond.")
            return None
        
    def close(self):
        self.sock.close()
        print("\nClient socket closed.")
  
# ===============================
# Main Client Program
# ===============================

if __name__ == "__main__":
    print(f"Simple File Transfer Application (UDP)")
    print("        CLIENT INTERFACE")
    print(f"\nCreated by: Ke, Xan Luo and Mojica, Maurienne Marie\n\n")
    config.checkDirectory("Client")
    
    while True:
        print("ENTER [1] TO START HANDSHAKE_REQUEST")
        user_input = input(">>> ").strip()
        if user_input == "1":
            break
        print("\nInvalid input. Please enter 1 to start handshake.\n")
        
    client = ReliableUDPClient(DEFAULT_PORT)
    if not client.connect():
        exit()
    os.system('cls')

    while True:
        print("\n====== CLIENT MENU ======")
        print("1. Download File from Server")
        print("2. Upload File to Server")
        print("3. Exit")

        choice = input("Choose option: ")

        if choice == "1":
            files = client.request_list_files()
            fname = input("\nEnter filename to download: ")

        elif choice == "2":
            # Show local file picker and send upload request
            client.request_upload()

        elif choice == "3":
            client.close()
            break