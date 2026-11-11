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


