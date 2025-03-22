# Jordan Bouret, s2795423
import sys
import struct
import socket
import time
import queue

OUTGOING_HEADER_FORMAT = "!BH"  # 1 byte for type, 2 bytes for sequence number
BYTES_PER_OUTGOING_HEADER = struct.calcsize(OUTGOING_HEADER_FORMAT)
BYTES_PER_OUTGOING_PACKET = 1028
PAYLOAD_SIZE = BYTES_PER_OUTGOING_PACKET - BYTES_PER_OUTGOING_HEADER

# ACK header: 16-bit unsigned short for the sequence number
ACK_FORMAT = "!H"
BYTES_PER_ACK_HEADER = struct.calcsize(ACK_FORMAT)

MAX_SEQ_NUM = pow(2, 8 * BYTES_PER_ACK_HEADER) # this is gonna be 2^16, so 65,536 in our case

# Thread-safe queue to collect ACKs from threads
ack_queue = queue.Queue()

def send_file_over_gbn(remoteHost, port, filename, retry_timeout, windowSize):
    # Check if window size is valid
    if windowSize > MAX_SEQ_NUM:
        print(f"Sorry: Window size cannot exceed {MAX_SEQ_NUM}")
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(retry_timeout)

    base = 0
    next_seq = 0
    packets = {}  # Store packets for retransmission
    eof_reached = False

    print(f"Now sending {filename} with window size {windowSize}...\n")

    try:
        with open(filename, "rb") as file:
            # Continue until all data is sent and acknowledged
            while not eof_reached or base < next_seq:
                # Send packets within window
                while next_seq < base + windowSize and not eof_reached:
                    data = file.read(PAYLOAD_SIZE)
                    if not data:
                        eof_reached = True
                        break

                    # Prepare packet with header
                    packet_header = struct.pack(OUTGOING_HEADER_FORMAT, 0, next_seq % MAX_SEQ_NUM)
                    packet = packet_header + data
                    
                    # Store packet for potential retransmission
                    packets[next_seq] = packet
                    
                    # Send the packet
                    sock.sendto(packet, (remoteHost, port))
                    print(f"Sending packet {next_seq % MAX_SEQ_NUM}")
                    
                    next_seq += 1

                # Try to receive ACKs (non-blocking)
                original_timeout = sock.gettimeout()
                sock.settimeout(0.01)  # Short timeout for non-blocking behavior
                
                ack_received = False
                window_advanced = False
                
                # Try to collect all available ACKs
                try:
                    while True:
                        response, _ = sock.recvfrom(BYTES_PER_ACK_HEADER)
                        ack_seq = struct.unpack(ACK_FORMAT, response)[0]
                        print(f"Received ACK for packet {ack_seq}")
                        ack_received = True
                        
                        # Determine if this ACK advances the window
                        # We need to handle wraparound in the 16-bit sequence space
                        base_mod = base % MAX_SEQ_NUM
                        
                        # Calculate the actual sequence number this ACK represents
                        # This accounts for wraparound in the sequence space
                        actual_ack = base + ((ack_seq - base_mod) % MAX_SEQ_NUM)
                        
                        # If this is a valid ACK that advances our window
                        if base <= actual_ack < next_seq:
                            # Move the window forward
                            old_base = base
                            base = actual_ack + 1
                            window_advanced = True
                            print(f"Window slides to base={base} (mod {base % MAX_SEQ_NUM})")
                            
                            # Clean up packets that are now acknowledged
                            for i in range(old_base, base):
                                if i in packets:
                                    del packets[i]
                except socket.timeout: # No more ACKs available at the moment, continue
                    pass
                
                sock.settimeout(original_timeout) # restore original timeout
                
                # if no ACKs received and we're waiting for ACKs, wait for the full timeout
                if not ack_received and base < next_seq:
                    try:
                        response, _ = sock.recvfrom(BYTES_PER_ACK_HEADER)
                        ack_seq = struct.unpack(ACK_FORMAT, response)[0]
                        print(f"Received ACK for packet {ack_seq}")
                        
                        # Process the ACK (same logic as above)
                        base_mod = base % MAX_SEQ_NUM
                        actual_ack = base + ((ack_seq - base_mod) % MAX_SEQ_NUM)
                        
                        if base <= actual_ack < next_seq:
                            old_base = base
                            base = actual_ack + 1
                            window_advanced = True
                            print(f"Window slides to base={base} (mod {base % MAX_SEQ_NUM})")
                            
                            for i in range(old_base, base):
                                if i in packets:
                                    del packets[i]
                    except socket.timeout:
                        # Timeout occurred, retransmit all packets in window
                        print(f"Timeout detected. Retransmitting window from {base % MAX_SEQ_NUM}")
                        for i in range(base, min(next_seq, base + windowSize)):
                            if i in packets:
                                sock.sendto(packets[i], (remoteHost, port))
                                print(f"Resending packet {i % MAX_SEQ_NUM}")

            # send EOF packet
            eof_header = struct.pack(OUTGOING_HEADER_FORMAT, 1, next_seq % MAX_SEQ_NUM)
            sock.sendto(eof_header, (remoteHost, port))
            print(f"Sent EOF packet with seq {next_seq % MAX_SEQ_NUM}")
            
            # wait for EOF ACK
            try:
                response, _ = sock.recvfrom(BYTES_PER_ACK_HEADER)
                ack_seq = struct.unpack(ACK_FORMAT, response)[0]
                print(f"Received ACK for EOF packet {ack_seq}")
            except socket.timeout:
                print("Timeout waiting for EOF ACK, but file transfer might be complete")

            print("File transmission complete!")

    except Exception as e:
        print(f"Error during transmission: {e}")
    finally:
        sock.close()


def is_between(start, value, end):
    """
    Check if a value is between start and end in a circular sequence space.
    This handles wraparound cases properly.
    """
    if start <= end:
        # Normal case: [start...end]
        return start <= value <= end
    else:
        # Wraparound case: [start...MAX_SEQ_NUM-1] + [0...end]
        return start <= value < MAX_SEQ_NUM or 0 <= value <= end


if __name__ == "__main__":
    if len(sys.argv) != 6:
        print("Usage: python3 Sender3.py <remote_host> <remote_port> <filename> <retry_timeout> <window_size>")
        sys.exit(1)

    remoteHost = sys.argv[1]
    port = int(sys.argv[2])
    filename = sys.argv[3]
    retry_timeout = float(sys.argv[4])  # Changed to float to allow fractional seconds
    windowSize = int(sys.argv[5])

    send_file_over_gbn(remoteHost, port, filename, retry_timeout, windowSize)

