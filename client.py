import socket
import struct
import os
import hashlib
import time   

# ===============================
# Protocol Constants
# ===============================
DEFAULT_PORT = 5555   
TYPE_SYN     = 1
TYPE_SYNACK  = 2
TYPE_ACK     = 3
TYPE_REQ     = 4      # Download request
TYPE_PUT     = 5      # Upload request
TYPE_DATA    = 6
TYPE_EOF     = 7
TYPE_FIN     = 8
TYPE_ERROR   = 9
MAX_PAYLOAD = 1024
TIMEOUT = 0.5          # ✅ shorter timeout for broadcast handshake
MAX_RETRIES = 5
HASH_SIZE = 32  # SHA-256 digest size


# ===============================
# Packet Format with SHA-256
# ===============================

def make_packet(msg_type, seq, payload=b""):
    length = len(payload)

    digest = hashlib.sha256(payload).digest()
    header = struct.pack("!BIH", msg_type, seq, length)

    return header + digest + payload


def parse_packet(packet):
    if len(packet) < 39:
        return None, None, None

    header = packet[:7]
    msg_type, seq, length = struct.unpack("!BIH", header)

    recv_hash = packet[7:39]
    payload = packet[39:39 + length]

    calc_hash = hashlib.sha256(payload).digest()

    if recv_hash != calc_hash:
        return None, None, None  # corrupted packet

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

                if r_type == TYPE_ACK and r_seq == self.seq:
                    self.seq += 1
                    return True

                if r_type == TYPE_ERROR:
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
        print("\nBroadcasting handshake request...")

        attempts = 0

        while attempts < 3:
            print("Handshake Attempt", attempts + 1, "...")

            syn_pkt = make_packet(TYPE_SYN, self.seq)

            # ✅ Broadcast SYN
            self.sock.sendto(syn_pkt, self.server_addr)

            try:
                data, addr = self.sock.recvfrom(4096)

                msg_type, seq, _ = parse_packet(data)

                if msg_type is None:
                    print("Corrupted packet ignored.")
                    continue

                if msg_type == TYPE_SYNACK:
                    print("Server found at:", addr[0])

                    # ✅ Save real server address (stop broadcasting)
                    self.server_addr = addr

                    # Send ACK back
                    ack_pkt = make_packet(TYPE_ACK, seq)
                    self.sock.sendto(ack_pkt, self.server_addr)

                    self.session_active = True
                    print("Session Established Successfully!\n")
                    return True

            except socket.timeout:
                attempts += 1
                time.sleep(0.5)

        print("No active server found.")
        return False


    # ---------------------------
    # Download File
    # ---------------------------
    def download(self, filename):
        if not self.session_active:
            print("No session established.")
            return

        print("\nRequesting download:", filename)

        if not self.send_reliable(TYPE_REQ, filename.encode()):
            return

        received_chunks = {}

        while True:
            try:
                data, _ = self.sock.recvfrom(4096)

                msg_type, seq, payload = parse_packet(data)

                if msg_type is None:
                    print("Corrupted DATA packet dropped.")
                    continue

                if msg_type == TYPE_DATA:
                    received_chunks[seq] = payload

                    ack_pkt = make_packet(TYPE_ACK, seq)
                    self.sock.sendto(ack_pkt, self.server_addr)

                elif msg_type == TYPE_EOF:
                    print("EOF received. Download complete.")
                    break

                elif msg_type == TYPE_ERROR:
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

        if not self.send_reliable(TYPE_PUT, filename.encode()):
            return

        seq_num = 0

        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(MAX_PAYLOAD)
                if not chunk:
                    break

                pkt = make_packet(TYPE_DATA, seq_num, chunk)

                retries = 0
                while retries < MAX_RETRIES:
                    self.sock.sendto(pkt, self.server_addr)

                    try:
                        data, _ = self.sock.recvfrom(4096)

                        r_type, r_seq, _ = parse_packet(data)

                        if r_type is None:
                            print("Corrupted ACK dropped.")
                            continue

                        if r_type == TYPE_ACK and r_seq == seq_num:
                            seq_num += 1
                            break

                    except socket.timeout:
                        retries += 1
                        print("Retransmitting chunk", seq_num)

        eof_pkt = make_packet(TYPE_EOF, seq_num)
        self.sock.sendto(eof_pkt, self.server_addr)

        print("Upload finished successfully!")


    # ---------------------------
    # Termination
    # ---------------------------
    def close(self):
        if self.session_active:
            print("\nClosing session...")

            self.send_reliable(TYPE_FIN)
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
    input("PRESS [ENTER] TO START HANDSHAKE_REQUEST")



    os.system('cls')

    client = ReliableUDPClient(DEFAULT_PORT)

    if not client.connect():
        exit()

    while True:
        print("\n====== CLIENT MENU ======")
        print("1. Download File")
        print("2. Upload File")
        print("3. Exit")

        choice = input("Choose option: ")

        if choice == "1":
            fname = input("Enter filename to download: ")
            client.download(fname)

        elif choice == "2":
            path = input("Enter filepath to upload: ")
            client.upload(path)

        elif choice == "3":
            client.close()
            break