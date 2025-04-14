import asyncio 
import os
from typing import List
import struct

import utils.build_messages as messages
import utils.verify_messages as verify
from utils.details import *
from utils.json_data import ResumeData
import utils.handlers as handler

TIMEOUT=3
NUM_CONN_TASKS = 4
NUM_HANDLE_TASKS = 2
NUM_DOWNLOAD_TASKS = 2
BLOCK_SIZE = 2**14

async def connection_worker(peer_queue: asyncio.Queue, handshake_queue: asyncio.Queue, torrent_details: TorrentDetails):
    while True:
        try:
            peer = await peer_queue.get()
        except asyncio.QueueEmpty:
            break

        try:
            print(f"Trying TCP connection to {peer}")
            # asyncio.open_connection returns (reader, writer)
            reader, writer = await asyncio.wait_for(asyncio.open_connection(peer.ip, peer.port), timeout=TIMEOUT)
        except Exception as e:
            print(f"Cannot make TCP connection with {peer}, Error: {type(e).__name__}: {e}")
            peer_queue.task_done()
            continue

        try:
            print(f"Trying BitTorrent handshake with {peer}")
            handshake_req = messages.build_bitTorrent_handshake(torrent_details)
            writer.write(handshake_req)
            await writer.drain()

            # For handshake response, we assume your messages.recv_whole_message can be awaited,
            # or you could wrap it via run_in_executor if it is blocking.
            handshake_resp = await asyncio.wait_for(messages.recv_whole_message(reader, isHandshake=True), timeout=TIMEOUT)
            if verify.is_handshake(handshake_resp, torrent_details.info_hash):
                print(f"BitTorrent handshake successful with {peer}")
            else:
                print(f"Invalid handshake response from {peer}")
                writer.close()
                await writer.wait_closed()
                peer_queue.task_done()
                continue
        except Exception as e:
            print(f"Handshake failed with {peer}, Error: {e}")
            writer.close()
            await writer.wait_closed()
            peer_queue.task_done()
            continue

        # Enqueue the successful connection for the next stage.
        await handshake_queue.put((peer, reader, writer))
        peer_queue.task_done()


async def wait_for_unchoke(reader: asyncio.StreamReader, peer: Peer) -> bool:
    while True:
        try:
            msg = await asyncio.wait_for(messages.recv_whole_message(reader, isHandshake=False), timeout=TIMEOUT)
        except asyncio.TimeoutError:
            print(f"Timeout while waiting for choke/unchoke from {peer}.")
            return False

        parsed = messages.parse_message(msg)

        if verify.is_unchoke(parsed):
            print(f"{peer} unchoked us. Proceeding to download.")
            return True
        elif verify.is_choke(parsed):
            print(f"{peer} is choked, waiting for unchoke...")
        else:
            print(f"Received irrelevant message from {peer} while waiting for unchoke.")


async def handle_worker(handshake_queue: asyncio.Queue, download_queue: asyncio.Queue, resume_data: ResumeData):
    while True:
        try:
            peer, reader, writer = await handshake_queue.get()
        except asyncio.TimeoutError:
            break  # No new peers in a while, exit

        try:
            # Wait for a bitfield or have message from the peer.
            msg = await asyncio.wait_for(messages.recv_whole_message(reader, isHandshake=False), timeout=TIMEOUT)
            parsed_message = messages.parse_message(msg)

            if verify.is_have(parsed_message):
                print(f"Received have message from {peer}")

                try:
                    pieces_to_request = handler.have_handler(parsed_message, resume_data.verified_pieces)

                    if len(pieces_to_request)==0:
                        print(f"No pieces needed from {peer}")
                        handshake_queue.task_done()
                        continue

                    unchoked = await wait_for_unchoke(reader, peer, TIMEOUT)
                    if unchoked:
                        await download_queue.put((peer, reader, writer, pieces_to_request))
                    else:
                        print(f"Did not receive unchoke from {peer}. Closing connection.")
                        writer.close()
                        await writer.wait_closed()

                    # Put this peer again for listening further have messages
                    # await handshake_queue.put((peer, reader, writer))

                except Exception as e:
                    print(f"Failed handling 'have' from {peer}, Error: {e}")
            
            elif verify.is_bitfeild(parsed_message):
                print(f"Received bitfeild message from {peer}")
        
                try:
                    pieces_to_request = handler.bitfield_handler(parsed_message, resume_data.verified_pieces)

                    if len(pieces_to_request)==0:
                        print(f"No pieces needed from {peer}")
                        handshake_queue.task_done()
                        continue

                    writer.write(messages.build_interested())
                    await writer.drain()

                    await download_queue.put((peer, reader, writer, pieces_to_request))

                    # Put this peer again for listening further have messages
                    # await handshake_queue.put((peer, reader, writer))

                except Exception as e:
                    print(f"Failed sending 'interested' to {peer} in respone of bitfeild, Error: {e}")  
            else:
                print(f"Received unexpected message from {peer}")

        except Exception as e:
            print(f"Error handling message from {peer}, Error: {e}")
            writer.close()
            await writer.wait_closed()
        
        handshake_queue.task_done()

async def download_worker(download_queue: asyncio.Queue, torrent_details: TorrentDetails, resume_data: ResumeData):
    """
    Asynchronous download worker:
      - Retrieves a tuple (peer, reader, writer).
      - Initiates piece download.
    """
    while True:
        try:
            peer, reader, writer, pieces_to_request = await download_queue.get()
        except asyncio.TimeoutError:
            break  # Exit if no new items to download

        try:
            print(f"Starting download from {peer}")
            await download_from_peer(peer, reader, writer, pieces_to_request, torrent_details, resume_data)
        except Exception as e:
            print(f"Error downloading from {peer}, Error: {e}")
        download_queue.task_done()


