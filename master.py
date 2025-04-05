import bencodepy
import sys
from utils.get_peers import *
import threading
import queue

peers_list = queue.Queue()

def populate_peers():
    get_peers_list(torrent_info,peers_list)

def connect_to_peers():
    while True:
        peers = peers_list.get()
        print(peers)


if __name__=="__main__":

    if len(sys.argv) != 2:
        print("Usage: python script.py <torrent_file>")
        sys.exit(1)

    file_name=sys.argv[1]

    try:
        with open(file_name,"rb") as torrent_file:
            file_content=torrent_file.read()
    except FileNotFoundError:
        print(f"Error: file {file_name} not found!")
        sys.exit(1)
    except Exception as E:
        print(f"Error : {E}")
        sys.exit(1)

    try:
        torrent_info = bencodepy.decode(file_content)
    except Exception as E:
        print(f"Error : {E}")
        sys.exit(1)

    tracker_thread = threading.Thread(target=populate_peers)
    connector_thread = threading.Thread(target=connect_to_peers)

    tracker_thread.start()
    connector_thread.start()

    tracker_thread.join()
    connector_thread.join()

