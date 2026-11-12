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

- receive(MSG): verifies the checksum, then computes
  offset = (seq - base) mod 2^16.
    - offset < w: the packet is in the window and is buffered.
    - Otherwise it is outside the window (an old duplicate or too far
      ahead) and is dropped.
  It then commits every contiguous packet starting at base, advancing
  base (mod 2^16) after each one.
- It sends an ACK for every packet that passes the checksum, including
  dropped duplicates, so the sender recovers from lost ACKs.


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

