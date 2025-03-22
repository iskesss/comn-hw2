import sys
import struct
import socket

INCOMING_PACKET_SIZE = 1028  # Increased by 1 byte for larger sequence number
INCOMING_HEADER_FORMAT = "!BH"  # Header format: flag (1 byte) and sequence number (2 bytes)
BYTES_PER_HEADER = struct.calcsize(INCOMING_HEADER_FORMAT)
ACK_FORMAT = "!H"  # 2 bytes for the seq number (16-bit)
MAX_SEQ_NUM = pow(2, 8 * struct.calcsize(ACK_FORMAT))

def receive_file_over_gbn(listen_port, filename):
    listen_ip = "127.0.0.1"  # I had to hardcode this for our assignment
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((listen_ip, listen_port))
    print(f"Receiver listening on {listen_ip}:{listen_port}...")

    expected_seq = 0

    with open(filename, "wb") as outfile:
        while True:
            packet, sender_addr = sock.recvfrom(INCOMING_PACKET_SIZE)

            if len(packet) < BYTES_PER_HEADER:  # verify that the packet is large enough to contain a header
                print("Received packet too small, ignoring")
                continue

            flag, seq = struct.unpack(INCOMING_HEADER_FORMAT, packet[:BYTES_PER_HEADER])

            if flag == 0: # if current packet holds data
                print(f"Received packet with seq={seq}, expected={expected_seq % MAX_SEQ_NUM}")

                if seq == expected_seq % MAX_SEQ_NUM:
                    data = packet[BYTES_PER_HEADER:]  # extract data from payload
                    outfile.write(data) # send data to "application layer" (outfile)
                    ack = struct.pack(ACK_FORMAT, seq) # build ack
                    sock.sendto(ack, sender_addr) # send ack
                    expected_seq += 1 # expected_seq++
                    print(f"😁Packet {seq} accepted, expecting {expected_seq % MAX_SEQ_NUM} next")
                else:
                    last_successfully_received = (expected_seq - 1) % MAX_SEQ_NUM # resend ACK for most recently received in-order packet (thereby requesting next expected packet from sender)
                    ack = struct.pack(ACK_FORMAT, last_successfully_received)
                    sock.sendto(ack, sender_addr)
                    print(f"😡Packet {seq} discarded, resending ACK for {last_successfully_received}")

            elif flag == 1:  # if we receive an EOF packet, acknowledge it and break the loop
                ack = struct.pack(ACK_FORMAT, seq)
                sock.sendto(ack, sender_addr)
                print(f"Received EOF packet with seq={seq}, transmission complete")
                break

    sock.close()
    print("File has been received successfully.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 Receiver3.py <listen_port> <filename>")
        sys.exit(1)

    listen_port = int(sys.argv[1])
    filename = sys.argv[2]

    receive_file_over_gbn(listen_port, filename)
