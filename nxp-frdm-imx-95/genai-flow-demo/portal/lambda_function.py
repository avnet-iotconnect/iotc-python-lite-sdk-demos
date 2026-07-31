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
import urllib.parse
import urllib.request
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
UPLOAD_BUCKET = os.environ.get("UPLOAD_BUCKET", "imx95-portal-uploads")

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


# --- timezone resolution ------------------------------------------------------
# The platform's user-create requires one of ITS timezone GUIDs (Windows-style
# names). The signup page sends the browser's IANA zone; map it: explicit table
# for common zones whose Windows name shares no city, then city-substring match,
# then standard (January) offset match, then US Central.
_IANA_KEYWORD = {
    "America/Chicago": "Central Time", "America/New_York": "Eastern Time",
    "America/Denver": "Mountain Time", "America/Phoenix": "Arizona",
    "America/Los_Angeles": "Pacific Time", "America/Anchorage": "Alaska",
    "Pacific/Honolulu": "Hawaii", "Asia/Shanghai": "Beijing",
    "Asia/Calcutta": "Kolkata", "Asia/Kolkata": "Kolkata",
}
_tz_cache = None


def _tz_list(c):
    global _tz_cache
    if _tz_cache is None:
        out = c._req("GET", c.urls["dashboardBaseUrl"] + "/master/timezone")
        _tz_cache = out.get("data", [])
    return _tz_cache


