#!/usr/bin/env python3
"""Phase-1 smoke test for the onboarding portal's IOTCONNECT client.

Reads secrets from the environment (or a --env-file that is NOT in the repo):
  IOTC_SOLUTION_KEY, IOTC_ADMIN_USER, IOTC_ADMIN_PASS  (IOTC_ENV defaults to poc)

Logs in, then prints the account's entities, roles, and device templates -
the three lookups the onboarding flow needs before it can create anything.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from iotc_client import Client  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-file", help="KEY=VALUE lines; kept outside the repo")
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
