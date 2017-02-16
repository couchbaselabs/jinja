import re
import sys
import time
import datetime
import subprocess
import os
import requests
import hashlib
import json
from threading import Thread
from couchbase.bucket import Bucket
from constants import *
from urlparse import urlparse

UBER_USER = os.environ.get('UBER_USER') or ""
UBER_PASS = os.environ.get('UBER_PASS') or ""


JOBS = {}
HOST = '127.0.0.1'
if len(sys.argv) == 2:
    HOST = sys.argv[1]

def getJS(url, params = None, retry = 5, append_api_json=True):
    print url
    res = None
    try:
        if append_api_json:
            res = requests.get("%s/%s" % (url, "api/json"), params = params, timeout=15)
        else:
            res = requests.get("%s" % url, params=params, timeout=15)
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

    if actions is None:
        return None
 
    obj = None
    keys = []
    for a in actions:
        if a is None:
            continue
        if 'keys' in dir(a):
            keys = a.keys()
        else:
            # check if new api
            if 'keys' in dir(a[0]):
                keys = a[0].keys() 
        if "urlName" in keys:
            if a["urlName"]!= "robot" and a["urlName"] != "testReport" and a["urlName"] != "tapTestReport":
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
            build = getAction(params, "name", "version_number") or getAction(params, "name", "cluster_version") or  getAction(params, "name", "build") or  getAction(params, "name", "COUCHBASE_SERVER_VERSION") or DEFAULT_BUILD
        else:
            build = getAction(params, "name", "SYNC_GATEWAY_VERSION") or getAction(params, "name", "COUCHBASE_MOBILE_VERSION") or getAction(params, "name", "CBL_iOS_Build")

        priority = getAction(params, "name", "priority") or P1
        if priority.upper() not in [P0, P1, P2]:
            priority = P1

    if build is None:
        return None, None

    build = build.replace("-rel","").split(",")[0]
    try:
        _build = build.split("-")
        if len(_build) == 1:
            raise Exception("Invalid Build number: {} Should follow 1.1.1-0000 naming".format(_build))

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
        print "unsupported version_number: " + build
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

# use case# redifine 'xdcr' as 'goxdcr' 4.0.1+
def caveat_swap_xdcr(doc):
    comp = doc["component"]
    if (doc["build"] >= "4.0.1") and (comp == "XDCR"):
        comp = "GOXDCR"
    return comp

# when build > 4.1.0 and os is WIN skip VIEW, TUNEABLE, 2I, NSERV, VIEW, EP
def caveat_should_skip_win(doc):
    skip = False
    os = doc["os"]
    comp = doc["component"]
    build = doc["build"]
    if build >= "4.1.0" and os  == "WIN" and\
        (comp == "VIEW" or comp=="TUNABLE" or comp =="2I" or\
         comp == "NSERV" or comp=="VIEW" or comp=="EP"):
        if doc["name"].lower().find("w01") == 0:
            skip = True
    return skip

# when build == 4.1.0 version then skip backup_recovery
def caveat_should_skip_backup_recovery(doc):
   skip = False
   if (doc["build"].find("4.1.0") == 0) and\
      (doc["component"] == "BACKUP_RECOVERY"):
       skip = True
   return skip

def caveat_should_skip(doc):
   return caveat_should_skip_win(doc) or\
          caveat_should_skip_backup_recovery(doc)

def isExecutor(name):
    return name.find("test_suite_executor") > -1

def skipCollect(params):
    skip_collect_u = getAction(params, "name", "SKIP_GREENBOARD_COLLECT")
    skip_collect_l = getAction(params, "name", "skip_greenboard_collect")
    return skip_collect_u or skip_collect_l

def isDisabled(job):
    status = job.get("color")
    return  status and (status == "disabled")

