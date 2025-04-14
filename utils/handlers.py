from utils.details import *
from typing import List
import struct
import hashlib

def chock_handler():
    pass

def unchock_handler():
    pass

def have_handler(parsed_message: ParsedMessage, verified_pieces: List[bool])->List[int]:
    piece_index, = struct.unpack(">I", parsed_message.payload)  # Big-endian unsigned int
    result = []

    if not verified_pieces[piece_index]:
        result.append(piece_index)

    return result

def bitfield_handler(parsed_message: ParsedMessage, verified_pieces: List[bool])->List[int]:
    payload = parsed_message.payload
    total_pieces = len(verified_pieces)
    result = []

    for byte_index, byte in enumerate(payload):
        for bit in range(8):
            piece_index = byte_index * 8 + (7 - bit)
            if piece_index >= total_pieces:
                break
            has_piece = (byte >> bit) & 1
            if has_piece and not verified_pieces[piece_index]:
                result.append(piece_index)

    return result

def piece_handler():
    pass

def verify_piece_hash(piece_data: bytearray, piece_hash: bytes):
    calculated_hash = hashlib.sha1(piece_data).digest()
    return calculated_hash == piece_hash