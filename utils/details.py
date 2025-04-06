from utils.get_details import *

piece_length = None
total_length = None
num_of_pieces = None
file_sizes = None
hash_of_pieces = None

def populate_details(info_dict: dict)->None:
    global piece_length
    global total_length
    global num_of_pieces
    global file_sizes
    global hash_of_pieces

    piece_length = get_piece_length(info_dict)
    total_length = get_total_length(info_dict)
    num_of_pieces = get_total_pieces(total_length,piece_length)
    file_sizes = get_file_sizes(info_dict)
    hash_of_pieces = get_hash_list(info_dict,num_of_pieces)