def resolve_timezone_guid(c, iana):
    zones = _tz_list(c)

    def find(pred):
        return next((z for z in zones if pred(("%s %s" % (z.get("utcName", ""), z.get("name", ""))).lower())), None)

    hit = None
    if iana:
        kw = _IANA_KEYWORD.get(iana)
        if kw:
            hit = find(lambda s: kw.lower() in s)
        if hit is None and "/" in iana:
            city = iana.rsplit("/", 1)[1].replace("_", " ").lower()
            hit = find(lambda s: city in s)
        if hit is None:
            try:
                import datetime
                from zoneinfo import ZoneInfo
                jan = datetime.datetime(2026, 1, 15, tzinfo=ZoneInfo(iana))
                off = jan.utcoffset()
                sign = "+" if off >= datetime.timedelta(0) else "-"
                total = abs(int(off.total_seconds()))
                tag = "(utc%s%02d:%02d)" % (sign, total // 3600, (total % 3600) // 60)
                if total == 0:
                    hit = find(lambda s: "(utc)" in s or "(utc+00:00)" in s)
                else:
                    hit = find(lambda s: tag in s)
            except Exception:
                pass
    if hit is None:
        hit = find(lambda s: "central time" in s)
    return (hit or {}).get("guid")


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
    tz_guid = resolve_timezone_guid(c, item.get("tz") or "")
    print("timezone: %r -> %s" % (item.get("tz"), tz_guid), flush=True)
    c.create_user(item["email"], first or "Portal", last or "User",
                  ADMIN_ROLE, ent_guid, timezone_guid=tz_guid)

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


# --- cockpit: the attendee's own web experience -------------------------------
# Every cockpit call runs with the ATTENDEE'S OWN /IOTCONNECT token (obtained by
# proxying their login), never the portal's master credentials - so the platform
# itself enforces that they only ever see and command their own entity's device.
def cockpit_client(user_token=None):
    cr = creds()
    c = Client(solution_key=cr["solution_key"], env=cr.get("env", "poc"), pf=cr.get("pf", "aws"))
    c.discover()
    if user_token:
        c.token = user_token
    return c


def telemetry_base(c):
    return (c.urls.get("telemetryBaseUrl")
            or c.urls["deviceBaseUrl"].replace("device", "telemetry"))


_TAG_STRIP = re.compile(r"(?is)<(script|style|nav|footer|header|aside|noscript)[^>]*>.*?</\1>")
_TAGS = re.compile(r"(?s)<[^>]+>")
_WS = re.compile(r"[ \t\x0b\f]+")
_BLANKS = re.compile(r"\n{3,}")


def html_to_text(html):
    """Readable text from a web page - stdlib only, no scraping stack."""
    import html as htmlmod
    body = re.search(r"(?is)<body[^>]*>(.*)</body>", html)
    text = body.group(1) if body else html
    text = _TAG_STRIP.sub(" ", text)
    text = re.sub(r"(?i)</(p|div|li|h[1-6]|tr|section|article)>", "\n\n", text)
    text = re.sub(r"(?i)<br[^>]*>", "\n", text)
    text = _TAGS.sub(" ", text)
    text = htmlmod.unescape(text)
    text = _WS.sub(" ", text)
    return _BLANKS.sub("\n\n", "\n".join(l.strip() for l in text.splitlines())).strip()


def pdf_to_text(data):
    """Text layer of a PDF (pypdf is vendored). Scanned pages yield nothing."""
    import io as _io
    from pypdf import PdfReader
    reader = PdfReader(_io.BytesIO(data))
    pages = []
    for page in reader.pages[:120]:
        try:
            pages.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001 - skip pages pypdf cannot decode
            continue
    return _BLANKS.sub("\n\n", "\n\n".join(pages)).strip()


def stage_and_send(c, b, name, data):
    """Put a text document in the private bucket and tell the board to fetch it."""
    key = "rag/%s/%s" % (b.get("deviceGuid", "unknown"), name)
    s3 = boto3.client("s3", region_name=REGION)
    s3.put_object(Bucket=UPLOAD_BUCKET, Key=key, Body=data)
    url = s3.generate_presigned_url("get_object",
                                    Params={"Bucket": UPLOAD_BUCKET, "Key": key},
                                    ExpiresIn=3600)
    c._req("POST", c.urls["deviceBaseUrl"] + "/template-command/device/%s/send" % b["deviceGuid"],
           body={"commandGuid": b["commandGuid"], "parameterValue": url, "gatewayGuid": ""})
    return resp(200, {"sent": True, "name": name, "bytes": len(data)})


def cockpit(event, path, method, headers, body_raw):
    token = headers.get("x-iotc-token") or headers.get("X-Iotc-Token")
    qs = event.get("queryStringParameters") or {}

    # Converting a large PDF or page can outlast API Gateway's 30 s ceiling, which
    # surfaced as a 503 even though the work completed. Hand those two jobs to an
    # asynchronous self-invoke and answer immediately - the board reports real
    # progress through rag_status telemetry anyway.
    if path.endswith(("/rag-upload", "/rag-url")) and not event.get("_rag_job"):
        if not token:
            return resp(401, {"error": "not signed in"})
        try:
            boto3.client("lambda", region_name=REGION).invoke(
                FunctionName=os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "imx95-portal-api"),
                InvocationType="Event",
                Payload=json.dumps({"_rag_job": True, "path": path,
                                    "token": token, "body": body_raw}).encode())
            return resp(202, {"queued": True})
        except Exception as e:  # noqa: BLE001 - fall through to run it inline
            print("async dispatch failed, running inline:", e)

    if path.endswith("/login"):
        try:
            b = json.loads(body_raw or "{}")
        except ValueError:
            return resp(400, {"error": "bad json"})
        email, password = (b.get("email") or "").strip(), b.get("password") or ""
        if not email or not password:
            return resp(400, {"error": "email and password are required"})
        c = cockpit_client()
        try:
            data = c.login(email, password)
        except IoTConnectError:
            return resp(401, {"error": "Sign-in failed - check the email and password "
                                       "from your welcome email."})
        return resp(200, {"token": data.get("access_token") or data.get("accessToken")})

    if not token:
        return resp(401, {"error": "not signed in"})
    c = cockpit_client(token)

    try:
        if path.endswith("/bootstrap"):
            devs = c.devices().get("data", [])
            devs = [d for d in devs if d.get("uniqueId", "").startswith("p95")] or devs
            out = {"devices": [{"guid": d["guid"], "uniqueId": d["uniqueId"],
                                "templateGuid": d.get("deviceTemplateGuid")} for d in devs[:10]],
                   "commands": {}}
            if out["devices"]:
                tpl = out["devices"][0]["templateGuid"]
                cmds = c._req("GET", c.urls["deviceBaseUrl"] + "/template-command/%s/lookup" % tpl)
                out["commands"] = {x.get("command"): x.get("guid")
                                   for x in cmds.get("data", []) if x.get("command")}
            return resp(200, out)

        if path.endswith("/telemetry"):
            guid = qs.get("guid") or ""
            rows = c._req("GET", telemetry_base(c) + "/Telemetry/device/" + guid).get("data", [])
            values, newest = {}, None
            for r in rows:
                values[r.get("attributeName")] = r.get("attributeValue")
                ts = r.get("deviceUpdatedDate")
                if ts and (newest is None or ts > newest):
                    newest = ts
            age = None
            if newest:
                try:
                    import datetime
                    t = datetime.datetime.strptime(newest[:19], "%Y-%m-%dT%H:%M:%S").replace(
                        tzinfo=datetime.timezone.utc)
                    age = (datetime.datetime.now(datetime.timezone.utc) - t).total_seconds()
                except ValueError:
                    pass
            return resp(200, {"values": values, "age_s": age})

        if path.endswith("/command"):
            b = json.loads(body_raw or "{}")
            c._req("POST", c.urls["deviceBaseUrl"] + "/template-command/device/%s/send"
                   % b["deviceGuid"],
                   body={"commandGuid": b["commandGuid"], "parameterValue": b.get("value", ""),
                         "gatewayGuid": ""})
            return resp(200, {"sent": True})

        if path.endswith("/rag-url"):
            # Scrape a web page into clean text and hand it to the board. The
            # conversion happens here so the board never needs a parser stack.
            b = json.loads(body_raw or "{}")
            url = (b.get("url") or "").strip()
            if not url.startswith(("http://", "https://")):
                return resp(400, {"error": "enter a full http(s) URL"})
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "iotconnect-rag/1.0"})
                with urllib.request.urlopen(req, timeout=25) as r:
                    raw = r.read(6 * 1024 * 1024)
                    ctype = (r.headers.get("Content-Type") or "").lower()
            except Exception as e:  # noqa: BLE001 - report fetch problems to the user
                return resp(400, {"error": "could not fetch that page: %s" % str(e)[:120]})
            if "pdf" in ctype or url.lower().endswith(".pdf"):
                text = pdf_to_text(raw)
            else:
                text = html_to_text(raw.decode("utf-8", "replace"))
            if len(text.strip()) < 40:
                return resp(400, {"error": "no readable text found at that URL"})
            host = re.sub(r"[^A-Za-z0-9]+", "_", urllib.parse.urlparse(url).netloc)[:40]
            return stage_and_send(c, b, host + ".txt", text.encode("utf-8"))

        if path.endswith("/rag-upload"):
            # The attendee drops a document in the cockpit; it is staged in a
            # private bucket and the board is told to fetch it with a short-lived
            # presigned URL, then chunk + embed it into its RAG database.
            b = json.loads(body_raw or "{}")
            name = re.sub(r"[^A-Za-z0-9._-]", "_", (b.get("name") or "document.txt"))[:80]
            data = base64.b64decode(b.get("content") or "")
            if not data:
                return resp(400, {"error": "empty file"})
            if len(data) > 4 * 1024 * 1024:
                return resp(400, {"error": "file too large (4 MB limit)"})
            # PDFs are converted here - the board only ever ingests plain text.
            if name.lower().endswith(".pdf") or data[:5] == b"%PDF-":
                text = pdf_to_text(data)
                if len(text.strip()) < 40:
                    return resp(400, {"error": "no extractable text in that PDF "
                                               "(scanned pages need OCR)"})
                name = re.sub(r"\.pdf$", "", name, flags=re.I) + ".txt"
                data = text.encode("utf-8")
            return stage_and_send(c, b, name, data)

        if path.endswith("/models"):
            fw = c.urls.get("firmwareBaseUrl", "")
            try:
                out = c._req("GET", fw + "/Module/lookup")
                return resp(200, {"models": out.get("data", []) or []})
            except IoTConnectError as e:
                return resp(200, {"models": [], "note": str(e)[:160]})

        if path.endswith("/model-push"):
            b = json.loads(body_raw or "{}")
            fw = c.urls.get("firmwareBaseUrl", "")
            out = c._req("POST", fw + "/Module/push",
                         body={"moduleGuid": b.get("moduleGuid"),
                               "devices": [b.get("deviceGuid")], "applyTo": 2})
            return resp(200, {"pushed": True, "detail": json.dumps(out)[:200]})
    except IoTConnectError as e:
        return resp(502, {"error": str(e)[-200:]})
    except (KeyError, ValueError) as e:
        return resp(400, {"error": str(e)[:200]})
    return resp(404, {"error": "not found"})


