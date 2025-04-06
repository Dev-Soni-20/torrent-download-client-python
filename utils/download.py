import struct
import socket
import random
import sys
from math import ceil
import queue
from typing import List, Tuple

import utils.details as details
from utils.json_data import ResumeData

PORT_NUMBER = 6881
TIMEOUT = 10
peer_id = b'-TR4003-' + bytes(random.getrandbits(8) for _ in range(12))
piece_length = details.piece_length
total_length = details.total_length
total_peices = details.num_of_pieces

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
    
def expect_bitfeild(sock: socket.socket)->list:
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

    bitfield = bitfield[:total_peices]
    
    return bitfield

def send_bitfeild(sock: socket.socket, resume_data: ResumeData)->None:
    bitfield_data = resume_data.bitfield_to_bytes
    bitfeild_msg = struct.pack(">Ib", 1 + len(bitfield_data), 5) + bitfield_data
    sock.sendall(bitfeild_msg)

def receive_pieces(sock: socket.socket)->None:
    pass


def connect_to_peer(ip: str, port: int, info_hash: bytes)->None:
    sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    sock.timeout(TIMEOUT)

    #TCP Connection
    try:
        sock.connect((ip,port))
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    #BitTorrent Handshake
    try:
        bitTorrent_handshake(sock, info_hash)
    except socket.timeout:
        print(f"Timeout occured while handshaking on the peer {ip}:{port}\n")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    #Sending and Receiving the bit-field message:
    
    

def create_connection_to_peers(torrent_info: dict, info_hash:bytes, peers_list: List[Tuple[str,int]])->None:
    for (ip,port) in peers_list:
        connect_to_peer(ip, port, info_hash)



__all__ = ["create_connection_to_peers"]