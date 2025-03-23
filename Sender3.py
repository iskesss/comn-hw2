# Jordan Bouret 2795423
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

MSN = pow(2, 8 * BYTES_PER_ACK_HEADER) # MSN = "Max Sequence Number". for our assignment this is gonna be 2^16 (65,536)

def send_file_over_gbn(remoteHost, port, filename, retry_timeout, windowSize):
    # Check if window size is valid
    if windowSize > MSN:
        print(f"Sorry: Window size cannot exceed {MSN}")
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(retry_timeout)

    base = 0
    next_seq = 0
    packets = {}  # local transient cache of packets in case retransmission is needed. i'm storing this as a hashmap with {seq : packet}
    eof_reached = False

    print(f"Now sending {filename} with window size {windowSize}...\n")

    with open(filename, "rb") as file:
        while (not eof_reached) or (base < next_seq):
            # I think there are 2 cases here...
            # 1) All packets are ACKed quickly, in which case base = base + windowSize, and next_seq stays as-is. Skip retryTimeout altogether. YAY!
            # 2) After waiting for retryTimeout, not all packets have been ACKed, in which case base = base + H (where H is the highest consecutive ACK received),
            #    and we need to retransmit packets from base to next_seq that are still within the window.

            while (next_seq < base+windowSize) and (not eof_reached):
                data = file.read(PAYLOAD_SIZE)
                if not data:
                    eof_reached = True
                    break

                packet_header = struct.pack(OUTGOING_HEADER_FORMAT, 0, next_seq % MSN)
                packet = packet_header + data

                packets[next_seq] = packet # store curr packet locally in case we end up needing to retransmit it

                print(f"Sending {next_seq % MSN}")
                sock.sendto(packet, (remoteHost, port))
                next_seq += 1 # next_seq++

            # try to receive ACKs for the packets we just sent
            original_timeout = sock.gettimeout()
            sock.settimeout(0.01)  # just a short timeout for sake of non-blocking

            any_acks_received = False

            # try to collect all available ACKs
            try:
                while True:
                    response, _ = sock.recvfrom(BYTES_PER_ACK_HEADER)
                    ack_seq = struct.unpack(ACK_FORMAT, response)[0]
                    print(f"{ack_seq} ACK'd 🤩")
                    any_acks_received = True

                    # determine if this ACK advances the window (and handle wraparound ofc)
                    base_mod = base % MSN

                    # calculate the actual sequence number this ACK represents
                    # this accounts for wraparound in the sequence space
                    actual_ack = base + ((ack_seq - base_mod) % MSN)

                    if base <= actual_ack < next_seq: # if this is a valid ACK that advances our window
                        # then we shift the window forward
                        old_base = base
                        base = actual_ack + 1
                        print(f"Base {old_base}—>{base} ({base%MSN} in sequence space)")

                        # delete ACK'd packets from local cache
                        for i in range(old_base, base):
                            if i in packets:
                                del packets[i]
            except socket.timeout: # no more ACKs available at the moment, continue!
                pass

            sock.settimeout(original_timeout) # restore original timeout

            # if we're waiting for ACKs but literally none have arrived, wait for the full timeout
            if (not any_acks_received) and (base < next_seq):
                try:
                    response, _ = sock.recvfrom(BYTES_PER_ACK_HEADER)
                    ack_seq = struct.unpack(ACK_FORMAT, response)[0]
                    print(f"{ack_seq} ACK'd ⏳")

                    # process the ACK (same logic as above)
                    base_mod = base % MSN
                    actual_ack = base + ((ack_seq - base_mod) % MSN)

                    if base <= actual_ack < next_seq:
                        old_base = base
                        base = actual_ack + 1
                        print(f"Window slides to base={base} (mod {base % MSN})")

                        # delete ACK'd packets from local cache
                        for i in range(old_base, base):
                            if i in packets:
                                del packets[i]
                except socket.timeout:
                    # timeout occurred, retransmit all packets in window
                    print(f"Timeout detected. Retransmitting window from {base % MSN}")
                    for i in range(base, min(next_seq, base + windowSize)):
                        if i in packets:
                            sock.sendto(packets[i], (remoteHost, port))
                            print(f"Resending packet {i % MSN}")

        # send EOF packet
        eof_header = struct.pack(OUTGOING_HEADER_FORMAT, 1, next_seq % MSN)
        sock.sendto(eof_header, (remoteHost, port))
        print(f"Sent EOF packet with seq {next_seq % MSN}")

        try: # wait for EOF ACK
            response, _ = sock.recvfrom(BYTES_PER_ACK_HEADER)
            ack_seq = struct.unpack(ACK_FORMAT, response)[0]
            print(f"Received ACK for EOF packet {ack_seq}")
        except socket.timeout:
            print("Timeout waiting for EOF ACK, but file transfer might be complete")

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

    send_file_over_gbn(remoteHost, port, filename, retry_timeout, windowSize)
