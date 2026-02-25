from pathlib import Path
import sys

# Config File: Checks if directory exists, if not, it creates one.

target_folder_server = Path(__file__).resolve().parent / "nscomServer"
target_folder_client = Path(__file__).resolve().parent / "nscomClient"

def checkDirectory(role): # param role e.g. "Server"/"Client"
    if role == "Server":
        if not target_folder_server.exists(): # If it doesn't exist, it creates the directory.
            target_folder_server.mkdir()
        else:
            if not target_folder_server.is_dir(): # If it exists, but not directory.
                print("[SERVER] CONFIG ERROR - A file named 'nscomServer' exists. Please move/delete the file and run the application again.")
                sys.exit()
    elif role == "Client":
        if not target_folder_client.exists(): # If it doesn't exist, it creates the directory.
            target_folder_client.mkdir()
        else:
            if not target_folder_client.is_dir(): # If it exists, but not directory. If directory, disregard.
                print("[CLIENT] CONFIG ERROR - A file named 'nscomClient' exists. Please move/delete the file and run the application again.")
                sys.exit()