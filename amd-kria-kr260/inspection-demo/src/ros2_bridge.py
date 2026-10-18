# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
"""Optional ROS 2 bridge for the KR260 inspection cell demo.

Runs as a separate process on the board inside a ROS 2 Jazzy environment. It
forwards ROS 2 topic data to app.py over a localhost UDP socket (port 5577),
where it appears in the ros2_data telemetry attribute and drives the
ros2_bridge_active flag, and it executes ros2-call cloud commands that app.py
forwards to port 5578 (v1 calls std_srvs/srv/Trigger services). A 5 second
heartbeat datagram keeps ros2_bridge_active true even while topics are quiet.

Topic and service mappings are declared in ros2_bridge.json next to this file.

Requires ROS 2 Jazzy (sudo apt install ros-jazzy-ros-base, from the
packages.ros.org repository) on Ubuntu 24.04. The bridge is optional and is
not started by install.sh; run it manually:

    source /opt/ros/jazzy/setup.bash
    python3 /opt/demo/ros2_bridge.py
"""

import json
import os
import socket
import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, Float64, Int32, String
from std_srvs.srv import Trigger

TYPES = {'String': String, 'Float64': Float64, 'Int32': Int32, 'Bool': Bool}
APP_UDP = ('127.0.0.1', 5577)
CMD_PORT = 5578


class IotcBridge(Node):
    def __init__(self, config):
        super().__init__('iotc_inspection_bridge')
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for sub in config.get('telemetry_topics', []):
            topic = sub.get('topic') if isinstance(sub, dict) else None
            if not topic:
                self.get_logger().warning('Skipping telemetry_topics entry without a topic: %r' % (sub,))
                continue
            msg_type = TYPES.get(sub.get('type', 'String'))
            if msg_type is None:
                self.get_logger().warning('Unsupported type %s for %s' % (sub.get('type'), topic))
                continue
            key = sub.get('key') or topic.strip('/').replace('/', '_')
            self.create_subscription(msg_type, topic,
                                     lambda msg, k=key: self.forward(k, msg.data), 10)
            self.get_logger().info('Forwarding %s as telemetry key %s' % (topic, key))
        # Pre-create service clients here, not on the UDP thread: creating
        # rclpy entities while the executor spins is not thread safe. Note:
        # rclpy's Node already owns a read-only 'services' property, so this
        # map must use a different attribute name.
        self.trigger_clients = {}
        for svc in config.get('services', []):
            name = svc.get('name') if isinstance(svc, dict) else None
            service = svc.get('service') if isinstance(svc, dict) else None
            if not name or not service:
                self.get_logger().warning('Skipping services entry missing name/service: %r' % (svc,))
                continue
            self.trigger_clients[name] = self.create_client(Trigger, service)
            self.get_logger().info('Mapping ros2-call "%s" to service %s' % (name, service))
        # Heartbeat so app.py knows the bridge is alive even with quiet topics.
        self.create_timer(5.0, self._heartbeat)

    def _heartbeat(self):
        try:
            self.sock.sendto(b'{}', APP_UDP)
        except OSError:
            pass

    def forward(self, key, value):
        try:
            self.sock.sendto(json.dumps({key: value}).encode('utf-8'), APP_UDP)
        except (OSError, TypeError, ValueError):
            pass

    def handle_command(self, text):
        parts = text.strip().split(None, 1)
        name = parts[0] if parts else ''
        cli = self.trigger_clients.get(name)
        if cli is None:
            self.get_logger().warning('ros2-call for unmapped service: %s' % name)
            return
        if not cli.wait_for_service(timeout_sec=3.0):
            self.get_logger().warning('Service for %s not available' % name)
            return
        cli.call_async(Trigger.Request())
        self.get_logger().info('Called service for %s' % name)


def command_listener(node):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(('127.0.0.1', CMD_PORT))
    except OSError as e:
        # A bridge that cannot receive commands must not look healthy.
        node.get_logger().fatal('cannot bind command port %d: %s; is another bridge running?' % (CMD_PORT, e))
        os._exit(1)
    while True:
        try:
            payload, _ = sock.recvfrom(2048)
            node.handle_command(payload.decode('utf-8'))
        except Exception as e:
            node.get_logger().error('command error: %s' % e)


def main():
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ros2_bridge.json')
    config = {}
    if os.path.isfile(cfg_path):
        with open(cfg_path) as f:
            config = json.load(f)
    rclpy.init()
    node = IotcBridge(config)
    threading.Thread(target=command_listener, args=(node,), daemon=True).start()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    rclpy.shutdown()


if __name__ == '__main__':
    main()
