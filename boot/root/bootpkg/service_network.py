import hashlib
import hardware

from . import settings

def create_link_local_ip(nic):
    h = hashlib.sha256(nic.config('mac')).digest()
    return f"169.254.{((((h[0]<<8)+h[1]) % 254)+1)}.{h[2]}", "255.255.0.0"


async def init_network_local_link_ips():
    if not settings.NETWORK_SET_LOCAL_LINK_IP:
        return

    for nic in hardware.nics:
        # Set up by default a link-local ip, generated using the nic's mac address
        # It can be reconfigured later by the application, or stay as-is.
        # 127.0.0.2 is a fake ip to disable gateway and dns connectivity
        nic.ifconfig(create_link_local_ip(nic) + ("127.0.0.2", "127.0.0.2"))

        if not nic.active():
            nic.active(True)

    print('Network config:')
    for nic in hardware.nics:
        print("  - ", nic.ifconfig())

