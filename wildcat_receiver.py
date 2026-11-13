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

         # partial reliability (only used when allowed_loss > 0 or realtime modeling)
        self.delivered = 0          #packets commited
        self.skipped = 0            # holes given up on
        self.blocked_since = None   # when the hole at base started blocking later packets
        self.skip_after = 0.5       # seconds a hole may block before we skip it
        self.realtime = False       # real-time mode: ignore the loss budget
        

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
        #bool used for resetting time, keeps track of if base has updated to next packet
        progressed = False
        #checking while the base is in buffer, we pop and commit it
        # ensures we wait and commit in order despite packets arriving out-of-order
        while self.base in self.buffer:
            
            payload = self.buffer.pop(self.base)
            self.my_logger.commit(payload)
            #we increment and go onto the next base/payload
            #also add one to delivered, need to keep track for partial reliability
            self.delivered+=1
            self.base = (self.base + 1) % self.maxx
            
            #set progressed to true, use this for timeout reset
            progressed = True
        if not self.buffer:
            self.blocked_since = None
        # start the timer if we just reached a new hole, or this hole has no timer yet
        elif progressed or self.blocked_since is None:
            self.blocked_since = time.time()


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



    #Answers has the hole at base waited long enough AND am I allowed to skip it
    def maybe_skip(self):
        #need to take the lock since this is called in run() and is in a separate thread from receive()
        with self.lock:
            #nothing is blocking, we don't skip or
            if self.blocked_since is None:
                return
            #something is blocked and the time since it has been block is less than half a second (limit for hold)
            elif (time.time() - self.blocked_since) < self.skip_after:
                return
            #we cannot skip, if we do, the actual loss rate exceeds the "network's" set amount
            if not self.realtime and (self.skipped+1)*100 > self.allowed_loss*(self.delivered+self.skipped+1):
                return
            # all conditions met to skip the packet, we add one to base and skipped total 
            self.skipped+=1
            self.base = (self.base + 1) % self.maxx
            # now the base has moved, we need to deliver everything since we skipped that packet in the window
            # we build the ack after packets are commmited in order from the buffer
            self.deliver_in_order()
            ack = self.build_ack()
            #send the ack, making a copy to avoid corruption via pass-by-reference errors
            self.my_tunnel.magic_send(bytearray(ack))

    def run(self):
        while not self.die:
            #if there is an allowed loss OR we are simulating a realtime network
            if self.allowed_loss > 0 or self.realtime:
                #call function to determine if packets can be skipped
                self.maybe_skip()
            time.sleep(0.01)
            
    def join(self):
        self.die = True
        super().join()