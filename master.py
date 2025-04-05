import bencodepy
import sys
from utils.get_peers import *
from utils.download import *
import threading
import queue

populated_peers_list = queue.Queue()

def populate_peers():
    print("Populating Peers")
    try:
        get_peers_list(torrent_info,populated_peers_list)
        print(f"Populated Peers, Queue Size: {populated_peers_list.qsize()}")
    except Exception as e:
        print(f"Error in populating peers: {e}")

def connect_to_peers():
    #Logic for set 4 Onwards, goes here
    #Step 4.1 setting up TCP connects to the peers
    print("Waiting for peers to be populated...")    
    try:
        print(f"===============Length of the peer_list: {populated_peers_list.qsize()} ==========================")
        set_tcp_connections(populated_peers_list)
    except Exception as e:
        print(f"Error in setting TCP connection to peers: {e}")
    


if(__name__=="__main__"):

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