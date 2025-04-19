import asyncio 
import os
from typing import List
import struct

import utils.build_messages as messages
import utils.verify_messages as verify
from utils.details import *
from utils.json_data import ResumeData
from utils.logger import Logger, CONNECTION_LOGGER, HANDLE_LOGGER
import utils.handlers as handler


TIMEOUT=5 # Maximum Timeout for a particular ongoing connection
NUM_CONN_TASKS = 4 # Number of threads alloted for handling TCP Connections and BitTorrent Handshake
NUM_HANDLE_TASKS = 2 #Number of threads alloted for handling pieces messages, bit field messages, choke/unchoke messages
NUM_DOWNLOAD_TASKS = 8 #Number of threads alloted for downloading the pieces (1 Thread/peer)
MAX_CLAIM_PER_PEER = 1 #Maximum number of pieces a peer can claim to give/download from
BLOCK_SIZE = 2**14

async def connection_worker(peer_queue: asyncio.Queue, handshake_queue: asyncio.Queue, torrent_details: TorrentDetails, logger: CONNECTION_LOGGER):
    while True:
        try:
            peer = await peer_queue.get()
        except asyncio.QueueEmpty:
            break

        try:
            logger.tcp_connection_attempt(peer.ip, peer.port)
            # asyncio.open_connection returns (reader, writer)
            reader, writer = await asyncio.wait_for(asyncio.open_connection(peer.ip, peer.port), timeout=TIMEOUT)
        except Exception as e:
            logger.tcp_connection_error(peer.ip, peer.port, f"{type(e).__name__}: {e}")
            peer_queue.task_done()
            continue

        try:
            logger.handshake_attempt(peer.ip, peer.port)
            handshake_req = messages.build_bitTorrent_handshake(torrent_details)
            writer.write(handshake_req)
            await writer.drain()
            handshake_resp = await asyncio.wait_for(messages.recv_whole_message(reader, isHandshake=True), timeout=TIMEOUT)

            if verify.is_handshake(handshake_resp, torrent_details.info_hash):
                logger.handshake_success(peer.ip, peer.port)
            else:
                logger.handshake_failure(peer.ip, peer.port)
                writer.close()
                await writer.wait_closed()
                peer_queue.task_done()
                continue

        except Exception as e:
            logger.handshake_error(peer.ip, peer.port, str(e))
            writer.close()
            await writer.wait_closed()
            peer_queue.task_done()
            continue

        # Enqueue the successful connection for the next stage.
        await handshake_queue.put((peer, reader, writer))
        peer_queue.task_done()


async def wait_for_unchoke(reader: asyncio.StreamReader, peer: Peer, logger: HANDLE_LOGGER) -> bool:
    while True:
        try:
            msg = await asyncio.wait_for(messages.recv_whole_message(reader, isHandshake=False), timeout=TIMEOUT)
        except asyncio.TimeoutError:
            print(f"Timeout while waiting for choke/unchoke from {peer}.")
            return False

        parsed = messages.parse_message(msg)

        if verify.is_unchoke(parsed):
            logger.unchoke_received(peer.ip, peer.port)  
            return True
        elif verify.is_choke(parsed):
            logger.choke_received(peer.ip, peer.port)  
        else:
            logger.irrelevant_message(peer.ip, peer.port) 


async def handle_worker(handshake_queue: asyncio.Queue, download_queue: asyncio.Queue, resume_data: ResumeData, logger: HANDLE_LOGGER):
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
                logger.have_message_received(peer.ip, peer.port) 
                
                try:
                    pieces_to_request = handler.have_handler(parsed_message, resume_data.verified_pieces)

                    if len(pieces_to_request) == 0:
                        logger.no_pieces_needed(peer.ip, peer.port)
                        handshake_queue.task_done()
                        continue

                    unchoked = await wait_for_unchoke(reader, peer, logger)
                    
                    if unchoked:
                        await download_queue.put((peer, reader, writer, pieces_to_request))
                    else:
                        print(f"Did not receive unchoke from {peer}. Closing connection.")
                        writer.close()
                        await writer.wait_closed()

                except Exception as e:
                    logger.failed_handling_have(peer.ip, peer.port, str(e)) 

            elif verify.is_bitfeild(parsed_message):
                logger.bitfield_message_received(peer.ip, peer.port)
                
                try:
                    pieces_to_request = handler.bitfield_handler(parsed_message, resume_data.verified_pieces)

                    if len(pieces_to_request) == 0:
                        logger.no_pieces_needed(peer.ip, peer.port)
                        handshake_queue.task_done()
                        continue

                    writer.write(messages.build_interested())
                    await writer.drain()
                    await download_queue.put((peer, reader, writer, pieces_to_request))

                except Exception as e:
                    logger.failed_handling_bitfield(peer.ip, peer.port, str(e)) 
            else:
                print(f"Received unexpected message from {peer}")

        except Exception as e:
            logger.error_handling_message(peer.ip, peer.port, str(e)) 
            writer.close()
            await writer.wait_closed()

        handshake_queue.task_done()

async def download_worker(download_queue: asyncio.Queue, torrent_details: TorrentDetails, resume_data: ResumeData, logger: Logger):

    while True:
        try:
            peer, reader, writer, pieces_to_request = await download_queue.get()
        except asyncio.TimeoutError:
            break  # Exit if no new items to download

        try:
            logger.info(f"Started download from {peer.ip}:{peer.port}")
            await download_from_peer(peer, reader, writer, pieces_to_request, torrent_details, resume_data, logger)

        except Exception as e:
            logger.error(f"Download failed from {peer.ip}:{peer.port} — {e}")

        download_queue.task_done()

