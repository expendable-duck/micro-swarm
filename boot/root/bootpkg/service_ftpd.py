from . import auftpd
from . import settings

async def routine_ftpd():
    if not settings.FTPD_ENABLE:
        return

    async with auftpd.FTPServer("0.0.0.0", cmd_port=settings.FTPD_PORT, verbose_level=1) as ftp:
        await ftp.wait()

