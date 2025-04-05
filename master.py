import bencodepy
import sys
from utils.get_peers import *
from utils.download import *
import threading
import queue
import hashlib

peers_list = queue.Queue()

def populate_peers(torrent_info, info_hash):
    get_peers_list(torrent_info, info_hash, peers_list)

def connect_to_peers(torrent_info, info_hash):

    #Logic for set 4 Onwards, goes here

    #Step 4.1 setting up TCP connects to the peers
    
    while True:
        peers = peers_list.get()
        create_connection_to_peers(torrent_info, info_hash, peers)


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

    try:
        info_dict = torrent_info[b'info']

        info_bencoded = bencodepy.encode(info_dict)
        info_hash = hashlib.sha1(info_bencoded).digest()       
    except Exception as E:
        print(f"Error : {E}")
        sys.exit(1)

    tracker_thread = threading.Thread(target=populate_peers,args=(torrent_info, info_hash))
    connector_thread = threading.Thread(target=connect_to_peers)

    tracker_thread.start()
    connector_thread.start()

    tracker_thread.join()
    connector_thread.join()

