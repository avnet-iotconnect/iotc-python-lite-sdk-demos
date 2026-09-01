#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
"""Phase-1 smoke test for the onboarding portal's IOTCONNECT client.

Reads secrets from the environment (or a --env-file that is NOT in the repo):
  IOTC_SOLUTION_KEY, IOTC_ADMIN_USER, IOTC_ADMIN_PASS  (IOTC_ENV defaults to poc)

Default mode logs in, then prints the account's entities, roles, and device
templates - the three lookups the onboarding flow needs before it can create
anything.

--test-user-password EMAIL runs the password-at-create experiment: the
published POST /User spec has no password field (users set one via the emailed
invite), but if the server silently honors one, the portal signup form could
collect a password and attendees would never need to check email. The probe
mirrors the Lambda's onboard flow exactly - throwaway entity under the portal
parent, then the user with password+confirmPassword and sendInvitationEmail
off - and then tries to log in as that user. Cleanup is best-effort; anything
left behind is named PwProbe* and printed for manual deletion in the console.
"""
import argparse
import json
import os
import secrets
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from iotc_client import Client, IoTConnectError  # noqa: E402

# Same defaults (and env overrides) as lambda_function.py.
PORTAL_PARENT = os.environ.get("PORTAL_PARENT", "9A993EB8-B6EE-41D7-B13E-01CA53D52B89")  # IMX95-Portal
ADMIN_ROLE = os.environ.get("ADMIN_ROLE", "6F3294E9-F31B-4A3B-8A48-42D200917846")


def probe_user_password(c, email, password, keep=False):
    """Create entity + user-with-password (no invite email), then try to log in."""
    ent_name = "PwProbe" + uuid.uuid4().hex[:6]
    print("[1/4] creating throwaway entity %s under IMX95-Portal..." % ent_name)
    out = c._req("POST", c.urls["entityBaseUrl"] + "/Entity",
                 body={"name": ent_name, "parentEntityGuid": PORTAL_PARENT})
    ent_guid = out["data"][0]["entityGuid"]
    print("      entity %s" % ent_guid)

    print("[2/4] creating user %s with password in the payload, invite email OFF..." % email)
    created = c.create_user(email, "Password", "Probe", ADMIN_ROLE, ent_guid,
                            password=password, send_invitation=False)
    print("      create response: %s" % json.dumps(created)[:400])
    data = created.get("data") or []
    row = data[0] if isinstance(data, list) and data else {}
    user_guid = row.get("newId") or row.get("userGuid")  # the API returns newId

    print("[3/4] logging in as %s with that password..." % email)
    verdict = None
    try:
        Client().login(email, password)
        verdict = ("PASS: the server honored the password field - login succeeded.\n"
                   "      Portal change is viable: collect a password at signup, pass it\n"
                   "      through create_user(), and attendees never check email.")
    except IoTConnectError as e:
        verdict = ("FAIL: login rejected - the password field was ignored or refused.\n"
                   "      Server said: %s\n"
                   "      Conclusion: stick with the invitation-email flow (or pre-event\n"
                   "      signup so invites are already in inboxes)." % e)

    print("[4/4] cleanup (best-effort)...")
    if keep:
        print("      --keep: leaving entity %s / user %s in place" % (ent_name, email))
    else:
        for label, url in (("user", user_guid and c.urls["entityBaseUrl"] + "/User/" + user_guid),
                           ("entity", c.urls["entityBaseUrl"] + "/Entity/" + ent_guid)):
            if not url:
                print("      %s: no guid in create response - delete manually in the console" % label)
                continue
            try:
                # body={} so Content-Type is sent - a bare DELETE gets HTTP 412
                # "Unsupported content type ''" from this API.
                c._req("DELETE", url, body={})
                print("      %s deleted" % label)
            except IoTConnectError as e:
                print("      %s delete failed (remove %s manually in the console): %s"
                      % (label, ent_name, str(e)[:200]))

    print("\n" + verdict)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-file", help="KEY=VALUE lines; kept outside the repo")
    ap.add_argument("--test-user-password", metavar="EMAIL",
                    help="probe whether POST /User honors a password field: create a "
                         "throwaway entity+user with this email (no invite mail is sent, "
                         "so a plus-addressed alias works), then try to log in as them")
    ap.add_argument("--password", help="password for --test-user-password "
                                       "(default: a generated one, printed)")
    ap.add_argument("--keep", action="store_true",
                    help="skip cleanup of the probe entity/user")
    args = ap.parse_args()
    if args.env_file:
        for line in open(args.env_file):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    c = Client()
    print("discovering (%s/%s)..." % (c.env, c.pf))
    c.discover()
    print("auth:", c.urls["authBaseUrl"])
    c.login(os.environ["IOTC_ADMIN_USER"], os.environ["IOTC_ADMIN_PASS"])
    print("login OK - bearer token acquired\n")

    if args.test_user_password:
        # Upper+lower+digit+symbol and 16+ chars, to clear any complexity rule.
        password = args.password or ("Probe1!" + secrets.token_hex(5))
        print("probe password: %s" % password)
        probe_user_password(c, args.test_user_password, password, keep=args.keep)
        return

    for label, fn in (("ENTITIES", c.entities), ("ROLES", c.roles), ("TEMPLATES", c.templates)):
        try:
            out = fn()
            data = out.get("data", out)
            print("=== %s (%d) ===" % (label, len(data) if isinstance(data, list) else 1))
            print(json.dumps(data, indent=1)[:1200])
        except Exception as e:
            print("=== %s FAILED: %s" % (label, e))
        print()


if __name__ == "__main__":
    main()
