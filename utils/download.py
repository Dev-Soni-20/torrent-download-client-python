import struct
import socket
import random
import sys
from typing import List, Tuple
import hashlib

import utils.details as details
from utils.json_data import ResumeData

PORT_NUMBER = 6881
BLOCK_SIZE = min(2**14, details.piece_length)
TIMEOUT = 10
peer_id = b'-TR4003-' + bytes(random.getrandbits(8) for _ in range(12))

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

    bitfield = bitfield[:details.num_of_pieces]
    
    return bitfield

def send_bitfeild(sock: socket.socket, resume_data: ResumeData)->None:
    bitfield_data = resume_data.verified_to_bytes()
    bitfeild_msg = struct.pack(">Ib", 1 + len(bitfield_data), 5) + bitfield_data
    sock.sendall(bitfeild_msg)

def request_piece_transfer(sock: socket.socket, piece_ind: int)->None:    
    buffer = bytearray(details.piece_length)
    offset = 0

    while offset < details.piece_length:
        block_len = min(BLOCK_SIZE, details.piece_length - offset)
        payload = struct.pack(">IbIII", 13, 6, piece_ind, offset, block_len)
        sock.sendall(payload)

        piece_len_resp = recvall(sock,4)
        len = struct.unpack(">I")

        piece_resp = recvall(sock,len)
        msg_id_resp, piece_ind_resp, offset_resp = struct.unpack(">bII", piece_resp[:9])
        block = piece_resp[9:]

        buffer[offset_resp : offset_resp+len(block)] = block
        offset += len(block)

    sha1 = hashlib.sha1(buffer).digest()
    if sha1 != details.hash_of_pieces[piece_ind]:
        raise ValueError("Piece hash does not match! Download corrupted.")

    return buffer

def receive_pieces(sock: socket.socket, bitfeild: List[bool], pieces_state: List[bool])->None:
    # first, send interested or not interested message
    
    flag = False
    for i in range(details.num_of_pieces):
        if bitfeild[i]==True and pieces_state==0:
            flag=True
            break

    if flag:
        not_interested_packet = struct.pack(">Ib", 1, 2)
        sock.sendall(not_interested_packet)
    else:
        not_interested_packet = struct.pack(">Ib", 1, 3)
        sock.sendall(not_interested_packet)
        return
    
    # At this point, peer has some pieces that we are interested in
    # Receive choke or unchoke message

    permission_packet = recvall(sock, 5)
    length, permission = struct.unpack(">Ib", permission_packet)

    if length!=1:
        raise ValueError("Unexpected length for choke/unchoke")
    
    if permission==1:
        #received unchoke
        sock.settimeout(None)

        while permission != 0:
            next_packet = recvall(sock,5)
            length, permission = struct.unpack(">Ib", next_packet)
            if length!=1:
                raise ValueError("Unexpected length for choke/unchoke")
            
        sock.settimeout(TIMEOUT)

    # At this point, we have received choke message from the peer.

    for i in range(details.num_of_pieces):
        if bitfeild[i]==True and pieces_state[i]==0:
            # We should download this packet from peer
            pieces_state[i]=1

            request_piece_transfer(sock)




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

def create_connection_to_peers(torrent_info: dict, info_hash:bytes, peers_list: List[Tuple[str,int]], resume_data: ResumeData)->None:
    # 0: not started, 1: began exchange with some thread, 2: successfully downloaded
    pieces_state = [0 for _ in range(details.num_of_pieces)]

    for i in range(details.num_of_pieces):
        if resume_data.verified_pieces[i] is True:
            pieces_state[i]=2
    
    for (ip,port) in peers_list:
        connect_to_peer(ip, port, info_hash)



__all__ = ["create_connection_to_peers"]