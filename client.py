import socket
import struct
import os
import hashlib
import time   

# ===============================
# Protocol Constants
# ===============================
DEFAULT_PORT = 5555   
HANDSHAKE_REQUEST  = 1
HANDSHAKE_RESPONSE = 2
ACK                = 3
DOWNLOAD_REQ       = 4
DOWNLOAD_ACK       = 5
DOWNLOAD_ERROR     = 6
UPLOAD_REQ         = 7
UPLOAD_ACK         = 8
UPLOAD_CHUNK       = 9
DATA               = 6
EOF                = 7
HEADER_FORMAT = "!B I H 32s"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAX_PAYLOAD = 1024
TIMEOUT = 0.5          # ✅ shorter timeout for broadcast handshake
MAX_RETRIES = 5
HASH_SIZE = 32  # SHA-256 digest size


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


# ===============================
# Reliable UDP Client Class
# ===============================

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


    # ---------------------------
    # Reliable Send (Stop-and-Wait)
    # ---------------------------
    def send_reliable(self, msg_type, payload=b""):
        retries = 0

        while retries < MAX_RETRIES:
            pkt = make_packet(msg_type, self.seq, payload)
            self.sock.sendto(pkt, self.server_addr)

            try:
                data, _ = self.sock.recvfrom(4096)

                r_type, r_seq, r_payload = parse_packet(data)

                if r_type is None:
                    print("Corrupted response detected. Dropping...")
                    continue

                if r_type == ACK and r_seq == self.seq:
                    self.seq += 1
                    return True

                if r_type == DOWNLOAD_ERROR:
                    print("Server ERROR:", r_payload.decode())
                    return False

            except socket.timeout:
                retries += 1
                print("Timeout... Retransmitting seq", self.seq)

        print("Failed after maximum retries.")
        return False


    # ---------------------------
    # Session Establishment (Broadcast Handshake)
    # ---------------------------
    def connect(self):
        print("\nHANDSHAKE_REQUEST")

        for attempt in range(1, 4):   # Exactly 3 attempts
            print(f"Retry {attempt}/3...")

            syn_pkt = make_packet(HANDSHAKE_REQUEST, self.seq)

            # Broadcast SYN
            self.sock.sendto(syn_pkt, self.server_addr)

            try:
                data, addr = self.sock.recvfrom(4096)

                msg_type, seq, _ = parse_packet(data)

                if msg_type is None:
                    print("Corrupted packet ignored.")
                else:
                    if msg_type == HANDSHAKE_RESPONSE:

                        print(f"\nServer found at ({addr[0]})")

                        # Save real server address
                        self.server_addr = addr

                        # DO NOT send automatic ACK here
                        # Just mark session active
                        self.session_active = True

                        print("Handshake response received. Session ready.")
                        return True

            except socket.timeout:
                if attempt < 3:
                    time.sleep(0.5)  # Short delay before retrying

        print("\nNo active server found.")
        return False


    # ---------------------------
    # Download File
    # ---------------------------
    def download(self, filename):
        if not self.session_active:
            print("No session established.")
            return

        print("\nRequesting download:", filename)

        if not self.send_reliable(DOWNLOAD_REQ, filename.encode()):
            return

        received_chunks = {}

        while True:
            try:
                data, _ = self.sock.recvfrom(4096)

                msg_type, seq, payload = parse_packet(data)

                if msg_type is None:
                    print("Corrupted DATA packet dropped.")
                    continue

                if msg_type == DATA:
                    received_chunks[seq] = payload
                    ack_pkt = make_packet(ACK, seq)
                    self.sock.sendto(ack_pkt, self.server_addr)

                elif msg_type == EOF:
                    print("EOF received. Download complete.")
                    break

                elif msg_type == DOWNLOAD_ERROR:
                    print("Server ERROR:", payload.decode())
                    return

            except socket.timeout:
                print("Timeout while receiving file.")
                return

        save_name = "downloaded_" + filename

        with open(save_name, "wb") as f:
            for i in sorted(received_chunks.keys()):
                f.write(received_chunks[i])

        print("File saved as:", save_name)


    # ---------------------------
    # Upload File
    # ---------------------------
    def upload(self, filepath):
        if not self.session_active:
            print("No session established.")
            return

        if not os.path.exists(filepath):
            print("File not found locally.")
            return

        filename = os.path.basename(filepath)
        print("\nUploading file:", filename)

        if not self.send_reliable(UPLOAD_REQ, filename.encode()):
            return

        seq_num = 0

        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(MAX_PAYLOAD)
                if not chunk:
                    break

                pkt = make_packet(UPLOAD_CHUNK, seq_num, chunk)

                retries = 0
                while retries < MAX_RETRIES:
                    self.sock.sendto(pkt, self.server_addr)

                    try:
                        data, _ = self.sock.recvfrom(4096)

                        r_type, r_seq, _ = parse_packet(data)

                        if r_type is None:
                            print("Corrupted ACK dropped.")
                            continue

                        if r_type == ACK and r_seq == seq_num:
                            seq_num += 1
                            break

                    except socket.timeout:
                        retries += 1
                        print("Retransmitting chunk", seq_num)

        eof_pkt = make_packet(EOF, seq_num)
        self.sock.sendto(eof_pkt, self.server_addr)

        print("Upload finished successfully!")


    # ---------------------------
    # Termination
    # ---------------------------
    def close(self):
        if self.session_active:
            print("\nClosing session...")

            self.send_reliable(EOF)
            self.session_active = False

        self.sock.close()
        print("Client closed.")


# ===============================
# Main Client Program
# ===============================

if __name__ == "__main__":
    print(f"Simple File Transfer Application (UDP)")
    print("        CLIENT INTERFACE")
    print(f"\nCreated by: Ke, Xan Luo and Mojica, Maurienne Marie\n\n")
    
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
            fname = input("(Show File List on Server)")
            client.download(fname)

        elif choice == "2":
            path = input("Show file list on from Client")
            client.upload(path)

        elif choice == "3":
            client.close()
            break