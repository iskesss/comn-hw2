# Jordan Bouret, s2795423 
import sys
import struct
import socket

INCOMING_PACKET_SIZE = 1027 # Packet size for receiving data
INCOMING_HEADER_FORMAT = "!BB" # Header format: flag (1 byte) and sequence number (1 byte)
BYTES_PER_HEADER = struct.calcsize(INCOMING_HEADER_FORMAT)

ACK_FORMAT = "!B" # 1 unsigned byte for the sequence number (REMEMEBER, THIS CANNOT EXCEED 256. IMPLEMENT SOMETHING WITH MOD IN THIS FILE!!!)

def receive_file_over_gbn(filename, listen_port):
    listen_ip = "127.0.0.1" # I had to hardcode this for our assignment
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((listen_ip,listen_port))
    print(f"Receiver3 listening on {listen_ip}:{listen_port}...")
    expected_seq = 0
    with open(filename, "wb") as outfile:
        while True:
            packet, sender_addr = sock.recvfrom(INCOMING_PACKET_SIZE)
            if len(packet) < BYTES_PER_HEADER: # verify that the packet is large enough to contain a header
                continue
            flag, seq = struct.unpack(INCOMING_HEADER_FORMAT, packet[:BYTES_PER_HEADER])
            if flag == 0: # if current packet holds data
                if seq == expected_seq:
                    data = packet[BYTES_PER_HEADER:] # fetch data from payload
                    outfile.write(data) # send data to "application layer" (outfile)
                    ack = struct.pack(ACK_FORMAT, seq) # build ack 
                    sock.sendto(ack, sender_addr) # send ack
                    expected_seq += 1 # expected_seq_num++ 
                else:
                    # resend ACK for most recently received in-order packet (thereby requesting next expected packet from sender)
                    last_successfully_received = expected_seq - 1
                    ack = struct.pack(ACK_FORMAT, last_successfully_received)
                    sock.sendto(ack, sender_addr)
            elif flag == 1:  # if we receive an EOF packet, acknowledge it and break the loop
                ack = struct.pack(ACK_FORMAT, seq)
                sock.sendto(ack, sender_addr)
                break
    sock.close()
    print("File has been received successfully.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Receiver3 CLI arguments incorrect")
        sys.exit(1)
    listen_port = int(sys.argv[1])
    filename = sys.argv[2]
    receive_file_over_gbn(listen_port,filename)

