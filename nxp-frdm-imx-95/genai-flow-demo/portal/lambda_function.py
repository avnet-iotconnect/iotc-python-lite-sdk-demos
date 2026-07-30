# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
# -----------------------------------------------------------------------------
# i.MX95 onboarding portal - API Lambda.
#
# Routes (HTTP API, payload v2):
#   POST /api/signup            {name,email,company,eventCode?} -> pending (or
#                               instant onboard when eventCode matches); emails
#                               the approver one-click approve/reject links.
#   GET  /api/status/{id}?t=    applicant polls; returns state (+ kit URL when ready)
#   GET  /api/approve/{id}?k=   approver one-click: runs the IOTCONNECT onboard
#   GET  /api/reject/{id}?k=    approver one-click: rejects
#   GET  /api/kit/{id}?t=       downloads the board kit (zip: cert+key+config+README)
#
# The onboard flow is the one verified end-to-end on 2026-07-30 (see
# iotc_client.py): entity under IMX95-Portal + invited user + iMX95genai device
# with a self-signed cert; the kit connected from a real FRDM i.MX95.
# -----------------------------------------------------------------------------
import base64
import io
import json
import os
import re
import secrets as pysecrets
import time
import uuid
import zipfile

import boto3

from iotc_client import Client, IoTConnectError

REGION = os.environ.get("AWS_REGION", "us-east-1")
TABLE = os.environ.get("TABLE", "imx95-portal-requests")
SECRET_ID = os.environ.get("SECRET_ID", "imx95-portal/iotconnect")
APPROVER = os.environ.get("APPROVER_EMAIL", "michael@lamptribe.com")
EVENT_CODE = os.environ.get("EVENT_CODE", "")  # empty disables instant onboarding
PORTAL_PARENT = os.environ.get("PORTAL_PARENT", "9A993EB8-B6EE-41D7-B13E-01CA53D52B89")  # IMX95-Portal
TEMPLATE_GUID = os.environ.get("TEMPLATE_GUID", "91DD49FB-CFB8-4035-9B51-1F37D3EB2D1D")  # iMX95genai
ADMIN_ROLE = os.environ.get("ADMIN_ROLE", "6F3294E9-F31B-4A3B-8A48-42D200917846")
CONSOLE_URL = "https://awspoc.iotconnect.io"

ddb = boto3.resource("dynamodb", region_name=REGION).Table(TABLE)
ses = boto3.client("ses", region_name=REGION)
sm = boto3.client("secretsmanager", region_name=REGION)

_creds = None


def creds():
    global _creds
    if _creds is None:
        _creds = json.loads(sm.get_secret_value(SecretId=SECRET_ID)["SecretString"])
    return _creds


def iotc():
    cr = creds()
    c = Client(solution_key=cr["solution_key"], env=cr.get("env", "poc"), pf=cr.get("pf", "aws"))
    c.discover()
    c.login(cr["admin_user"], cr["admin_pass"])
    return c


# --- crypto: self-signed device cert -----------------------------------------
def make_device_cert(cn):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    import datetime
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(name).issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=3650))
            .sign(key, hashes.SHA256()))
    key_pem = key.private_bytes(serialization.Encoding.PEM,
                                serialization.PrivateFormat.TraditionalOpenSSL,
                                serialization.NoEncryption()).decode()
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    return cert_pem, key_pem


# --- the proven onboard flow --------------------------------------------------
def slug(s, maxlen=18):
    return re.sub(r"[^A-Za-z0-9]", "", s)[:maxlen] or "Customer"


def onboard(item):
    c = iotc()
    base = slug(item["company"] or item["name"])
    existing = {e["name"] for e in c.entities().get("data", [])}
    ent_name = base
    n = 1
    while ent_name in existing:
        n += 1
        ent_name = "%s%d" % (base, n)
    first, _, last = (item["name"] or "Portal User").partition(" ")
    out = c._req("POST", c.urls["entityBaseUrl"] + "/Entity",
                 body={"name": ent_name, "parentEntityGuid": PORTAL_PARENT})
    ent_guid = out["data"][0]["entityGuid"]
    # Entity creation does NOT invite anyone (its userGuid/isWelcomeEmail response
    # is misleading) - the user must be created explicitly. This call issues the
    # invitation and sends the platform welcome email.
    c.create_user(item["email"], first or "Portal", last or "User",
                  ADMIN_ROLE, ent_guid)

    duid = "p95" + uuid.uuid4().hex[:9]
    cert_pem, key_pem = make_device_cert(duid)
    c._req("POST", c.urls["deviceBaseUrl"] + "/Device",
           body={"uniqueId": duid, "displayName": "%s FRDM i.MX95" % ent_name,
                 "deviceTemplateGuid": TEMPLATE_GUID, "entityGuid": ent_guid,
                 "certificateText": cert_pem})
    det = c._req("GET", c.urls["deviceBaseUrl"] + "/Device/uniqueId/" + duid)
    dd = det.get("data", det)
    if isinstance(dd, list):
        dd = dd[0]
    cfg = {"ver": "2.1", "pf": creds().get("pf", "aws"), "cpid": dd.get("cpId"),
           "env": creds().get("env", "poc"), "uid": duid,
           "disc": "https://awsdiscovery.iotconnect.io"}
    return {"entity_name": ent_name, "entity_guid": ent_guid, "duid": duid,
            "cert_pem": cert_pem, "key_pem": key_pem,
            "device_config": json.dumps(cfg, indent=2)}


