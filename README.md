CS 340 Fall 2026
Project 2: Partially Reliable Transport
Prof. Rashna Kumar


Names & NetID
-------------
Arthur Zakrzewski, ipj6642
Aarya Patel, lxk9828


How to Run
----------
Receiver:
  python3 start_receiver.py <PORT> <ALLOWED_LOSS> <WINDOW_SIZE> <LOSS_RATE> <CORRUPT_RATE>
Sender:
  python3 start_sender.py <IP> <PORT> <ALLOWED_LOSS> <WINDOW_SIZE> <LOSS_RATE> <CORRUPT_RATE>

Example (localhost, w=20, 20% loss, 20% corruption):
  python3 start_receiver.py 8000 0 20 20 20
  python3 start_sender.py localhost 8000 0 20 20 20
Lines typed into the sender will be committed with the payloads appearing in log.txt

Tests:
  python3 test.py



Receiver Design
--------
State: base (next seq to deliver) and a buffer of seq -> payload for
out-of-order arrivals

Overall design:
- buffer -> an out of order dictionary mapping sequence numbers to payloads. This is for packets that arrived early and are waiting for the gap before them to be filled
- base -> the "leftmost" sequence number in the receiver window, i.e. the next packet we need to commit in order. This is also the window_start we report back in every ACK
- maxx -> 65536 (2^16), used with modulo everywhere so sequence numbers wrap around max uint16
- delivered / skipped -> counters of how many packets we've committed vs. given up on, used for the partial reliability loss budget
- blocked_since -> timestamp of when the hole at base started holding up later packets (None if nothing is blocked)
- receive() and run() both touch base, buffer and the counters, so we always grab the lock before reading or updating them

Functions:
- receive(): We drop any packet shorter than 4 bytes or with a bad checksum, and let the sender's timer resend it. The seq number is the first 2 bytes, and the payload is everything between the seq and the checksum. We compute offset = (seq - base) % maxx, which is how far ahead of base the packet is, with wraparound handled. If the offset is less than the window size, we store the packet in the buffer. Otherwise it's an old duplicate or too far ahead, and we drop it. Either way, we then call deliver_in_order() and send an ACK, so the sender can recover if our last ACK was lost.

- deliver_in_order(): While base is in the buffer, we pop it, commit it, and move base forward by one (mod maxx). Since we only ever commit the packet at base, a missing packet stops the loop and everything after it waits in the buffer. Afterwards, we set blocked_since to None if the buffer is empty, or to the current time if a new hole is now blocking later packets.

- build_ack():
    - Every 16-bit field (seq, window_start, checksum) is stored as two bytes, high byte first. We split a number with (n >> 8) and (n & 0xFF), and rebuild it with (high << 8) | low. The ACK bitmap uses one bit per window slot, so it's ceil(w/8) bytes long, in code this implemented by adding 7 to the window and floor division of 8
    Bit i stands for seq (base + i) % 65536 and is 1 if that packet is in the receiver's buffer. Bit i is stored in byte i // 8 at position i % 8, counting from the least significant bit. The receiver sets it with bitmap[i // 8] |= 1 << (i % 8), and the sender checks it with (bitmap[i // 8] >> (i % 8)) & 1
    


Sender Design
------

Note that in the wildcat_sender, *new_packet*, *run* and *receive* functions run each one on a separate thread (3 threads).

