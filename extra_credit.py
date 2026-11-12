#
# Extra Credit assignment: 
# Simulation and Analysis of a "live" stream and its packet loss and network speed/reliability
#

import sys
import time
import test

FPS = 20
DURATION = 15            # seconds of streaming per trial
DRAIN = 3                # seconds to wait after the last frame for resends
DEADLINE = 0.2           # frames older than 200 ms are dropped (real-time simulation)


def run_trial(alpha, w, loss, corruption, port):
    #use test sender and receiver constructorers
    s = test.sender("localhost", port, alpha, w, loss, corruption, "log/exp")
    r = test.receiver(alpha, w, loss, corruption, "log/exp")

    #commit logs and magic send

    if realtime:
        s.my_wildcat_sender.deadline = DEADLINE
        r.my_wildcat_receiver.skip_after = DEADLINE
        r.my_wildcat_receiver.realtime = True

    ##
    ## Measurement wrappers
    ##

    #list of (payload, commit_time), records when each frame is committed
    commits = []
    original_commit = r.my_logger.commit
    def timed_commit(payload):
        commits.append((bytes(payload), time.time()))
        original_commit(payload)
    r.my_logger.commit = timed_commit

    #count the total number of transmitted packets
    #includes retransmitted packets
    send_count = [0]
    original_send = s.my_tunnel.magic_send
    def counting_send(pkt):
        send_count[0] += 1
        original_send(pkt)
    s.my_tunnel.magic_send = counting_send


    ##
    ## Loop for payloads, one frame ever 1/FPS seconds
    ##

    n_frames = FPS * DURATION
    start = time.time()

    for frame_id in (n_frames):
        payload = f"{frame_id},{time.time()}".encode()
        s.send(payload)
        time.sleep(1/FPS)
    elapsed = time.time() - start
    time.sleep(DRAIN)

    
    r.stop()
    s.stop()

    ##
    ## Stats
    ##
    delivered_ids = set()
    latencies = []
    for payload, t_commit in commits:
        frame_id, t_sent = payload.decode().split(",")
        delivered_ids.add(int(frame_id))
        latencies.append((t_commit - float(t_sent)) * 1000)  #in milliseconds, we take the packet travel time and 
    
    latencies.sort()
    
    


if __name__ == "__main__":
    port = 9000
    #TODO





