#!/usr/bin/env python3

# Author: Nick Waterton <nick.waterton@med.ge.com>
# Description: OH interface to harmony hub after 206 firmware upgrade mess
# N Waterton 121st December 2018 V1.0: initial release

from __future__ import print_function

# import the necessary packages
import logging
from logging.handlers import RotatingFileHandler
global HAVE_MQTT
HAVE_MQTT = False
try:
    import paho.mqtt.client as paho
    HAVE_MQTT = True
except ImportError:
    print("paho mqtt client not found")
import time, os, sys, json
from _thread import start_new_thread
import asyncio

#harmony
import discovery
import harmony_client

__version__ = __VERSION__ = "1.0.0"
        
def pprint(obj):
    """Pretty JSON dump of an object."""
    log.info(json.dumps(obj, sort_keys=True, indent=2, separators=(',', ': ')))
        
def discover():
    hubs = discovery.discover()
    pprint(hubs)

def show_current_activity(client, arg):
    log.info(client.current_activity)
    
def show_config(client, arg):
    pprint(client.config)
    
def show_devices(client, arg):
    pprint(client.devices)
    
def show_activities(client, arg):
    pprint(client.activities)
    
def start_activity(client, arg):
    client.start_activity(arg.activity)
    log.info('%s started' % arg.activity)
   
def change_channel(client, arg):
    client.change_channel(arg.channel)
    log.info('changed to channel %s started' % arg.channel)
    
def send_command(client, arg):
    client.send_command(arg.device_id, arg.command, arg.repeat_num, arg.delay_secs, arg.hold_secs)
    log.info('command sent')
    
def power_off(client, arg):
    client.power_off()
    log.info('PowerOff sent')
    
def sync(client, arg):
    client.sync()
    log.info('sync requested')

def setup_logger(logger_name, log_file, level=logging.DEBUG, console=False):
    try: 
        l = logging.getLogger(logger_name)
        formatter = logging.Formatter('[%(levelname)1.1s %(asctime)s] (%(threadName)-10s) %(message)s')
        if log_file is not None:
            fileHandler = logging.handlers.RotatingFileHandler(log_file, mode='a', maxBytes=2000000, backupCount=5)
            fileHandler.setFormatter(formatter)
        if console == True:
          streamHandler = logging.StreamHandler()

        l.setLevel(level)
        if log_file is not None:
            l.addHandler(fileHandler)
        if console == True:
          l.addHandler(streamHandler)
             
    except Exception as e:
        print("Error in Logging setup: %s - do you have permission to write the log file??" % e)
        sys.exit(1)
      
def on_connect(mosq, userdata, flags, rc):
    #log.info("rc: %s" % str(rc))
    log.info("Connected to MQTT Server")
    mosq.subscribe(sub_topic +"#", 0)

def on_publish(mosq, obj, mid):
    #log.info("published: %s %s" % (str(mid), str(obj)))
    pass

def on_subscribe(mosq, obj, mid, granted_qos):
    log.info("Subscribed: %s %s" % (str(mid), str(granted_qos)))

def on_disconnect():
    pass

def on_log(mosq, obj, level, string):
    log.info(string)
    
def on_message(mosq, obj, msg): #not used
    log.info("message received topic: %s" % msg.topic)
    #log.info("message topic: %s, value:%s received" % (msg.topic,msg.payload.decode("utf-8")))
    command = msg.topic.split('/')[-1]
    log.info("Received Command: %s, Setting: %d" % (image_name,msg.payload.decode("utf-8")))


