import uasyncio
from uio import IOBase
import os

from . import settings

class TelnetServer(IOBase):

    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.buf=bytearray()

        self.parse_state = self.STATE_BYTE

        self.peer = self.reader.get_extra_info('peername')
        print("New telnet connection: {}".format(self.peer))

    STATE_BYTE = 0
    STATE_EXPECT_COMMAND = 1
    STATE_EXPECT_OPTION = 2

    async def accept(self):
        self.writer.write(bytes([255, 252, 34])) # dont allow line mode
        await self.writer.drain()
        self.writer.write(bytes([255, 251, 1])) # turn off local echo
        await self.writer.drain()

        try:
            # Link the terminal to this connection
            os.dupterm(self)
            while True:
                try:
                    try:
                        res = await self.reader.read(1)

                        if res == b'':
                            return

                        # Slip telnet codes
                        for b in res:
                            if self.parse_state == self.STATE_BYTE:
                                if b == 255:
                                    self.parse_state = self.STATE_EXPECT_COMMAND
                                else:
                                    self.buf.append(b)
                            elif self.parse_state == self.STATE_EXPECT_COMMAND:
                                if b in (251, 252, 253, 253):
                                    self.parse_state = self.STATE_EXPECT_OPTION
                                else:
                                    self.parse_state = self.STATE_BYTE
                                    if b == 255:
                                        self.buf.append(b)
                            else: # self.parse_state == STATE_EXPECT_OPTION:
                                self.parse_state = self.STATE_BYTE

                        # Indicate to the dupterm
                        os.dupterm_notify(None)

                    except uasyncio.TimeoutError:
                        res = b''
                except KeyboardInterrupt:
                    uasyncio.create_task(self.trigger_keyboard_interrupt())

        except OSError as err:
            return

        finally:
            await self.reader.wait_closed()
            os.dupterm(None)
            print('Telnet client disconnected: {}'.format(self.peer))

    async def trigger_keyboard_interrupt(self):
        raise KeyboardInterrupt()

    def readinto(self,b):
        read_len = min(len(self.buf),len(b))
        if read_len:
            b[0:read_len] = self.buf[0:read_len]
            self.buf[:] = self.buf[read_len:]
            return read_len
        else:
            return None

    def write(self,data):
        try:
            if len(data) == 0:
                return 0
            self.writer.s.write(bytes(data).replace(b'\255', b'\255\255').replace(b'\003', b'ctrl-c'))#+b'\r\n')
            return len(data)
        except KeyboardInterrupt:
            uasyncio.create_task(self.trigger_keyboard_interrupt())
            # Replay the write
            self.write(data)


async def _accept_handler(reader, writer):
    await TelnetServer(reader, writer).accept()

async def routine_remote_eval():

    if not settings.TELNET_ENABLE:
        return

    HOST = "0.0.0.0"

    async with await uasyncio.start_server(_accept_handler, HOST, settings.TELNET_PORT) as server:
        print(f'Telnet server started on {HOST}:{settings.TELNET_PORT}')
        await server.wait_closed()

    print("Telnet server stopped")

