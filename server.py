import config # Initial Configuration (Checking for directory)
import socket
import threading
import json
import os
import struct

PORT = 5555
MAX_RETRIES = 3
BUFFER_SIZE = 1024

HEADER_FORMAT = "!I"

SERVER_BUSY = false # Unsure if needed, might change the design

def startSocket():
    global sock

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", PORT))
    print("[SERVER] SOCKET - Server Listening...")

def receive_message():
    while True:
        data, addr = sock.recvfrom(BUFFER_SIZE)

        if message["message_type"] == "DOWNLOAD_REQUEST" # Will switch to binary
            # Checks if the file is available if not ERROR message reply








# MAIN PROGRAM
os.system('cls')
print(f"Simple File Transfer Application (UDP)")
print("        SERVER INTERFACE")
print(f"\nCreated by: Ke, Xan Luo and Mojica, Maurienne Marie\n\n")
input("PRESS [ENTER] TO START THE SERVER")
os.system('cls')

config.checkDirectory("Server")
startSocket()