import requests
import hashlib
import json
from mc_bin_client import MemcachedClient as McdClient

JENKINS = "http://qa.sc.couchbase.com"
OS_TYPES = ["UBUNTU","CENTOS","DEBIAN","WIN","OSX","MAC"]
COMPONENTS = ["VIEW", "QUERY", "REB", "XDCR","TUQ","RZA", "FAILOVER","CLI","DCP"]
DEFAULT_BUILD = "0.0.0-xxxx"
EXCLUDED = []

P0 = "P0"
P1 = "P1"
P2 = "P2"
JOBS = {}
HOST="127.0.0.1"
PORT=11210
client = McdClient(HOST, PORT)
client.sasl_auth_plain("jenkins", "")

def getJS(url, params = None):
    res = requests.get("%s/%s" % (url, "api/json"), params = params)
    assert res.status_code == 200, res.reason
    return res

def getAction(actions, key, value = None):

    obj = None

    for a in actions:
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


                doc["build"] = doc["build"].replace("-rel","")

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
                    client.set(key, 0, 0, val)
                except:
                    print "set failed, couchbase down?: %s:%s"  % (HOST,PORT)

def poll():

    res = getJS(JENKINS, {"depth" : 0, "tree" : "jobs[name,url]"})
    j = res.json()
    for job in j["jobs"]:
        doc = {}
        doc["name"] = job["name"]
        if job["name"] in EXCLUDED:
           continue

        if job["name"] not in JOBS:
            JOBS[job["name"]] = []

        for os in OS_TYPES:
            if os in doc["name"].upper():
                doc["os"] = os
                break

        if "os" not in doc:
            print "job name has unrecognized os: %s" %  doc["name"]
            EXCLUDED.append(doc["name"])
            continue

        for comp in COMPONENTS:
            if comp in doc["name"].upper():
                doc["component"] = comp
                break

        if "component" not in doc:
            print "job name has unrecognized component: %s" %  doc["name"]
            EXCLUDED.append(doc["name"])
            continue

        doc["url"] = job["url"]
        storeJob(doc)

if __name__ == "__main__":
    while True:
        poll()
