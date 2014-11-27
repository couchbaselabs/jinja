import time
import subprocess
import os
import requests
import hashlib
import json
from mc_bin_client import MemcachedClient as McdClient
from constants import *

HOST = "127.0.0.1"
PORT = 11210

def getJS(url, params = None):
    res = requests.get("%s/%s" % (url, "api/json"), params = params)
    assert res.status_code == 200, res.reason
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

def storeJob(doc):

    bucket = "server"
    client = McdClient(HOST, PORT)
    if "mobile" in doc["name"]:
        bucket = "mobile"
    client.sasl_auth_plain(bucket, "")

    url = doc["url"]
    res = getJS(url, {"depth" : 0}).json()
    buildHist = {}
    if res["lastBuild"]:

        bids = [b["number"] for b in res["builds"]]
        for bid in bids:
            if bid in JOBS[doc["name"]]:
                continue # job already stored
            else:
                JOBS[doc["name"]].append(bid)

            doc["build_id"] = bid
            res = getJS(url+str(bid), {"depth" : 0}).json()
            doc["result"] = res["result"]

            if res["result"] not in ["SUCCESS", "UNSTABLE"]:
                continue # invalid build

            actions = res["actions"]
            totalCount = getAction(actions, "totalCount") or 0
            if totalCount > 0:
                failCount  = getAction(actions, "failCount") or 0
                skipCount  = getAction(actions, "skipCount") or 0
                doc["failCount"] = failCount
                doc["totalCount"] = totalCount - skipCount

                params = getAction(actions, "parameters")
                if params is None:
                    doc["priority"] = P1
                    doc["build"] = DEFAULT_BUILD
                else:
                    doc["build"] = getAction(params, "name", "version_number") or DEFAULT_BUILD
                    doc["priority"] = getAction(params, "name", "priority") or P1
                    if doc["priority"].upper() not in [P0, P1, P2]:
                        doc["priority"] = P1


                doc["build"] = doc["build"].replace("-rel","").split(",")[0]

                if doc["os"] in ["ANDROID", "IOS"]:
                    ts =  res["timestamp"]/1000;
                    _os = doc["os"].lower()

                    #todo get branch latest
                    cmd = "cd couchbase-lite-%s && git describe --tags `git log --until %s --max-count=1 | grep commit | awk '{print $2}'`" % (_os, ts)
                    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    build = p.stdout.readlines()[0]
                    doc["build"] = build

                try:
                    _build= doc["build"].split("-")
                    rel, bno = _build[0], _build[1]
                    doc["build"] = "%s-%s" % (rel, bno.zfill(4))
                except:
                    print "unsupported version_number: "+doc["build"]
                    continue


                if doc["build"] in buildHist:
                    print "REJECTED- doc already in build results: %s" % doc
                    print buildHist

                    # attempt to delete if this record has been stored in couchbase
                    try:
                        oldKey = "%s-%s" % (doc["name"], doc["build_id"])
                        oldKey = hashlib.md5(oldKey).hexdigest()
                        client.delete(oldKey, vbucket = 0)
                        print "DELETED- %s:%s" % (doc["build"],doc["build_id"])
                    except:
                        pass

                    continue # already have this build results


                key = "%s-%s" % (doc["name"], doc["build_id"])
                key = hashlib.md5(key).hexdigest()
                val = json.dumps(doc)
                try:
                    print val
                    client.set(key, 0, 0, val, 0)
                    buildHist[doc["build"]] = doc["build_id"]
                except:
                    print "set failed, couchbase down?: %s:%s"  % (HOST,PORT)


def poll():

    for JENKINS in JENKINS_URLS:
        res = getJS(JENKINS, {"depth" : 0, "tree" : "jobs[name,url]"})
        j = res.json()

        for job in j["jobs"]:
            doc = {}
            doc["name"] = job["name"]

            if job["name"] not in JOBS:
                JOBS[job["name"]] = []

            for os in PLATFORMS:
                if os in doc["name"].upper():
                    doc["os"] = os

            if "os" not in doc:
                print "job name has unrecognized os: %s" %  doc["name"]
                doc["os"] = "NA"

            for comp in FEATURES:
                tag, _c = comp.split("-")
                if tag in doc["name"].upper():
                    doc["component"] = _c
                    break

            if "component" not in doc:
                print "job name has unrecognized component: %s" %  doc["name"]
                doc["component"] = "MISC"

            doc["url"] = job["url"]

            try:
                storeJob(doc)
            except:
                pass

def cloneRepos():
    os.system("rm -rf couchbase-lite-ios")
    os.system("git clone https://github.com/couchbase/couchbase-lite-ios")
    os.system("rm -rf couchbase-lite-android")
    os.system("git clone https://github.com/couchbase/couchbase-lite-android")


if __name__ == "__main__":
    while True:
        cloneRepos()
        poll()
        time.sleep(30)
