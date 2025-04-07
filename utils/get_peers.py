import struct
import socket
import random
import sys
from urllib.parse import urlparse
from typing import List, Tuple
import queue

PORT_NUMBER = 6881
MAX_TRY = 1
MAX_TIME_TO_WAIT = 1

class InvalidConnectionRespone(Exception):
    pass

class InvalidAnnounceRespone(Exception):
    pass

def _make_connection_request(tracker_ip: str, tracker_port: int, count:int)->int:
    sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    sock.settimeout(MAX_TIME_TO_WAIT)

    protocol_id = 0x41727101980  # protocol ID (predifend for biTorrent protocol)
    action = 0  # connect
    transaction_id = random.randint(0, 2**32 - 1)

    connection_req=struct.pack(">QLL", protocol_id, action, transaction_id)

    try:
        # print(f"Trying to connect to {tracker_ip}:{tracker_port}")
        sock.sendto(connection_req,(tracker_ip,tracker_port))
    except socket.timeout:
        if count==MAX_TRY:
            # print(f"Cannot connect to {tracker_ip}:{tracker_port}, tring next tracker\n")
            raise TimeoutError("Timeout Reached!")
        else:
            # print(f"Trying to connect to {tracker_ip}:{tracker_port} again!\n")
            return _make_connection_request(tracker_ip,tracker_port,count+1)
    except socket.gaierror:
        raise socket.gaierror
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    # print("The connection request has been sent")

    try:
        connection_resp, addr = sock.recvfrom(2048)
    except socket.timeout:
        if count==MAX_TRY:
            # print(f"Did not recieve response from {tracker_ip}:{tracker_port}, tring next tracker\n")
            raise TimeoutError("Timeout Reached!")
        else:
            # print(f"Did not recieve respose, trying to connect to {tracker_ip}:{tracker_port} again!\n")
            return _make_connection_request(tracker_ip,tracker_port,count+1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    
    # print("The connection respone has been received")


    if len(connection_resp)<16:
        raise InvalidConnectionRespone("Invalid connection respone from tracker: Packet of less than 16 bytes is received!\n")

    action_resp, transaction_id_resp, connection_id_resp = struct.unpack(">LLQ", connection_resp)
    
    if action!=action_resp:
        raise InvalidConnectionRespone("Invalid connection respone from tracker: action is not 0 (connect) in response!\n")
    
    if transaction_id!=transaction_id_resp:
        raise InvalidConnectionRespone("Invalid connection respone from tracker: transaction_id does not match!\n")
    
    print(connection_id_resp)
    return connection_id_resp

def _make_announce_request(connection_id: int, info_hash: bytes, total_length: int, tracker_ip: str, tracker_port: int, count: int)->List[Tuple[str, int]]:
    transaction_id = random.randint(0, 2**32 - 1)
    peer_id = b'-TR4003-' + bytes(random.getrandbits(8) for _ in range(12))
    port = PORT_NUMBER
    action = 1 

    # Belows are generally 0 for announce request
    downloaded=0
    left=total_length
    uploaded=0

    event = 2	# 0: none, 1: completed, 2: started, 3: stopped
    ip=0	# let tracker detect
    key = random.randint(0, 2**32 - 1)	# keep it the same across one session, used for client side detection
    num_want = -1

    announce_req = struct.pack(">QLL20s20sQQQLLLlH", connection_id, action, transaction_id, info_hash, peer_id, downloaded, left, uploaded, event, ip, key, num_want, port)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(MAX_TIME_TO_WAIT)
    

    # print(f"Announce Request Length: {len(announce_req)}")

    try:
        # print(f"Sending an announce request to {tracker_ip}:{tracker_port}")
        sock.sendto(announce_req, (tracker_ip, tracker_port))
    except socket.timeout:
        if count==MAX_TRY:
            # print(f"Cannot connect to {tracker_ip}:{tracker_port}, tring next tracker\n")
            raise TimeoutError("Timeout Reached!")
        else:
            # print(f"Trying to connect to {tracker_ip}:{tracker_port} again!\n")
            return _make_announce_request(connection_id, info_hash)
    except socket.gaierror:
        raise socket.gaierror
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    # print("The announce request has been sent")
    
    try:
        announce_resp, addr = sock.recvfrom(4096)
    except socket.timeout:
        if count==MAX_TRY:
            # print(f"Did not recieve response from {tracker_ip}:{tracker_port}, tring next tracker\n")
            raise TimeoutError("Timeout Reached!")
        else:
            # print(f"Did not recieve respose, trying to connect to {tracker_ip}:{tracker_port} again!\n")
            return _make_connection_request(tracker_ip,tracker_port,count+1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    # print("The announce respone has been received")

    # print(f"Announce Response Length: {len(announce_resp)}\n")

    if len(announce_resp)<20:
        raise InvalidAnnounceRespone("Invalid announce respone from tracker: Packet of less than 20 bytes is received!\n")
    
    action_resp, transaction_id_resp, interval, leechers, seeders = struct.unpack(">LLLLL", announce_resp[0:20])

    if action!=action_resp:
        raise InvalidAnnounceRespone("Invalid announce respone from tracker: action is not 1 (announce) in response!\n")
    
    if transaction_id!=transaction_id_resp:
        raise InvalidAnnounceRespone("Invalid announce respone from tracker: transaction_id does not match!\n")
    
    peers = []
    offset = 20

    while offset<len(announce_resp):
        ip_packed = announce_resp[offset:offset+4]
        port_packed = announce_resp[offset+4:offset+6]

        ip = socket.inet_ntoa(ip_packed)
        port = struct.unpack(">H", port_packed)[0]

        peers.append((ip,port))
        offset+=6

    return peers
    

def get_peers_list(torrent_info: dict, info_hash: bytes, peer_list: queue.Queue)->None:
    tracker_url_list = []

    # Extracting all the trackers from the torrent file
    try:
        tracker_url_list.append(torrent_info[b'announce'].decode('utf-8'))

        if b'announce-list' in torrent_info:
            announce_list = torrent_info[b'announce-list']
            if announce_list[0][0].decode('utf-8') not in tracker_url_list:
                tracker_url_list.append(announce_list[0][0].decode('utf-8'))

            for url in announce_list[1:]:
                tracker_url_list.append(url[0].decode('utf-8'))

    except Exception as E:
        print(f"Error : {E}")
        sys.exit(1)

    # calculate the total length of the files in torrent
    try:
        total_length = 0
        info_dict = torrent_info[b'info']

        if b'files' in info_dict:
            files_list = info_dict[b'files']

            for file in files_list:
                total_length += file[b'length']
        else:
            total_length += info_dict[b'length']
    
    except Exception as E:
        print(f"Error : {E}")
        sys.exit(1)

    for url in tracker_url_list:
        parsed_url=urlparse(url)

        tracker_ip=parsed_url.hostname
        tracker_port=parsed_url.port

        try:
            connection_id =_make_connection_request(tracker_ip,tracker_port,1)
        except socket.gaierror:
            print("DNS lookup failed, trying next one!\n")
            continue
        except TimeoutError:
            print("Seems like this tracker is not working, trying next one!\n")
            continue
        except InvalidAnnounceRespone as inv:
            print(inv, "Trying next tracker!")
            continue
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

        try:
            peer_list.put(_make_announce_request(connection_id, info_hash, total_length, tracker_ip, tracker_port,1))
        except TimeoutError:
            continue
        except InvalidAnnounceRespone as inv:
            print(inv)
            continue
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

__all__ = ["get_peers_list"]