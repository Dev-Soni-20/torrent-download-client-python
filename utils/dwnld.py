import socket
import utils.build_messages as messages
import utils.verify_messages as verify
from utils.details import *
import asyncio 
import os

TIMEOUT=10
NUM_CONN_TASKS = 10
NUM_HANDLE_TASKS = 5
NUM_DOWNLOAD_TASKS = 2
BLOCK_SIZE = 2**14

def download(peer: Peer, details: TorrentDetails):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(TIMEOUT)

    try:
        print(f"Trying TCP connection to {peer}\n")
        sock.connect((peer.ip,peer.port))
    except Exception as e:
        print(f"Cannot make TCP connection with {peer}, Error: {e}\n")
        return None
    
    # TCP connection has been set up, now try bittorrent handshake

    try:
        print(f"Trying BitTorrent handshake with {peer}\n")
        handshake_req = messages.build_bitTorrent_handshake(details)

        sock.sendall(handshake_req)

        handshake_resp = messages.recv_whole_message(sock, True)

        if verify.is_handshake(handshake_resp):
            print(f"BitTorrent handshake is successful with {peer}\n")
    except Exception as e:
        print(f"Cannot make BitTorrent handshake with {peer}, Error: {e}\n")
        return None

    # BitTorrent Handshake is completed successfully.

    try:
        print(f"Trying to get Bitfeild message from {peer}\n")
        bitfeild_resp = messages.recv_whole_message(sock, False)
    except Exception as e:
        print(f"Did not received bitfeild message from {peer}, Error: {e}")
        print("Continuing...")

    try:
        sock.sendall(messages.build_interested())
    except Exception as e:
        print(f"Cannot make BitTorrent handshake with {peer}, Error: {e}\n")
        return None
    
############################ Trying Code from GPT ###################################

async def connection_worker(peer_queue: asyncio.Queue, handshake_queue: asyncio.Queue, torrent_details: TorrentDetails):
    """
    Asynchronous connection worker:
      - Gets peers from peer_queue.
      - Opens a TCP connection using asyncio streams.
      - Performs BitTorrent handshake.
      - Enqueues a tuple (peer, reader, writer) on success.
    """
    while True:
        try:
            peer = peer_queue.get_nowait()
        except asyncio.QueueEmpty:
            break

        try:
            print(f"Trying TCP connection to {peer}")
            # asyncio.open_connection returns (reader, writer)
            reader, writer = await asyncio.wait_for(asyncio.open_connection(peer.ip, peer.port), timeout=TIMEOUT)
        except Exception as e:
            print(f"Cannot make TCP connection with {peer}, Error: {e}")
            peer_queue.task_done()
            continue

        try:
            print(f"Trying BitTorrent handshake with {peer}")
            handshake_req = messages.build_bitTorrent_handshake(torrent_details)
            writer.write(handshake_req)
            await writer.drain()

            # For handshake response, we assume your messages.recv_whole_message can be awaited,
            # or you could wrap it via run_in_executor if it is blocking.
            handshake_resp = await asyncio.wait_for(messages.recv_whole_message(reader, expect_handshake=True), timeout=TIMEOUT)
            if verify.is_handshake(handshake_resp):
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

async def handle_worker(handshake_queue: asyncio.Queue, download_queue: asyncio.Queue):
    """
    Asynchronous handler worker:
      - Retrieves a tuple (peer, reader, writer).
      - Listens for an expected message from the peer.
      - Optionally sends an "interested" message.
      - Enqueues for download stage.
    """
    while True:
        try:
            peer, reader, writer = await asyncio.wait_for(handshake_queue.get(), timeout=TIMEOUT)
        except asyncio.TimeoutError:
            break  # No new peers in a while, exit

        try:
            # Wait for a bitfield or have message from the peer.
            msg = await asyncio.wait_for(messages.recv_whole_message(reader, expect_handshake=False), timeout=TIMEOUT)

            #################################################################################################
            """
            Needed to implement the logic of getting an available packets, create a list of available packets, send it
            to download task to only download that pieces.
            """
            #################################################################################################


            if verify.is_have(msg) or verify.is_bitfield(msg):
                print(f"Received expected message from {peer}")
                # Optionally, send an "interested" message:
                try:
                    writer.write(messages.build_interested())
                    await writer.drain()
                except Exception as e:
                    print(f"Failed sending 'interested' to {peer}, Error: {e}")
            else:
                print(f"Received unexpected message from {peer}")
            await download_queue.put((peer, reader, writer))
        except Exception as e:
            print(f"Error handling message from {peer}, Error: {e}")
            writer.close()
            await writer.wait_closed()
        handshake_queue.task_done()

async def download_worker(download_queue: asyncio.Queue, torrent_details: TorrentDetails):
    """
    Asynchronous download worker:
      - Retrieves a tuple (peer, reader, writer).
      - Initiates piece download.
    """
    while True:
        try:
            peer, reader, writer = await asyncio.wait_for(download_queue.get(), timeout=TIMEOUT)
        except asyncio.TimeoutError:
            break  # Exit if no new items to download

        try:
            print(f"Starting download from {peer}")
            await download_from_peer(peer, reader, writer, torrent_details)
        except Exception as e:
            print(f"Error downloading from {peer}, Error: {e}")
        download_queue.task_done()


async def download_from_peer(peer: Peer, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, torrent_details: TorrentDetails):
    try:
        print(f"[{peer.ip}:{peer.port}] Starting download")

        total_pieces = len(torrent_details.piece_hashes)

        for piece_index in range(total_pieces):
            piece_length = torrent_details.piece_lengths[piece_index]
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
                        if verify.is_piece(msg):
                            r_index, r_begin, r_block = verify.parse_piece(msg)
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

            # Optionally: verify hash here, or store it
            # if not verify_piece_hash(piece_data, torrent_details.piece_hashes[piece_index]):
            #     print(f"[{peer.ip}] Invalid hash for piece {piece_index}, discarding.")
            #     continue

            # TODO: save piece_data to disk or buffer

        print(f"[{peer.ip}] Download finished successfully.")

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
            with open(file_path, 'r+b') as f:
                f.seek(file_write_offset)
                f.write(data_to_write)
    
async def main(peers: list, details: TorrentDetails):
    # Create async queues for pipeline stages
    peer_queue = asyncio.Queue()
    handshake_queue = asyncio.Queue()
    download_queue = asyncio.Queue()

    # Populate the peer_queue
    for peer in peers:
        await peer_queue.put(peer)

    # Launch connection tasks.
    conn_tasks = [asyncio.create_task(connection_worker(peer_queue, handshake_queue, details))
                  for _ in range(NUM_CONN_TASKS)]
    # Launch handling tasks.
    handle_tasks = [asyncio.create_task(handle_worker(handshake_queue, download_queue))
                    for _ in range(NUM_HANDLE_TASKS)]
    # Launch download tasks.
    download_tasks = [asyncio.create_task(download_worker(download_queue, details))
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
