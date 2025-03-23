# Jordan Bouret 2795423
import sys
import struct
import socket

BYTES_PER_HEADER = struct.calcsize("!HB") # ! = big endian, H = ushort, B = uchar
BYTES_PER_PACKET = 1027 # 3 bytes for header, 1024 for payload 

def send_file_over_rdt1(remoteHost, port, filename):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    seq = 0 # this is rdt1, so seq doesn't matter and will be ignored by the receiver
    with open(filename, "rb") as file: 
        while True:
            # Read data such that header + data fits in BYTES_PER_PACKET
            data = file.read(BYTES_PER_PACKET - BYTES_PER_HEADER)
            if not data:
                break
            header = struct.pack("!HB",seq,0) # sending a flag == 0 tells the receiver there's still data to be transmitted
            packet = header + data
            sock.sendto(packet, (remoteHost, port))
            seq += 1
            if seq > 65536: # to avoid overflow of 2-byte flag
                seq = 0

    header = struct.pack("!HB",seq,1) # we want to send an EOF packet now that we're out of data to transmit
    sock.sendto(header, (remoteHost, port)) 
    sock.close()
    print("File has successfully been transferred (EOF packet just sent).")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 Sender1.py <ip> <port> <file_to_send>")
        sys.exit(1)  
    remoteHost = sys.argv[1]
    port = int(sys.argv[2])
    filename = sys.argv[3]
    send_file_over_rdt1(remoteHost,port,filename)


