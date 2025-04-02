# Jordan Bouret 2795423
import sys
import struct
import socket
import time
import os

BYTES_PER_OUTGOING_PACKET = 1027
# Header: flag (1 byte) and sequence number (1 byte)
OUTGOING_HEADER_FORMAT = "!BB"
BYTES_PER_OUTGOING_HEADER = struct.calcsize(OUTGOING_HEADER_FORMAT)
PAYLOAD_SIZE = BYTES_PER_OUTGOING_PACKET - BYTES_PER_OUTGOING_HEADER

# ACK header: one unsigned byte for the sequence number
ACK_FORMAT = "!B"
BYTES_PER_ACK_HEADER = struct.calcsize(ACK_FORMAT)

def send_file_over_rdt3(remoteHost, port, filename, retry_timeout):
    transmission_start_time = time.time()
    total_retransmissions = 0
    file_size = os.path.getsize(filename) # this'll be used to calculate throughput later 

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(retry_timeout)
    seq = 0  # we can get away with simply making this an alternating bit: 0 then 1
    # print(f"Now sending {filename}...\n")
    with open(filename, "rb") as file:
        while True:
            data = file.read(PAYLOAD_SIZE)
            if not data:
                break
            header = struct.pack(OUTGOING_HEADER_FORMAT, 0, seq)
            packet = header + data
            packet_acked = False
            while not packet_acked:
                # print(f"└[Sending pack {seq}] —————>")
                sock.sendto(packet, (remoteHost, port))
                try:
                    response, _ = sock.recvfrom(BYTES_PER_ACK_HEADER)
                    ack_seq, = struct.unpack(ACK_FORMAT, response[:BYTES_PER_ACK_HEADER])
                    if ack_seq == seq:
                        packet_acked = True
                        # print(f"┌[Received ack {seq}] <—————")
                        # toggle sequence number (flip da bit)
                        seq = 1 - seq
                    # if we get an ACK for the wrong seq, ignore it and wait
                except socket.timeout:
                    # timeout occurred (we must retransmit)
                    total_retransmissions += 1
                    continue

    # send the EOF packet: flag=1 indicates end-of-file.
    # we wanna use the current sequence number for the EOF packet.
    eof_header = struct.pack(OUTGOING_HEADER_FORMAT, 1, seq)
    eof_packet_acked = False
    eof_pack_retransmissions = 0 
    MAX_EOF_PACK_RETRANSMISSIONS = 5
    while not eof_packet_acked and eof_pack_retransmissions < MAX_EOF_PACK_RETRANSMISSIONS:
        # print(f"└[Sending EOF pack (attempt {eof_pack_retransmissions})] —>")
        eof_pack_retransmissions += 1
        sock.sendto(eof_header, (remoteHost, port))
        try:
            response, _ = sock.recvfrom(BYTES_PER_ACK_HEADER)
            ack_seq, = struct.unpack(ACK_FORMAT, response[:BYTES_PER_ACK_HEADER])
            if ack_seq == seq:
                eof_packet_acked = True
                # print("✓[Accepted EOF ack (yippee!!!)] <–")
        except socket.timeout:
            total_retransmissions += 1
            continue
        
    sock.close()
    transmission_end_time = time.time()
    total_transfer_time = transmission_end_time - transmission_start_time
    throughput = (file_size / 1024) / total_transfer_time # this gives us throughput in Kbps 

    # "the sender must output number of retransmissions and throughput (in Kbytes/second) only in a single line;
    # no other terminal output should be displayed; the following output implies that the
    # number of retransmissions is 10 and the throughput is 200 Kbytes/second: `10 200` "
    print(f"{total_retransmissions} {int(throughput)}")

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python3 Sender2.py <ip> <port> <file_to_send> <retry_timeout_in_ms>")
        sys.exit(1)
    remoteHost = sys.argv[1]
    port = int(sys.argv[2])
    filename = sys.argv[3]
    retry_timeout = float(sys.argv[4]) / 1000.0 # convert milliseconds to seconds
    send_file_over_rdt3(remoteHost, port, filename, retry_timeout)
