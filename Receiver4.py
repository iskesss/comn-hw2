# Jordan Bouret 2795423
import sys
import struct
import socket

INCOMING_PACKET_SIZE = 1028 
INCOMING_HEADER_FORMAT = "!BH"  # header format: flag (1 byte) and seq number (2 bytes)
BYTES_PER_HEADER = struct.calcsize(INCOMING_HEADER_FORMAT)
ACK_FORMAT = "!H"  # 2 bytes for the seq number (16-bit)
MSN = pow(2, 8 * struct.calcsize(ACK_FORMAT))

def receive_file_over_sr(listen_port, filename, windowSize):
    listen_ip = "127.0.0.1"  # I had to hardcode this for our assignment
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((listen_ip, listen_port))
    print(f"Receiver listening on {listen_ip}:{listen_port}...")

    base = 0  # base of the receiver's window
    buffer = {}  # buffer to store out-of-order packets {seq: data}

    with open(filename, "wb") as outfile:
        while True:
            packet, sender_addr = sock.recvfrom(INCOMING_PACKET_SIZE)

            if len(packet) < BYTES_PER_HEADER:  # verify that the packet is large enough to contain a header
                print("Received packet too small, ignoring")
                continue

            flag, seq = struct.unpack(INCOMING_HEADER_FORMAT, packet[:BYTES_PER_HEADER])

            if flag == 0: # if current packet holds data
                print(f"Received packet with seq={seq}, base={base % MSN}")

                # Calculate actual sequence number (handling wraparound)
                base_mod = base % MSN
                actual_seq = base + ((seq - base_mod) % MSN)
                
                if base <= actual_seq < base + windowSize: # is curr packet within acceptable window ?
                    # we must always ACK packets within the window (this is what makes Selective Repeat special)
                    ack = struct.pack(ACK_FORMAT, seq)
                    sock.sendto(ack, sender_addr)
                    print(f"😁 Packet {seq} within window, sending ACK")
                    
                    # store curr packet (unless we've already done so)
                    if actual_seq not in buffer:
                        buffer[actual_seq] = packet[BYTES_PER_HEADER:]
                        print(f"Buffered packet {seq}")
                    
                    while base in buffer: # deliver in-order packets to outfile (application layer)
                        outfile.write(buffer[base])
                        print(f"Delivered packet {base % MSN} to application")
                        del buffer[base]
                        base += 1
                        print(f"Window advanced to base={base % MSN}")
                elif actual_seq < base: # seq is less than window base
                    # this is a duplicate of a packet we've already processed (our initial ack(s) probably got lost or took too long). 
                    # we should still send an ACK to let the sender know we got it
                    ack = struct.pack(ACK_FORMAT, seq)
                    sock.sendto(ack, sender_addr)
                    print(f"Duplicate packet {seq}, already processed. Sent ACK.")
                else:
                    # packet is beyond our window, ignore it
                    print(f"Packet {seq} is beyond window, ignoring")

            elif flag == 1:  # if we receive an EOF packet, acknowledge it and break the loop
                ack = struct.pack(ACK_FORMAT, seq)
                sock.sendto(ack, sender_addr)
                print(f"Received EOF packet with seq={seq}, transmission complete")
                
                # deliver any remaining buffered packets
                sorted_seqs = sorted(buffer.keys())
                for seq in sorted_seqs:
                    outfile.write(buffer[seq])
                    print(f"Flushing buffered packet {seq % MSN} to application")
                
                break

    sock.close()
    print("File has been received successfully.")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 Receiver3.py <listen_port> <filename> <window_size>")
        sys.exit(1)

    listen_port = int(sys.argv[1])
    filename = sys.argv[2]
    windowSize = int(sys.argv[3])

    receive_file_over_sr(listen_port, filename, windowSize)