def lambda_handler(event, context):
    # Asynchronous re-invoke of a RAG conversion job (see cockpit()).
    if event.get("_rag_job"):
        try:
            return cockpit(event, event["path"], "POST",
                           {"x-iotc-token": event.get("token")}, event.get("body") or "")
        except Exception as e:  # noqa: BLE001 - log; the board reports its own status
            print("rag job failed:", e)
            return {"ok": False}

    rc = event.get("requestContext", {})
    http = rc.get("http", {})
    method, path = http.get("method", ""), http.get("path", "")
    qs = event.get("queryStringParameters") or {}
    base_url = "https://" + rc.get("domainName", "") + (
        "/" + rc.get("stage", "") if rc.get("stage") not in (None, "", "$default") else "")

    if method == "OPTIONS":
        return resp(200, "")

    if method == "GET" and path in ("/", "/index.html", "/cockpit", "/cockpit.html"):
        name = "cockpit.html" if "cockpit" in path else "index.html"
        try:
            page = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), name)).read()
            return resp(200, page, "text/html; charset=utf-8")
        except OSError:
            return html(500, "Portal", "%s missing from deployment" % name)

    if "/api/cockpit/" in path:
        body_raw = (base64.b64decode(event["body"]).decode() if event.get("isBase64Encoded")
                    else event.get("body") or "")
        hdrs = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
        return cockpit(event, path, method, hdrs, body_raw)

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
                "company": company, "tz": (b.get("tz") or "")[:64],
                "state": "pending", "created_at": int(time.time())}
        instant = bool(EVENT_CODE) and (b.get("eventCode") or "").strip() == EVENT_CODE
        if os.environ.get("REQUIRE_CODE") == "1" and not instant:
            return resp(400, {"error": "A valid attendee code is required for this event - "
                                       "get it from the workshop host."})
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