async def download_from_peer(peer: Peer, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                             pieces_available_from_peer: List[int], torrent_details: TorrentDetails,
                             resume_data: ResumeData, logger: Logger):

    piece_length = torrent_details.piece_length
    total_pieces = torrent_details.num_of_pieces

    try:
        logger.info(f"[{peer.ip}:{peer.port}] Starting download")

        while True:
            logger.info(f"[{peer.ip}:{peer.port}] Claiming a batch to download")

            claimed = []
            async with resume_data.lock:
                for piece_index in pieces_available_from_peer:
                    if len(claimed) >= MAX_CLAIM_PER_PEER:
                        break
                    if not resume_data.verified_pieces[piece_index] and piece_index not in resume_data.claimed_pieces:
                        resume_data.claimed_pieces.add(piece_index)
                        claimed.append(piece_index)

            if not claimed:
                logger.warn(f"[{peer.ip}] No more claimable pieces. Closing connection.")
                break  # All pieces are claimed/verified — nothing more that this peer can do

            logger.info(f"[{peer.ip}:{peer.port}] Batch Claimed → {claimed}")

            for piece_index in claimed:
                
                num_blocks = (piece_length + BLOCK_SIZE - 1) // BLOCK_SIZE
                piece_data = bytearray(piece_length)

                for block_num in range(num_blocks):
                
                    begin = block_num * BLOCK_SIZE
                    block_length = min(BLOCK_SIZE, piece_length - begin)
                    request_msg = messages.build_request(piece_index, begin, block_length)
                    writer.write(request_msg)
                    await writer.drain()

                    while True:
                        try:
                            msg = await messages.recv_whole_message(reader, isHandshake=False)
                            parsed = messages.parse_message(msg)

                            if verify.is_piece(parsed):
                                r_index, r_begin = struct.unpack(">II", parsed.payload[:8])
                                r_block = parsed.payload[8:]

                                if r_index == piece_index and r_begin == begin:
                                    piece_data[begin:begin + len(r_block)] = r_block
                                    break
                        except Exception as e:
                            logger.error(f"[{peer.ip}] Error during block read: {e}")
                            raise e

                # Hash verification
                if not handler.verify_piece_hash(piece_data, torrent_details.hash_of_pieces[piece_index]):
                    logger.warn(f"[{peer.ip}] Invalid hash for piece {piece_index}. Discarding...")
                    async with resume_data.lock:
                        resume_data.claimed_pieces.discard(piece_index)
                    continue

                save_piece_to_disk(piece_index, piece_data, torrent_details)
                logger.success(f"[{peer.ip}] Piece {piece_index} downloaded and verified ✅")

                async with resume_data.lock:
                    resume_data.verified_pieces[piece_index] = True
                    resume_data.downloaded += 1
                    resume_data.claimed_pieces.discard(piece_index)

                logger.update_stats(resume_data.downloaded, torrent_details.num_of_pieces, peer.ip)

    except Exception as e:
        logger.error(f"[{peer.ip}] Peer download error: {e}")
        async with resume_data.lock:
            for piece_index in claimed:
                resume_data.claimed_pieces.discard(piece_index)

    finally:
        writer.close()
        await writer.wait_closed()

def save_piece_to_disk(piece_index: int, piece_data: bytes, torrent_details: TorrentDetails):
    
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

        # Check if there is an intersection between [global_offset, piece_end) and [file_offset, file_end)
        overlap_start = max(global_offset, file_offset)
        overlap_end = min(piece_end, file_end)

        if overlap_start < overlap_end:
            # There is an overlapping region. Calculating the corresponding part in the piece data.
            piece_data_start = overlap_start - global_offset
            piece_data_end = overlap_end - global_offset
            data_to_write = piece_data[piece_data_start:piece_data_end]

            # Determine the offset within the file where the data should go.
            file_write_offset = overlap_start - file_offset

            # Ensure the directory exists.
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            #Make the file
            if not os.path.exists(file_path):
                with open(file_path, 'wb') as f:
                    f.truncate(file_length)

            # Open the file in binary read/write mode.
            with open(file_path, 'r+b') as f:
                f.seek(file_write_offset)
                f.write(data_to_write)
    
async def main(peers: list, details: TorrentDetails, resume_data: ResumeData, logger: Logger):
    # Create async queues for pipeline stages
    peer_queue = asyncio.Queue()
    handshake_queue = asyncio.Queue()
    download_queue = asyncio.Queue()

    # Populate the peer_queue
    for peer in peers:
        await peer_queue.put(Peer(peer[0],peer[1]))

    # Launch connection tasks.
    tcp_bit_logger = CONNECTION_LOGGER()
    conn_tasks = [asyncio.create_task(connection_worker(peer_queue, handshake_queue, details, tcp_bit_logger))
                  for _ in range(NUM_CONN_TASKS)]
    # Launch handling tasks.
    handle_logger = HANDLE_LOGGER()
    handle_tasks = [asyncio.create_task(handle_worker(handshake_queue, download_queue, resume_data, handle_logger))
                    for _ in range(NUM_HANDLE_TASKS)]
    # Launch download tasks.
    download_tasks = [asyncio.create_task(download_worker(download_queue, details, resume_data, logger))
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
