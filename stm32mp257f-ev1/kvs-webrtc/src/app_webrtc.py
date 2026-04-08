import asyncio
import json
import queue
import threading
import traceback
from base64 import b64decode, b64encode

import av
import boto3
import websockets
from aiortc import MediaStreamTrack, RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaBlackhole
from aiortc.sdp import candidate_from_sdp
from botocore.auth import SigV4QueryAuth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
from botocore.session import Session

webrtc_client: 'KinesisVideoClient | None' = None
_webrtc_loop: asyncio.AbstractEventLoop | None = None
_stop_event: threading.Event = threading.Event()


class FrameQueueVideoTrack(MediaStreamTrack):
    kind = "video"

    def __init__(self, frame_queue: queue.Queue):
        super().__init__()
        self._queue = frame_queue
        self._timestamp = 0

    async def recv(self):
        # Poll the queue with async sleep to avoid blocking an executor thread.
        # asyncio.sleep() is immediately cancellable, so task cancellation is clean.
        while True:
            try:
                frame_array = self._queue.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.005)
                continue
            frame = av.VideoFrame.from_ndarray(frame_array, format='rgb24')
            frame.pts = self._timestamp
            frame.time_base = '1/30'
            self._timestamp += 1
            return frame


class KinesisVideoClient:
    def __init__(self, client_id, region, channel_arn, credentials, frame_queue):
        self.client_id = client_id
        self.region = region
        self.channel_arn = channel_arn
        self.credentials = credentials
        self.video_track = FrameQueueVideoTrack(frame_queue)
        self._websocket = None
        if self.credentials:
            self.kinesisvideo = boto3.client('kinesisvideo',
                                             region_name=self.region,
                                             aws_access_key_id=self.credentials['accessKeyId'],
                                             aws_secret_access_key=self.credentials['secretAccessKey'],
                                             aws_session_token=self.credentials['sessionToken']
                                             )
        else:
            self.kinesisvideo = boto3.client('kinesisvideo', region_name=self.region)
        self.endpoints = None
        self.endpoint_https = None
        self.endpoint_wss = None
        self.ice_servers = None
        self.PCMap = {}
        self.DCMap = {}

    def get_signaling_channel_endpoint(self):
        if self.endpoints is None:
            endpoints = self.kinesisvideo.get_signaling_channel_endpoint(
                ChannelARN=self.channel_arn,
                SingleMasterChannelEndpointConfiguration={'Protocols': ['HTTPS', 'WSS'], 'Role': 'MASTER'}
            )
            self.endpoints = {
                'HTTPS': next(o['ResourceEndpoint'] for o in endpoints['ResourceEndpointList'] if o['Protocol'] == 'HTTPS'),
                'WSS': next(o['ResourceEndpoint'] for o in endpoints['ResourceEndpointList'] if o['Protocol'] == 'WSS')
            }
            self.endpoint_https = self.endpoints['HTTPS']
            self.endpoint_wss = self.endpoints['WSS']
        return self.endpoints

    def prepare_ice_servers(self):
        if self.credentials:
            kinesis_video_signaling = boto3.client('kinesis-video-signaling',
                                                   endpoint_url=self.endpoint_https,
                                                   region_name=self.region,
                                                   aws_access_key_id=self.credentials['accessKeyId'],
                                                   aws_secret_access_key=self.credentials['secretAccessKey'],
                                                   aws_session_token=self.credentials['sessionToken']
                                                   )
        else:
            kinesis_video_signaling = boto3.client('kinesis-video-signaling',
                                                   endpoint_url=self.endpoint_https,
                                                   region_name=self.region)
        ice_server_config = kinesis_video_signaling.get_ice_server_config(
            ChannelARN=self.channel_arn,
            ClientId='MASTER'
        )

        iceServers = [RTCIceServer(urls=f'stun:stun.kinesisvideo.{self.region}.amazonaws.com:443')]
        for iceServer in ice_server_config['IceServerList']:
            iceServers.append(RTCIceServer(
                urls=iceServer['Uris'],
                username=iceServer['Username'],
                credential=iceServer['Password']
            ))
        self.ice_servers = iceServers
        return self.ice_servers

    def create_wss_url(self):
        if self.credentials:
            auth_credentials = Credentials(
                access_key=self.credentials['accessKeyId'],
                secret_key=self.credentials['secretAccessKey'],
                token=self.credentials['sessionToken']
            )
        else:
            session = Session()
            auth_credentials = session.get_credentials()

        SigV4 = SigV4QueryAuth(auth_credentials, 'kinesisvideo', self.region, 299)
        aws_request = AWSRequest(
            method='GET',
            url=self.endpoint_wss,
            params={'X-Amz-ChannelARN': self.channel_arn, 'X-Amz-ClientId': self.client_id}
        )
        SigV4.add_auth(aws_request)
        PreparedRequest = aws_request.prepare()
        return PreparedRequest.url

    def decode_msg(self, msg):
        try:
            data = json.loads(msg)
            payload = json.loads(b64decode(data['messagePayload'].encode('ascii')).decode('ascii'))
            return data['messageType'], payload, data.get('senderClientId')
        except json.decoder.JSONDecodeError:
            return '', {}, ''

    def encode_msg(self, action, payload, client_id):
        return json.dumps({
            'action': action,
            'messagePayload': b64encode(json.dumps(payload.__dict__).encode('ascii')).decode('ascii'),
            'recipientClientId': client_id,
        })

    async def handle_sdp_offer(self, payload, client_id, websocket):
        iceServers = self.prepare_ice_servers()
        configuration = RTCConfiguration(iceServers=iceServers)
        pc = RTCPeerConnection(configuration=configuration)
        self.DCMap[client_id] = pc.createDataChannel('kvsDataChannel')
        self.PCMap[client_id] = pc

        @pc.on('connectionstatechange')
        async def on_connectionstatechange():
            if client_id in self.PCMap:
                print(f'[{client_id}] connectionState: {self.PCMap[client_id].connectionState}')

        @pc.on('iceconnectionstatechange')
        async def on_iceconnectionstatechange():
            if client_id in self.PCMap:
                print(f'[{client_id}] iceConnectionState: {self.PCMap[client_id].iceConnectionState}')

        @pc.on('icegatheringstatechange')
        async def on_icegatheringstatechange():
            if client_id in self.PCMap:
                print(f'[{client_id}] iceGatheringState: {self.PCMap[client_id].iceGatheringState}')

        @pc.on('signalingstatechange')
        async def on_signalingstatechange():
            if client_id in self.PCMap:
                print(f'[{client_id}] signalingState: {self.PCMap[client_id].signalingState}')

        @pc.on('track')
        def on_track(track):
            MediaBlackhole().addTrack(track)

        @pc.on('datachannel')
        async def on_datachannel(channel):
            @channel.on('message')
            def on_message(dc_message):
                for i in self.PCMap:
                    if self.DCMap[i].readyState == 'open':
                        try:
                            self.DCMap[i].send(f'broadcast: {dc_message}')
                        except Exception as e:
                            print(f"Error sending message: {e}")
                    else:
                        print(f"Data channel {i} is not open. Current state: {self.DCMap[i].readyState}")
                print(f'[{channel.label}] datachannel_message: {dc_message}')

        self.PCMap[client_id].addTrack(self.video_track)

        await self.PCMap[client_id].setRemoteDescription(RTCSessionDescription(
            sdp=payload['sdp'],
            type=payload['type']
        ))
        await self.PCMap[client_id].setLocalDescription(await self.PCMap[client_id].createAnswer())
        await websocket.send(self.encode_msg('SDP_ANSWER', self.PCMap[client_id].localDescription, client_id))

    async def handle_ice_candidate(self, payload, client_id):
        if client_id in self.PCMap:
            candidate = candidate_from_sdp(payload['candidate'])
            candidate.sdpMid = payload['sdpMid']
            candidate.sdpMLineIndex = payload['sdpMLineIndex']
            await self.PCMap[client_id].addIceCandidate(candidate)

    async def signaling_client(self):
        self.get_signaling_channel_endpoint()
        wss_url = self.create_wss_url()

        try:
            while not _stop_event.is_set():
                try:
                    async with websockets.connect(wss_url) as websocket:
                        self._websocket = websocket
                        print('Signaling Server Connected!')
                        async for message in websocket:
                            if _stop_event.is_set():
                                return
                            msg_type, payload, client_id = self.decode_msg(message)
                            if msg_type == 'SDP_OFFER':
                                await self.handle_sdp_offer(payload, client_id, websocket)
                            elif msg_type == 'ICE_CANDIDATE':
                                await self.handle_ice_candidate(payload, client_id)
                except websockets.ConnectionClosed:
                    if _stop_event.is_set():
                        return
                    print('Connection closed, reconnecting...')
                    self.get_signaling_channel_endpoint()
                    wss_url = self.create_wss_url()
                    continue
                finally:
                    self._websocket = None
        except asyncio.CancelledError:
            pass
        finally:
            self.PCMap.clear()
            self.DCMap.clear()

    def refresh_credentials(self, access_key_id, secret_access_key, session_token):
        self.credentials = {
            'accessKeyId': access_key_id,
            'secretAccessKey': secret_access_key,
            'sessionToken': session_token
        }
        self.kinesisvideo = boto3.client(
            'kinesisvideo',
            region_name=self.region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            aws_session_token=session_token
        )


