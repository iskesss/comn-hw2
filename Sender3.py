# Jordan Bouret, s2795423
import sys
import struct
import socket
import time
import threading
import queue

BYTES_PER_OUTGOING_PACKET = 1027
OUTGOING_HEADER_FORMAT = "!BB"
BYTES_PER_OUTGOING_HEADER = struct.calcsize(OUTGOING_HEADER_FORMAT)
PAYLOAD_SIZE = BYTES_PER_OUTGOING_PACKET - BYTES_PER_OUTGOING_HEADER

# ACK header: one unsigned byte for the sequence number
ACK_FORMAT = "!B"
BYTES_PER_ACK_HEADER = struct.calcsize(ACK_FORMAT)

def send_packet(sock, remoteHost, port, data, seq) -> int: # This is a thread function. Each thread sends packet numbered #seq, but can receieve and return any ack
    header = struct.pack(OUTGOING_HEADER_FORMAT,0,seq)
    packet = header + data
    print(f"Sending packet {seq}")
    sock.sendto(packet, (remoteHost, port))
    
    try:
        # Wait for ACK response
        response, _ = sock.recvfrom(BYTES_PER_ACK_HEADER)
        ack_seq = struct.unpack(ACK_FORMAT, response)[0]
        print(f"Thread received ACK for packet {ack_seq}")

        # Place the received ack in our shared queue
        ack_queue.put(ack_seq)
        return ack_seq
    except socket.timeout:
        print(f"Thread timed out waiting for ACK {seq]")
        return None # shucks.


def send_file_over_gbn(remoteHost, port, filename, retryTimeout, windowSize):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(retry_timeout)

    base = 0
    next_seq = 0
    eof_reached = False
    active_threads = []
    #packetlist = [] # A = acked, S = sent, U = usable, N = Not usable <---- NEVERMIND I DON'T THINK WE NEED THIS

    print(f"Now sending {filename}...\n")

    with open(filename, "rb") as file:
        while not eof_reached or base < next_seq: 
            while next_seq < base + windowSize and not eof_reached:
                data = file.read(PAYLOAD_SIZE)
                if not data:
                    eof_reached = True
                    break
                thread = threading.Thread(
                        target = send_packet, 
                        args=(sock, remoteHost, port, data, next_seq % 256)
                )
                thread.daemon = True # make sure this thread exits when the main program does
                thread.start()
                active_threads.append( (thread, next_seq % 256) ) # insert pair
                next_seq += 1
            # I think there are 2 cases here...
            # 1) All threads return acks, in which case base = base + windowSize, and seq stays as-is. Skip retryTimeout altogether. YAY!
            # 2) After waiting for retryTimeout, not all threads have returned acks, in which case base = base + H (where H is the highest ack returned), 
            #    then seq is decremented such that seq = base. In this case, resend seq+1 and all proceeding packets less than base + windowSize.
            
            # let's check for ACKs (non-blocking)
            try:
                # Process al available ACKs
                while True:
                    ack = ack_queue.get_nowait()
                    print(f"Processing ACK {ack}")

                    # if the current ack is for base or below base, slide da window
                    if (ack >= base%256) or (base%256 > 200 and ack < 50):
                        jjjk



                

        


if __name__ == "__main__":
    if len(sys.argv) != 6:
        print("Sender3 CLI arguments incorrect")
        sys.exit(1)
    remoteHost = sys.argv[1]
    port = int(sys.argv[2])
    filename = sys.argv[3]
    retryTimeout = sys.argv[4]
    windowSize = int(sys.argv[5])

    send_file_over_gbn(remoteHost,port,filename,retryTimeout,windowSize)
