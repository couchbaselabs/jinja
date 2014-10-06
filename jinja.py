import time
import requests
import hashlib
import json
from mc_bin_client import MemcachedClient as McdClient
from constants import *

HOST = "127.0.0.1"
PORT = 11210
client = McdClient(HOST, PORT)
client.sasl_auth_plain("jenkins", "")

def getJS(url, params = None):
    res = requests.get("%s/%s" % (url, "api/json"), params = params)
    assert res.status_code == 200, res.reason
    return res

def getAction(actions, key, value = None):

    obj = None

    for a in actions:
        if a is None:
            continue
        if key in a.keys():
            if value:
                if a["name"] == value:
                    obj = a["value"]
                    break
            else:
                obj = a[key]
                break

    return obj

def storeJob(doc):

    url = doc["url"]
    res = getJS(url, {"depth" : 0}).json()
    lastBuild = None
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
                unset = "0.0.0-xxx"
                if params is None:
                    doc["priority"] = P1
                    doc["build"] = DEFAULT_BUILD
                else:
                    doc["build"] = getAction(params, "name", "version_number") or DEFAULT_BUILD
                    doc["priority"] = getAction(params, "name", "priority") or P1
                    if doc["priority"].upper() not in [P0, P1, P2]:
                        doc["priority"] = P1


                doc["build"] = doc["build"].replace("-rel","").split(",")[0]

                print "%s v %s" % (doc["build"], lastBuild)

                if lastBuild == doc["build"]:
                    continue # already have results for this build
                else:
                    lastBuild = doc["build"]

                try:
                    rel, bno = doc["build"].split("-")
                    doc["build"] = "%s-%s" % (rel, bno.zfill(4))
                except:
                    print "unsupported version_number: "+doc["build"]
                    continue

                key = "%s-%s" % (doc["name"], doc["build_id"])
                key = hashlib.md5(key).hexdigest()
                val = json.dumps(doc)
                try:
                    print val
                    client.set(key, 0, 0, val, 0)
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

            for os in OS_TYPES:
                if os in doc["name"].upper():
                    doc["os"] = os

            if "os" not in doc:
                print "job name has unrecognized os: %s" %  doc["name"]
                doc["os"] = "NA"

            for comp in COMPONENTS:
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

if __name__ == "__main__":
    poll()