async def download_from_peer(peer: Peer, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, pieces_to_request:List[int], torrent_details: TorrentDetails, resume_data: ResumeData):
    try:
        print(f"[{peer.ip}:{peer.port}] Starting download")

        total_pieces = torrent_details.num_of_pieces
        piece_length = torrent_details.piece_length

        print(pieces_to_request,end="\n\n\n")

        for piece_index in pieces_to_request:
            
            num_blocks = (piece_length + BLOCK_SIZE - 1) // BLOCK_SIZE
            piece_data = bytearray(piece_length)

            for block_num in range(num_blocks):
                begin = block_num * BLOCK_SIZE
                block_length = min(BLOCK_SIZE, piece_length - begin)

                # Send request for the block
                request_msg = messages.build_request(piece_index, begin, block_length)
                writer.write(request_msg)
                await writer.drain()

                # Await the full response
                while True:
                    try:
                        msg = await messages.recv_whole_message(reader, isHandshake=False)
                        parsed_message = messages.parse_message(msg)

                        if verify.is_piece(parsed_message):
                            r_index, r_begin = struct.unpack(">II", parsed_message.payload[:8])
                            r_block = parsed_message.payload[8:]

                            if r_index == piece_index and r_begin == begin:
                                piece_data[begin:begin+len(r_block)] = r_block
                                break  # Valid block received
                    except asyncio.IncompleteReadError:
                        print(f"[{peer.ip}] Incomplete read. Closing connection.")
                        return
                    except Exception as e:
                        print(f"[{peer.ip}] Error receiving piece: {e}")
                        return

            print(f"[{peer.ip}] Completed piece {piece_index + 1}/{total_pieces}")


            # verify hash here, or store it
            if not handler.verify_piece_hash(piece_data, torrent_details.hash_of_pieces[piece_index]):
                print(f"[{peer.ip}] Invalid hash for piece {piece_index}, discarding.")
                continue

            print(f"Piece Index {piece_index} downloaded successfully from {peer}.")

            async with resume_data.lock:
                resume_data.verified_pieces[piece_index] = True
                resume_data.downloaded += 1
            
            # TODO: save piece_data to disk or buffer
            save_piece_to_disk(piece_index, piece_data, torrent_details)

    except Exception as e:
        print(f"[{peer.ip}] Download failed, Error: {e}")

def save_piece_to_disk(piece_index: int, piece_data: bytes, torrent_details: TorrentDetails):
    """
    Save the fully downloaded piece to disk.
    
    This function handles multi-file torrents. It maps the piece's global offset into one
    or more files based on file boundaries.
    
    Assumes:
      - torrent_details.piece_length: standard piece length
      - torrent_details.files: a list of dictionaries, each containing:
          'path'   : File path (str)
          'length' : Length of the file (int)
          'offset' : Starting offset of the file in the torrent's byte stream (int)
    """
    # Global offset within the entire torrent data for this piece.
    global_offset = piece_index * torrent_details.piece_length
    piece_size = len(piece_data)
    piece_end = global_offset + piece_size

    # Iterate over each file to see if the piece overlaps.
    for file_entry in torrent_details.files:
        file_path = file_entry['path']
        file_offset = file_entry['offset']
        file_length = file_entry['length']
        file_end = file_offset + file_length

        # Check if there is an intersection between [global_offset, piece_end)
        # and [file_offset, file_end)
        overlap_start = max(global_offset, file_offset)
        overlap_end = min(piece_end, file_end)

        if overlap_start < overlap_end:
            # There is an overlapping region.
            # Calculate the corresponding part in the piece data.
            piece_data_start = overlap_start - global_offset
            piece_data_end = overlap_end - global_offset
            data_to_write = piece_data[piece_data_start:piece_data_end]

            # Determine the offset within the file where the data should go.
            file_write_offset = overlap_start - file_offset

            # Ensure the directory exists.
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Open the file in binary read/write mode.
            # It is assumed the file is already created with the correct size.
            # If not, you may want to create or truncate the file.

            if not os.path.exists(file_path):
                with open(file_path, 'wb') as f:
                    f.truncate(file_length)

            with open(file_path, 'r+b') as f:
                f.seek(file_write_offset)
                f.write(data_to_write)
    
async def main(peers: list, details: TorrentDetails, resume_data: ResumeData):
    # Create async queues for pipeline stages
    peer_queue = asyncio.Queue()
    handshake_queue = asyncio.Queue()
    download_queue = asyncio.Queue()

    # Populate the peer_queue
    for peer in peers:
        await peer_queue.put(Peer(peer[0],peer[1]))

    # Launch connection tasks.
    conn_tasks = [asyncio.create_task(connection_worker(peer_queue, handshake_queue, details))
                  for _ in range(NUM_CONN_TASKS)]
    # Launch handling tasks.
    handle_tasks = [asyncio.create_task(handle_worker(handshake_queue, download_queue, resume_data))
                    for _ in range(NUM_HANDLE_TASKS)]
    # Launch download tasks.
    download_tasks = [asyncio.create_task(download_worker(download_queue, details, resume_data))
                      for _ in range(NUM_DOWNLOAD_TASKS)]

    # Wait until all peers have been processed by the connection stage.
    await peer_queue.join()
    # Wait until all handshake tasks have processed their peers.
    await handshake_queue.join()
    # Wait until downloads are complete.
    await download_queue.join()

    # Cancel remaining tasks if any
    for task in conn_tasks + handle_tasks + download_tasks:
        task.cancel()
    print("All tasks completed.")
