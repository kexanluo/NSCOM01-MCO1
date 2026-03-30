import uuid
import socket
import threading

PEER_IP = "192.168.100.92"   #changeable
DEFAULT_PORT = 5555

class SIPClient:
    def __init__(self):
        self.local_ip = "192.168.100.92"   # CHANGE THIS
        self.local_rtp_port = 6000
        self.remote_rtp_port = None
        self.peer_addr = None
        self.call_established = False
        self.seq = 1
        self.call_id = uuid.uuid4()

    def setup_socket(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) #FOR TESTING SAME IP/DEVICE
        self.sock.bind((self.local_ip, self.local_rtp_port))

    def build_sip_message(self, method, sdp=None):
        call_id = str(self.call_id)
        headers = [
            f"{method} sip:voip SIP/2.0",
            f"Via: SIP/2.0/UDP {self.local_ip}:{self.local_rtp_port};branch=z9hG4bK{uuid.uuid4()}",
            f"From: <sip:client@{self.local_ip}>;tag={uuid.uuid4()}",
            f"To: <sip:client>",
            f"Call-ID: {call_id}",
            f"CSeq: {self.seq} {method}",
            f"Contact: <sip:{self.local_ip}:{self.local_rtp_port}>",
            "Max-Forwards: 70"
        ]
        body = ""
        if sdp:
            body = "\r\n".join(sdp)
            headers.append("Content-Type: application/sdp")
            headers.append(f"Content-Length: {len(body)}")
        else:
            headers.append("Content-Length: 0")
        message = "\r\n".join(headers) + "\r\n\r\n" + body
        return message.encode()

    def create_sdp_offer(self):
        return [
            "v=0",
            f"o=- {self.seq} {self.seq} IN IP4 {self.local_ip}",
            "s=VoIP Call",
            f"c=IN IP4 {self.local_ip}",
            "t=0 0",
            f"m=audio {self.local_rtp_port} RTP/AVP 0",
            "a=rtpmap:0 PCMU/8000"
        ]

    def send_invite(self):
        print(f"[SIP] 📞 INVITE sent to {PEER_IP}:{DEFAULT_PORT}")
        print("[SIP] Negotiating session parameters (SDP included)...")
        self.peer_addr = (PEER_IP, DEFAULT_PORT)
        sdp = self.create_sdp_offer()
        sip_msg = self.build_sip_message("INVITE", sdp)
        self.sock.sendto(sip_msg, self.peer_addr)

    def receive(self):
        data, addr = self.sock.recvfrom(4096)
        msg = data.decode(errors="ignore")

        if "INVITE" in msg:
            print(f"\n[SIP] INVITE received from {addr[0]}")
            self.peer_addr = addr

            if "\r\n\r\n" in msg:
                sdp_part = msg.split("\r\n\r\n")[1]
                for line in sdp_part.split("\r\n"):
                    if line.startswith("m=audio"):
                        self.remote_rtp_port = int(line.split()[1])

            sdp_answer = [
                "v=0",
                f"o=- {self.seq} {self.seq} IN IP4 {self.local_ip}",
                "s=VoIP Call",
                f"c=IN IP4 {self.local_ip}",
                "t=0 0",
                f"m=audio {self.local_rtp_port} RTP/AVP 0",
                "a=rtpmap:0 PCMU/8000"
            ]

            response = self.build_sip_message("200 OK", sdp_answer)
            self.sock.sendto(response, addr)

            print("[SIP] Sent 200 OK with SDP")

        elif "200 OK" in msg:
            print(f"\n[SIP] 📩 200 OK received from {addr[0]}")
            print("[SIP] ✔ SDP received → Extracting media parameters...")

            if "\r\n\r\n" in msg:
                sdp_part = msg.split("\r\n\r\n")[1]
                for line in sdp_part.split("\r\n"):
                    if line.startswith("m=audio"):
                        self.remote_rtp_port = int(line.split()[1])

            ack_msg = self.build_sip_message("ACK")
            self.sock.sendto(ack_msg, addr)

            self.peer_addr = addr
            self.call_established = True

            print(f"[SIP] 📤 ACK sent to {addr[0]}")
            print("[SIP] 🎉 Call established successfully")

        elif "ACK" in msg:
            print(f"[SIP] 📥 ACK received from {addr[0]}")
            print("[SIP] 🎉 Call fully confirmed on both sides")

            self.call_established = True

        elif "BYE" in msg:
            print(f"[SIP] 📥 BYE received from {addr[0]}")
            print("[SIP] 🔚 Call terminated gracefully")

            ok_msg = self.build_sip_message("200 OK")
            self.sock.sendto(ok_msg, addr)

            self.call_established = False

    def send_bye(self):
        if self.peer_addr:
            print(f"[SIP] 📤 BYE sent to {self.peer_addr[0]}")
            print("[SIP] 🔚 Call termination initiated...")
            bye_msg = self.build_sip_message("BYE")
            self.sock.sendto(bye_msg, self.peer_addr)
            self.call_established = False
        else:
            print("[SIP] ❌ No active call to terminate")

def listen_loop(client):
        while True:
            try:
                client.receive()
            except Exception as e:
                print(f"[SIP] ❌ Error: {e}")

def main():
    client = SIPClient()
    client.setup_socket()  
    print(f"[SIP] 🚀 Client started on {client.local_ip}:{client.local_rtp_port}")

    # Start listening thread
    listen_thread = threading.Thread(target=listen_loop, args=(client,))
    listen_thread.daemon = True
    listen_thread.start()

    while True:
        print("\n--- SIP MENU ---")
        print("1. Call (Send INVITE)")
        print("2. Wait for Call (Receive INVITE)")
        print("3. End Call (Send BYE)")
        print("4. Exit")

        try:
            choice = int(input("Select option: "))
        except ValueError:
            print("[SIP] ❌ Invalid input. Enter a number.")
            continue

        if choice == 1:
            client.send_invite()

        elif choice == 2:
            print("[SIP] ⏳ Waiting for incoming call...")

        elif choice == 3:
            client.send_bye()

        elif choice == 4:
            print("[SIP] 👋 Exiting...")
            break

        else:
            print("[SIP] ❌ Invalid choice. Try again.")

if __name__ == "__main__":
    main()