import hardware

async def init_network():
    """
        Setup network, and add NICs (Network Interface Controller) in global nics list
    """
    hardware.nics = []

    import machine
    import network

    # Wired LAN
    hardware.nics.append(
        network.LAN(
            mdc = machine.Pin(16),
            mdio = machine.Pin(17),
            power = None,
            phy_type = network.PHY_RTL8201,
            phy_addr=0,
        )
    )
