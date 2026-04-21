# Protective ReRoute

## Introduction
This directory explores Protective ReRoute (PRR), a routing algorithm used by Google. The algorithm is a variant of ECMP for adjusting the path of a packet through a network. Rather than being routed for load balancing, however, PRR is used to allow end hosts to avoid network paths that are experiencing faults. In Google's use they've seen as much as a ninety percent reduction in the time of faults, and their own simulations show downtime reduction to just a few seconds for ninety five percent of TCP connections, according to [this paper.](https://dl.acm.org/doi/10.1145/3603269.3604867)

## Topology
For demonstration this exercise uses a topology with two hosts, connected by a network of fourteen switches. One switch acts as ingress and another as egress, and between those are three layers each of four switches, each layer fully connected to the next.

<p align="center">
<img src="images/Network Diagram.png" title="PRR Network Topology"/>
</p>

## Protective ReRoute
Protective ReRoute, as stated, is a variant of ECMP. Rather than hash and route only on the flow's 5-tuple, however, PRR also hashes on IPv6's Flow Label field. This allows an end host to change its Flow Label whenever it detects an outage in an attempt to find a different route through the network.

A host considers a detection to have been detected whenever it would trigger a TCP Retransmission Time Out. While this isn't always caused by a network failure, or may be caused by a fault in the return path, unnecessary rerouting is not serious, and causes minimal disruption. Because of this, when a fault occurs, both hosts in a connection will repeatedly change flow label until they both reach a path that is not experiencing a fault.

## Claim
The paper discusses Google's simulations of TCP recovery through this method, and an analysis of the results. They show that most connections will recover very quickly, with over ninety five percent recovering in just a few seconds. This is the claim that I have chosen to test and replicate.

<p align="center">
<img src="images/Verify Figure 4.png" title="Google's TCP Simulation Results"/>
</p>

## Experimental Setup
Each switch is set to use PRR to decide which port to use for egress. The `ipv4_lpm table` is used to match a /24, which applies the hashing, and a `prr_nhop` table then matches on the hash results to do the forwarding. The Ingress and Egress switches also have a /32 match for last leg forwarding.Each host has on it a `send.py` program that will repeatedly send a TCP packet to the specified host, and then wait for a response. The program can also be started in "listening" mode, which causes it to watch for these packets and then respond. A variable within the program can be set to cause the program to spin up multiple threads.

Each program, or thread within the program, keeps an exponential average of the response time for each packet. When a sending program does not hear a response within a timeout, it will enter a failing mode. In the failing mode it will no longer update its reponse time average, and will randomly change the packet's IPv4 ToS field before each new send. When it again detects a response, it records in a file how long the connection was failing, from the last successful packet to the latest, then it exits failing mode.

Tests are run through the control layer using the `break_links.py` script. When a test is running an additional /32 match is added to the `ipv4_lpm` table of some subset of the switches that will drop the packets traveling through these switches in order to simulate a fault in the network. These extra entries are left alone for 40 seconds before, at the end of the test, theyare removed. The script then waits for ten seconds between tests for any connections that are still failing to recover.

By taking down a set of routers for this time, the logs of fault durations can be used to detect how quickly each connection recovered from a fault. These can then be compiled into a graph using `data_grapher.py` through pychart.

## Limitations
This experiment has several important differences from the original paper's. First, this is being emulated in Mininet. While Mininet is good, it isn't quite the same as running on real hardware, which may experience different issues than a clean emulation. It also is not as large as the real networks Google was able to use for testing, which can span across a continent, or even multiple continents.

The largest difference is that, as noted above, this experiment is being done with IPv4 rather than IPv6. Early on Mininet was having issues with IPv6, so the algorithm was instead converted to use IPv4. Rather than the Flow Label field from IPv6, the experiment uses IPv4's ToS/DSCP field. This field is meant to be used for differentiated service, and is not meant to be set by the end host, but in this emulated network the only practical difference is the size of the field. The overall algorithm is not different for this change.

## Results
Overall the results show PRR as successfully reducing the duration of visible faults in the system. The end hosts immediately begin adjusting the ToS field as soon as a fault is encountered, and almost always find a new path to the other host within seconds, as promised.

<p algin="center">
<img src="images/Figure 1.png" title="A Graph of Outage Times"/>
</p>

Despite the few outages that lasted for a long duration the average duration of an outage was only seven seconds, and over half of all outages were recovered in fewer than 3 seconds. From this the overall figure from Google that 95% of issues are resolved in just a few seconds seems very accurate.

## Issues
There were a few problems in the creation and execution of these experiments. The largest of these is one that is likely skewing the results somewhat in favor of PRR. While the only interruptions to the connection between hosts should have been the faults caused by the experiments, Scapy was instead failing to register response packets periodically without any actual fault necessary. Inspection of network showed responses being received well within the timeout window, but the program still frequently hit its timeout anyways. This means that the datapoints include many small faults that have no connection to the experiments, and whose recovery likely has nothing to do with PRR, from an unidentified source.

There also is likely room for better test creation. While some care was taken to ensure a connection was unlikely to pass two consecutive tests, the specific switches and numbers of switches were chosen without much order to them.

Other than this, the only issues found were ones that were easily corrected or accounted for. For one, the hash input for each switch was changed to include the identifier of the switch itself. Before this was added each switch used the same hash input, so rather than having 64 paths through the network there were actually only 4, as a packet that hashed to Port 3 on one switch would also hash to Port 3 on all other switches.

A small stumble occurred when creating the control plane program, as the process of connecting to a switch for adjusting its table entries also wipes any existing table entries. This made the previously implemented `make_switch_commands.py`, written to generate all 14 switch's `sx-commands` without having to manually adjust them, somewhat redundant. Luckily the code was easily transferred over to re-initialize the switches to the proper table entries.

