pyharmony-ws
================

A command line and MQTT to harmony Hub websocket client

Since logitech disabled access to the XMPP server recently (dec 2018), here is a quick hack of a websockets client, using port 8088.

Thanks to the folks at Home Assistant for the basic details.

This is version 1.0 so it may be buggy!

Tested with firmware version V206
* Tested on Ubuntu 18.04
* Tested with Python 3.6  **This is a python 3.6 program, IT WILL NOT WORK on lower versions **

## Features
* Auto discovery of Hub (optional)
* command line interface (harmony_server)
* client interface to add to your own programs (harmony_client)
* start_activity
* change_channel
* send_command
* show_current_activity
* Continuous notifications (with client)
* post to mqtt topic
* run activities/commands by subscribing to mqtt topic
* designed for openhab2 compatibility

## Dependencies
The following libraries/modules are used. Some are optional:
* aiohttp     *required*
* paho-mqtt   *optional*

run `./harmony_server.py -h` (or `python3 harmony_server.py -h`) to get the available options. This is what you will get:

```bash
usage: harmony_server.py [-h] (-ip IP | -d) [-b BROKER] [-p PORT] [-u USER]
                         [-pw PASSWORD] [-pt PUB_TOPIC] [-st SUB_TOPIC]
                         [-l LOG] [-D] [-V]
                         {show_config,show_devices,show_activities,show_current_activity,start_activity,change_channel,power_off,sync,send_command}
                         ...

Harmony MQTT-WS Client and Control

positional arguments:
  {show_config,show_devices,show_activities,show_current_activity,start_activity,change_channel,power_off,sync,send_command}
    show_config         Print the Harmony device configuration.
    show_devices        Print the Harmony devices.
    show_activities     Print the Harmony activities.
    show_current_activity
                        Print the current activity config.
    start_activity      Switch to a different activity.
    change_channel      Change channel.
    power_off           Stop the activity.
    sync                Sync the harmony.
    send_command        Send a simple command.

optional arguments:
  -h, --help            show this help message and exit
  -ip IP, --IP IP       IP Address of harmony Hub. (default: None)
  -d, --discover        Scan for Harmony devices.
  -b BROKER, --broker BROKER
                        mqtt broker to publish sensor data to. (default=None)
  -p PORT, --port PORT  mqtt broker port (default=1883)
  -u USER, --user USER  mqtt broker username. (default=None)
  -pw PASSWORD, --password PASSWORD
                        mqtt broker password. (default=None)
  -pt PUB_TOPIC, --pub_topic PUB_TOPIC
                        topic to publish harmony data to.
                        (default=/harmony_status/)
  -st SUB_TOPIC, --sub_topic SUB_TOPIC
                        topic to publish harmony commands to.
                        (default=/harmony_command/)
  -l LOG, --log LOG     log file. (default=None)
  -D, --debug           debug mode
  -V, --version         show program's version number and exit
```

## quick start
run `harmony_server.py -d`
will list all the local hubs
```bash
Searching for Hubs
Completed scan, 1 hub(s) found.
[
  {
    "accountId": "10380219",
    "current_fw_version": "4.15.206",
    "discoveryServerUri": "http",
    "discoveryServerUriCF": "https",
    "email": "your-email@domain",
    "friendlyName": "Harmony Hub",
    "host_name": "Harmony Hub",
    "hubId": "156",
    "hubProfiles": "{Harmony=\"2.0\"}",
    "ip": "192.168.1.187",
    "minimumOpenApiClientVersionRequired": "1",
    "mode": "3",
    "oohEnabled": "true",
    "openApiVersion": "2",
    "port": "5222",
    "productId": "Pimento",
    "protocolVersion": "{HTTP=\"1.0\", RF=\"1.0\", WEBSOCKET=\"1.0\"}",
    "recommendedOpenApiClientVersion": "1",
    "remoteId": "xxxxxxxx",
    "setupSessionClient": "xxxxxxxxxxxxxx",
    "setupSessionIsStale": "true",
    "setupSessionSetupType": "",
    "setupSessionType": "0",
    "setupStatus": "0",
    "uuid": "xxxxxxxxxxxxxxxxxxxxxxxxxx"
  }
]
```

Now you have the Hub IP (if you didn't before)
run `harmony_server.py -ip 192.168.1.187 show_current_activity
```bash
Watch TV
```
another example
run `harmony_server.py -ip 192.168.1.187 start_activity "Watch Netflix"

## MQTT interface
To start an MQTT server interface, supply a broker ip, port, user and password (default ports are 1883, user None, password None)
run `harmony_server.py -ip 192.168.1.187 -b 192.168.1.119 -l ./harmony.log -D`
for a full verbose logging MQTT interface. (less output without `-D`)

Now you can subscribe to the current activity on `/harmony_status/#` and send commands to `/harmony_command/`
commands are "start_activity", "send_command", "change_channel"
If you send `All` to `/harmony_command/send_command` it will re-publish the current activity and status.
If you send `Sync` to `/harmony_command/send_command` it will initiate a Hub Sync.

You will receive real time notification of changes to status on `/harmony_status/current_activity_starting` and `/harmony_status/current_activity_started`

`<Cntrl-C>` to Exit.

That's it for a quick hack.