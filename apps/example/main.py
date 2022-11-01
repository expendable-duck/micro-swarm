import uasyncio

async def init_func_1():
    print("init function 1 begin")
    await uasyncio.sleep_ms(300)
    print("init function 1 end")

async def init_func_2():
    await uasyncio.sleep_ms(100)
    print("init function 2 begin")
    await uasyncio.sleep_ms(100)
    print("init function 2 end")

async def routine_a():
    print("routine function a begin")
    await uasyncio.sleep_ms(3000)
    print("routine function a end")

async def routine_b():
    await uasyncio.sleep_ms(1000)
    print("routine function b begin")
    await uasyncio.sleep_ms(1000)
    print("routine function b end")
