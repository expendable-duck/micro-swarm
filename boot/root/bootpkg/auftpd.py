#
# Small ftp server for ESP8266 Micropython
# Based on the work of chrisgp - Christopher Popp and pfalcon - Paul Sokolovsky
#
# The server accepts passive mode only. It runs in background.
# Start the server with:
#
# import auftpd
# async with auftpd.FTPServer("0.0.0.0", [cmd_port=21, verbose_level=0]) as ftp:
#     await ftp.wait()
#
# cmd_port is the port number (default 21)
# verbose_level controls the level of printed activity messages, values 0, 1, 2
#
# Copyright (c) 2016 Christopher Popp (initial ftp server framework)
# Copyright (c) 2016 Paul Sokolovsky (background execution control structure)
# Copyright (c) 2016 Robert Hammelrath (putting the pieces together and a
# few extensions)
# Copyright (c) 2020 Jan Wieck Use separate FTP servers per socket for STA + AP mode
# Copyright (c) 2021 JD Smith Use a preallocated buffer and improve error handling.
# Copyright (c) 2022 expendable-duck Changed the paradigm to async, using uasyncio.
# Distributed under MIT License
#
import socket
import hardware
import os
import gc
import sys
import errno
from time import sleep_ms, localtime
import uasyncio

_CHUNK_SIZE = const(1024)

