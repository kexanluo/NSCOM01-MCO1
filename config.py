from pathlib import Path
import sys

target_folder_server = Path(__file__).resolve().parent / "nscomServer"
target_folder_client = Path(__file__).resolve().parent / "nscomClient"

def checkDirectory(role):
    if role == "Server":
        if not target_folder_server.exists():
            target_folder_server.mkdir()
        else:
            if not target_folder_server.is_dir():
                print("[SERVER] CONFIG ERROR - A file named 'nscomServer' exists. Please move/delete the file and run the application again.")
                sys.exit()
    elif role == "Client":
        if not target_folder_client.exists():
            target_folder_client.mkdir()
        else:
            if not target_folder_client.is_dir():
                print("[CLIENT] CONFIG ERROR - A file named 'nscomClient' exists. Please move/delete the file and run the application again.")
                sys.exit()