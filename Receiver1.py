# Jordan Bouret 2795423
import socket
import sys
import struct

BYTES_PER_HEADER = struct.calcsize("!HB") # ! = big endian, H = ushort, B = uchar 
BYTES_PER_PACKET = 1027 # 3 bytes for header, 1024 for payload 

def receive_file_over_rdt1(filename, listen_port):
    listen_ip = "127.0.0.1" # I had to hardcore this for our assignment
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((listen_ip,listen_port))
    print(f"Receiver listening on {listen_ip}:{listen_port}...")

    with open(filename, "wb") as file:
        while True:
            packet, address = sock.recvfrom(BYTES_PER_PACKET)
            if len(packet) < BYTES_PER_HEADER:
                continue # we want to ignore incomplete packets
            flag = struct.unpack("!HB", packet[:BYTES_PER_HEADER])[1] # ignore seq, extract flag
            data = packet[BYTES_PER_HEADER:] 
            if flag == 1:
                # We just received an EOF packet, indicating the end of our transmission
                print("EOF Packet Received! File transfer complete :)") 
                break
            file.write(data)
    sock.close()



if __name__ == "__main__":
    if len(sys.argv) !=  3:
        print("Usage: python3 Receiver1.py <port> <save_received_file_as>")
        sys.exit(1)
    port = int(sys.argv[1])
    filename = sys.argv[2] # (save_as)
    receive_file_over_rdt1(filename, port) 

