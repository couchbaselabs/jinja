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

HOST =  "127.0.0.1"
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

def getBuildAndPriority(params, isMobile = False):
    build = None
    priority = DEFAULT_BUILD

    if params:
        if not isMobile:
            build = getAction(params, "name", "version_number") or getAction(params, "name", "cluster_version") or  getAction(params, "name", "build") or DEFAULT_BUILD
        else:
            build = getAction(params, "name", "COUCHBASE_MOBILE_VERSION") or getAction(params, "name", "CBL_iOS_Build")

        priority = getAction(params, "name", "priority") or P1
        if priority.upper() not in [P0, P1, P2]:
            priority = P1

    build = build.replace("-rel","").split(",")[0]
    try:
        _build = build.split("-")
        rel, bno = _build[0], _build[1]
        # check partial rel #'s
        rlen = len(rel.split("."))
        while rlen < 3:
            rel = rel+".0"
            rlen+=1

        # verify rel, build
        m=re.match("^\d\.\d\.\d{1,5}", rel)
        if m is None:
            print "unsupported version_number: "+build
            return None, None
        m=re.match("^\d{1,10}", bno)
        if m is None:
            print "unsupported version_number: "+build
            return None, None

        build = "%s-%s" % (rel, bno.zfill(4))
    except:
        print "unsupported version_number: "+doc["build"]
        return None, None

    return build, priority

def getClaimReason(actions):
    reason = ""

    if not getAction(actions, "claimed"):
        return reason # job not claimed

    reason = getAction(actions, "reason") or ""
    try:
        rep_dict={m:"<a href=\"https://issues.couchbase.com/browse/{0}\">{1}</a>".
            format(m,m) for m in re.findall(r"([A-Z]{2,4}[-: ]*\d{4,5})", reason)}
        if rep_dict:
            pattern = re.compile('|'.join(rep_dict.keys()))
            reason = pattern.sub(lambda x: rep_dict[x.group()],reason)
    except Exception as e:
        pass

    return reason

def storeJob(jobDoc, view, first_pass = True, lastTotalCount = -1):

    bucket = view["bucket"]

    client = Bucket('couchbase://localhost/'+bucket)

    doc = jobDoc
    url = doc["url"]

    res = getJS(url, {"depth" : 0}).json()

    if res is None:
        return

    # operate as 2nd pass if test_executor
    if jobDoc["name"] == "test_suite_executor":
        first_pass = False

    buildHist = {}
    if res["lastBuild"]:

        bids = [b["number"] for b in res["builds"]]

        if first_pass:
            bids.reverse()  # bottom to top 1st pass

        for bid in bids:

            oldName = JOBS.get(doc["name"])
            if oldName and bid in JOBS[doc["name"]]:
                continue # job already stored
            else:
                if oldName and first_pass == False:
                    JOBS[doc["name"]].append(bid)

            doc["build_id"] = bid
            res = getJS(url+str(bid), {"depth" : 0}).json()
            if res is None:
                return

            if "result" not in res:
                continue

            doc["result"] = res["result"]
            doc["duration"] = res["duration"]

            if res["result"] not in ["SUCCESS", "UNSTABLE", "FAILURE", "ABORTED"]:
                continue # unknown result state

            actions = res["actions"]
            totalCount = getAction(actions, "totalCount") or 0
            failCount  = getAction(actions, "failCount") or 0
            skipCount  = getAction(actions, "skipCount") or 0
            doc["claim"] = getClaimReason(actions)
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
            componentParam = getAction(params, "name", "component")
            if componentParam:
                componentParam = getAction(params, "name", "component")
                subComponentParam = getAction(params, "name", "subcomponent")
                osParam = getAction(params, "name", "OS") or getAction(params, "name", "os")
                if not componentParam or not subComponentParam or not osParam:
                    continue

                pseudoName = str(osParam+"-"+componentParam+"_"+subComponentParam)
                _os, _comp = getOsComponent(pseudoName, view)
                if not _os or not _comp:
                    continue # unkown os or comp
                doc["os"] = _os
                doc["component"] = _comp
                doc["name"] = pseudoName

            if bucket == "server":
                doc["build"], doc["priority"] = getBuildAndPriority(params)
            else:
                doc["build"], doc["priority"] = getBuildAndPriority(params, True)

            if not doc.get("build"):
                continue

            histKey = doc["name"]+"-"+doc["build"]
            if not first_pass and histKey in buildHist:

                #print "REJECTED- doc already in build results: %s" % doc
                #print buildHist

                # attempt to delete if this record has been stored in couchbase

                try:
                    oldKey = "%s-%s" % (doc["name"], doc["build_id"])
                    oldKey = hashlib.md5(oldKey).hexdigest()
                    client.remove(oldKey)
                    #print "DELETED- %d:%s" % (bid, histKey)
                except:
                    pass

                continue # already have this build results


            key = "%s-%s" % (doc["name"], doc["build_id"])
            key = hashlib.md5(key).hexdigest()

            try:
                client.upsert(key, doc)
                buildHist[histKey] = doc["build_id"]
            except:
                print "set failed, couchbase down?: %s:%s"  % (HOST,PORT)


    if first_pass:
        storeJob(jobDoc, view, first_pass = False, lastTotalCount = lastTotalCount)

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

def poll(view):

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

            os, comp = getOsComponent(doc["name"], view)
            if not os or not comp:
                if job["name"] != "test_suite_executor":
                    continue

            JOBS[job["name"]] = []
            doc["os"] = os
            doc["component"] = comp
            doc["url"] = job["url"]

            try:
                storeJob(doc, view)
            except:
                pass

if __name__ == "__main__":
    for view in VIEWS:
        JOBS = {}
        poll(view)
