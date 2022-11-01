# Minimal TCP server that evals python code sent to it

import errno
import sys
import uasyncio

from . import settings

async def _handle_request(reader, writer):
    src = None
    try:
        src = await reader.read(-1)
    except uasyncio.TimeoutError:
        pass
    except Exception as e:
        if e.args[0] == errno.ECONNRESET:  # connection reset by client
            pass
        else:
            raise e
    finally:
        await writer.drain()
        writer.close()
        reader.close()
        await writer.wait_closed()
        await reader.wait_closed()

    if src:
        try:
            exec(src)
        except Exception as err:
            print("*** Remote eval exception: ***")
            sys.print_exception(err)

async def routine_remote_eval():

    if not settings.REMOTE_EVAL_ENABLE:
        return

    HOST = "0.0.0.0"

    async with await uasyncio.start_server(_handle_request, HOST, settings.REMOTE_EVAL_PORT) as server:
        print(f'Remote control server started on {HOST}:{settings.REMOTE_EVAL_PORT}')
        await server.wait_closed()

    print("Remote control server stopped")
