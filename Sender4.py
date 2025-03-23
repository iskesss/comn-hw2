# Jordan Bouret 2795423
import sys
import struct
import socket
import time

OUTGOING_HEADER_FORMAT = "!BH"  # 1 byte for type, 2 bytes for sequence number
BYTES_PER_OUTGOING_HEADER = struct.calcsize(OUTGOING_HEADER_FORMAT)
BYTES_PER_OUTGOING_PACKET = 1028
PAYLOAD_SIZE = BYTES_PER_OUTGOING_PACKET - BYTES_PER_OUTGOING_HEADER

# ACK header: 16-bit unsigned short for the sequence number
ACK_FORMAT = "!H"
BYTES_PER_ACK_HEADER = struct.calcsize(ACK_FORMAT)

MSN = pow(2, 8 * BYTES_PER_ACK_HEADER) # MSN = "Max Sequence Number". for our assignment this is gonna be 2^16 (65,536)

def send_file_over_sr(remoteHost, port, filename, retry_timeout, windowSize):
    # Check if window size is valid
    if windowSize > MSN:
        print(f"Sorry: Window size cannot exceed {MSN}")
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(retry_timeout)

    base = 0
    next_seq = 0
    packets = {}  # local transient cache of packets in case retransmission is needed. i'm storing this as a hashmap with {seq : packet}
    send_times = {}  # dictionary to store send time for each packet {seq: send_time}
    acked = set()  # set of sequence numbers that have been ACKed
    eof_reached = False

    print(f"Now sending {filename} with window size {windowSize}...\n")

    with open(filename, "rb") as file:
        while (not eof_reached) or (base < next_seq):
            # Send new packets within the window
            while (next_seq < base + windowSize) and (not eof_reached):
                data = file.read(PAYLOAD_SIZE)
                if not data:
                    eof_reached = True
                    break

                packet_header = struct.pack(OUTGOING_HEADER_FORMAT, 0, next_seq % MSN)
                packet = packet_header + data

                packets[next_seq] = packet # store curr packet locally in case we end up needing to retransmit it
                send_times[next_seq] = time.time()  # Record send time for timeout checking

                print(f"Sending {next_seq % MSN}")
                sock.sendto(packet, (remoteHost, port))
                
                next_seq += 1 # next_seq++

            # Try to receive ACKs with a short timeout
            original_timeout = sock.gettimeout()
            sock.settimeout(0.01)  # Short non-blocking timeout to collect available ACKs
            
            any_acks_received = False
            
            try:
                while True:
                    response, _ = sock.recvfrom(BYTES_PER_ACK_HEADER)
                    ack_seq = struct.unpack(ACK_FORMAT, response)[0]
                    print(f"{ack_seq} ACK'd 🤩")
                    any_acks_received = True
                    
                    # Calculate the actual sequence number this ACK represents
                    base_mod = base % MSN
                    actual_ack = base + ((ack_seq - base_mod) % MSN)
                    
                    if base <= actual_ack < next_seq:  # if this is a valid ACK
                        # Mark this packet as ACKed
                        acked.add(actual_ack)
                        
                        # Remove the packet from our tracking
                        if actual_ack in packets:
                            del packets[actual_ack]
                        if actual_ack in send_times:
                            del send_times[actual_ack]
                        
                        # Slide window if base packet is ACKed
                        while base in acked:
                            base += 1
                            print(f"Window slides to base={base} (mod {base % MSN})")
            except socket.timeout:
                pass  # No more ACKs available at the moment
            
            sock.settimeout(original_timeout)  # Restore original timeout
            
            # If no ACKs received, wait for a full timeout and check for expired packets
            if not any_acks_received and base < next_seq:
                try:
                    response, _ = sock.recvfrom(BYTES_PER_ACK_HEADER)
                    ack_seq = struct.unpack(ACK_FORMAT, response)[0]
                    print(f"{ack_seq} ACK'd ⏳")
                    
                    # Process the ACK
                    base_mod = base % MSN
                    actual_ack = base + ((ack_seq - base_mod) % MSN)
                    
                    if base <= actual_ack < next_seq:
                        acked.add(actual_ack)
                        
                        if actual_ack in packets:
                            del packets[actual_ack]
                        if actual_ack in send_times:
                            del send_times[actual_ack]
                        
                        while base in acked:
                            base += 1
                            print(f"Window slides to base={base} (mod {base % MSN})")
                            
                except socket.timeout:
                    # Check for timed out packets and retransmit only those - in SR we don't retransmit the entire window
                    current_time = time.time()
                    for seq in list(send_times.keys()):
                        if seq < base:
                            # This packet is outside the window, remove it
                            del send_times[seq]
                            if seq in packets:
                                del packets[seq]
                        elif current_time - send_times[seq] >= retry_timeout:
                            # This packet has timed out, retransmit it
                            if seq in packets:
                                print(f"Timeout for packet {seq % MSN}, retransmitting")
                                sock.sendto(packets[seq], (remoteHost, port))
                                send_times[seq] = current_time  # Update send time

        # send EOF packet
        eof_header = struct.pack(OUTGOING_HEADER_FORMAT, 1, next_seq % MSN)
        sock.sendto(eof_header, (remoteHost, port))
        print(f"Sent EOF packet with seq {next_seq % MSN}")
        
        eof_send_time = time.time()
        eof_acked = False

        # Try to get EOF ACK with retries
        while not eof_acked:
            try:
                response, _ = sock.recvfrom(BYTES_PER_ACK_HEADER)
                ack_seq = struct.unpack(ACK_FORMAT, response)[0]
                if ack_seq == next_seq % MSN:
                    print(f"Received ACK for EOF packet {ack_seq}")
                    eof_acked = True
                else:
                    print(f"Received unexpected ACK {ack_seq}, waiting for EOF ACK")
            except socket.timeout:
                # Resend EOF packet if timeout
                current_time = time.time()
                if current_time - eof_send_time >= retry_timeout:
                    print("Timeout waiting for EOF ACK, resending EOF")
                    sock.sendto(eof_header, (remoteHost, port))
                    eof_send_time = current_time
                    
                    # After a few retries, assume file transfer is complete
                    if current_time - eof_send_time >= retry_timeout * 3:
                        print("Maximum EOF retries reached, assuming transfer complete")
                        break

        print("File transmission complete!")


if __name__ == "__main__":
    if len(sys.argv) != 6:
        print("Usage: python3 Sender3.py <remote_host> <remote_port> <filename> <retry_timeout> <window_size>")
        sys.exit(1)

    remoteHost = sys.argv[1]
    port = int(sys.argv[2])
    filename = sys.argv[3]
    retry_timeout = float(sys.argv[4])
    windowSize = int(sys.argv[5])

    send_file_over_sr(remoteHost, port, filename, retry_timeout, windowSize)