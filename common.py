import queue
import random

log_file = "log.txt"

class magic_tunnel:
    my_recv = None

    def __init__(self, loss_rate, corrupt_rate):
        self.loss_rate = loss_rate
        self.corrupt_rate = corrupt_rate
        self.send_queue = queue.Queue()
        self.recv_queue = queue.Queue()
    
    def do_magic(self, packet_byte_array):
        loss = random.randint(0,100)
        corrupt = random.randint(0,100)
        if loss < self.loss_rate:
            # packet got lost
            return None
        if corrupt < self.corrupt_rate:
            # packet got corrupted
            # print("Before corrupt: ")
            # print_bits(packet_byte_array)
            bit_to_flip = random.randint(0, len(packet_byte_array) * 8 - 1)
            byte_to_be_flipped = packet_byte_array[int(bit_to_flip / 8)]
            flipped_byte = byte_to_be_flipped ^ (1 << (bit_to_flip % 8))
            packet_byte_array[int(bit_to_flip / 8)] = flipped_byte
            # print("After corrupt: ")
            # print_bits(packet_byte_array)
        return packet_byte_array
    
    def magic_send(self, packet_byte_array):
        pkt_to_send = self.do_magic(packet_byte_array)
        if pkt_to_send == None:
            print("Send lost")
            return
        else:
            self.send_queue.put(pkt_to_send)

    def magic_recv(self, packet_byte_array):
        if self.my_recv == None:
            raise Exception("Receive function not registered")
        else:
            pkt_to_receive = self.do_magic(packet_byte_array)
            if pkt_to_receive == None:
                print("Receive lost")
                return
            else:
                self.my_recv(pkt_to_receive)
        pass

    def get_packet(self):
        ret_pkt = None
        try:
            ret_pkt = self.send_queue.get_nowait()
        except queue.Empty:
            ret_pkt = None
        return ret_pkt

def print_bits(byte_array):
    print_str = ""
    for b in byte_array:
        print_str = print_str + bin(b) + " "
    print(print_str)

class logger:
    commit_list = []
    def __init__(self, my_log_file=log_file):
        self.my_log_file = my_log_file
        open(self.my_log_file, 'w+').close()
        self.commit_list = []

    def commit(self, packet):
        self.commit_list = self.commit_list + [packet]
        with open(self.my_log_file, 'a') as f:
            f.write(packet.__repr__())
            f.write("\n")
    
    def get_commit_list(self):
        return self.commit_list