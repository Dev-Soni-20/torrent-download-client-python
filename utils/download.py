import struct
import socket
import random
import sys
from math import ceil
import queue
from typing import List, Tuple

PORT_NUMBER = 6881
TIMEOUT = 10
peer_id = b'-TR4003-' + bytes(random.getrandbits(8) for _ in range(12))
total_peices = None

def get_peice_length(torrent_info:dict)->int:
    try:
        len = torrent_info[b'info'][b'piece length']      
    except Exception as E:
        print(f"Error : {E}")
        sys.exit(1)

    return len

def get_total_length(torrent_info:dict)->int:
    try:
        total_length = 0
        info_dict=torrent_info[b'info']

        if b'files' in info_dict:
            files_list = info_dict[b'files']

            for file in files_list:
                total_length += file[b'length']
        else:
            total_length += info_dict[b'length']
    
    except Exception as E:
        print(f"Error : {E}")
        sys.exit(1)

    return total_length

def get_total_peices(total_length: int, peice_length: int)->int:
    return ceil(total_length/peice_length)

def recvall(sock: socket.socket, n: int)->bytes:
    data = b''

    while(len(data)<n):
        part = sock.recv(n-len(data))

        if not part:
            raise ConnectionError("Peer closed connection")
        
        data+=part

    return data

def bitTorrent_handshake(sock: socket.socket, info_hash: bytes)->None:
    msg_req = b'bitTorrent protocol'
    len_req = 19

    handshake_req = struct.pack(">B19s8x20s20s", len_req, msg_req, info_hash, peer_id)
    sock.sendall(handshake_req)

    handshake_resp = recvall(sock,68)

    len_resp, msg_resp, info_hash_resp, peer_id_resp = struct.unpack(">B19s8x20s20s", handshake_resp)

    if len_resp!=len_req or msg_resp!=msg_req or info_hash_resp!=info_hash:
        raise ValueError("Invalid handshake")
    
def expect_bitfeild(sock: socket.socket)->None:
    packet_len_bytes = recvall(sock, 4)
    packet_len = struct.unpack(">I", packet_len_bytes)[0]

    bitfeild_content = recvall(sock, packet_len)

    msg_id = bitfeild_content[0]
    if msg_id != 5:
        raise ValueError(f"Expected bitfield message (5), got {msg_id}")

    bitfield = []
    bitfield_bytes = bitfeild_content[1:]

    for byte in bitfield_bytes:
        for i in range(8):
            bit = (byte >> (7 - i)) & 1
            bitfield.append(bool(bit))

    # Step 6: Trim to exact number of pieces
    bitfield = bitfield[:total_peices]
    
    return bitfield


def connect_to_peer(ip: str, port: int, info_hash: bytes)->None:
    sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    sock.timeout(TIMEOUT)

    try:
        sock.connect((ip,port))
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    try:
        bitTorrent_handshake(sock, info_hash)
    except socket.timeout:
        print(f"Timeout occured while handshaking on the peer {ip}:{port}\n")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    



def create_connection_to_peers(torrent_info: dict, info_hash:bytes, peers_list: List[Tuple[str,int]])->None:
    global total_peices
    peice_length = get_peice_length(torrent_info)
    total_length = get_total_length(torrent_info)
    total_peices = get_total_peices(total_length,peice_length)

    for (ip,port) in peers_list:
        connect_to_peer(ip, port, info_hash)



__all__ = ["create_connection_to_peers"]