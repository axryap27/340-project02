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
        
        # lock for accesing the shared memory between the 3 threads
        self.lock = threading.Lock()

        # packets in flight that aren't confirmed yet: DICT
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

        # checksum failure
        if checksum(to_check) != checksum_in_pkt:
            # TODO: prolly log it
            return 

        bitmap = pkt[2:-2]

        # try and acquire the lock to potentially slide the window
        with self.lock:
            

    
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