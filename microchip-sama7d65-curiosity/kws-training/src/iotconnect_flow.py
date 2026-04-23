from __future__ import annotations

import hashlib
import hmac
import json
import ssl
import time
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as et
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    import boto3
except ImportError:  # pragma: no cover
    boto3 = None

try:
    import paho.mqtt.client as mqtt
except ImportError:  # pragma: no cover
    mqtt = None

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


DEFAULT_DISCOVERY_BASE = "https://discovery.iotconnect.io"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_discovery_api_base(base_url: str) -> str:
    base = (base_url or DEFAULT_DISCOVERY_BASE).strip().rstrip("/")
    if base.endswith("/api/v2.1/dsdk"):
        return base
    if base.endswith("/api/v2.1"):
        return f"{base}/dsdk"
    if base.endswith("/api"):
        return f"{base}/v2.1/dsdk"
    return f"{base}/api/v2.1/dsdk"


def _content_type(file_name: str) -> str:
    suffix = Path(file_name).suffix.lower()
    return {
        ".gz": "application/gzip",
        ".json": "application/json",
        ".tar": "application/x-tar",
        ".txt": "text/plain",
        ".wav": "audio/wav",
        ".zip": "application/zip",
    }.get(suffix, "application/octet-stream")


@dataclass
class NativeUploadConfig:
    config_path: Path
    device_cert_path: Path
    device_key_path: Path
    ca_cert_path: Optional[Path] = None
    discovery_url: str = ""
    preferred_bucket_name: str = ""
    default_region: str = "us-east-1"
    fs_url_override: str = ""
    fs_buckets_override_json: str = ""
    mqtt_host_override: str = ""
    mqtt_port_override: int = 0
    mqtt_username_override: str = ""
    mqtt_client_id_override: str = ""
    file_topic_override: str = ""
    device_id_override: str = ""
    debug: bool = False


@dataclass
class NativeIdentity:
    config_loaded: bool = False
    discovery_url: str = ""
    identity_url: str = ""
    device_id: str = ""
    mqtt_host: str = ""
    mqtt_port: int = 8883
    mqtt_username: str = ""
    mqtt_client_id: str = ""
    file_topic: str = ""
    fs_url: str = ""
    fs_buckets: list[dict[str, Any]] = field(default_factory=list)
    raw_payload: dict[str, Any] = field(default_factory=dict)
    source: str = "none"


