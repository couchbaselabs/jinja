import re
import time
import datetime
import subprocess
import os
import requests
import hashlib
import json
from couchbase.bucket import Bucket
from constants import *

JOBS = {}
HOST = '127.0.0.1'

def getJS(url, params = None, retry = 5):
    print url
    res = None

    try:
        res = requests.get("%s/%s" % (url, "api/json"), params = params, timeout=15)
        data = res.json()
        return data
    except:
        print "[Error] url unreachable: %s" % url
        res = None
        if retry:
            retry = retry - 1
            return getJS(url, params, retry)
        else:
            pass

    return res

def getAction(actions, key, value = None):

    obj = None
    for a in actions:
        if a is None:
            continue
        keys = a.keys()
        if "urlName" in keys:
            if a["urlName"] != "testReport" and a["urlName"] != "tapTestReport":
                continue

        if key in keys:
            if value:
                if a["name"] == value:
                    obj = a["value"]
                    break
            else:
                obj = a[key]
                break

    return obj


def storeBuild(url):
    view = BUILD_VIEW
    client = Bucket(HOST+'/server')

    job = getJS(url)
    if not job:
        print "No job info for build"
        return
    result = job.get("result")
    if not result:
        return

    actions = job["actions"]
    totalCount = getAction(actions, "totalCount") or 0
    failCount  = getAction(actions, "failCount") or 0
    skipCount  = getAction(actions, "skipCount") or 0

    if totalCount == 0:
        return

    params = getAction(actions, "parameters")
    os = getAction(params, "name", "DISTRO") or job["fullDisplayName"].split()[2].split(",")[0]
    version = getAction(params, "name", "VERSION")
    build = getAction(params, "name", "CURRENT_BUILD_NUMBER") or getAction(params, "name", "BLD_NUM")

    if not (version or build):
        return

    build = version+"-"+build.zfill(4)

    name=os+"_watson-unix"
    if getAction(params, "name", "UNIT_TEST"):
        name += "_unit"

    os, comp = getOsComponent(name, view)
    if not os or not comp:
        return


    duration = int(job["duration"]) or 0

    # lookup pass count fail count version
    doc = {
      "build_id": int(job["id"]),
      "claim": "",
      "name": name,
      "url": url,
      "component": comp,
      "failCount": failCount,
      "totalCount": totalCount,
      "result": result,
      "duration": duration,
      "priority": "P0",
      "os": os,
      "build": build
    }

    key = "%s-%s" % (doc["name"], doc["build_id"])
    print key+","+build
    key = hashlib.md5(key).hexdigest()
    try:
        if version == "4.1.0":
            # not tracking, remove and ignore
            client.remove(key)
        else:
            client.upsert(key, doc)
    except Exception as ex:
        print "set failed, couchbase down?: %s %s"  % (HOST, ex)

def getOsComponent(name, view):
    _os = _comp = None

    PLATFORMS = view["platforms"]
    FEATURES = view["features"]

    for os in PLATFORMS:
        if os in name.upper():
            _os = os

    if _os is None:

        # attempt partial name lookup
        for os in PLATFORMS:
            if os[:3] == name.upper()[:3]:
                _os = os

    if _os is None and view["bucket"] != "mobile":
        # attempt initial name lookup
        for os in PLATFORMS:
            if os[:1] == name.upper()[:1]:
                _os = os

    if _os is None:
        print "%s: job name has unrecognized os: %s" %  (view["bucket"], name)

    for comp in FEATURES:
        tag, _c = comp.split("-")
        docname = name.upper()
        docname = docname.replace("-","_")
        if tag in docname:
            _comp = _c
            break

    if _comp is None:
        print "%s: job name has unrecognized component: %s" %  (view["bucket"], name)

    return _os, _comp


if __name__ == "__main__":
    urls = ["http://server.jenkins.couchbase.com/job/watson-toy/213",
            "http://server.jenkins.couchbase.com/job/watson-toy/212",
            "http://server.jenkins.couchbase.com/job/watson-toy/215",
            "http://server.jenkins.couchbase.com/job/watson-toy/208",
            "http://server.jenkins.couchbase.com/job/watson-toy/214",
            "http://server.jenkins.couchbase.com/job/watson-toy/216",
            "http://server.jenkins.couchbase.com/job/watson-toy/211",
            "http://server.jenkins.couchbase.com/job/watson-toy/218",
            "http://server.jenkins.couchbase.com/job/watson-toy/227",
            "http://server.jenkins.couchbase.com/job/watson-toy/222",
            "http://server.jenkins.couchbase.com/job/watson-toy/225",
            "http://server.jenkins.couchbase.com/job/watson-toy/219",
            "http://server.jenkins.couchbase.com/job/watson-toy/226",
            "http://server.jenkins.couchbase.com/job/watson-toy/220"]

    for url in urls:
        storeBuild(url) 