KIT_README = """Your /IOTCONNECT i.MX95 board kit
=================================

1. Check your inbox: IOTCONNECT sent you an invite - set your password, then
   log in at {console} to see your own dashboard.

2. Install the GenAI demo on your FRDM i.MX95 (one time):
   https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/tree/main/nxp-frdm-imx-95/genai-flow-demo

3. Copy the three files from this kit into the demo directory on the board
   (default /opt/demo/):
       iotcDeviceConfig.json  device-cert.pem  device-pkey.pem

4. Start the demo (or reboot the board). It connects as device {duid}
   in YOUR entity ({entity}) - only you can see it.

Demo commands (from the IOTCONNECT console): ask-llm, ask-agent, ask-vlm,
voice-start, run-benchmark, set-model, set-backend ... full list in the repo README.
"""


def build_kit_zip(item):
    ob = json.loads(item["onboard"])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("iotcDeviceConfig.json", ob["device_config"])
        z.writestr("device-cert.pem", ob["cert_pem"])
        z.writestr("device-pkey.pem", ob["key_pem"])
        z.writestr("README.txt", KIT_README.format(console=CONSOLE_URL, duid=ob["duid"],
                                                   entity=ob["entity_name"]))
    return buf.getvalue()


# --- http plumbing ------------------------------------------------------------
def resp(code, body, ctype="application/json", b64=False):
    return {"statusCode": code,
            "headers": {"Content-Type": ctype,
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Headers": "Content-Type"},
            "isBase64Encoded": b64,
            "body": body if isinstance(body, str) else json.dumps(body)}


def html(code, title, msg):
    page = ("<!DOCTYPE html><html><body style='font-family:system-ui;max-width:540px;"
            "margin:80px auto;text-align:center'><h2>%s</h2><p>%s</p></body></html>"
            % (title, msg))
    return resp(code, page, "text/html; charset=utf-8")


def send_approval_email(item, base_url):
    a = "%s/api/approve/%s?k=%s" % (base_url, item["id"], item["admin_token"])
    r = "%s/api/reject/%s?k=%s" % (base_url, item["id"], item["admin_token"])
    body = ("New i.MX95 portal signup:\n\n  Name:    %s\n  Email:   %s\n  Company: %s\n\n"
            "APPROVE (one click):\n%s\n\nREJECT:\n%s\n" %
            (item["name"], item["email"], item["company"], a, r))
    ses.send_email(Source=APPROVER, Destination={"ToAddresses": [APPROVER]},
                   Message={"Subject": {"Data": "[i.MX95 portal] approval needed: %s" % item["email"]},
                            "Body": {"Text": {"Data": body}}})


def do_onboard(item):
    ob = onboard(item)
    ddb.update_item(Key={"id": item["id"]},
                    UpdateExpression="SET #s=:s, onboard=:o, approved_at=:t",
                    ExpressionAttributeNames={"#s": "state"},
                    ExpressionAttributeValues={":s": "ready", ":o": json.dumps(ob), ":t": int(time.time())})
    return ob


def lambda_handler(event, context):
    rc = event.get("requestContext", {})
    http = rc.get("http", {})
    method, path = http.get("method", ""), http.get("path", "")
    qs = event.get("queryStringParameters") or {}
    base_url = "https://" + rc.get("domainName", "") + (
        "/" + rc.get("stage", "") if rc.get("stage") not in (None, "", "$default") else "")

    if method == "OPTIONS":
        return resp(200, "")

    if method == "GET" and path in ("/", "/index.html"):
        try:
            page = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "index.html")).read()
            return resp(200, page, "text/html; charset=utf-8")
        except OSError:
            return html(500, "Portal", "index.html missing from deployment")

    if method == "POST" and path.endswith("/api/signup"):
        try:
            b = json.loads(base64.b64decode(event["body"]) if event.get("isBase64Encoded")
                           else event.get("body") or "{}")
        except ValueError:
            return resp(400, {"error": "bad json"})
        name, email, company = (b.get("name") or "").strip(), (b.get("email") or "").strip(), (b.get("company") or "").strip()
        if not name or not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            return resp(400, {"error": "name and a valid email are required"})
        item = {"id": uuid.uuid4().hex[:12], "token": pysecrets.token_urlsafe(16),
                "admin_token": pysecrets.token_urlsafe(16), "name": name, "email": email,
                "company": company, "state": "pending", "created_at": int(time.time())}
        instant = bool(EVENT_CODE) and (b.get("eventCode") or "").strip() == EVENT_CODE
        ddb.put_item(Item=item)
        if instant:
            try:
                do_onboard(item)
                return resp(200, {"id": item["id"], "token": item["token"], "state": "ready"})
            except (IoTConnectError, Exception) as e:  # noqa: BLE001 - surface to applicant
                ddb.update_item(Key={"id": item["id"]},
                                UpdateExpression="SET #s=:s, error_detail=:e",
                                ExpressionAttributeNames={"#s": "state"},
                                ExpressionAttributeValues={":s": "error", ":e": str(e)[:400]})
                return resp(500, {"error": "onboarding failed", "detail": str(e)[:200]})
        try:
            send_approval_email(item, base_url)
        except Exception as e:  # noqa: BLE001 - email failure should not lose the signup
            print("approval email failed:", e)
        return resp(200, {"id": item["id"], "token": item["token"], "state": "pending"})

    m = re.match(r".*/api/(status|approve|reject|kit)/([A-Za-z0-9]+)$", path)
    if not m:
        return resp(404, {"error": "not found"})
    action, rid = m.groups()
    got = ddb.get_item(Key={"id": rid}).get("Item")
    if not got:
        return html(404, "Not found", "Unknown request.") if action in ("approve", "reject") else resp(404, {"error": "unknown id"})

    if action in ("approve", "reject"):
        if qs.get("k") != got["admin_token"]:
            return html(403, "Forbidden", "Bad approval link.")
        if got["state"] == "ready":
            return html(200, "Already onboarded", "%s was already approved." % got["email"])
        if action == "reject":
            ddb.update_item(Key={"id": rid}, UpdateExpression="SET #s=:s",
                            ExpressionAttributeNames={"#s": "state"},
                            ExpressionAttributeValues={":s": "rejected"})
            return html(200, "Rejected", "%s was rejected. Nothing was created." % got["email"])
        try:
            ob = do_onboard(got)
            return html(200, "Approved ✓",
                        "Entity <b>%s</b> + device <b>%s</b> created. %s got their IOTCONNECT "
                        "invite automatically; their kit download is now unlocked."
                        % (ob["entity_name"], ob["duid"], got["email"]))
        except (IoTConnectError, Exception) as e:  # noqa: BLE001
            ddb.update_item(Key={"id": rid}, UpdateExpression="SET #s=:s, error_detail=:e",
                            ExpressionAttributeNames={"#s": "state"},
                            ExpressionAttributeValues={":s": "error", ":e": str(e)[:400]})
            return html(500, "Onboarding failed", str(e)[:300])

    if qs.get("t") != got["token"]:
        return resp(403, {"error": "bad token"})
    if action == "status":
        out = {"state": got["state"], "console": CONSOLE_URL}
        if got["state"] == "ready":
            ob = json.loads(got["onboard"])
            out.update(entity=ob["entity_name"], duid=ob["duid"],
                       kit="/api/kit/%s?t=%s" % (rid, got["token"]))
        if got["state"] == "error":
            out["detail"] = got.get("error_detail", "")[:200]
        return resp(200, out)
    if action == "kit":
        if got["state"] != "ready":
            return resp(409, {"error": "not ready"})
        data = build_kit_zip(got)
        return {"statusCode": 200,
                "headers": {"Content-Type": "application/zip",
                            "Content-Disposition": "attachment; filename=imx95-board-kit-%s.zip" % rid,
                            "Access-Control-Allow-Origin": "*"},
                "isBase64Encoded": True,
                "body": base64.b64encode(data).decode()}
    return resp(404, {"error": "not found"})
