#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Client class for connecting to Logitech Harmony devices."""

import json
import asyncio
import websockets
from aiohttp import ClientSession
from urllib.parse import urlparse

import logging

DEFAULT_CMD = 'vnd.logitech.connect'
DEFAULT_DISCOVER_STRING = '_logitech-reverse-bonjour._tcp.local.'
DEFAULT_DOMAIN = 'svcs.myharmony.com'
DEFAULT_HUB_PORT = '8088'

#logger = logging.getLogger(__name__)
logger = logging.getLogger('Main')

class HarmonyClient():
    """An websocket client for connecting to the Logitech Harmony devices."""
    
    decode_status = {0:'Off', 1:'Starting', 2:'Started', 3:'Turning Off'}
    __version__ = '1.0'

    def __init__(self, ip_address, loop=None, mqttc=None, pub_topic='/harmony_status/'):
        self.connected = False
        self._ip_address = ip_address
        self._mqttc = mqttc
        if self._mqttc:
            self._mqttc.on_message = self._on_message
            self._pub_topic = pub_topic
            
        self._friendly_name = None
        self._remote_id = None
        self._domain = DEFAULT_DOMAIN
        self._email = None
        self._account_id = None
        self._websocket = None
        self._msgid = 0
        self._config = None
        self._activities = None
        self._current_activity = None
        self._activity_status = None
        self._devices = None
        self._current_activity_name = None
        if not loop:
            self.loop = asyncio.get_event_loop()
            if not self.loop.is_running():
                #run loop in another thread
                from threading import Thread
                self.t = Thread(target=self.loop.run_until_complete, args=(self.connect(),))
                self.t.start()  
        else:
            self.loop = loop    
        
    def _on_message(self, mosq, obj, msg):
        logger.debug("CLIENT: message received topic: %s" % msg.topic)
        #log.info("message topic: %s, value:%s received" % (msg.topic,msg.payload.decode("utf-8")))
        command = msg.topic.split('/')[-1]
        message = msg.payload.decode("utf-8")
        logger.debug("CLIENT: Received Command: %s, Setting: %s" % (command,message))
        func = None
        
        if 'start_activity' in command:
            logger.debug('start_activity: %s' % message)
            if 'PowerOff' in message:
                func = self._power_off()
            else:
                logger.debug('Activities are: %s' % self._activities)
                if message in [activity['name'] for activity in self._activities]:    #check for valid activities here
                    func = self._start_activity(self.get_activity_id(message))
                else:
                    logger.warn('activity: %s not found in activity list' % message)
                    
        elif 'send_command' in command:
            logger.debug('send_command: %s' % message) #example: mosquitto_pub -t "/harmony_command/send_command" -m "{\"command\":\"InputHdmi1\",\"device\":\"49046118\",\"command_delay\":0}"
            if message == "All":
                if self._current_activity_name:
                    logger.debug('Publishing current activities')
                    self.publish('current_activity', self._current_activity_name)
                    self.publish('current_activity_starting', self._current_activity_name)
                    self.publish('current_activity_started', self._current_activity_name)
                return
            elif message == "Sync":    
                func = self._sync()
            else:
                param = json.loads(message)
                func = self._send_command(param['device'], param['command'], param.get('repeat_num',1), param.get('delay_sec',0.4), param.get('command_delay',0))
            
        elif 'change_channel' in command:
            logger.debug('change_channel: %s' % message)
            func = self._change_channel(message)
            
        else:
            logger.warn('Command: %s not found' % command)
                               
        if func:
            #have to use this as mqtt client is running in another thread...
            asyncio.run_coroutine_threadsafe(func,self.loop)
            
    def pprint(self,obj):
        """Pretty JSON dump of an object."""
        return(json.dumps(obj, sort_keys=True, indent=2, separators=(',', ': ')))
    
    @property
    def config(self):
        return self._config
        
    @property
    def activities(self):
        return self._activities
        
    @property
    def devices(self):
        return self._devices
        
    @property
    def current_activity(self):
        return self._current_activity_name
        
    @property
    def current_activity_status(self):
        return self._activity_status

    @property
    def json_config(self):
        """Returns configuration as a dictionary (json)"""

        result = {}

        activity_dict = {}
        for activity in self._config.get('activity'):
            activity_dict.update({activity['id']: activity['label']})

        result.update(Activities=activity_dict)

        devices_dict = {}
        for device in self._config.get('device'):
            command_list = []
            for controlGroup in device['controlGroup']:
                for function in controlGroup['function']:
                    action = json.loads(function['action'])
                    command_list.append(action.get('command'))

            device_dict = {
                'id'      : device.get('id'),
                'commands': command_list
            }

            devices_dict.update({device.get('label'): device_dict})

        result.update(Devices=devices_dict)

        return result

    @property
    def name(self):
        return self._friendly_name

    @property
    def email(self):
        return self._email

    @property
    def account_id(self):
        return self._account_id
        
    def publish(self, topic, message):
        '''
        mqtt publish
        '''
        if self._mqttc is None:
            logger.debug('No MQTT client configured')
            return
        
        self._mqttc.publish(self._pub_topic+topic, message)
        logger.info('published: %s: %s' % (topic, message))

    async def retrieve_hub_info(self):
        """Retrieve the harmony Hub information."""
        logger.debug("Retrieving Harmony Hub information.")
        url = 'http://{}:{}/'.format(self._ip_address, DEFAULT_HUB_PORT)
        headers = {
            'Origin': 'http://localhost.nebula.myharmony.com',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Accept-Charset': 'utf-8',
        }
        json_request = {
            "id ": 1,
            "cmd": "connect.discoveryinfo?get",
            "params": {}
        }
        async with ClientSession() as session:
            async with session.post(
                url, json=json_request, headers=headers) as response:
                json_response = await response.json()
                self._friendly_name = json_response['data']['friendlyName']
                self._remote_id = str(json_response['data']['remoteId'])
                domain = urlparse(json_response['data']['discoveryServerUri'])
                self._domain = domain.netloc if domain.netloc else \
                    DEFAULT_DOMAIN
                self._email = json_response['data']['email']
                self._account_id = str(json_response['data']['accountId'])

    async def _perform_connect(self):
        """Connect to Hub Web Socket"""
        # Return connected if we are already connected.
        if self._websocket:
            if self._websocket.open:
                return True

            if not self._websocket.closed:
                await self._disconnect()

        logger.debug("Starting connect.")
        if self._remote_id is None:
            # We do not have the remoteId yet, get it first.
            await self.retrieve_hub_info()

        if self._remote_id is None:
            #No remote ID means no connect.
            return False

        logger.debug("Connecting to %s for hub %s",
                     self._ip_address, self._remote_id)
        self._websocket = await websockets.connect(
            'ws://{}:{}/?domain={}&hubId={}'.format(
            self._ip_address, DEFAULT_HUB_PORT, self._domain, self._remote_id
            )
        )

    async def connect(self):
        """Connect to Hub Web Socket"""
        await self._perform_connect()

        response = await self._send_request(
            '{}/vnd.logitech.statedigest?get'.format(DEFAULT_CMD)
        )

        if response.get('code') != 200:
            logger.debug("Harmony did not connect")
            await self._disconnect()
            return False
        logger.debug("Harmony Connected")
        self._current_activity = response['data']['activityId']
        self._account_id = response['data']['accountId']
        await self._get_config()
        logger.debug("got configuration")
        self._current_activity_name = self.get_activity_name(self._current_activity)
        logger.debug('Current Activity: %s' % self._current_activity_name)
        self.publish('current_activity', self._current_activity_name)
        if self._current_activity_name == 'PowerOff':
            self._activity_status = 0
        else:
            self._activity_status = 2
        self.connected = True

        await self._receive_loop()
        
    async def _receive_loop(self):
        while self._websocket.open:
            try:
                response_json = await self._websocket.recv()
                response = json.loads(response_json)
                logger.debug("Received data: %s", self.pprint(response))
                reponse_type = response.get('type', None)
                if reponse_type:
                    if reponse_type == 'connect.stateDigest?notify':
                        self._activity_status = response['data']['activityStatus']
                        self.show_notification(response['data']['activityId'], self._activity_status)
                    elif reponse_type == 'harmony.engine?startActivityFinished':
                        self._current_activity = response['data']['activityId']
                        self._current_activity_name = self.get_activity_name(self._current_activity)
                        self.publish('current_activity', self._current_activity_name)
                        logger.info('Activity: %s started' % self._current_activity_name)

            except websockets.exceptions.ConnectionClosed:
                logger.debug('WS connection closed')
                break
                
        await self._disconnect()
        logger.debug('Exited Receive Loop')
        
    def disconnect(self):
        asyncio.run_coroutine_threadsafe(self._disconnect(),self.loop)

    async def _disconnect(self, send_close=None):
        """Disconnect from Hub"""
        logger.debug("Disconnecting from %s", self._ip_address)
        await self._websocket.close()
        self._websocket = None
        self.connected = False

    async def _send_request(self, command, params=None,
                            wait_for_response=True, msgid=None):
        """Send a payload request to Harmony Hub and return json response."""
        # Make sure we're connected.
        await self._perform_connect()

        if params is None:
            params = {
                "verb"  : "get",
                "format": "json"
            }

        if not msgid:
            msgid = self._msgid = self._msgid + 1

        payload = {
            "hubId"  : self._remote_id,
            "timeout": 30,
            "hbus"   : {
                "cmd": command,
                "id" : msgid,
                "params": params
            }
        }

        logger.debug("Sending payload: %s", self.pprint(payload))
        await self._websocket.send(json.dumps(payload))

        if not wait_for_response:
            return
        return await self._wait_response(msgid)

    async def _wait_response(self, msgid):
        """Await message on web socket"""
        logger.debug("Waiting for response")
        while True:
            response_json = await self._websocket.recv()
            response = json.loads(response_json)
            logger.debug("Received response: %s", self.pprint(response))
            if response.get('id') == msgid:
                return response

    async def _get_config(self):
        """Retrieves the Harmony device configuration.

        Returns:
            A nested dictionary containing activities, devices, etc.
        """
        if self._config:
            logger.debug("using previous config")
            return
            
        logger.debug("Getting configuration")
        response = await self._send_request(
            'vnd.logitech.harmony/vnd.logitech.harmony.engine?config'
        )

        assert response.get('code') == 200

        self._config = response.get('data')

        self._activities = list(
            {'name': a['label'],
             'name_match': a['label'].lower(),
             'id': int(a['id'])
             } for a in self._config.get('activity'))

        self._devices = list(
            {'name': a['label'],
             'name_match': a['label'].lower(),
             'id': int(a['id'])
             } for a in self._config.get('device'))

        return self._config

    async def _get_current_activity(self):
        """Retrieves the current activity ID.

        Returns:
            A int with the current activity ID.
        """
        logger.debug("Retrieving current activity")
        response = await self._send_request(
            'vnd.logitech.harmony/vnd.logitech.harmony.engine'
            '?getCurrentActivity'
        )

        assert response.get('code') == 200
        activity = response['data']['result']
        return int(activity)
        
    def show_notification(self, act_id, status=None):
        '''
        activityStatus	0 = Hub is off, 1 = Activity is starting, 2 = Activity is started, 3 = Hub is turning off
        '''
        if self._config is not None:
            current_activity = self.get_activity_name(act_id)
            self._current_activity_name = current_activity
            logger.debug("Activity: %s changed to %d (%s)" % (current_activity, status, self.decode_status[status]))
            if self._mqttc is not None:
                #self.publish('current_activity', self._current_activity_name)
                if status == 1:
                    self.publish('current_activity_starting', current_activity)
                elif status == 2:
                    self.publish('current_activity_started', current_activity)
                elif status == 3:
                    self.publish('current_activity_starting', 'PowerOff')
                elif status == 0:
                    self.publish('current_activity_started', current_activity)
                    
    def start_activity(self, activity):
        if activity.isdigit():
            activity_id = int(activity)
        else:
            activity_id = self.get_activity_id(activity)
            
        asyncio.run_coroutine_threadsafe(self._start_activity(activity_id),self.loop)
                    
    async def _start_activity(self, activity_id):
        """Starts an activity.

        Args:
            activity_id: An int or string identifying the activity to start

        Returns:
            True if activity started, otherwise False
        """
        logger.debug("Starting activity %s", activity_id)
        params = {
            "async": "true",
            "timestamp": 0,
            "args": {
                "rule": "start"
            },
            "activityId": str(activity_id)
        }
 
        await self._send_request('harmony.activityengine?runactivity', params, False)
        
    def sync(self):
        asyncio.run_coroutine_threadsafe(self._sync(),self.loop)

    async def _sync(self):
        """Syncs the harmony hub with the web service.
        """

        logger.debug("Performing sync")
        await self._send_request('setup.sync', None, False)

        return True
        
    def send_command(self, device, command, command_repeat=1, repeat_delay=0.4, command_delay=0):
        if device.isdigit():
            device_id = int(device)
        else:
            device_id = self.get_device_id(device)
        asyncio.run_coroutine_threadsafe(self._send_command(device_id, command, command_repeat, repeat_delay, command_delay),self.loop)

    async def _send_command(self, device, command, command_repeat=1, repeat_delay=0.4, command_delay=0):
        """Send a simple command to the Harmony Hub.

        Args:
            device_id (str): Device ID from Harmony Hub configuration to control
            command (str): Command from Harmony Hub configuration to control
            command_repeat (int) : number of repeats
            repeat-delay (float): delay between repeats
            command_delay (float): Delay in seconds between sending the press command and the release command.

        Returns:
            None if successful
        """
        for x in range(command_repeat):
            logger.debug("Sending command %s to device %s with delay %ss",command, device, command_delay)
            params = {
                "status": "press",
                "timestamp": '0',
                "verb": "render",
                "action": '{{"command": "{}",'
                          '"type": "IRCommand",'
                          '"deviceId": "{}"}}'.format(command, device)
            }

            await self._send_request(
                'vnd.logitech.harmony/vnd.logitech.harmony.engine?holdAction',
                params, False
            )

            if command_delay > 0:
                await asyncio.sleep(command_delay)

            params['status'] = 'release'
            await self._send_request(
                'vnd.logitech.harmony/vnd.logitech.harmony.engine?holdAction',
                params, False
            )
            if command_repeat > 1:
               await asyncio.sleep(repeat_delay) 
        
    def change_channel(self, channel):
        asyncio.run_coroutine_threadsafe(self._change_channel(channel),self.loop)

    async def _change_channel(self, channel):
        """Changes a channel.
        Args:
            channel: Channel number
        Returns:
          An HTTP 200 response (hopefully)
        """
        logger.debug("Changing channel to %s", channel)
        params = {
            "timestamp": 0,
            'channel': str(channel)
        }
        await self._send_request('harmony.engine?changeChannel', params, False)
        
    def power_off(self):
        asyncio.run_coroutine_threadsafe(self._power_off(),self.loop)

    async def _power_off(self):
        """Turns the system off if it's on, otherwise it does nothing.

        Returns:
            True if the system becomes or is off
        """
        if self._current_activity != -1:
            return await self._start_activity(-1)
        else:
            return True
    
    @staticmethod
    def search(item_name, item, list):
        """Search for the item in the list."""
        return next(
            (element for element in list
             if element[item_name] == item), None)

    def get_activity_id(self, activity_name):
        """Find the activity ID for the provided activity name."""
        item = self.search('name_match', activity_name.lower(),
                           self._activities)
        return item.get('id') if item else None

    def get_activity_name(self, activity_id):
        """Find the activity name for the provided ID."""
        item = self.search('id', int(activity_id), self._activities)
        return item.get('name') if item else None

    def get_device_id(self, device_name):
        """Find the device ID for the provided device name."""
        item = self.search('name_match', device_name.lower(), self._devices)
        return item.get('id') if item else None

    def get_device_name(self, device_id):
        """Find the device name for the provided ID."""
        item = self.search('id', device_id, self._devices)
        return item.get('name') if item else None


def create_and_connect_client(ip_address, port=None,
                                    connect_attempts=5):

    """Creates a Harmony client and initializes session.

    Args:
        ip_address (str): Harmony device IP address
        port (str): Harmony device port
        activity_callback (function): Function to call when the current activity has changed.


    Returns:
        A connected HarmonyClient instance
    """
    client = HarmonyClient(ip_address)
    i = 0
    while (i < connect_attempts and not client.connected):
        i = i + 1
        time.sleep(2)
    if i == connect_attempts:
        logger.error("Failed to connect to %s after %d tries" % (ip_address,i))
        client.disconnect()
        return False

    logger.debug("connected to client")
    return client
