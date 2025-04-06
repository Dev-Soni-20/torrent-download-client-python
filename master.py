import bencodepy
import sys
import threading
import queue
import hashlib
import os
import time

from utils.get_peers import *
from utils.download import *
from utils.json_data import ResumeData
import utils.details as details

RESUME_FILENAME = "resume.json"

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

    if len(sys.argv) != 3:
        print("Usage: python3 master.py <path_to_torrent_file> <path_to_download>")
        sys.exit(1)

    file_name=sys.argv[1]
    save_loc=sys.argv[2]

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

    details.populate_details(info_dict)

    try:
        name = info_dict[b'name'].decode('utf-8')

        if b'files' in info_dict:
            dir_path=os.path.join(save_loc, name)
        else:
            root, ext = os.path.splitext(name)
            print(root, ext)
            dir_path=os.path.join(save_loc, root)

        os.makedirs(dir_path, exist_ok=True)
        json_file_path=os.path.join(dir_path, RESUME_FILENAME)

        if RESUME_FILENAME in os.listdir(dir_path):
            resume_data = ResumeData.from_json(json_file_path)
        else:
            resume_data = ResumeData(
                info_hash= info_hash.hex(),
                piece_length= details.piece_length,
                total_pieces= details.num_of_pieces,
                downloaded= 0,
                file_sizes= details.file_sizes,
                mtime= int(time.time()),
                verified_pieces= [False for _ in range(details.num_of_pieces)],
                last_active= time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            )
    except Exception as E:
        print(f"Error : {E}")
        sys.exit(1)

    try:
        tracker_thread = threading.Thread(target=populate_peers, args=(torrent_info, info_hash))
        connector_thread = threading.Thread(target=connect_to_peers, args=(torrent_info, info_hash))

        tracker_thread.start()
        connector_thread.start()

        tracker_thread.join()
        connector_thread.join()
    except KeyboardInterrupt:
        print("Exiting. Saving resume data.")
        resume_data.to_json(json_file_path)
        sys.exit(0)

