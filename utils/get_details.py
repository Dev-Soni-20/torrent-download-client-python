import sys
from math import ceil
from typing import List

def get_piece_length(info_dict:dict)->int:
    try:
        len = info_dict[b'piece length']      
    except Exception as E:
        print(f"Error : {E}")
        sys.exit(1)

    return len

def get_total_length(info_dict:dict)->int:
    total_length = 0
    try:

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

def get_total_pieces(total_length: int, peice_length: int)->int:
    return ceil(total_length/peice_length)

def get_file_sizes(info_dict: dict)->list:
    file_sizes = []
    try:
        if b'files' in info_dict:
            files_list = info_dict[b'files']

            for file in files_list:
                file_sizes.append(file[b'length'])
        else:
            file_sizes.append(info_dict[b'length'])
    
    except Exception as E:
        print(f"Error : {E}")
        sys.exit(1)

    return file_sizes

def get_hash_list(info_dict: dict, num_of_pieces: int)->List[bytes]:
    hashes = list()

    pieces = info_dict[b'pieces']
    
    for i in range(num_of_pieces):
        hashes.append(pieces[20*i:20*(i+1)])
    
    return hashes

__all__=["get_piece_length", "get_total_length", "get_total_pieces", "get_file_sizes", "get_hash_list"]