Overall design:
    buffer -> a dictionary mapping sequence numbers to packet data ([pkt, expiration_time, acked]) kept to self.window_size

    next_seq_num -> the next sequence number the sender is to send (incremented by one each time)

    first_unacked_seq_num -> the "leftmost" sequence number in the sender window, representing the first packet in order that hasn't been acked yet

    * Multiple threads will be using the above shared memory so we are careful to use locks any time we read or update them *

    new_packet(): loop while self.die is not set to true to prevent a packet trying to be sent after join() is called 
        within this loop, try to see if the window is full, if yes, sleep for a short period of time, giving the window an opportunity to slide with a new ack that could come in, and follow in looping again
            once the buffer is not empty, assemble our packet, with the next_seq_num, the packet_byte_array, and the checksum using our helper

            Then, we create an expiration_time to check against in the future with run() loops. This is set to 400ms ahead of the current time to account for the 10ms sleep on each run() loop and other slowdowns to keep it under the 0.5s retransmission deadline

            Store these two alongside a False acked value into the buffer corresponding to the appropriate sequence number

        Send the packet byte array, and shift up the next_seq_num accounting for wraparounds for uint_16 max and return out of the loop.

    receive(): receiving ack messages -> check for corruption with a checksum check using our helper and compare it to the value sent over.
        We calculate a value called to_slide which is (window_start - first_unacked_seq_num) while accounting for wraparounds with the modulo.

        Note that we can't slide more than the window size over, as that would imply that the base of the receiver is greater than the next_sequence number, additionally we cannot slide the window backwards, with both being handled with the following check
            to_slide > self.window_size
        
        if to_side is less than or equal to the window_size
            we know we can slide the window forward that many packets, as they have been acknowledged on the receiver side
                we loop forward deleting these packets from the sender in flight packet buffer, accounting for wraparounds, and then update the first_unacked_seq_num value to the received start of the receiver window
            
            then we update our ack bookkeeping in our sender window, by iterating through the sent over bitmap with bit 0 corresponding to the packet with seq_num window_start.

    run(): looping while not self.die, trying to get ahold of the lock to get the current timestamp, iterate through all key value pairs in the send buffer dictionary, and if we find that the current timestamp is greater than the expiration time stored in the buffer, and the packet hasn't been acked yet as per the buffer -> we must resend it and update the bookkeeping with a new expiration timestamp, creating a per-packet retransmission timer
        Each loop run ends with a sleep for 10ms, to not be constantly fighting for the lock when there isn't much going on in run besides dispatching retransmissions 



Extra Credit:
-------------


Results
-------

Settings: 20 fps for 15 seconds per trial (300 frames), 3 second drain, corruption = 0, loss rate roughly matched to alpha. Real-time mode uses a 200ms deadline. Each row is one run, so numbers vary a bit between runs since loss is random.

* Each row is a single run, so the numbers will vary a bit between runs since loss is random *

Mode      alpha  w   loss  delivered%  avg ms  p95 ms  retx%
-------------------------------------------------------------
normal      0    8    5      100.0      151     542     9.7
normal      0   32    5      100.0      163     498    11.0
normal     10    8   10       97.3      261     646    21.7
normal     10   32   10       97.0      295     712    19.7
normal     20    8   20       91.7      396     816    43.3
normal     20   32   20       94.3      556     821    46.0
realtime    0    8    5       89.3       64     250     0.0
realtime    0   32    5       90.0       56     219     0.0
realtime   10    8   10       82.7      100     269     1.0
realtime   10   32   10       81.3      120     308     2.0
realtime   20    8   20       59.3      249     482     1.7
realtime   20   32   20       65.0      264     607     0.7



Discussion
----------

normal mode: we delivered at least 100 - alpha percent of frames in every setting, but this reliability cost us a lot of latency
        every lost frame holds up all the frames behind it until a retransmission arrives (at least 0.4s), so p95 latency sat between 0.5 and 0.8 seconds
        the retransmission rate also climbed from about 10% to 45% as the loss rate went up

real-time mode: flips the trade-off. Since we don't retransmit frames older than 200ms, average latency dropped to roughly 55-265ms and p95 stayed under about 0.6 seconds, with almost no retransmissions the only latency the cost is delivery, which fell to about 59-90% of frames

window size: this made a smaller difference. In normal mode, w = 32 tended to have higher latency than w = 8, since more frames can pile up behind a single hole
    Overall, for a live stream or game the real-time behavior is what we want, since a fresh frame now is better than a perfect frame a second late, while something like a file transfer should stay fully reliable

Notes:
  the effective loss rate is roughly double the configured rate, since every packet passes through both the sender's and the receiver's tunnel, and each one applies the loss rate. This is why real-time mode still drops about 10% of frames even at a configured 5% loss.
  In real-time mode alpha doesn't limit skipping, since the deadline overrides the loss budget (a late frame is useless anyway), which is why the real-time alpha = 20 rows deliver below 80%
