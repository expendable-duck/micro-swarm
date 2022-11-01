import hardware
import board
import uasyncio
import socket
import json
import os
from . import settings

BEACON_REPEAT_MS = 2000

async def routine_beacon_broadcast():
    """
        Broadcast the device information regularly to network
    """

    if not settings.BEACON_ENABLE:
        return

    app = None
    app_version = None
    try:
        from . import app
        app_version = getattr(app, "VERSION", None)
    except Exception:
        pass

    uname = os.uname()
    beacon_content = json.dumps({
        "type": "beacon",
        "ifconfigs": [nic.ifconfig() for nic in hardware.nics],
        "settings": {
            "board": dict((attr, getattr(board, attr)) for attr in sorted(dir(board)) if not attr.startswith('_')),
            "boot": dict((attr, getattr(settings, attr)) for attr in sorted(dir(settings)) if not attr.startswith('_')),
        },
        "versions": {
            "app": app_version,
            "boot": settings.VERSION,
            "micropython": dict((attr, getattr(uname, attr)) for attr in sorted(dir(uname)) if not attr.startswith('_')),
        },
    })

    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            while True:
                for ip in settings.BEACON_DESTINATION_IPS:
                    s.sendto(beacon_content, (ip, settings.BEACON_DESTINATION_PORT))
                await uasyncio.sleep_ms(BEACON_REPEAT_MS)
        except OSError:
            pass
        finally:
            if s:
                s.close()
        await uasyncio.sleep_ms(BEACON_REPEAT_MS)
