import struct

def is_handshake(packet: bytes, info_hash:bytes) -> bool:
    if len(packet)!=68:
        return False
    
    len_resp, msg_resp, info_hash_resp, peer_id_resp = struct.unpack(">B19s8x20s20s", packet)

    if len_resp!=19 or msg_resp!='BitTorrent protocol' or info_hash_resp!=info_hash:
        return False
    
    return True