class IotConnectNativeUploader:
    def __init__(self, config: NativeUploadConfig):
        self.config = config
        self.identity = NativeIdentity()
        self.last_error = ""
        self._last_refresh_monotonic = 0.0

    def _log(self, message: str):
        if self.config.debug:
            print(f"[iotconnect-flow] {message}")

    def _parse_bucket_overrides(self) -> list[dict[str, Any]]:
        raw = self.config.fs_buckets_override_json.strip()
        if not raw:
            return []
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            raise ValueError("KWS_IOTC_FS_BUCKETS_JSON must contain a JSON array.")
        return [item for item in parsed if isinstance(item, dict)]

    def _ensure_paths(self):
        if not self.config.config_path.is_file():
            raise FileNotFoundError(f"Device config not found: {self.config.config_path}")
        if not self.config.device_cert_path.is_file():
            raise FileNotFoundError(f"Device certificate not found: {self.config.device_cert_path}")
        if not self.config.device_key_path.is_file():
            raise FileNotFoundError(f"Device private key not found: {self.config.device_key_path}")
        if self.config.ca_cert_path is not None and not self.config.ca_cert_path.is_file():
            raise FileNotFoundError(f"CA certificate not found: {self.config.ca_cert_path}")

    def _load_device_config(self) -> dict[str, Any]:
        self._ensure_paths()
        return json.loads(self.config.config_path.read_text(encoding="utf-8"))

    def _fetch_json(self, url: str) -> dict[str, Any]:
        self._log(f"GET {url}")
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def _build_discovery_url(self, device_config: dict[str, Any]) -> str:
        discovery_base = self.config.discovery_url.strip() or str(device_config.get("disc", "")).strip()
        api_base = _normalize_discovery_api_base(discovery_base)
        cpid = urllib.parse.quote(str(device_config.get("cpid", "")).strip(), safe="")
        env = urllib.parse.quote(str(device_config.get("env", "")).strip(), safe="")
        platform = urllib.parse.quote(str(device_config.get("pf", "")).strip(), safe="")
        if not cpid or not env or not platform:
            raise ValueError("Device config is missing cpid, env, or pf.")
        return f"{api_base}/cpId/{cpid}/env/{env}?pf={platform}"

    def refresh_identity(self, force: bool = False) -> NativeIdentity:
        if not force and self._last_refresh_monotonic and (time.monotonic() - self._last_refresh_monotonic) < 60:
            return self.identity

        fs_buckets_override = self._parse_bucket_overrides()
        identity = NativeIdentity(source="override" if fs_buckets_override or self.config.file_topic_override else "none")

        try:
            device_config = self._load_device_config()
            discovery_url = self._build_discovery_url(device_config)
            discovery_json = self._fetch_json(discovery_url)
            discovery_base_url = str(discovery_json.get("d", {}).get("bu", "")).strip()
            if not discovery_base_url:
                raise ValueError("Discovery response did not include a base identity URL.")

            uid = urllib.parse.quote(str(device_config.get("uid", "")).strip(), safe="")
            if not uid:
                raise ValueError("Device config is missing uid.")

            identity_url = f"{discovery_base_url.rstrip('/')}/uid/{uid}"
            identity_json = self._fetch_json(identity_url)
            payload = identity_json.get("d", {})
            protocol = payload.get("p", {})
            topics = protocol.get("topics", {})
            fs_config = protocol.get("fs", {}) if isinstance(protocol.get("fs", {}), dict) else {}

            identity = NativeIdentity(
                config_loaded=True,
                discovery_url=discovery_url,
                identity_url=identity_url,
                device_id=self.config.device_id_override or str(protocol.get("id", "")).strip() or str(device_config.get("did", "")).strip(),
                mqtt_host=self.config.mqtt_host_override or str(protocol.get("h", "")).strip(),
                mqtt_port=int(self.config.mqtt_port_override or protocol.get("p") or 8883),
                mqtt_username=self.config.mqtt_username_override or str(protocol.get("un", "")).strip(),
                mqtt_client_id=self.config.mqtt_client_id_override or str(protocol.get("id", "")).strip(),
                file_topic=self.config.file_topic_override or str(topics.get("fu", "")).strip(),
                fs_url=self.config.fs_url_override or str(fs_config.get("url", "")).strip(),
                fs_buckets=fs_buckets_override or list(fs_config.get("buckets", [])),
                raw_payload=identity_json,
                source="identity",
            )
            self.last_error = ""
        except Exception as exc:
            self.last_error = str(exc)
            self._log(f"Identity refresh failed: {exc}")

            if not self.config.device_cert_path.is_file() or not self.config.device_key_path.is_file():
                self.identity = identity
                self._last_refresh_monotonic = time.monotonic()
                return self.identity

            fallback_device_id = self.config.device_id_override
            try:
                device_config = self._load_device_config()
                fallback_device_id = fallback_device_id or str(device_config.get("did", "")).strip()
            except Exception:
                pass

            identity = NativeIdentity(
                config_loaded=False,
                discovery_url="",
                identity_url="",
                device_id=fallback_device_id,
                mqtt_host=self.config.mqtt_host_override,
                mqtt_port=int(self.config.mqtt_port_override or 8883),
                mqtt_username=self.config.mqtt_username_override,
                mqtt_client_id=self.config.mqtt_client_id_override or fallback_device_id,
                file_topic=self.config.file_topic_override,
                fs_url=self.config.fs_url_override,
                fs_buckets=fs_buckets_override,
                raw_payload={},
                source="override" if (self.config.fs_url_override or fs_buckets_override or self.config.file_topic_override) else "none",
            )

        self.identity = identity
        self._last_refresh_monotonic = time.monotonic()
        return self.identity

    def _verify_arg(self) -> Any:
        if self.config.ca_cert_path is not None:
            return str(self.config.ca_cert_path)
        return True

    def selected_bucket(self) -> Optional[dict[str, Any]]:
        identity = self.refresh_identity()
        buckets = identity.fs_buckets
        if not buckets:
            return None

        if self.config.preferred_bucket_name:
            for bucket in buckets:
                if str(bucket.get("bn", "")).strip() == self.config.preferred_bucket_name:
                    return bucket

        for bucket in buckets:
            if not bucket.get("ca", False):
                return bucket
        return buckets[0]

    def status_text(self) -> str:
        identity = self.refresh_identity()
        if not self.config.device_cert_path.is_file() or not self.config.device_key_path.is_file():
            return "Device certificate files are missing."
        if not identity.device_id:
            if self.last_error:
                return f"IoTConnect identity unavailable: {self.last_error}"
            return "IoTConnect identity is not loaded yet."
        if not identity.fs_url or not identity.fs_buckets:
            return "Identity loaded, but this device does not expose /IOTCONNECT file upload yet."
        if not identity.file_topic:
            return "Identity loaded, but no /IOTCONNECT FILE topic is configured for this device."
        if mqtt is None:
            return "paho-mqtt is not installed."
        if requests is None:
            return "requests is not installed."
        return "/IOTCONNECT native upload is ready."

    def ready(self) -> bool:
        identity = self.refresh_identity()
        return bool(
            identity.device_id
            and identity.mqtt_host
            and identity.mqtt_client_id
            and identity.fs_url
            and identity.fs_buckets
            and identity.file_topic
            and self.config.device_cert_path.is_file()
            and self.config.device_key_path.is_file()
            and mqtt is not None
            and requests is not None
        )

    def boto3_ready(self) -> bool:
        return self.ready() and boto3 is not None

    def snapshot(self) -> dict[str, Any]:
        identity = self.refresh_identity()
        bucket = self.selected_bucket()
        return {
            "ready": self.ready(),
            "status": self.status_text(),
            "device_id": identity.device_id,
            "config_path": str(self.config.config_path),
            "config_loaded": identity.config_loaded,
            "discovery_url": identity.discovery_url,
            "identity_url": identity.identity_url,
            "source": identity.source,
            "file_topic": identity.file_topic,
            "fs_url_configured": bool(identity.fs_url),
            "bucket_count": len(identity.fs_buckets),
            "selected_bucket": str(bucket.get("bn", "")).strip() if bucket else "",
            "selected_bucket_customer_account": bool(bucket.get("ca", False)) if bucket else False,
            "last_error": self.last_error,
        }

    def _selected_bucket_credentials(self) -> tuple[str, str, str, dict[str, Any], str]:
        bucket = self.selected_bucket()
        if bucket is None:
            raise RuntimeError("No /IOTCONNECT S3 bucket is configured for this device.")

        region = str(bucket.get("region", "")).strip() or self.config.default_region or "us-east-1"
        access_key, secret_key, session_token = self._get_iot_credentials()
        if bucket.get("ca", False):
            role_arn = str(bucket.get("rarn", "")).strip()
            if not role_arn:
                raise RuntimeError("Customer bucket is missing rarn for cross-account access.")
            access_key, secret_key, session_token = self._assume_cross_account_role(
                access_key,
                secret_key,
                session_token,
                role_arn,
            )
        return access_key, secret_key, session_token, bucket, region

    def create_boto3_session(self):
        if boto3 is None:
            raise RuntimeError("boto3 is not installed.")
        access_key, secret_key, session_token, _bucket, region = self._selected_bucket_credentials()
        return boto3.session.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            aws_session_token=session_token,
            region_name=region,
        )

    def discover_state_machine_arn(self, name_prefix: str = "conv-") -> str:
        session = self.create_boto3_session()
        client = session.client("stepfunctions")
        paginator = client.get_paginator("list_state_machines")
        for page in paginator.paginate():
            for item in page.get("stateMachines", []):
                name = str(item.get("name", "")).strip()
                arn = str(item.get("stateMachineArn", "")).strip()
                if name_prefix and not name.startswith(name_prefix):
                    continue
                if arn:
                    return arn
        raise RuntimeError(f"No Step Functions state machine found with prefix {name_prefix!r}.")

    def _sign(self, key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    def _get_iot_credentials(self) -> tuple[str, str, str]:
        identity = self.refresh_identity()
        if requests is None:
            raise RuntimeError("requests is not installed.")
        if not identity.fs_url:
            raise RuntimeError("No /IOTCONNECT credential URL is configured.")
        if not identity.device_id:
            raise RuntimeError("No device ID is available for IoT credential exchange.")

        response = requests.get(
            url=identity.fs_url,
            cert=(str(self.config.device_cert_path), str(self.config.device_key_path)),
            verify=self._verify_arg(),
            headers={"x-amzn-iot-thingname": identity.device_id},
            timeout=30,
        )
        if response.status_code != 200:
            raise RuntimeError(f"IoT credentials request failed: HTTP {response.status_code}")
        credentials = response.json().get("credentials", {})
        access_key = str(credentials.get("accessKeyId", "")).strip()
        secret_key = str(credentials.get("secretAccessKey", "")).strip()
        session_token = str(credentials.get("sessionToken", "")).strip()
        if not access_key or not secret_key or not session_token:
            raise RuntimeError("IoT credential response did not include temporary AWS credentials.")
        return access_key, secret_key, session_token

    def _assume_cross_account_role(
        self,
        access_key: str,
        secret_key: str,
        session_token: str,
        role_arn: str,
    ) -> tuple[str, str, str]:
        if requests is None:
            raise RuntimeError("requests is not installed.")
        timestamp = _utc_now()
        date_stamp = timestamp.strftime("%Y%m%d")
        amz_date = timestamp.strftime("%Y%m%dT%H%M%SZ")
        region = self.config.default_region or "us-east-1"
        session_name = f"iotc-{uuid.uuid4().hex[:12]}"

        payload_parts = {
            "Action": "AssumeRole",
            "DurationSeconds": "3600",
            "RoleArn": role_arn,
            "RoleSessionName": session_name,
            "Version": "2011-06-15",
        }
        payload = "&".join(
            f"{key}={urllib.parse.quote(str(value), safe='')}" for key, value in sorted(payload_parts.items())
        )
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        canonical_headers = f"host:sts.amazonaws.com\nx-amz-date:{amz_date}\nx-amz-security-token:{session_token}\n"
        signed_headers = "host;x-amz-date;x-amz-security-token"
        canonical_request = f"POST\n/\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
        credential_scope = f"{date_stamp}/{region}/sts/aws4_request"
        string_to_sign = (
            f"AWS4-HMAC-SHA256\n{amz_date}\n{credential_scope}\n"
            f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
        )

        k_date = self._sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
        k_region = self._sign(k_date, region)
        k_service = self._sign(k_region, "sts")
        k_signing = self._sign(k_service, "aws4_request")
        signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        response = requests.post(
            "https://sts.amazonaws.com/",
            data=payload,
            headers={
                "Authorization": (
                    "AWS4-HMAC-SHA256 "
                    f"Credential={access_key}/{credential_scope}, "
                    f"SignedHeaders={signed_headers}, Signature={signature}"
                ),
                "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                "X-Amz-Date": amz_date,
                "X-Amz-Security-Token": session_token,
            },
            timeout=30,
        )
        if response.status_code != 200:
            raise RuntimeError(f"STS AssumeRole failed: HTTP {response.status_code}")

        root = et.fromstring(response.content)
        ns = {"sts": "https://sts.amazonaws.com/doc/2011-06-15/"}
        creds = root.find(".//sts:Credentials", ns)
        if creds is None:
            raise RuntimeError("STS AssumeRole response did not include credentials.")
        return (
            creds.findtext("sts:AccessKeyId", default="", namespaces=ns),
            creds.findtext("sts:SecretAccessKey", default="", namespaces=ns),
            creds.findtext("sts:SessionToken", default="", namespaces=ns),
        )

    def _sign_s3_headers(
        self,
        method: str,
        bucket_name: str,
        object_key: str,
        access_key: str,
        secret_key: str,
        session_token: str,
        region: str,
        payload: bytes,
        headers: dict[str, str],
    ) -> tuple[str, dict[str, str]]:
        timestamp = _utc_now()
        date_stamp = timestamp.strftime("%Y%m%d")
        amz_date = timestamp.strftime("%Y%m%dT%H%M%SZ")
        encoded_key = urllib.parse.quote(object_key, safe="/-_.~")
        host = f"{bucket_name}.s3.{region}.amazonaws.com"

        request_headers = dict(headers)
        request_headers["Host"] = host
        request_headers["X-Amz-Content-Sha256"] = hashlib.sha256(payload).hexdigest()
        request_headers["X-Amz-Date"] = amz_date
        if session_token:
            request_headers["X-Amz-Security-Token"] = session_token

        canonical_headers = ""
        signed_header_names: list[str] = []
        for key in sorted(request_headers.keys(), key=str.lower):
            canonical_headers += f"{key.lower()}:{request_headers[key].strip()}\n"
            signed_header_names.append(key.lower())
        signed_headers = ";".join(signed_header_names)
        canonical_request = (
            f"{method}\n/{encoded_key}\n\n{canonical_headers}\n{signed_headers}\n"
            f"{request_headers['X-Amz-Content-Sha256']}"
        )
        credential_scope = f"{date_stamp}/{region}/s3/aws4_request"
        string_to_sign = (
            f"AWS4-HMAC-SHA256\n{amz_date}\n{credential_scope}\n"
            f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
        )

        k_date = self._sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
        k_region = self._sign(k_date, region)
        k_service = self._sign(k_region, "s3")
        k_signing = self._sign(k_service, "aws4_request")
        signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        request_headers["Authorization"] = (
            "AWS4-HMAC-SHA256 "
            f"Credential={access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        return f"https://{host}/{encoded_key}", request_headers

    def put_object(self, file_name: str, payload: bytes) -> dict[str, Any]:
        if requests is None:
            raise RuntimeError("requests is not installed.")

        access_key, secret_key, session_token, bucket, region = self._selected_bucket_credentials()
        bucket_name = str(bucket.get("bn", "")).strip()
        if not bucket_name:
            raise RuntimeError("Selected /IOTCONNECT bucket does not have a bucket name.")

        timestamp = _utc_now()
        object_key = (
            f"device-uploads/{self.identity.device_id}/{timestamp.strftime('%Y/%m/%d')}/"
            f"{uuid.uuid4()}-{Path(file_name).name}"
        )

        url, headers = self._sign_s3_headers(
            method="PUT",
            bucket_name=bucket_name,
            object_key=object_key,
            access_key=access_key,
            secret_key=secret_key,
            session_token=session_token,
            region=region,
            payload=payload,
            headers={
                "Content-Length": str(len(payload)),
                "Content-Type": _content_type(file_name),
            },
        )
        response = requests.put(url, data=payload, headers=headers, timeout=300)
        if response.status_code not in {200, 201, 204}:
            raise RuntimeError(f"S3 upload failed: HTTP {response.status_code}")

        tail = object_key.split("/")[-4:]
        url_path = "/".join(tail)
        return {
            "bucket": bucket_name,
            "customer_account_bucket": bool(bucket.get("ca", False)),
            "object_key": object_key,
            "region": region,
            "s3_uri": f"s3://{bucket_name}/{object_key}",
            "url_path": url_path,
        }

    def publish_file_event(self, url_path: str, custom_fields: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if mqtt is None:
            raise RuntimeError("paho-mqtt is not installed.")

        identity = self.refresh_identity()
        if not identity.file_topic:
            raise RuntimeError("No /IOTCONNECT FILE topic is configured.")
        if not identity.mqtt_host or not identity.mqtt_client_id:
            raise RuntimeError("IoTConnect MQTT settings are incomplete.")

        payload = {"d": [{"d": {"url": url_path, "cf": custom_fields or {}}}]}
        result_state = {"published": False, "topic": identity.file_topic}
        connect_error: list[str] = []
        connected = {"value": False}

        client = mqtt.Client(client_id=identity.mqtt_client_id, clean_session=True, userdata=None, protocol=mqtt.MQTTv311)

        if identity.mqtt_username:
            client.username_pw_set(identity.mqtt_username, None)

        def on_connect(_client, _userdata, _flags, rc, _properties=None):
            connected["value"] = rc == 0
            if rc != 0:
                connect_error.append(f"MQTT connect failed with rc={rc}")

        client.on_connect = on_connect
        client.tls_set(
            ca_certs=str(self.config.ca_cert_path) if self.config.ca_cert_path else None,
            certfile=str(self.config.device_cert_path),
            keyfile=str(self.config.device_key_path),
            cert_reqs=ssl.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLSv1_2,
        )
        client.tls_insecure_set(False)
        client.connect(identity.mqtt_host, identity.mqtt_port, keepalive=60)
        client.loop_start()

        try:
            for _ in range(40):
                if connected["value"] or connect_error:
                    break
                time.sleep(0.25)
            if connect_error:
                raise RuntimeError(connect_error[0])
            if not connected["value"]:
                raise RuntimeError("Timed out waiting for MQTT connection.")

            info = client.publish(identity.file_topic, payload=json.dumps(payload), qos=0)
            info.wait_for_publish(timeout=10)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError(f"MQTT publish failed with rc={info.rc}")
            result_state["published"] = True
            return result_state
        finally:
            try:
                client.disconnect()
            finally:
                client.loop_stop()
