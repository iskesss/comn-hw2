# Jordan Bouret 2795423
import sys
import struct
import socket

INCOMING_PACKET_SIZE = 1027 # Packet size for receiving data
INCOMING_HEADER_FORMAT = "!BB" # Header format: flag (1 byte) and sequence number (1 byte)
BYTES_PER_HEADER = struct.calcsize(INCOMING_HEADER_FORMAT)

ACK_FORMAT = "!B" # 1 unsigned byte for the sequence number
BYTES_PER_ACK = struct.calcsize(ACK_FORMAT)

def receive_file_over_rdt3(filename, listen_port):
    listen_ip = "127.0.0.1" # I had to hardcode this for our assignment
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((listen_ip,listen_port))
    # print(f"Receiver2 listening on {listen_ip}:{listen_port}...")
    expected_seq = 0
    with open(filename, "wb") as outfile:
        while True:
            packet, sender_addr = sock.recvfrom(INCOMING_PACKET_SIZE) 
            if len(packet) < BYTES_PER_HEADER: # verify that the packet is large enough to contain a header
                continue
            flag, seq = struct.unpack(INCOMING_HEADER_FORMAT, packet[:BYTES_PER_HEADER])
            if flag == 0: # if current packet holds data
                # print(f"—> [Received pack {seq}]┐")
                if seq == expected_seq:
                    # then write the packet's payload data to the output file
                    data = packet[BYTES_PER_HEADER:]
                    outfile.write(data)
                    ack = struct.pack(ACK_FORMAT, seq) # acknowledge received packet
                    # print(f"<– [Sending ack {seq}  ]┘")
                    sock.sendto(ack, sender_addr)
                    expected_seq = 1 - expected_seq # flip expected seq number 0->1 or 1->0
                else:
                    # we received a duplicate packet, so resend the last ACK
                    last_ack = 1 - expected_seq # toggle bit
                    ack = struct.pack(ACK_FORMAT, last_ack)
                    sock.sendto(ack, sender_addr)
            elif flag == 1:  # if we receive an EOF packet, acknowledge it and break the loop
                # print(f"—> [Received EOF pack]┐")
                # print(f"<— [Sending EOF ack  ]┘")
                ack = struct.pack(ACK_FORMAT, seq)
                sock.sendto(ack, sender_addr)
                break
    sock.close()
    # print("File has been received successfully.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 Receiver2.py <port> <save_received_file_as>")
        sys.exit(1)
    listen_port = int(sys.argv[1])
    filename = sys.argv[2]
    receive_file_over_rdt3(filename, listen_port)

