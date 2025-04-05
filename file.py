import bencodepy
import sys
from utils.get_peers import *

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

# for x in torrent_info:
#     print(x, torrent_info[x],end="\n\n")

peers = get_peers_list(torrent_info)

print(peers)