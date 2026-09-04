Avnet /IOTCONNECT is a cloud platform-as-a-service for building, connecting, and managing Internet of Things solutions. It handles device onboarding, data collection, visualization, rules, and fleet management so developers do not have to build that infrastructure themselves.

/IOTCONNECT is available on both Amazon Web Services (AWS) and Microsoft Azure back ends, letting customers choose their preferred cloud while using the same tools and APIs.

A device template in /IOTCONNECT defines a device's schema: the telemetry attributes it reports, the commands it accepts, and its data types. Every device of the same kind shares a template, so a fleet is managed consistently.

Telemetry in /IOTCONNECT is device-to-cloud (D2C) data such as sensor readings, sent by the device on an interval or on change. It appears on dashboards and can trigger rules.

Commands in /IOTCONNECT are cloud-to-device (C2D) messages that tell a device to do something, such as change a setting or run an action. Commands can require an acknowledgement so the sender knows they were received.

Devices connect to /IOTCONNECT over MQTT, a lightweight publish-subscribe messaging protocol designed for constrained devices and unreliable networks. Each device authenticates with credentials such as an x.509 certificate or a key.

An x.509 certificate is a digital identity that lets a device prove who it is using mutual TLS. /IOTCONNECT issues each device its own certificate and private key so the connection is encrypted and authenticated.

Entities in /IOTCONNECT are organizational units that group users and devices, allowing multi-tenant isolation. A sub-entity can be given access only to its own devices, which is how one account can host many isolated customers or attendees.

/IOTCONNECT provides a full REST API that exposes every platform feature programmatically, so custom applications and automated fleets can onboard devices, send commands, and read telemetry without using the web portal.

OTA, or over-the-air update, is /IOTCONNECT's mechanism to push new firmware or software to devices remotely. It is used to update the operating system or application across an entire fleet.

Model push in /IOTCONNECT is a specialized update that delivers a new AI or machine-learning model to edge devices, separate from a full firmware OTA, so a device's intelligence can be refreshed without reflashing it.

A rule in /IOTCONNECT watches incoming telemetry and triggers an action when a condition is met, such as sending an alert, an email, or a command when a temperature crosses a threshold.

Dashboards in /IOTCONNECT visualize device data with widgets such as gauges, charts, and maps, giving a live view of one device or an entire fleet.

The device SDK lets a device connect to /IOTCONNECT with minimal code. A lightweight lite SDK is available for constrained hardware; it handles the MQTT connection, telemetry publishing, and command callbacks.

/IOTCONNECT supports connectors and integrations that link the platform to other services and data systems, extending it into larger enterprise workflows.

A digital twin is the cloud's live representation of a physical device, holding its latest state and configuration. Applications read and act on the twin rather than talking to the device directly.

Fleet management in /IOTCONNECT means monitoring, updating, and controlling large numbers of devices at once, including grouping devices, rolling out updates in stages, and tracking device health.

Avnet is a global technology distributor and solutions provider; /IOTCONNECT is its IoT platform, often demonstrated on development boards from partners such as NXP, Renesas, Microchip, and Qualcomm.

Documentation for /IOTCONNECT, including its REST API reference, is published at docs.iotconnect.io, which describes how to onboard devices, define templates, and build applications.

Device claiming is the act of associating a physical board with a user's account by installing its identity credentials, after which the device appears in that user's entity and begins reporting to their dashboards.
