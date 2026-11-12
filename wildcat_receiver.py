import common
import threading
import zlib
import time


#checksum helper
def checksum(data):
    return zlib.crc32(bytes(data)) & 0xFFFF


# NOTE: packet_byte_array is bytearray object

class wildcat_receiver(threading.Thread):
    def __init__(self, allowed_loss, window_size, my_tunnel, my_logger):
        super(wildcat_receiver, self).__init__()
        self.allowed_loss = allowed_loss
        self.window_size = window_size
        self.my_tunnel = my_tunnel
        self.my_logger = my_logger
        self.die = False
        self.lock = threading.Lock()

        # needs a buffer to store and reassemble out of order packets
        self.buffer = {}
        self.base = 0
        self.maxx = 65536
        

    def receive(self, packet_byte_array):
        pkt = packet_byte_array
        #too short
        if len(pkt) < 4:
            return 
        body = pkt[:-2]
        checksum_in_pkt = (pkt[-2] << 8) | pkt[-1]
        #checksum fail, corrupted packet
        if(checksum(body) != checksum_in_pkt):
            return

        #seq is the first two bytes of body and payload is the rest
        #convert seq into one number since seqs can be split across more than 1 byte 
        seq = (body[0] << 8) | body[1]
        payload = body[2:]
        #some lock
        with self.lock:
            offset = (seq - self.base) % self.maxx
            if offset < self.window_size:
                if seq not in self.buffer:
                  self.buffer[seq] = payload

            # rebuild order from buffer via the base seq number
            self.deliver_in_order()

            # build the ack from the ordered payloads + bitmap
            ack = self.build_ack()

            # copy the ack by wrapping in bytearray in case of corrupted values since original packet is passed by reference
            self.my_tunnel.magic_send(bytearray(ack))


    ##
    ## HELPERS
    ##

    def deliver_in_order(self):
        #checking while the base is in buffer, we pop and commit it
        while self.base in self.buffer:
            payload = self.buffer.pop(self.base)
            self.my_logger.commit(payload)
            #we increment and go onto the next base/payload
            self.base = (self.base + 1) % self.maxx
        #this ensures we wait and commit in order despite packets arriving out-of-order

    def build_ack(self):
        # build the ack from base + bitmap of buffered packets
        window_start = bytearray([self.base >> 8, self.base & 0xFF])

        #ceiling calculation number of bytes for map size
        bitmap = bytearray((self.window_size + 7) // 8)

        #bitmapping, set to 1 if in received else 0
        for i in range(0, self.window_size):
            if ((self.base+i) % self.maxx) in self.buffer:
                bitmap[i // 8] |= 1 << (i % 8)
                            
        ack_body = window_start + bitmap 
        ack_checksum = checksum(ack_body)
        return ack_body + bytearray([ack_checksum >> 8, ack_checksum & 0xFF])


    # for partial reliability??
    def maybe_skip(self):
        #TODO
        pass


    def run(self):
        while not self.die:
            time.sleep(0.01)
            
    def join(self):
        self.die = True
        super().join()