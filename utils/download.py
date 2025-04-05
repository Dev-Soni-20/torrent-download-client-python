#Making the Tcp connection to all the peers
import queue
import socket

MAX_TIMEOUT_TCP_CONNECT = 10

def set_tcp_connections(peer_list: queue.Queue):
    active_connections = []
    while not peer_list.empty():

        peer_group = peer_list.get()

        for ip,port in peer_group:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(MAX_TIMEOUT_TCP_CONNECT)
                sock.connect((ip, port))
                # Optional: Set to blocking mode again if needed (after connect)
                # sock.settimeout(None)  # or another timeout if you want
                active_connections.append(sock)
                print(f"Connected to {ip}:{port} and socket is open")

            except socket.timeout:
                print(f"Connection to {ip}:{port} timed out")
            except socket.error as e:
                print(f"Socket error while connecting to {ip}:{port} — {e}")


__all__ = ["set_tcp_connections"]