def purgeDisabled(job, bucket):
    client = Bucket(HOST+'/'+bucket)
    name = job["name"]
    bids = [b["number"] for b in job["builds"]]
    high_bid = bids[0]
    for bid in xrange(high_bid):
        # reconstruct doc id
        bid = bid + 1
        oldKey = "%s-%s" % (name, bid)
        oldKey = hashlib.md5(oldKey).hexdigest()
        # purge
        try:
            client.remove(oldKey)
        except Exception as ex:
            print "[WARN] did not find disabled job to delete: [%s-%s]" % (name,bid)
            pass # delete ok

def storeTest(jobDoc, view, first_pass = True, lastTotalCount = -1, claimedBuilds = None):

    bucket = view["bucket"]

    claimedBuilds = claimedBuilds or {}
    client = Bucket(HOST+'/'+bucket)

    doc = jobDoc
    url = doc["url"]

    if url.find("sdkbuilds.couchbase") > -1:
        url = url.replace("sdkbuilds.couchbase", "sdkbuilds.sc.couchbase")

    res = getJS(url, {"depth" : 0})

    if res is None:
        return

    # do not process disabled jobs
    if isDisabled(doc):
        purgeDisabled(res, bucket)
        return

    # operate as 2nd pass if test_executor
    if isExecutor(doc["name"]):
        first_pass = False

    buildHist = {}
    if res.get("lastBuild") is not None:

        bids = [b["number"] for b in res["builds"]]

        if first_pass:
            bids.reverse()  # bottom to top 1st pass

        for bid in bids:

            oldName = JOBS.get(doc["name"]) is not None
            if oldName and bid in JOBS[doc["name"]]:
                continue # job already stored
            else:
                if oldName and first_pass == False:
                    JOBS[doc["name"]].append(bid)

            doc["build_id"] = bid
            res = getJS(url+str(bid), {"depth" : 0})
            if res is None:
                return

            if "result" not in res:
                continue

            doc["result"] = res["result"]
            doc["duration"] = res["duration"]

            if res["result"] not in ["SUCCESS", "UNSTABLE", "FAILURE", "ABORTED"]:
                continue # unknown result state

            actions = res["actions"]
            params = getAction(actions, "parameters")
            if skipCollect(params):
                job = getJS(url, {"depth" : 0})
                purgeDisabled(job, bucket)
                return

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
            if params is None:
               # possibly new api
               if not 'keys' in dir(actions) and len(actions) > 0:
                   # actions is not a dict and has data
                   # then use the first object that is a list
                   for a in actions:
                      if not 'keys' in dir(a):
                          params = a

            componentParam = getAction(params, "name", "component")
            if componentParam is None:
                testYml = getAction(params, "name", "test")
                if testYml and testYml.find(".yml"):
                    testFile = testYml.split(" ")[1]
                    componentParam = "systest-"+str(os.path.split(testFile)[-1]).replace(".yml","")

            if componentParam:
                subComponentParam = getAction(params, "name", "subcomponent")
                if subComponentParam is None:
                    subComponentParam = "server"
                osParam = getAction(params, "name", "OS") or getAction(params, "name", "os")
                if osParam is None:
                    osParam = doc["os"]
                if not componentParam or not subComponentParam or not osParam:
                    continue

                pseudoName = str(osParam+"-"+componentParam+"_"+subComponentParam)
                doc["name"] = pseudoName
                _os, _comp = getOsComponent(pseudoName, view)
                if _os and  _comp:
                   doc["os"] = _os
                   doc["component"] = _comp
                if not doc.get("os") or not doc.get("component"):
                   continue


            if bucket == "server":
                doc["build"], doc["priority"] = getBuildAndPriority(params)
            else:
                doc["build"], doc["priority"] = getBuildAndPriority(params, True)

            if not doc.get("build"):
                continue

            # run special caveats on collector
            doc["component"] = caveat_swap_xdcr(doc)
            if caveat_should_skip(doc):
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

            try: # get custom claim if exists
                oldDoc = client.get(key)
                customClaim =  oldDoc.value.get('customClaim')
                if customClaim:
                    claimedBuilds[doc["build"]] = customClaim
            except:
                pass #ok, this is new doc 

            if doc["build"] in claimedBuilds: # apply custom claim
                doc['customClaim'] = claimedBuilds[doc["build"]] 

            try:
                client.upsert(key, doc)
                buildHist[histKey] = doc["build_id"]
            except:
                print "set failed, couchbase down?: %s"  % (HOST)


    if first_pass:
        storeTest(jobDoc, view, first_pass = False, lastTotalCount = lastTotalCount, claimedBuilds = claimedBuilds)


