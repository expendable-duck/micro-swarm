import select
import uasyncio

import board
import hardware
from . import slimDNS

from . import settings

async def routine_mdns():
    """
        Broadcast the hostname.local using the mDNS mechanism
    """

    if not settings.MDNS_ENABLE:
        return

    while True:

        poll = select.poll()
        servers = []

        for nic in hardware.nics:
            try:
                local_addr = nic.ifconfig()[0]
                server = slimDNS.SlimDNSServer(local_addr, board.host_name)
                poll.register(server.sock, select.POLLIN)
                servers.append(server)
            except OSError:
                pass

        if servers:
            while True:
                events = poll.poll(0)
                for event in events:
                    for server in servers:
                        if event[0] == server.sock:
                            server.process_waiting_packets()

                await uasyncio.sleep_ms(settings.MDNS_POLL_MS)

        await uasyncio.sleep_ms(settings.MDNS_POLL_MS)
