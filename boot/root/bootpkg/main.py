import _thread
import machine
import micropython
import sys
import uasyncio

from . import hardware
from . import service_beacon
from . import service_ftpd
from . import service_mdns
from . import service_network
from . import service_remote_eval
from . import service_telnet

program_tasks = []
stop_signal = uasyncio.Event()

def main():
    micropython.alloc_emergency_exception_buf(100)

    pkgs = [
        hardware,
    ]
    run_routines("init", pkgs)

    pkgs = [
        service_beacon,
        service_ftpd,
        service_mdns,
        service_network,
        service_remote_eval,
        service_telnet,
    ]
    run_routines("init", pkgs)

    # Try to load the main routine from src
    app = None
    try:
        from . import app
    except Exception as err:
        sys.print_exception(err)

    pkgs = [
        hardware,
        service_beacon,
        service_ftpd,
        service_mdns,
        service_network,
        service_remote_eval,
        service_telnet,
    ]

    loop = uasyncio.get_event_loop()

    # Start system routines
    for service_package in pkgs:
        for routine_name in dir(service_package):
            if routine_name.startswith("routine_"):
                loop.create_task(getattr(service_package, routine_name)())

    # Execute program init while system routines runs, and wait for program init to finish (but system routines are still active)
    if app:
        run_routines("init", [ app ])

    # Start program routines
    program_tasks.extend(loop.create_task(getattr(app, routine_name)()) for routine_name in dir(app) if routine_name.startswith("routine_"))

    # Have a task designed to cancel every program_tasks when stop_signal is triggered
    # It is necessary to have a task and not do it after KeyboardInterrupt, because
    # the task.cancel() loop would then trigger "can't cancel self" exception.
    stop_signal = uasyncio.Event()
    async def stopper():
        # Wait for ctrl-c
        await stop_signal.wait()
        # Stop program tasks
        for task in program_tasks:
            task.cancel()
    stopper_task = loop.create_task(stopper())


    # On normal runtime, if there is an unhandled exception, reset to go back to a good machine state
    loop.set_exception_handler(task_exception_handler)

    try:
        loop.run_until_complete(stopper_task)

        # Unreachable
        print("Assertion failed: this code should be unreachable. resetting.")
        machine.reset()

    except KeyboardInterrupt as e:
        stop_signal.set()

    print("Stopping program tasks, but keeping system tasks running")

    # We'll enter the repl, so we're in debug mode:
    # disable the exception handler that reboots on crash
    # loop.set_exception_handler(None)

    # Continue the loop in a thread to let the main thread run the repl
    # as the stop signal was sent, only the system tasks will still run
    _thread.start_new_thread(loop.run_forever, ())

async def reset_after_ms(delay_ms):
    # Stop program tasks
    for task in program_tasks:
        task.cancel()
    # Sleep a little
    await uasyncio.sleep_ms(delay_ms)
    # If no ctrl-c was sent during the sleep, reset
    if not stop_signal.is_set():
        machine.reset()

def task_exception_handler(loop, context):
    print("An uncaught exception triggered, resetting in 60 seconds (ctrl-c to cancel reset)...")
    loop.create_task(reset_after_ms(60_000))
    loop.default_exception_handler(loop, context)


def run_routines(prefix, packages):
    tasks = []
    loop = uasyncio.get_event_loop()

    for pkg in packages:
        for routine_name in dir(pkg):
            if routine_name.startswith(prefix+"_"):
                tasks.append(loop.create_task(getattr(pkg, routine_name)()))

    def waiter():
        for t in tasks:
            await t

    loop.run_until_complete(waiter())
    return tasks
