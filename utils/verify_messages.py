import struct
from utils.details import *

def is_handshake(packet: bytes, info_hash:bytes) -> bool:
    if len(packet)!=68:
        return False
    
    len_resp, msg_resp, info_hash_resp, peer_id_resp = struct.unpack(">B19s8x20s20s", packet)
    
    if len_resp!=19 or msg_resp!=b'BitTorrent protocol' or info_hash_resp!=info_hash:
        return False
    
    return True

def is_have(msg: ParsedMessage):
    return msg.id==4

def is_bitfeild(msg: ParsedMessage):
    return msg.id==5

def is_choke(msg: ParsedMessage) -> bool:
    return msg.id == 0 and msg.size == 1

def is_unchoke(msg: ParsedMessage) -> bool:
    return msg.id == 1 and msg.size == 1

def is_piece(msg: ParsedMessage) -> bool:
    return msg.id == 7 and msg.size > 9 and msg.payload is not None