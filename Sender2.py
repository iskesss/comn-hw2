# Jordan Bouret, s2795423
import sys
import struct
import socket
import time

# Configuration parameters
BYTES_PER_OUTGOING_PACKET = 1027
# Header: flag (1 byte) and sequence number (1 byte)
OUTGOING_HEADER_FORMAT = "!BB"
BYTES_PER_OUTGOING_HEADER = struct.calcsize(OUTGOING_HEADER_FORMAT)
PAYLOAD_SIZE = BYTES_PER_OUTGOING_PACKET - BYTES_PER_OUTGOING_HEADER

# ACK header: one unsigned byte for the sequence number
ACK_FORMAT = "!B"
BYTES_PER_ACK_HEADER = struct.calcsize(ACK_FORMAT)

def send_file_over_rdt3(remoteHost, port, filename, retry_timeout):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(retry_timeout)
    seq = 0  # Alternating bit: 0 then 1
    print(f"Now sending {filename}...")
    with open(filename, "rb") as file:
        while True:
            data = file.read(PAYLOAD_SIZE)
            if not data:
                break
            # Build a data packet with flag=0 and the current sequence number
            header = struct.pack(OUTGOING_HEADER_FORMAT, 0, seq)
            packet = header + data
            packet_acked = False
            while not packet_acked:
                print(f"└[Sending pack {seq}] —>")
                sock.sendto(packet, (remoteHost, port))
                try:
                    response, _ = sock.recvfrom(BYTES_PER_ACK_HEADER)
                    # Unpack the ACK packet to get the acked sequence number
                    ack_seq, = struct.unpack(ACK_FORMAT, response[:BYTES_PER_ACK_HEADER])
                    if ack_seq == seq:
                        packet_acked = True
                        print(f"┌[Received ack {seq}] <—")
                        # Toggle sequence number (alternating bit)
                        seq = 1 - seq
                    # If we get an ACK for the wrong sequence, ignore it and wait
                except socket.timeout:
                    # Timeout occurred, so we retransmit the packet
                    continue

    # send the EOF packet: flag=1 indicates end-of-file.
    # we use the current sequence number for the EOF packet.
    eof_header = struct.pack(OUTGOING_HEADER_FORMAT, 1, seq)
    eof_packet_acked = False
    eof_pack_retransmissions = 0 
    MAX_EOF_PACK_RETRANSMISSIONS = 5
    while not eof_packet_acked and eof_pack_retransmissions < MAX_EOF_PACK_RETRANSMISSIONS:
        print(f"└[Sending EOF pack (attempt {eof_pack_retransmissions})] —>")
        eof_pack_retransmissions += 1
        sock.sendto(eof_header, (remoteHost, port))
        try:
            response, _ = sock.recvfrom(BYTES_PER_ACK_HEADER)
            ack_seq, = struct.unpack(ACK_FORMAT, response[:BYTES_PER_ACK_HEADER])
            if ack_seq == seq:
                eof_packet_acked = True
                print("✓[Accepted EOF ack (yippee!!!)] <–")
            # Otherwise, ignore and retransmit EOF packet
        except socket.timeout:
            continue

    sock.close()
    print("File has successfully been sent.")

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python3 Sender2.py <ip> <port> <file_to_send> <retry_timeout>")
        sys.exit(1)
    remoteHost = sys.argv[1]
    port = int(sys.argv[2])
    filename = sys.argv[3]
    retry_timeout = float(sys.argv[4])
    send_file_over_rdt3(remoteHost, port, filename, retry_timeout)
