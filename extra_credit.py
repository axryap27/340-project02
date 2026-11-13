#
# Extra Credit assignment: 
# Simulation and Analysis of a "live" stream and its packet loss and network speed/reliability
#

import time
import test

FPS = 20
DURATION = 15            # seconds of streaming per trial
DRAIN = 3                # seconds to wait after the last frame for resends
DEADLINE = 0.2           # frames older than 200 ms are dropped (real-time simulation)


def run_trial(alpha, w, loss, corruption, port, realtime):
    #use test sender and receiver constructorers
    s = test.sender("localhost", port, alpha, w, loss, corruption, "log/exp")
    r = test.receiver(port, alpha, w, loss, corruption, "log/exp")

    #if we are doing realtime network simulation simulation, we create an articial deadline for both sides
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
    for frame_id in range(n_frames):
        payload = f"{frame_id},{time.time()}".encode()
        s.send(payload)
        time.sleep(1/FPS)
    time.sleep(DRAIN)
    
    r.stop()
    s.stop()

    ##
    ## Stats
    ##
    delivered_ids = set()
    latencies = []
    for payload, t_commit in commits:
        #split the payload and convert bits into string, split by comma
        frame_id, t_sent = payload.decode().split(",")

        #cast int and float for decoded id and time_sent values since decode returns strings from bits
        delivered_ids.add(int(frame_id))
        latencies.append((t_commit - float(t_sent)) * 1000)  # latency in ms: commit time - send time 
    
    latencies.sort()


    #stat computation

    #percent delivered out of total possible delivered
    delivered = 100 * len(delivered_ids) / n_frames

    #avg and p95 calculation with error handling for divide by zero
    if latencies:
        avg = sum(latencies) / len(latencies)
        #p95 latency by taking 95th percentile index of the sorted latencies list
        p95 = latencies[int(0.95 * len(latencies))]
    else:
        avg = p95 = 0
    
    #retransmission rate: 
        # total # of retransmitted frames calculated by subtracting total # of frames from total send count
        # percentage calculated
    ret_rate = 100 * (send_count[0] - n_frames) / n_frames
    
    return delivered, avg, p95, ret_rate

    


if __name__ == "__main__":
    port = 6767
    #overall we are doing 12 trials, 6 with realtime and 6 control with varying alpha, loss and window size
    for realtime in [False, True]:
        #varying inputs for alpha and loss rate
        for alpha, loss in [(0, 5), (10, 10), (20, 20)]:
            #8 byte and 32 byte window size trials
            for w in [8, 32]:
                #returns statistics
                st = run_trial(alpha, w, loss, 0, port, realtime)
                #we change ports for each trial iteration
                port += 1
                mode = "realtime" if realtime else "normal"
                print("RESULT", mode, alpha, w, loss, st)




