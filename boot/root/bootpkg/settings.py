#########
# BOOT settings
#########
# This boot package code version
VERSION = "1.0.0"

#########
# FTPD is an FTP service used to upload app code
# (no security whatsoever)
#########
FTPD_ENABLE = True
FTPD_PORT = 21

#########
# MDNS is a zeroconf multicast udp server used to send the device's hostname.local
#########
MDNS_ENABLE = True
# Udp sockets can't be blocking, so we have to poll
# regularly to see if we've received packets
MDNS_POLL_MS = 500

#########
# BEACON is a service that regularly send a udp packet
# to send this device's configuration
#########
BEACON_ENABLE = True
# The time between two beacon sent
BEACON_REPEAT_MS = 2000
# List of ips to send beacon udp packet to.
# Use ["255.255.255.255"] to broadcast on networks
BEACON_DESTINATION_IPS = [ "255.255.255.255" ]
BEACON_DESTINATION_PORT = 1139


#########
# REMOTE_EVAL is a tcp socket where you can send python to be executed
# (no security whatsoever)
#########
REMOTE_EVAL_ENABLE = True
REMOTE_EVAL_PORT = 1139

#########
# TELNET server
# (no security whatsoever)
#########
TELNET_ENABLE = True
TELNET_PORT = 23

#########
# NETWORK settings
#########
# Set up pseudorandom 169.254.xxx.xxx ips to each network interface (no DNS, no gateway)
NETWORK_SET_LOCAL_LINK_IP = True