_month_name = ("", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


class ftp_data_connection:
    def __init__(self, ftp_server):
        self.ftp = ftp_server

    async def __aenter__(self):
        if self.ftp.active:  # active mode
            await self.ftp.log_msg(2, "FTP Data connection with:", self.ftp.act_data_addr)
            self._reader, self._writer = await uasyncio.open_connection(self.ftp.act_data_addr, self.ftp.actv_data_port)
        else:  # passive mode
            await self.ftp.log_msg(2, "FTP Data connection with:", self.ftp.remote_addr)
            self._pasv_ready = uasyncio.Event()
            self.ftp._pasv_handler = self._pasv_handler
            self.ftp._pasv_trigger.set()
            await self._pasv_ready.wait()

        return self._reader, self._writer

    async def __aexit__(self, exc_type, exc, tb):
        await self._writer.drain()
        self._writer.close()
        self._reader.close()
        await self._writer.wait_closed()
        await self._reader.wait_closed()

    async def _pasv_handler(self, reader, writer):
        self._reader = reader
        self._writer = writer
        self._pasv_ready.set()


class FTPServer:

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.stop()
        await self.wait()

    def __init__(self, server_ip, cmd_port=21, pasv_data_port=13333, actv_data_port=20, verbose_level=0):

        self.verbose_level = verbose_level

        self.local_addr = server_ip
        self.local_port = cmd_port

        self.cwd = '/'
        self.fromname = None

        self.active = True
        self.pasv_data_addr = server_ip
        self.pasv_data_port = pasv_data_port
        self.actv_data_port = actv_data_port

        self.local_addr = server_ip

        self._pasv_trigger = uasyncio.Event()
        self.client_busy = False

    async def start(self):
        await self.log_msg(1, "FTP server started on {}:{}".format(self.local_addr, self.local_port))
        self.cmd_server  = await uasyncio.start_server(self.handle_commands_connection,  self.local_addr, self.local_port)
        self.data_server = await uasyncio.start_server(self.handle_pasv_data_connection, self.pasv_data_addr, self.pasv_data_port)

    async def wait(self):
        await self.cmd_server.wait_closed()
        await self.data_server.wait_closed()
        await self.log_msg(1, "FTP server stopped")


    def stop(self):
        self.cmd_server.close()
        self.data_server.close()

    async def send_list_data(self, path, writer, full):
        try:
            for fname in os.listdir(path):
                writer.write(self.make_description(path, fname, full))
                await writer.drain()
        except Exception as e:  # path may be a file name or pattern
            path, pattern = self.split_path(path)
            try:
                for fname in os.listdir(path):
                    if self.fncmp(fname, pattern):
                        writer.write(self.make_description(path, fname, full))
                        await writer.drain()
            except:
                pass

    def make_description(self, path, fname, full):
        if full:
            stat = os.stat(self.get_absolute_path(path, fname))
            file_permissions = ("drwxr-xr-x"
                                if (stat[0] & 0o170000 == 0o040000)
                                else "-rw-r--r--")
            file_size = stat[6]
            tm = stat[7] & 0xffffffff
            tm = localtime(tm if tm < 0x80000000 else tm - 0x100000000)
            if tm[0] != localtime()[0]:
                description = "{} 1 owner group {:>10} {} {:2} {:>5} {}\r\n".\
                    format(file_permissions, file_size,
                        _month_name[tm[1]], tm[2], tm[0], fname)
            else:
                description = "{} 1 owner group {:>10} {} {:2} {:02}:{:02} {}\r\n".\
                    format(file_permissions, file_size,
                        _month_name[tm[1]], tm[2], tm[3], tm[4], fname)
        else:
            description = fname + "\r\n"
        return description

    async def send_file_data(self, path, writer):
        buffer = bytearray(_CHUNK_SIZE)
        mv = memoryview(buffer)
        with open(path, "rb") as file:
            bytes_read = file.readinto(buffer)
            while bytes_read > 0:
                writer.write(mv[0:bytes_read])
                await writer.drain()
                bytes_read = file.readinto(buffer)

    async def save_file_data(self, path, reader, mode):
        buffer = bytearray(_CHUNK_SIZE)
        mv = memoryview(buffer)
        with open(path, mode) as file:
            bytes_read = await reader.readinto(buffer)
            while bytes_read > 0:
                file.write(mv[0:bytes_read])
                bytes_read = await reader.readinto(buffer)

    def get_absolute_path(self, cwd, payload):
        # Just a few special cases "..", "." and ""
        # If payload start's with /, set cwd to /
        # and consider the remainder a relative path
        if payload.startswith('/'):
            cwd = "/"
        for token in payload.split("/"):
            if token == '..':
                cwd = self.split_path(cwd)[0]
            elif token != '.' and token != '':
                if cwd == '/':
                    cwd += token
                else:
                    cwd = cwd + '/' + token
        return cwd

    def split_path(self, path):  # instead of path.rpartition('/')
        tail = path.split('/')[-1]
        head = path[:-(len(tail) + 1)]
        return ('/' if head == '' else head, tail)

    # compare fname against pattern. Pattern may contain
    # the wildcards ? and *.
    def fncmp(self, fname, pattern):
        pi = 0
        si = 0
        while pi < len(pattern) and si < len(fname):
            if (fname[si] == pattern[pi]) or (pattern[pi] == '?'):
                si += 1
                pi += 1
            else:
                if pattern[pi] == '*':  # recurse
                    if pi == len(pattern.rstrip("*?")):  # only wildcards left
                        return True
                    while si < len(fname):
                        if self.fncmp(fname[si:], pattern[pi + 1:]):
                            return True
                        else:
                            si += 1
                    return False
                else:
                    return False
        if pi == len(pattern.rstrip("*")) and si == len(fname):
            return True
        else:
            return False

    def open_dataclient(self):
        return ftp_data_connection(self)

    async def handle_pasv_data_connection(self, reader, writer):
        await self._pasv_trigger.wait()
        handler = self._pasv_handler
        self._pasv_trigger.clear()
        await handler(reader, writer)


    async def handle_commands_connection(self, reader, writer):
        self.reader = reader
        self.writer = writer

        peername = self.writer.get_extra_info('peername')
        self.remote_addr = peername[0]
        self.act_data_addr = peername[0]

        await self.log_msg(2, "FTP Command connection from:", self.remote_addr)
        await self.write("220 Hello, this is the {}.\r\n".format(sys.platform))
        await self.exec_ftp_commands()


    async def exec_ftp_commands(self):
        while True:
            try:
                gc.collect()

                data = (await self.reader.readline()).decode("utf-8").rstrip("\r\n")

                if len(data) <= 0:
                    # No data, close
                    # This part is NOT CLEAN; there is still a chance that a
                    # closing data connection will be signalled as closing
                    # command connection
                    await self.log_msg(2, "*** No data, assume QUIT")
                    return

                if self.client_busy:  # check if another client is busy
                    await self.write("400 Device busy.\r\n")  # tell so the remote client
                    return  # and quit
                self.client_busy = True  # now it's my turn

                # check for log-in state may done here, like
                # if self.logged_in == False and not command in\
                #    ("USER", "PASS", "QUIT"):
                #    self.writer.write("530 Not logged in.\r\n")
                #    return

                command = data.split()[0].upper()
                payload = data[len(command):].lstrip()  # partition is missing
                path = self.get_absolute_path(self.cwd, payload)
                await self.log_msg(2, "Command={}, Payload={}".format(command, payload))

                if command == "USER":
                    # self.logged_in = True
                    await self.write("230 Logged in.\r\n")
                    # If you want to see a password,return
                    #   "331 Need password.\r\n" instead
                    # If you want to reject an user, return
                    #   "530 Not logged in.\r\n"
                elif command == "PASS":
                    # you may check here for a valid password and return
                    # "530 Not logged in.\r\n" in case it's wrong
                    # self.logged_in = True
                    await self.write("230 Logged in.\r\n")
                elif command == "SYST":
                    await self.write("215 UNIX Type: L8\r\n")
                elif command in ("TYPE", "NOOP", "ABOR"):  # just accept & ignore
                    await self.write('200 OK\r\n')
                elif command == "QUIT":
                    await self.write('221 Bye.\r\n')
                    return
                elif command == "PWD" or command == "XPWD":
                    await self.write('257 "{}"\r\n'.format(self.cwd))
                elif command == "CWD" or command == "XCWD":
                    try:
                        if (os.stat(path)[0] & 0o170000) == 0o040000:
                            self.cwd = path
                            await self.write('250 OK\r\n')
                        else:
                            await self.write('550 Fail\r\n')
                    except:
                        await self.write('550 Fail\r\n')
                elif command == "PASV":
                    await self.write('227 Entering Passive Mode ({},{},{}).\r\n'.format(
                        self.pasv_data_addr.replace('.', ','),
                        self.pasv_data_port >> 8, self.pasv_data_port % 256))
                    self.active = False
                elif command == "PORT":
                    items = payload.split(",")
                    if len(items) >= 6:
                        self.act_data_addr = '.'.join(items[:4])
                        if self.act_data_addr == "127.0.1.1":
                            # replace by command session addr
                            self.act_data_addr = self.remote_addr
                        self.pasv_data_port = int(items[4]) * 256 + int(items[5])
                        await self.write('200 OK\r\n')
                        self.active = True
                    else:
                        await self.write('504 Fail\r\n')
                elif command == "LIST" or command == "NLST":
                    if payload.startswith("-"):
                        option = payload.split()[0].lower()
                        path = self.get_absolute_path(
                                self.cwd, payload[len(option):].lstrip())
                    else:
                        option = ""
                    try:
                        async with self.open_dataclient() as (reader, writer):
                            await self.write("150 Directory listing:\r\n")
                            await self.send_list_data(path, writer,
                                                command == "LIST" or 'l' in option)
                            await self.write("226 Done.\r\n")
                    except Exception as err:
                        await self.write('550 Fail\r\n')
                        raise err
                elif command == "RETR":
                    try:
                        async with self.open_dataclient() as (reader, writer):
                            await self.write("150 Opened data connection.\r\n")
                            await self.send_file_data(path, writer)
                            await self.write("226 Done.\r\n")
                    except:
                        await self.write('550 Fail\r\n')
                elif command == "STOR" or command == "APPE":
                    try:
                        async with self.open_dataclient() as (reader, writer):
                            await self.write("150 Opened data connection.\r\n")
                            await self.save_file_data(path, reader,
                                                "wb" if command == "STOR" else "ab")
                            await self.write("226 Done.\r\n")
                    except:
                        await self.write('550 Fail\r\n')
                elif command == "SIZE":
                    try:
                        await self.write('213 {}\r\n'.format(os.stat(path)[6]))
                    except:
                        await self.write('550 Fail\r\n')
                elif command == "MDTM":
                    try:
                        tm=localtime(os.stat(path)[8])
                        await self.write('213 {:04d}{:02d}{:02d}{:02d}{:02d}{:02d}\r\n'.format(*tm[0:6]))
                    except:
                        await self.write('550 Fail\r\n')
                elif command == "STAT":
                    if payload == "":
                        await self.write("211-Connected to ({})\r\n"
                                   "    Data address ({})\r\n"
                                   "    TYPE: Binary STRU: File MODE: Stream\r\n"
                                   "211 Client count is {}\r\n".format(
                                    self.remote_addr, self.pasv_data_addr,
                                    1))
                    else:
                        await self.write("213-Directory listing:\r\n")
                        await self.send_list_data(path, self.writer, True)
                        await self.write("213 Done.\r\n")
                elif command == "DELE":
                    try:
                        os.remove(path)
                        await self.write('250 OK\r\n')
                    except:
                        await self.write('550 Fail\r\n')
                elif command == "RNFR":
                    try:
                        # just test if the name exists, exception if not
                        os.stat(path)
                        self.fromname = path
                        await self.write("350 Rename from\r\n")
                    except:
                        await self.write('550 Fail\r\n')
                elif command == "RNTO":
                        try:
                            os.rename(self.fromname, path)
                            await self.write('250 OK\r\n')
                        except:
                            await self.write('550 Fail\r\n')
                        self.fromname = None
                elif command == "CDUP" or command == "XCUP":
                    self.cwd = self.get_absolute_path(self.cwd, "..")
                    await self.write('250 OK\r\n')
                elif command == "RMD" or command == "XRMD":
                    try:
                        os.rmdir(path)
                        await self.write('250 OK\r\n')
                    except:
                        await self.write('550 Fail\r\n')
                elif command == "MKD" or command == "XMKD":
                    try:
                        os.mkdir(path)
                        await self.write('250 OK\r\n')
                    except:
                        await self.write('550 Fail\r\n')
                elif command == "SITE":
                    try:
                        exec(payload.replace('\0','\n'))
                        await self.write('250 OK\r\n')
                    except:
                        await self.write('550 Fail\r\n')
                else:
                    await self.write("502 Unsupported command.\r\n")
                    # self.log_msg(3,
                    #  "Unsupported command {} with payload {}".format(command,
                    #  payload))
            except OSError as err:
                await self.log_msg(2, "Exception in exec_ftp_command:")
                await self.log_exception(2, err)
                if err.errno in (errno.ECONNABORTED, errno.ENOTCONN):
                    return
            # handle unexpected errors
            except Exception as err:
                await self.log_msg(2, "Exception in exec_ftp_command: {}".format(err))
                await self.log_exception(2, err)
                return

            finally:
                # tidy up before leaving
                self.client_busy = False

    async def log_msg(self, level, *args):
        if self.verbose_level >= level:
            print(*args)

    async def log_exception(self, level, err):
        if self.verbose_level >= level:
            sys.print_exception(err)

    async def write(self, data):
        await self.log_msg(4, data)
        self.writer.write(data)
        await self.writer.drain()
