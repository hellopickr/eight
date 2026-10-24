#!/usr/bin/env python3
"""Upload Eight's App Store screenshots to the 1.0 draft in App Store Connect.

Uses the App Store Connect API key from Codemagic's "Codemagic" integration
(APP_STORE_CONNECT_KEY_IDENTIFIER, APP_STORE_CONNECT_ISSUER_ID,
APP_STORE_CONNECT_PRIVATE_KEY). Only touches the app with bundle ID
com.hellopickr.eight. It never submits anything for review.

Usage: upload_screenshots.py <folder of PNGs> [version] [display type]
"""
import base64, glob, hashlib, json, os, re, sys, time, urllib.error, urllib.request

import jwt  # PyJWT, with cryptography for ES256

API = "https://api.appstoreconnect.apple.com/v1"
BUNDLE_ID = os.environ.get("BUNDLE_ID", "com.hellopickr.eight")
if BUNDLE_ID != "com.hellopickr.eight":
    sys.exit("Refusing to run: this script is only for Eight (com.hellopickr.eight).")

folder = sys.argv[1]
version_string = sys.argv[2] if len(sys.argv) > 2 else "1.0"
display_type = sys.argv[3] if len(sys.argv) > 3 else "APP_IPHONE_67"  # 6.9-inch, 1320 x 2868


def private_key():
    raw = os.environ["APP_STORE_CONNECT_PRIVATE_KEY"].strip()
    # Codemagic integrations pass the key as a reference: "@file:/path/key.p8" or "@env:VAR".
    for _ in range(3):
        if raw.startswith("@file:"):
            raw = open(os.path.expanduser(raw[len("@file:"):]), encoding="utf-8").read().strip()
        elif raw.startswith("@env:"):
            raw = os.environ[raw[len("@env:"):]].strip()
        else:
            break
    raw = raw.replace("\\n", "\n")
    if "BEGIN" not in raw:
        try:
            raw = base64.b64decode(raw).decode()
        except Exception:
            pass
    body = re.sub(r"-----[^-]+-----", "", raw)
    body = re.sub(r"\s+", "", body)
    lines = [body[i:i + 64] for i in range(0, len(body), 64)]
    return "-----BEGIN PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END PRIVATE KEY-----\n"


KEY = private_key()
_token = {"value": None, "exp": 0}


def token():
    now = int(time.time())
    if _token["value"] and now < _token["exp"] - 60:
        return _token["value"]
    exp = now + 15 * 60
    _token["value"] = jwt.encode(
        {"iss": os.environ["APP_STORE_CONNECT_ISSUER_ID"], "iat": now, "exp": exp, "aud": "appstoreconnect-v1"},
        KEY,
        algorithm="ES256",
        headers={"kid": os.environ["APP_STORE_CONNECT_KEY_IDENTIFIER"], "typ": "JWT"},
    )
    _token["exp"] = exp
    return _token["value"]


def call(method, path, body=None):
    url = path if path.startswith("http") else API + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token())
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            text = r.read().decode()
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as e:
        print(f"{method} {url} -> HTTP {e.code}\n{e.read().decode()[:2000]}")
        raise


files = sorted(glob.glob(os.path.join(folder, "*.png")))
if not files:
    sys.exit("No screenshots found in " + folder)
print("Screenshots:", [os.path.basename(f) for f in files])

apps = call("GET", f"/apps?filter[bundleId]={BUNDLE_ID}")["data"]
apps = [a for a in apps if a["attributes"]["bundleId"] == BUNDLE_ID]
if len(apps) != 1:
    sys.exit(f"Expected exactly one app for {BUNDLE_ID}, found {len(apps)}")
app = apps[0]
print("App:", app["id"], app["attributes"]["name"], app["attributes"]["bundleId"])

versions = call("GET", f"/apps/{app['id']}/appStoreVersions?filter[platform]=IOS&filter[versionString]={version_string}")["data"]
if not versions:
    sys.exit(f"No iOS version {version_string} found")
version = versions[0]
print("Version:", version["attributes"]["versionString"], version["attributes"].get("appStoreState"))

locs = call("GET", f"/appStoreVersions/{version['id']}/appStoreVersionLocalizations")["data"]
loc = next((l for l in locs if l["attributes"]["locale"] == "en-US"), None) or locs[0]
print("Localization:", loc["attributes"]["locale"])

sets = call("GET", f"/appStoreVersionLocalizations/{loc['id']}/appScreenshotSets?limit=50")["data"]
shot_set = next((s for s in sets if s["attributes"]["screenshotDisplayType"] == display_type), None)
if shot_set is None:
    shot_set = call("POST", "/appScreenshotSets", {"data": {
        "type": "appScreenshotSets",
        "attributes": {"screenshotDisplayType": display_type},
        "relationships": {"appStoreVersionLocalization": {"data": {"type": "appStoreVersionLocalizations", "id": loc["id"]}}},
    }})["data"]
    print("Created screenshot set", display_type)
else:
    old = call("GET", f"/appScreenshotSets/{shot_set['id']}/appScreenshots?limit=50")["data"]
    for s in old:
        call("DELETE", f"/appScreenshots/{s['id']}")
    print(f"Replaced {len(old)} old screenshot(s) in {display_type}")

uploaded = []
for path in files:
    blob = open(path, "rb").read()
    shot = call("POST", "/appScreenshots", {"data": {
        "type": "appScreenshots",
        "attributes": {"fileName": os.path.basename(path), "fileSize": len(blob)},
        "relationships": {"appScreenshotSet": {"data": {"type": "appScreenshotSets", "id": shot_set["id"]}}},
    }})["data"]
    for op in shot["attributes"]["uploadOperations"]:
        part = blob[op["offset"]:op["offset"] + op["length"]]
        req = urllib.request.Request(op["url"], data=part, method=op["method"])
        for h in op.get("requestHeaders") or []:
            req.add_header(h["name"], h["value"])
        with urllib.request.urlopen(req, timeout=120) as r:
            r.read()
    call("PATCH", f"/appScreenshots/{shot['id']}", {"data": {
        "type": "appScreenshots", "id": shot["id"],
        "attributes": {"uploaded": True, "sourceFileChecksum": hashlib.md5(blob).hexdigest()},
    }})
    uploaded.append(shot["id"])
    print("Uploaded", os.path.basename(path))

call("PATCH", f"/appScreenshotSets/{shot_set['id']}/relationships/appScreenshots",
     {"data": [{"type": "appScreenshots", "id": i} for i in uploaded]})

# Wait for Apple to finish processing so failures show up in this build.
for _ in range(30):
    states = [s["attributes"].get("assetDeliveryState", {}).get("state")
              for s in call("GET", f"/appScreenshotSets/{shot_set['id']}/appScreenshots?limit=50")["data"]]
    print("Processing:", states)
    if all(s == "COMPLETE" for s in states):
        print(f"Done: {len(states)} screenshots are on the {version_string} draft.")
        break
    if any(s == "FAILED" for s in states):
        sys.exit("Apple rejected a screenshot; see states above.")
    time.sleep(10)
