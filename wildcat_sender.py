import common
import threading
import zlib
import time

# NOTE: packet_byte_array is bytearray object

# sender is going to need an array of packets in flight for the sliding window to occur, handling 
# go back N with packets in flight


# Sender maintains a sliding window of up to w unacknowledged packets.
# Sender uses per-packet retransmission timers; any unacknowledged packet must be resent within 0.5 s of (last send or timeout).

#checksum helper
def checksum(data):
    return zlib.crc32(bytes(data)) & 0xFFFF

class wildcat_sender(threading.Thread):
    def __init__(self, allowed_loss, window_size, my_tunnel, my_logger):
        super(wildcat_sender, self).__init__()
        self.allowed_loss = allowed_loss
        self.window_size = window_size
        self.my_tunnel = my_tunnel
        self.my_logger = my_logger
        self.die = False
        # add as needed

        # packets in flight that aren't confirmed yet: DICT
        self.buffer = {}

        # the seq num to send the next packet with
        self.next_seq_num = 0

        # earliest unacked packet seq num
        self.window_start = 0

        # have to keep track of start of buffer 
        # and next sequence number 
    
    def new_packet(self, packet_byte_array):
        self.my_tunnel.magic_send(packet_byte_array)


    def receive(self, packet_byte_array):
        print(f"received: {packet_byte_array}")
    
    def run(self):
        while not self.die:
            time.sleep(0.01)
    
    def join(self):
        self.die = True
        super().join()