import sys
import socket
import common
import wildcat_sender
import select
import threading
import queue
import traceback
import time

class UDP_sender(threading.Thread):
    def __init__(self, ip, port, my_tunnel):
        super(UDP_sender, self).__init__()
        self.send_addr = (ip, port)
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.inputs = [self.udp_socket]
        self.outputs = [self.udp_socket]
        self.my_tunnel = my_tunnel
        self.die = False
    
    def run(self):
        while not self.die:
            try:
                readable, writable, exceptional = select.select(self.inputs, self.outputs, self.inputs)
                for r in readable:
                    udp_data, _ = r.recvfrom(4096)
                    self.my_tunnel.magic_recv(bytearray(udp_data))
                for w in writable:
                    next_pkt = self.my_tunnel.get_packet()
                    if(next_pkt == None):
                        pass
                    else:
                        w.sendto(next_pkt, self.send_addr)
                for e in exceptional:
                    traceback.print_exc()
            except Exception as e:
                traceback.print_exc()
        self.udp_socket.close()

    def join(self):
        self.die = True
        super().join()

if __name__ == '__main__':
    if(len(sys.argv) != 7):
        raise Exception("Wrong number of argument!")
    
    ip = sys.argv[1]
    port = int(sys.argv[2])
    allowed_loss = int(sys.argv[3])
    window_size = int(sys.argv[4])
    loss_rate = int(sys.argv[5])
    corrupt_rate = int(sys.argv[6])

    if(allowed_loss > 100 or allowed_loss < 0):
        raise Exception("allowed_loss our of range")
    
    if(loss_rate > 100 or loss_rate < 0):
        raise Exception("loss_rate our of range")

    if(corrupt_rate > 100 or corrupt_rate < 0):
        raise Exception("corrupt_rate our of range")

    my_tunnel = common.magic_tunnel(loss_rate, corrupt_rate)
    my_logger = common.logger()
    my_wildcat_sender = wildcat_sender.wildcat_sender(allowed_loss, window_size, my_tunnel, my_logger)
    my_wildcat_sender.start()
    my_tunnel.my_recv = my_wildcat_sender.receive
    udp_sender = UDP_sender(ip, port, my_tunnel)
    udp_sender.start()
    
    try:
        while True:
            s = input()
            my_wildcat_sender.new_packet(bytearray(str.encode(s)))
    except KeyboardInterrupt:
        udp_sender.join()
        my_wildcat_sender.join()
