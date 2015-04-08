import re
import time
import datetime
import subprocess
import os
import requests
import hashlib
import json
from mc_bin_client import MemcachedClient as McdClient
from constants import *

HOST = "127.0.0.1"
PORT = 11210 
if os.environ.get('MC_PORT'):
    PORT = int(os.environ.get('MC_PORT'))

def getJS(url, params = None):
    res = None
    try:
        res = requests.get("%s/%s" % (url, "api/json"), params = params, timeout=3)
    except:
        print "[Error] url unreachable: %s" % url
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

def storeJob(jobDoc, bucket, first_pass = True):

    client = McdClient(HOST, PORT)
    client.sasl_auth_plain(bucket, "")

    doc = jobDoc
    url = doc["url"]
    res = getJS(url, {"depth" : 0}).json()

    if res is None:
        return

    buildHist = {}
    if res["lastBuild"]:

        bids = [b["number"] for b in res["builds"]]
        if first_pass:
            bids.reverse() # reverse bid order from oldest to newest

        lastTotalCount = -1
        for bid in bids:
            if bid in JOBS[doc["name"]]:
                continue # job already stored
            else:
                if first_pass == False:
                    JOBS[doc["name"]].append(bid)

            doc["build_id"] = bid
            res = getJS(url+str(bid), {"depth" : 0}).json()
            if res is None:
                return

            if "result" not in res:
                continue

            doc["result"] = res["result"]


            if bucket == "server":
                if res["result"] not in ["SUCCESS", "UNSTABLE", "FAILURE", "ABORTED"]:
                    continue # unknown result state

                actions = res["actions"]
                totalCount = getAction(actions, "totalCount") or 0
                failCount  = getAction(actions, "failCount") or 0
                skipCount  = getAction(actions, "skipCount") or 0
                if totalCount == 0:
                    if lastTotalCount == -1:
                        continue # no tests ever passed for this build
                    else:
                        totalCount = lastTotalCount
                        failCount = totalCount
                else:
                    lastTotalCount = totalCount

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
                try:
                    _build= doc["build"].split("-")
                    rel, bno = _build[0], _build[1]
                    # check partial rel #'s
                    rlen = len(rel.split("."))
                    while rlen < 3:
                        rel = rel+".0"
                        rlen+=1

                    # verify rel, build
                    m=re.match("^\d\.\d\.\d{1,5}", rel)
                    if m is None:
                        print "unsupported version_number: "+doc["build"]
                        continue
                    m=re.match("^\d{1,10}", bno)
                    if m is None:
                        print "unsupported version_number: "+doc["build"]
                        continue

                    doc["build"] = "%s-%s" % (rel, bno.zfill(4))
                except:
                    print "unsupported version_number: "+doc["build"]
                    continue

            else:
                # use date as version for sdk and mobile
                if res["result"] not in ["SUCCESS", "UNSTABLE", "FAILURE", "ABORTED"]:
                    continue 

                actions = res["actions"]
                totalCount = getAction(actions, "totalCount") or 0
                failCount  = getAction(actions, "failCount") or 0
                skipCount  = getAction(actions, "skipCount") or 0
                if totalCount == 0:
                    if lastTotalCount == -1:
                        continue # no tests ever passed for this build
                    else:
                        totalCount = lastTotalCount
                        failCount = totalCount
                else:
                    lastTotalCount = totalCount

                doc["failCount"] = failCount
                doc["totalCount"] = totalCount - skipCount
                doc["priority"] =  P0

                now = datetime.datetime.now()
                doc["build"] = "%s-%d%d%d" % (MOBILE_VERSION, now.year, now.month, now.day)

            if doc["build"] in buildHist:

                #print "REJECTED- doc already in build results: %s" % doc
                #print buildHist

                # attempt to delete if this record has been stored in couchbase
                try:
                    oldKey = "%s-%s" % (doc["name"], doc["build_id"])
                    oldKey = hashlib.md5(oldKey).hexdigest()
                    client.delete(oldKey, vbucket = 0)
                    #print "DELETED- %s:%s" % (doc["build"],doc["build_id"])
                except:
                    pass

                continue # already have this build results


            key = "%s-%s" % (doc["name"], doc["build_id"])
            key = hashlib.md5(key).hexdigest()
            val = json.dumps(doc)
            try:
                #print val
                client.set(key, 0, 0, val, 0)
                buildHist[doc["build"]] = doc["build_id"]
            except:
                print "set failed, couchbase down?: %s:%s"  % (HOST,PORT)

    if first_pass:
        storeJob(jobDoc, bucket, first_pass = False)

def poll(view):

    PLATFORMS = view["platforms"]
    FEATURES = view["features"]

    for url in view["urls"]:
        res = getJS(url, {"depth" : 0, "tree" : "jobs[name,url]"})
        if res is None:
            continue

        j = res.json()

        for job in j["jobs"]:
            doc = {}
            doc["name"] = job["name"]

            if job["name"] in JOBS:
                # already processed
                continue

            for os in PLATFORMS:
                if os in doc["name"].upper():
                    doc["os"] = os

            if "os" not in doc:

                # attempt partial name lookup
                for os in PLATFORMS:
                    if os[:3] == doc["name"].upper()[:3]:
                        doc["os"] = os

            if "os" not in doc:
                # attempt initial name lookup
                for os in PLATFORMS:
                    if os[:1] == doc["name"].upper()[:1]:
                        doc["os"] = os

            if "os" not in doc:
                print "%s: job name has unrecognized os: %s" %  (view["bucket"], doc["name"])
                continue

            for comp in FEATURES:
                tag, _c = comp.split("-")
                docname = doc["name"].upper()
                docname = docname.replace("-","_")
                if tag in docname:
                    doc["component"] = _c
                    break

            if "component" not in doc:
                print "%s: job name has unrecognized component: %s" %  (view["bucket"], doc["name"])
                continue


            JOBS[job["name"]] = []
            doc["url"] = job["url"]

            try:
                storeJob(doc, view["bucket"])
            except:
                pass

if __name__ == "__main__":
    for view in VIEWS:
        poll(view)
