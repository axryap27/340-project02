import sys
import socket
import common
import wildcat_receiver
import select
import threading
import queue
import traceback
import time

class UDP_receiver(threading.Thread):
    def __init__(self, port, my_tunnel):
        super(UDP_receiver, self).__init__()
        self.port = port
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.bind(('', self.port))
        self.inputs = [self.udp_socket]
        self.outputs = [self.udp_socket]
        self.my_tunnel = my_tunnel
        self.die = False
        self.peer_addr = (0, 0)
    
    def run(self):
        while not self.die:
            try:
                readable, writable, exceptional = select.select(self.inputs, self.outputs, self.inputs)
                for r in readable:
                    udp_data, client_addr = r.recvfrom(4096)
                    self.peer_addr = client_addr
                    self.my_tunnel.magic_recv(bytearray(udp_data))
                for w in writable:
                    next_pkt = self.my_tunnel.get_packet()
                    if(next_pkt == None):
                        pass
                    else:
                        w.sendto(next_pkt, self.peer_addr)
                for e in exceptional:
                    traceback.print_exc()
            except Exception as e:
                traceback.print_exc()
        self.udp_socket.close()

    def join(self):
        self.die = True
        super().join()

if __name__ == '__main__':
    if(len(sys.argv) != 6):
        raise Exception("Wrong number of argument!")

    port = int(sys.argv[1])
    allowed_loss = int(sys.argv[2])
    window_size = int(sys.argv[3])
    loss_rate = int(sys.argv[4])
    corrupt_rate = int(sys.argv[5])

    if(allowed_loss > 100 or allowed_loss < 0):
        raise Exception("allowed_loss our of range")
    
    if(loss_rate > 100 or loss_rate < 0):
        raise Exception("loss_rate our of range")

    if(corrupt_rate > 100 or corrupt_rate < 0):
        raise Exception("corrupt_rate our of range")
    
    my_logger = common.logger()
    my_tunnel = common.magic_tunnel(loss_rate, corrupt_rate)
    my_wildcat_receiver = wildcat_receiver.wildcat_receiver(allowed_loss, window_size, my_tunnel, my_logger)
    my_wildcat_receiver.start()
    my_tunnel.my_recv = my_wildcat_receiver.receive
    udp_receiver = UDP_receiver(port, my_tunnel)
    udp_receiver.start()

    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        udp_receiver.join()
        my_wildcat_receiver.join()