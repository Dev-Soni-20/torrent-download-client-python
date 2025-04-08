import struct
import random
import socket
import asyncio
import utils.details as details
from utils.details import TorrentDetails, ParsedMessage
import utils.handlers as handler

def build_bitTorrent_handshake(details: TorrentDetails):
    pstrlen = 19
    pstr = "BitTorrent protocol"

    peer_id = b'-TR4003-' + bytes(random.getrandbits(8) for _ in range(12))
    
    handshake_req = struct.pack(">B19s8x20s20s", pstrlen, pstr, details.info_hash, peer_id)

    return handshake_req

def build_keep_alive():
    # length, msg_id
    keep_alive_req = struct.pack(">I", 0)

    return keep_alive_req

def build_choke():
    # length, msg_id
    chock_resp = struct.pack(">Ib", 1, 0)

    return chock_resp

def build_unchoke():
    # length, msg_id
    unchock_resp = struct.pack(">Ib", 1, 1)

    return unchock_resp

def build_interested():
    # length, msg_id
    interested_req = struct.pack(">Ib", 1, 2)

    return interested_req

def build_uninterested():
    # length, msg_id
    uninterested_req = struct.pack(">Ib", 1, 2)

    return uninterested_req

def build_have(piece_index: int):
    # length, msg_id, piece_index
    have_resp = struct.pack(">IbI", 5, 4, piece_index)
    return have_resp

def build_bitfeild(bitfeild: list, details: TorrentDetails):
    bitfield_length = (details.num_of_pieces+7)//8
   
    bitfield_bytes = bytearray(bitfield_length)
    
    for i, has_piece in enumerate(bitfeild):
        if has_piece:
            # Set the bit at the appropriate position (MSB first in each byte)
            bitfield_bytes[i // 8] |= (1 << (7 - (i % 8)))
    
    total_length = 1 + len(bitfield_bytes)  # 1 byte for msg_id plus payload length
    bitfield_resp = struct.pack(">Ib", total_length, 5) + bytes(bitfield_bytes)
    return bitfield_resp

def build_request(piece_index: int, begin: int, length: int):
    # request message: length, msg_id, followed by piece_index, begin, and request length (all 4 bytes each)
    request_req = struct.pack(">IbIII", 13, 6, piece_index, begin, length)
    return request_req

def build_piece(piece_index: int, begin: int, block: bytes):
    # piece message: length, msg_id, followed bypiece index + begin + block
    block_length = len(block)
    total_length = 9 + block_length
    header = struct.pack(">IbII", total_length, 7, piece_index, begin)
    piece_resp = header + block
    return piece_resp

def build_cancel(piece_index: int, begin: int, length: int):
    # cancel message: length, msg_id, followed by piece_index, begin, and length
    cancel_req = struct.pack(">IbIII", 13, 8, piece_index, begin, length)
    return cancel_req

def build_port(port: int):
    # port message: length=3, msg_id=9, followed by the 2-byte port number
    port_resp = struct.pack(">IbH", 3, 9, port)
    return port_resp

def recvall(sock: socket.socket, n: int)->bytes:
    data = b''

    while(len(data)<n):
        part = sock.recv(n-len(data))
        if not part:
            raise ConnectionError("Peer closed connection")
        data+=part

    return data

async def recv_whole_message(reader: asyncio.StreamReader, isHandshake: bool) -> bytes:
    if isHandshake:
        # Handshake messages are fixed size (68 bytes)
        message = await reader.readexactly(68)
    else:
        # Read the 4-byte length prefix
        len_bytes = await reader.readexactly(4)
        length = struct.unpack(">I", len_bytes)[0]
        # Now read the payload of the specified length
        payload = await reader.readexactly(length)
        message = len_bytes + payload
    return message

def parse_message(packet: bytes)->ParsedMessage:
    length = None if len(packet) < 4 else struct.unpack(">I", packet[:4])[0]
    id = None if len(packet) < 5 else struct.unpack(">b", packet[4:5])[0]
    payload = None if len(packet) < 6 else packet[5:]

    parsed_msg = ParsedMessage(length, id, payload)

    return parsed_msg

def message_handler(packet: bytes):
    parsed_message = parse_message(packet)

    if parse_message.id==0:
        handler.chock_handler()

    elif parse_message.id==1:
        handler.unchock_handler()

    elif parse_message.id==4:
        handler.have_handler()

    elif parse_message.id==5:
        handler.bitfeild_handler()
        
    elif parse_message.id==7:
        handler.piece_handler()

