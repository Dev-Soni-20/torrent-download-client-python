from utils.get_details import *

class TorrentDetails:
    def __init__(self, info_dict: dict, root: str):
        self.piece_length = get_piece_length(info_dict)
        self.total_length = get_total_length(info_dict)
        self.num_of_pieces = get_total_pieces(self.total_length, self.piece_length)
        self.file_sizes = get_file_sizes(info_dict)
        self.hash_of_pieces = get_hash_list(info_dict, self.num_of_pieces)
        self.info_hash = get_info_hash(info_dict)
        self.files = get_file_details(info_dict, root)

class ParsedMessage:
    def __init__(self, size, id, payload):
        self.size = size
        self.id = id
        self.payload = payload

class Peer:
    def __init__(self, ip: str, port: int):
        self.ip = ip
        self.port = port

    def __str__(self):
        return f"{self.ip}:{self.port}"