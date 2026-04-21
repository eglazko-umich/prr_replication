#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
# Reason-GPL: import-scapy
# Modified by eglazko@umich.edu to test Protective Reroute
import argparse
import sys
import socket
import random
import struct
import time
import random
import threading

from scapy.all import sendp, srp1, get_if_list, get_if_hwaddr, sniff
from scapy.all import Ether, IP, IPv6, UDP, TCP

intf = ""

def get_if():
    ifs=get_if_list()
    iface=None # "h1-eth0"
    for i in get_if_list():
        if "eth0" in i:
            iface=i
            break
    if not iface:
        print("Cannot find eth0 interface")
        exit(1)
    return iface

def send_loop(thread_id, addr, intf):
    eth = Ether(src=get_if_hwaddr(intf), dst='ff:ff:ff:ff:ff:ff')
    ip = IP(dst=addr, tos=random.randint(0,63)) 
    tcp = TCP(dport=6001 + (2 * thread_id), sport=6000 + (2 * thread_id)) 
    pkt = eth / ip / tcp / '1'

    last_success = time.monotonic()
    failing = False

    baseline = 100
    pkt.tos = thread_id

    while True:
        #print("send tos = {}".format(pkt.tos))
        #resp = srp1(pkt, iface=intf, timeout = (baseline + 10) / 1000, verbose=False)
        sendp(pkt, iface=intf, verbose=False)
        resp = sniff(iface = intf, filter="tcp and port {}".format(3001+(2*thread_id)), timeout=(baseline*2)/1000, count=1)
        if not(resp):
            failing = True
            pkt.tos = random.randint(0, 63)
            #print("No resp, new tos = {}".format(pkt.tos))
        else:
            #print("Yes resp")
            new_time = time.monotonic()
            if(failing):
                #print("Logging")
                failing = False
                time_down = new_time - last_success
                with open("test_logs/send_{}_log.txt".format(thread_id), 'a') as f:
                    f.write("{}n".format(time_down))
            else:
                rtt = new_time - last_success
                last_success = new_time
                baseline = 0.8 * baseline + 0.2 * rtt
        time.sleep(0.1)

def respond(packet, addr, intf, thread_id):
    eth = Ether(src=get_if_hwaddr(intf), dst='ff:ff:ff:ff:ff:ff')
    ip = IP(dst=addr, tos=random.randint(0,63)) 
    tcp = TCP(dport=3001 + (2 * thread_id), sport=3000 + (2 * thread_id)) 
    pkt = eth / ip / tcp / '1'

    sendp(pkt, iface=intf, verbose=False)

def listen(thread_id, addr, intf):
    incoming_sport = 6000 + (2 * thread_id)
    incoming_dport = 6001 + (2 * thread_id)
    pkt_filter = "host 10.0.1.1 and port {}".format(incoming_dport)
    print("Beginning sniffing for {}".format(pkt_filter))
    sniff(iface=intf, filter=pkt_filter, prn=lambda x: respond(x, addr, intf, thread_id))
    print("Done sniffing")

def main():
    if len(sys.argv)<2:
        print('pass 2 arguments: <destination> [listen]"')
        exit(1)

    addr = socket.gethostbyname(sys.argv[1])
    prr_fl = random.randint(0, 63)
    intf = get_if()

    listening = False
    if len(sys.argv) > 2 and sys.argv[2] == 'listen':
        listening = True

    threads = []
    num_threads = 1
    for i in range(num_threads):
        if listening:
            t = threading.Thread(target = listen, args = (i,addr, intf))
            threads.append(t)
            t.start()
        else:
            print("Creating thread.")
            t = threading.Thread(target = send_loop, args = (i, addr, intf))
            threads.append(t)
            t.start()

    print("Waiting for threads.")
    for t in threads:
        t.join()

if __name__ == '__main__':
    main()
