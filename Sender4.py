# Jordan Bouret 2795423

import sys
import struct
import socket
import time

OUTGOING_HEADER_FORMAT = "!BH"  # 1 byte for type, 2 bytes for sequence number
BYTES_PER_OUTGOING_HEADER = struct.calcsize(OUTGOING_HEADER_FORMAT)
BYTES_PER_OUTGOING_PACKET = 1028
PAYLOAD_SIZE = BYTES_PER_OUTGOING_PACKET - BYTES_PER_OUTGOING_HEADER

ACK_FORMAT = "!H"
BYTES_PER_ACK_HEADER = struct.calcsize(ACK_FORMAT)

MSN = pow(2, 8 * BYTES_PER_ACK_HEADER) # MSN = "Max Sequence Number". for our assignment this is gonna be 2^16 (65,536)

def send_file_over_sr(remoteHost, port, filename, retry_timeout, windowSize):
    if windowSize > MSN: # make sure the user didn't give us a ridiculous windowSize
        print(f"Sorry: Window size cannot exceed {MSN}")
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(retry_timeout)

    base = 0
    next_seq = 0
    local_packets = {}  # local transient cache of packets in case retransmission is needed. i'm storing this as a hashmap with {seq : packet}
    send_times = {}  # dictionary to store send time for each packet {seq: send_time}
    acked = set()  # set of sequence numbers that have been ACKed
    eof_reached = False

    # print(f"Now sending {filename} with window size {windowSize}...\n")

    with open(filename, "rb") as file:
        while (not eof_reached) or (base < next_seq):
            while (next_seq < base + windowSize) and (not eof_reached): # send new packets within the window
                data = file.read(PAYLOAD_SIZE)
                if not data:
                    eof_reached = True
                    break

                packet_header = struct.pack(OUTGOING_HEADER_FORMAT, 0, next_seq % MSN)
                packet = packet_header + data

                local_packets[next_seq] = packet # store curr packet locally in case we end up needing to retransmit it
                send_times[next_seq] = time.time()

                # print(f"Sending {next_seq % MSN}")
                sock.sendto(packet, (remoteHost, port))
                
                next_seq += 1 # next_seq++

            original_timeout = sock.gettimeout()
            sock.settimeout(0.01)  # just a short non-blocking timeout to collect available ACKs
            
            any_acks_received = False
            
            try:
                while True:
                    response, _ = sock.recvfrom(BYTES_PER_ACK_HEADER)
                    ack_seq = struct.unpack(ACK_FORMAT, response)[0]
                    # print(f"{ack_seq} ACK'd 🤩")
                    any_acks_received = True
                    
                    # figure out which seq number this ACK actually represents
                    base_mod = base % MSN # honestly I think that accounting for seq wraparound was overkill for this assignment, but I really wanted to try it :)
                    actual_ack = base + ((ack_seq - base_mod) % MSN)
                    
                    if base <= actual_ack < next_seq:  # if this is a valid ACK
                        acked.add(actual_ack) # mark this packet as ACK'd
                        
                        # remove the packet from our tracking
                        if actual_ack in local_packets:
                            del local_packets[actual_ack]
                        if actual_ack in send_times:
                            del send_times[actual_ack]
                        
                        # slide window if base packet is ACKed
                        while base in acked:
                            acked.remove(base)
                            base += 1
                            # print(f"Window slides to base={base} (mod {base % MSN})")
            except socket.timeout:
                pass
            
            sock.settimeout(original_timeout)
            
            if (not any_acks_received) and (base < next_seq):
                try:
                    response, _ = sock.recvfrom(BYTES_PER_ACK_HEADER)
                    ack_seq = struct.unpack(ACK_FORMAT, response)[0]
                    
                    base_mod = base % MSN
                    actual_ack = base + ((ack_seq - base_mod) % MSN)
                    
                    if base <= actual_ack < next_seq:
                        acked.add(actual_ack)
                        
                        if actual_ack in local_packets:
                            del local_packets[actual_ack]

                        if actual_ack in send_times:
                            del send_times[actual_ack]
                        
                        while base in acked:
                            acked.remove(base)
                            base += 1
                            # print(f"Window slides to base={base} (mod {base % MSN})")
                            
                except socket.timeout:
                    # check for timed out packets and retransmit only those (in SR we don't retransmit the entire window)
                    current_time = time.time()
                    for seq in list(send_times.keys()):
                        if seq < base: # this packet is outside our window... remove it!
                            del send_times[seq]
                            if seq in local_packets: # also rm from local cache
                                del local_packets[seq]
                        elif current_time - send_times[seq] >= retry_timeout:
                            # resend packet(s) that have timed out
                            if seq in local_packets:
                                # print(f"Timeout for packet {seq % MSN}, retransmitting 😡")
                                sock.sendto(local_packets[seq], (remoteHost, port))
                                send_times[seq] = current_time  # update send time

        # application layer doesn't have any more data to transmit, so send the EOF packet 
        eof_header = struct.pack(OUTGOING_HEADER_FORMAT, 1, next_seq % MSN)
        sock.sendto(eof_header, (remoteHost, port))
        # print(f"Sent EOF packet with seq {next_seq % MSN}")

        max_retries = 4
        retries = 0
        eof_acked = False

        while not eof_acked:
            try:
                response, _ = sock.recvfrom(BYTES_PER_ACK_HEADER)
                ack_seq = struct.unpack(ACK_FORMAT, response)[0]
                if ack_seq == next_seq % MSN:
                    eof_acked = True
                    # print(f"Received ACK for EOF packet {ack_seq}")
            except socket.timeout:
                retries += 1
                sock.sendto(eof_header, (remoteHost, port))
                # print(f"Timeout waiting for EOF ACK, retry {retries}/{max_retries}")
            if retries >= max_retries:
                # print("EOF was not acknowledged after {max_retries} send attempts... I give up (we can only assume file transfer is complete)")
                eof_acked = True

        sock.close()

if __name__ == "__main__":
    if len(sys.argv) != 6:
        print("Usage: python3 Sender4.py <remote_host> <remote_port> <filename> <retry_timeout> <window_size_in_ms>")
        sys.exit(1)

    remoteHost = sys.argv[1]
    port = int(sys.argv[2])
    filename = sys.argv[3]
    retry_timeout = float(sys.argv[4]) / 1000.0
    windowSize = int(sys.argv[5])

    send_file_over_sr(remoteHost, port, filename, retry_timeout, windowSize)