def storeBuild(client, run, name, view):
    job = getJS(run["url"], {"depth" : 0})
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

    name=os+"_"+name
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
      "url": run["url"],
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

def pollBuild(view):

    client = Bucket(HOST+'/server') # using server bucket (for now)

    tJobs = [] 

    for url in view["urls"]:

        j = getJS(url, {"depth" : 0})
        if j is None:
            continue

        name = j["name"]
        for job in j["builds"]:
            build_url = job["url"]

            j = getJS(build_url, {"depth" : 0, "tree":"runs[url,number]"})
            if j is None:
                continue

            try:
                t = None
                if not j:
                    # single run job
                    t = Thread(target=storeBuild, args=(client, job, name, view))
                else:
                    # each run is a result
                    for doc in j["runs"]:
                        t = Thread(target=storeBuild, args=(client, doc, name, view))
                t.start()
	        tJobs.append(t) 
            except Exception as ex:
                print ex
                pass
    return tJobs

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

def pollTest(view):

    tJobs = [] 
    
    for url in view["urls"]:

        j = getJS(url, {"depth" : 0, "tree" :"jobs[name,url,color]"})
        if j is None or j.get('jobs') is None:
            continue

        for job in j["jobs"]:
            doc = {}
            doc["name"] = job["name"]
            if job["name"] in JOBS:
                # already processed
                continue

            os, comp = getOsComponent(doc["name"], view)
            if not os or not comp:
                if not isExecutor(job["name"]):
                    # does not match os or comp and is not executor
                    continue

            JOBS[job["name"]] = []
            doc["os"] = os
            doc["component"] = comp
            doc["url"] = job["url"]
            doc["color"] = job.get("color")

            name = doc["name"]
            t = Thread(target=storeTest, args=(doc, view))
            t.start()
            tJobs.append(t)

            if len(tJobs) > 10:
                # intermediate join
                for t in tJobs:
                    t.join()
                tJobs = []

        for t in tJobs:
            t.join()


def collectBuildInfo(url):

        client = Bucket(HOST+'/server')
        res = getJS(url, {"depth" : 1, "tree" :"builds[number,url]"})
        if res is None:
            return

        builds = res['builds']
        for b in builds:
            url = b["url"]
            job = getJS(url)
            if job is not None:
                actions = job["actions"]
                params = getAction(actions, "parameters")
                version = getAction(params, "name", "VERSION")
                build_no = job["displayName"].replace(version+"-","").split("-")[0]
                key = version+"-"+build_no.zfill(4)
                try:
                    if float(version[:2]) > 4.6:
                        changeset_url = CHANGE_LOG_URL+"?ver={0}&from={1}&to={2}".\
                            format(version, str(int(build_no[1:])-1), build_no[1:])
                        job = getJS(changeset_url, append_api_json=False)
                    print key
                    client.upsert(key, job)
                except:
                    print "set failed, couchbase down?: %s"  % (HOST)

def collectAllBuildInfo():
    while True:
       time.sleep(120)
       try:
           for url in BUILDER_URLS:
               collectBuildInfo(url)
       except Exception as ex:
           print "exception occurred during build collection: %s" % (ex)


if __name__ == "__main__":

    # run build collect info thread
    tBuild = Thread(target=collectAllBuildInfo)
    tBuild.start()

    while True:
        # keep list of all threads
        try:
            for view in VIEWS:
                JOBS = {}
                if view["bucket"] == "build":
                    pollBuild(view)
                else:
                    pollTest(view)
        except Exception as ex:
            print "exception occurred during job collection: %s" % (ex)
        time.sleep(120)