def main():
    '''
    Main routine
    '''
    global log
    import argparse
    parser = argparse.ArgumentParser(description='Harmony MQTT-WS Client and Control')
    required_flags = parser.add_mutually_exclusive_group(required=True)
    # Required flags go here.
    required_flags.add_argument('-ip', '--IP', action="store", default=None, help="IP Address of harmony Hub. (default: None)")
    required_flags.add_argument('-d', '--discover',action='store_true',help='Scan for Harmony devices.')
    # Flags with default values go here.
    #parser.add_argument('-cid','--client_id', action="store", default=None, help='optional MQTT CLIENT ID (default=None)')
    parser.add_argument('-b','--broker', action="store", default=None, help='mqtt broker to publish sensor data to. (default=None)')
    parser.add_argument('-p','--port', action="store", type=int, default=1883, help='mqtt broker port (default=1883)')
    parser.add_argument('-u','--user', action="store", default=None, help='mqtt broker username. (default=None)')
    parser.add_argument('-pw','--password', action="store", default=None, help='mqtt broker password. (default=None)')
    parser.add_argument('-pt','--pub_topic', action="store",default='/harmony_status/', help='topic to publish harmony data to. (default=/harmony_status/)')
    parser.add_argument('-st','--sub_topic', action="store",default='/harmony_command/', help='topic to publish harmony commands to. (default=/harmony_command/)')
    parser.add_argument('-l','--log', action="store",default="None", help='log file. (default=None)')
    parser.add_argument('-D','--debug', action='store_true', help='debug mode', default = False)
    parser.add_argument('-V','--version', action='version',version='%(prog)s {version}'.format(version=__VERSION__))
    

    subparsers = parser.add_subparsers(dest='command')

    show_config_parser = subparsers.add_parser('show_config', help='Print the Harmony device configuration.')
    show_config_parser.set_defaults(func=show_config)
    
    show_devices_parser = subparsers.add_parser('show_devices', help='Print the Harmony devices.')
    show_devices_parser.set_defaults(func=show_devices)
    
    show_activities_parser = subparsers.add_parser('show_activities', help='Print the Harmony activities.')
    show_activities_parser.set_defaults(func=show_activities)

    show_activity_parser = subparsers.add_parser('show_current_activity', help='Print the current activity config.')
    show_activity_parser.set_defaults(func=show_current_activity)

    start_activity_parser = subparsers.add_parser('start_activity', help='Switch to a different activity.')
    start_activity_parser.add_argument('activity', help='Activity to switch to, id or label.')
    start_activity_parser.set_defaults(func=start_activity)

    start_activity_parser = subparsers.add_parser('change_channel', help='Change channel.')
    start_activity_parser.add_argument('channel', help='Channel to change to')
    start_activity_parser.set_defaults(func=change_channel)

    power_off_parser = subparsers.add_parser('power_off', help='Stop the activity.')
    power_off_parser.set_defaults(func=power_off)

    sync_parser = subparsers.add_parser('sync', help='Sync the harmony.')
    sync_parser.set_defaults(func=sync)

    command_parser = subparsers.add_parser('send_command', help='Send a simple command.')
    command_parser.add_argument('device_id', help='Specify the device id to which we will send the command.')
    command_parser.add_argument('command', help='IR Command to send to the device.')
    command_parser.add_argument('-repeat','--repeat_num', type=int, default=1, help='Number of times to repeat the command. Defaults to 1')
    command_parser.add_argument('-delay','--delay_secs', type=float, default=0.4, help='Delay between sending repeated commands. Not used if only sending a single command. Defaults to 0.4 seconds')
    command_parser.add_argument('-hold','--hold_secs', type=float, default=0.0,
                                help='Delay between sending press and '
                                     'sending release. Defaults to 0 '
                                     'seconds')                                                    
    command_parser.set_defaults(func=send_command)

    arg = parser.parse_args()
    
    if arg.debug:
      log_level = logging.DEBUG
    else:
      log_level = logging.INFO
    
    #setup logging
    if arg.log == 'None':
        log_file = None
    else:
        log_file=os.path.expanduser(arg.log)
    setup_logger('Main',log_file,level=log_level,console=True)
    
    log = logging.getLogger('Main')
    
    log.debug('Debug mode')
    
    broker = arg.broker
    port = arg.port
    user = arg.user
    password = arg.password
    
    if not HAVE_MQTT:
        broker = None
    
    global sub_topic
    sub_topic = arg.sub_topic
    mqttc = None
    loop = None
    server = False
    
    if arg.discover:
        log.info("Searching for Hubs")
        discover()
        sys.exit(0)
    
    if not arg.command and not broker:
        log.critical('You must define an MQTT broker, or give a command line argument')
        parser.print_help()
        sys.exit(2)

    try:
        if broker is not None:
            mqttc = paho.Client()               #Setup MQTT
            #mqttc.on_message = on_message
            mqttc.on_connect = on_connect
            mqttc.on_publish = on_publish
            mqttc.on_subscribe = on_subscribe
            if user is not None and password is not None:
                mqttc.username_pw_set(username=user,password=password)
            mqttc.connect(broker, port, 120)
            mqttc.loop_start()
            
            loop = asyncio.get_event_loop()
            log.info("Server Started")
            server = True
            
        client = harmony_client.HarmonyClient(arg.IP, loop, mqttc, arg.pub_topic)
        
        if not loop:
            while not client.connected:
                time.sleep(0.1)
            log.debug('connected')
            arg.func(client, arg)
            client.disconnect()
        else:
            while True:
                log.info("Connecting Client")
                loop.run_until_complete(client.connect())
                log.warn("Client Disconnected")
                time.sleep(60)  #retry every 60 seconds
        
    except (KeyboardInterrupt, SystemExit):
        log.info("System exit Received - Exiting program")
        if loop:
            loop.run_until_complete(client._disconnect())
        else:
            client.disconnect()
        
    finally:
        if mqttc:
            mqttc.loop_stop()
            mqttc.disconnect()
        if loop:
            loop.close()        
      

if __name__ == "__main__":
    main()
