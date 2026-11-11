import common
import threading
import zlib
import time

# NOTE: packet_byte_array is bytearray object


# checksum helper
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
        
        # lock for accesing the shared memory between the 3 threads
        self.lock = threading.Lock()

        # packets in flight that aren't confirmed yet: dictionary mapping seq_num -> packet data
        self.buffer = {} # [ready_to_resend_pkt, expiration_time, acked]

        # the seq num to send the next packet with
        self.next_seq_num = 0

        # earliest unacked packet seq num
        self.first_unacked_seq_num = 0
    
    def new_packet(self, packet_byte_array):
        # keep trying to send the packet and giving up the lock until there is space in the window
        while not self.die:
            with self.lock:
                if len(self.buffer) < self.window_size: # if window is not full, (using the length of the buffer dict as the source of truth)
                    
                    # assemble packet as a bytearray with our next sequence number and checksum
                    
                    pkt = bytearray() # empty bytearray to assemble the packet into
                    
                    seq_num = self.next_seq_num 

                    pkt += seq_num.to_bytes(2, byteorder='big')

                    pkt += packet_byte_array 

                    checksum_in_pkt = checksum(pkt).to_bytes(2, byteorder='big')

                    pkt += checksum_in_pkt 


                    # set the expiration time to be 400ms after the current time to be stored in the window
                    # this accounts for the fact that the run loop sleeps for 10ms on each run, and other slowdowns that might bring us closer to the 500ms retransmission deadline
                    expiration_time = time.time() + 0.4
                    acked = False # stored in order to know not to resend already acked packets sitting in the window

                    # store this packet in the buffer alongside expiration and whether it has been acked
                    self.buffer[seq_num] = [pkt, expiration_time, acked] 
                    
                    # SEND COPY OF THE PACKET THROUGH THE TUNNEL
                    # passed by reference into magic send which will corrupt the packet potentially 
                    # which would potentially corrupt the packet stored in our buffer dict
                    self.my_tunnel.magic_send(bytearray(pkt))

                    self.next_seq_num = (seq_num + 1) % 65536 # increment the seq num, wrapping around at uint16 max 

                    return # break out of the loop
            
            time.sleep(0.1) # give receive function a chance to run and slide the window, and try again
        


    def receive(self, packet_byte_array):
        pkt = packet_byte_array

        if len(pkt) < 4: # too small of a packet for our indexing
            return 

        window_start = int.from_bytes(pkt[0:2], byteorder='big')
        to_check = pkt[:-2]
        checksum_in_pkt = int.from_bytes(pkt[-2:], byteorder='big')

        # checksum failure check -> ignore the ack
        if checksum(to_check) != checksum_in_pkt:
            return 

        bitmap = pkt[2:-2]

        # try and acquire the lock to potentially slide the window
        with self.lock:
            # with this ack, calculate how many packets we can slide the window forward by 
            # note: accounting for wraparound,
            to_slide = (window_start - self.first_unacked_seq_num) % 65536

            # our slide can't be bigger than the window size, and the window size can't be before the first unacked seq num 
            if to_slide > self.window_size: # due to modulo, both invalid cases covered with this check
                return 

            # else 
            
            # slide window forward, deleting packets from the sender buffer that are confirmed acked
            for i in range(to_slide):
                to_del_seq_num = (self.first_unacked_seq_num + i) % 65536
                if to_del_seq_num in self.buffer:
                    del self.buffer[to_del_seq_num]
            
            self.first_unacked_seq_num = window_start # update the first unacked seq num to the receiver window's new base

            # if ack bitmap has new info for our packets in sender buffer, update them 

            for i in range(self.window_size):
                bitmap_byte = bitmap[i // 8]
                bitmap_bit = (bitmap_byte >> (i % 8))

                if 1 & bitmap_bit: # if bitmap shows that this packet has been acked
                    cur_seq_num = (window_start + i) % 65536 # find the seq_num
                    if cur_seq_num in self.buffer:
                        self.buffer[cur_seq_num][2] = True # set it to true in the window
            
    
    def run(self):
        while not self.die:
            with self.lock:
                cur_time = time.time()

                for seq_num, pkt_data in self.buffer.items():
                    
                    pkt = pkt_data[0]
                    expiration = pkt_data[1]
                    acked = pkt_data[2]

                    # if nearing the 0.5 retransmission limit and not acked in the window
                    if cur_time > expiration and not acked: 
                        self.my_tunnel.magic_send(bytearray(pkt)) # resend a copy of the stored pkt
                        new_expiration = cur_time + 0.4 # create a new retransmission expiration timestamp
                        self.buffer[seq_num][1] = new_expiration # update expiration bookkeeping in window

            time.sleep(0.01) # 10 ms
    
    def join(self):
        self.die = True
        super().join()