def stop_webrtc():
    """Signal the WebRTC signaling loop to exit and close the active websocket."""
    global _webrtc_loop
    _stop_event.set()
    loop = _webrtc_loop
    if loop is None or loop.is_closed():
        return

    async def _do_stop():
        # Close the websocket to immediately break out of the async-for receive loop.
        client = webrtc_client
        if client is not None and client._websocket is not None:
            try:
                await client._websocket.close()
            except Exception:
                pass
        # Also cancel any remaining aiortc tasks (ICE, DTLS, encoder) so they
        # don't linger after signaling_client() returns.
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for t in tasks:
            t.cancel()

    asyncio.run_coroutine_threadsafe(_do_stop(), loop)


def start_webrtc(region, channel_arn, access_key_id, secret_access_key, session_token, frame_queue):
    global webrtc_client, _webrtc_loop
    _stop_event.clear()
    try:
        assert all([region, channel_arn, access_key_id, secret_access_key])

        credentials = {
            'accessKeyId': access_key_id,
            'secretAccessKey': secret_access_key,
            'sessionToken': session_token
        }

        webrtc_client = KinesisVideoClient(
            client_id="MASTER",
            region=region,
            channel_arn=channel_arn,
            credentials=credentials,
            frame_queue=frame_queue
        )

        loop = asyncio.new_event_loop()
        _webrtc_loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(webrtc_client.signaling_client())
        except asyncio.CancelledError:
            pass
        finally:
            # Drain any remaining aiortc tasks before closing the loop.
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()
            _webrtc_loop = None
    except Exception:
        print("WebRTC thread crashed:")
        traceback.print_exc()
