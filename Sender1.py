# Jordan Bouret, s2795423
import sys
import struct
import socket

BYTES_PER_HEADER = struct.calcsize("!B") # ! = big endian, B = uchar
BYTES_PER_PACKET = 1024

def send_file_over_rdt1(remoteHost, port, filename):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    with open(filename, "rb") as file: 
        while True:
            # Read data such that header + data fits in BYTES_PER_PACKET
            data = file.read(BYTES_PER_PACKET - BYTES_PER_HEADER)
            if not data:
                break
            header = struct.pack("!B", 0) # sending a flag == 0 tells the receiver there's still data to be transmitted
            packet = header + data
            sock.sendto(packet, (remoteHost, port))

    header = struct.pack("!B", 1) # we want to send an EOF packet now that we're out of data to transmit
     
    sock.sendto(header,(remoteHost, port)) 
    sock.close()
    print("File has successfully been sent")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python sender.py <remoteHost> <port> <filename>")
        sys.exit(1)  
    remoteHost = sys.argv[1]
    port = int(sys.argv[2])
    filename = sys.argv[3]
    send_file_over_rdt1(remoteHost,port,filename)


