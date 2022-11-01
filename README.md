# The micro-swarm micropython framework

This is a small micropython framework to manage and keep up-to-date micropython programs inside a private LAN.

It has been tested with the wesp32 POE board, but there is no reason it should not work to another esp32 board,
nor any other micropython board (except maybe if you intend to use telnet, which involve some undocumented hacks).

The strong points of this framework are:
  - the async paradigm multiplexing tasks
  - the network autodiscovery using broadcast udp packets, do you don't have to keep track of ips
  - the ability to push code to all your devices connected to the LAN quickly in parallel

## TL;DR Getting started

```sh
git clone https://github.com/expendable-duck/micro-swarm.git
cd micro-swarm

# Install lftp, which is an external dependency
brew install lftp # For mac, for other oses use apt-get, yum, etc.

# Install python dependencies
pip3 install -r requirements.txt

# Change relevant values, and execute
script/program_code_boot example-device example wesp32 /dev/tty.usbserial-110

# Connect to the same network as the device, and get an ip on 169.254.0.0/16, then execute
script/push_code
```

## Security

There is no security, no password, so anyone getting access on the network will get full access of the device.
If you do not want that, keep your devices isolated, using a separate VLAN for example.

Another possibility is disabling ftpd, telnet and remote eval services in `boot/root/bootpkg/settings.py`, but
then remote push won't work obviously.

## Async

This framework use extensively the uasyncio library to allow independent tasks to run concurrently, including your own apps.
Do not use time.sleep() or any call blocking for too long. Instead use uasyncio, and async/await as much as possible to allow
you app to be responsive.

## How to create an app

You can make apps by adding a package in apps/. The app name is the package name. At boot, micro-swarm will look for async
functions whose name starts with `init_` and `routine_`. All function starting with `init_` and `routine_` MUST be async functions.
Init functions will be run at boot, and then all finish, before routine functions are run.

If you include libraries, your imports must be relative, there is no "libs" directory added to sys.path.

There is a basic async example app provided.

## How to create a new hardware target

Create a boot/hardwares/{hardware_name}/ package, like you would create an app package.
This code will not change from one app to another, only from one hardware to another.

## Settings

The hostname (same as device board name), the hardware name, and the app name are set up using `script/program_code_boot`.
You can change micro-swarm boot settings in `boot/root/bootpkg/settings.py`.

By default, every active nics will be set up using a pseudorandom link-local ip on the 169.254.0.0/16 network,
with no DNS and no gateway. The apps can change that at initalization.

## Services

This framework runs different services in the background:
- An MDNS udp server to send the device `{host_name}.local` on the network
- An ftp tcp server for app code sync
- A simple remote python eval code tcp server, used mainly to reboot remotly the device
- A telnet tcp server, used for manual maintainance

## File hierarchy

```
apps/{app_name}/                contains different apps to dispatch on your devices
boot/root/                      contains the micro-swarm boot code, that will be rsynced to the micropython root of the device through serial port.
boot/hardwares/{hardware_name}/ contains code specific for each hardware platform you want to distinguish
script/program_code_boot/       a python script used to push the micro-swarm boot code on the device using serial port. You should have to do this once, after it's over the network.
script/push_code                a python script used to push your apps on relevant devices, over the network
script/scan_devices             a python utility script used to show you what devices are detected over the network
```

## License

The project is subject to the MIT License. However, the slimDNS library has its own Apache license.
