import re
import sys
import time
import os
import requests
import hashlib
import copy
import json
import datetime
from optparse import OptionParser

from threading import Thread

from couchbase.bucket import Bucket, AuthError, N1QLQuery
from couchbase.cluster import Cluster, PasswordAuthenticator

from constants import *

UBER_USER = os.environ.get('UBER_USER') or ""
UBER_PASS = os.environ.get('UBER_PASS') or ""

DEBUG_MODE = True

JOBS = {}
#HOST = '172.23.98.63'
HOST = '127.0.0.1'

MAX_INSTALL_RETRIES_NUM = 3
MAX_TESTS_RUN_RETRIES_NUM = 5

if len(sys.argv) == 2:
    HOST = sys.argv[1]


def getJS(url, params=None, retry=5, append_api_json=True):
    res = None
    try:
        if append_api_json:
            res = requests.get("%s/%s" % (url, "api/json"), params=params, timeout=15)
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

def getURL(url, params=None, retry=5):
    res = None
    try:
        res = requests.get("%s" % url, params=params, timeout=15)
        return res.content
    except:
        print "[Error] url unreachable: %s" % url
        res = None
        if retry:
            retry = retry - 1
            return getURL(url, params, retry)
        else:
            pass

    return res


def getAction(actions, key, value=None):
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
            if a["urlName"] != "robot" and a["urlName"] != "testReport" and a["urlName"] != "tapTestReport":
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


def getBuildAndPriority(params, isMobile=False):
    build = None
    priority = DEFAULT_BUILD
    if params:
        if not isMobile:
            build = getAction(params, "name", "version_number") or \
                    getAction(params, "name","cluster_version") or \
                    getAction(params,"name","build") or \
                    getAction(params, "name", "COUCHBASE_SERVER_VERSION") or \
                    DEFAULT_BUILD
        else:
            build = getAction(params, "name", "SYNC_GATEWAY_VERSION") or \
                    getAction(params, "name","SYNC_GATEWAY_VERSION_OR_COMMIT") or \
                    getAction(params, "name", "COUCHBASE_MOBILE_VERSION") or \
                    getAction(params, "name", "CBL_iOS_Build")

        priority = getAction(params, "name", "priority") or P1
        if priority.upper() not in [P0, P1, P2]:
            priority = P1

    if build is None:
        return None, None

    build = build.replace("-rel", "").split(",")[0]
    try:
        _build = build.split("-")
        if len(_build) == 1:
            raise Exception("Invalid Build number: {} Should follow 1.1.1-0000 naming".format(_build))

        rel, bno = _build[0], _build[1]
        # check partial rel #'s
        rlen = len(rel.split("."))
        while rlen < 3:
            rel = rel + ".0"
            rlen += 1

        # verify rel, build
        m = re.match("^\d\.\d\.\d{1,5}", rel)
        if m is None:
            print "unsupported version_number: " + build
            return None, None
        m = re.match("^\d{1,10}", bno)
        if m is None:
            print "unsupported version_number: " + build
            return None, None

        build = "%s-%s" % (rel, bno.zfill(4))
    except:
        print "unsupported version_number: " + build
        return None, None

    return build, priority


def getClaimReason(actions):
    reason = ""

    if not getAction(actions, "claimed"):
        return reason  # job not claimed

    reason = getAction(actions, "reason") or ""
    try:
        rep_dict = {m: "<a href=\"https://issues.couchbase.com/browse/{0}\">{1}</a>".
            format(m, m) for m in re.findall(r"([A-Z]{2,4}[-: ]*\d{4,5})", reason)}
        if rep_dict:
            pattern = re.compile('|'.join(rep_dict.keys()))
            reason = pattern.sub(lambda x: rep_dict[x.group()], reason)
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
    if build >= "4.1.0" and os == "WIN" and \
            (comp == "VIEW" or comp == "TUNABLE" or comp == "2I" or \
             comp == "NSERV" or comp == "VIEW" or comp == "EP"):
        if doc["name"].lower().find("w01") == 0:
            skip = True
    return skip


# when build == 4.1.0 version then skip backup_recovery
def caveat_should_skip_backup_recovery(doc):
    skip = False
    if (doc["build"].find("4.1.0") == 0) and \
            (doc["component"] == "BACKUP_RECOVERY"):
        skip = True
    return skip


def caveat_should_skip(doc):
    return caveat_should_skip_win(doc) or \
           caveat_should_skip_backup_recovery(doc)


def caveat_should_skip_mobile(doc):
    # skip mobile component loading for non cen os
    return (doc["component"].find("MOBILE") > -1) and \
           (doc["os"].find("CEN") == -1)


def isExecutor(name):
    return name.find("test_suite_executor") > -1


def skipCollect(params):
    skip_collect_u = getAction(params, "name", "SKIP_GREENBOARD_COLLECT")
    skip_collect_l = getAction(params, "name", "skip_greenboard_collect")
    return skip_collect_u or skip_collect_l


def isDisabled(job):
    status = job.get("color")
    return status and (status == "disabled")


def purgeDisabled(job, bucket):
    client = newClient(bucket)
    name = job["name"]
    bids = [b["number"] for b in job["builds"]]
    if len(bids) == 0:
        return

    high_bid = bids[0]
    for bid in xrange(high_bid):
        # reconstruct doc id
        bid = bid + 1
        oldKey = "%s-%s" % (name, bid)
        if not DEBUG_MODE:
            oldKey = hashlib.md5(oldKey).hexdigest()
        # purge
        try:
            client.remove(oldKey)
        except Exception as ex:
            pass  # delete ok


def storeTest(jobDoc, view, first_pass=True, lastTotalCount=-1, claimedBuilds=None):
    bucket = view["bucket"]

    claimedBuilds = claimedBuilds or {}
    client = newClient(bucket)

    doc = copy.deepcopy(jobDoc)
    url = doc["url"]

    if url.find("sdkbuilds.couchbase") > -1:
        url = url.replace("sdkbuilds.couchbase", "sdkbuilds.sc.couchbase")

    res = getJS(url, {"depth": 0})

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

        if isExecutor(doc["name"]):
            # include more history
            start = bids[0] - 300
            if start > 0:
                bids = range(start, bids[0] + 1)
            bids.reverse()
        elif first_pass:
            bids.reverse()  # bottom to top 1st pass

        for bid in bids:
            doc = copy.deepcopy(jobDoc)
            oldName = JOBS.get(doc["name"]) is not None
            if oldName and bid in JOBS[doc["name"]]:
                continue  # job already stored
            else:
                if oldName and first_pass == False:
                    JOBS[doc["name"]].append(bid)

            doc["build_id"] = bid
            res = getJS(url + str(bid), {"depth": 0})
            if res is None:
                continue

            if "result" not in res:
                continue

            doc["result"] = res["result"]
            doc["duration"] = res["duration"]

            if res["result"] not in ["SUCCESS", "UNSTABLE", "FAILURE", "ABORTED"]:
                continue  # unknown result state

            actions = res["actions"]
            params = getAction(actions, "parameters")
            if skipCollect(params):
                job = getJS(url, {"depth": 0})
                purgeDisabled(job, bucket)
                return

            totalCount = getAction(actions, "totalCount") or 0
            failCount = getAction(actions, "failCount") or 0
            skipCount = getAction(actions, "skipCount") or 0
            doc["claim"] = getClaimReason(actions)
            if totalCount == 0:
                if lastTotalCount == -1:
                    continue  # no tests ever passed for this build
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
                    componentParam = "systest-" + str(os.path.split(testFile)[-1]).replace(".yml", "")

            if componentParam:
                subComponentParam = getAction(params, "name", "subcomponent")
                if subComponentParam is None:
                    subComponentParam = "server"
                osParam = getAction(params, "name", "OS") or getAction(params, "name", "os")
                if osParam is None:
                    osParam = doc["os"]
                if not componentParam or not subComponentParam or not osParam:
                    continue

                pseudoName = str(osParam + "-" + componentParam + "_" + subComponentParam)
                doc["name"] = pseudoName
                nameOrig = pseudoName
                _os, _comp = getOsComponent(pseudoName, view)
                if _os and _comp:
                    doc["os"] = _os
                    doc["component"] = _comp
                if not doc.get("os") or not doc.get("component"):
                    continue

            if bucket == "server":
                doc["build"], doc["priority"] = getBuildAndPriority(params)
            else:
                doc["build"], doc["priority"] = getBuildAndPriority(params, True)

            if doc["build"] is None and doc["priority"] is None and doc['os'] == "K8S":
                res = getJS(url + str(bid), {"depth": 0})
                if "description" in res:
                    params = res['description'].split(",")
                    try:
                        operator_version = params[0].split(":")[1]
                        op_major_version = operator_version.split("-")[0]

                        cb_version = params[1].split(":")[1]

                        if "-" not in cb_version:
                            cb_version = CB_RELEASE_BUILDS[cb_version[0:5]]
                        elif "enterprise" in cb_version:
                            cb_version = cb_version.split("-")[1][0:5] + "-" + CB_RELEASE_BUILDS[cb_version.split("-")[1][0:5]]

                        upgrade_version = params[2].split(":")[1]

                        if "-" not in upgrade_version:
                            upgrade_version = upgrade_version[0:5]
                        elif "enterprise" in upgrade_version:
                            upgrade_version = upgrade_version.split("-")[1][0:5]
                        else:
                            upgrade_version = upgrade_version.split("-")[0][0:5]

                        doc["build"] = cb_version
                        doc["priority"] = 'P0'
                        doc["name"] = doc["name"] + "-opver-" + op_major_version + "-upver-" + upgrade_version
                    except:
                        pass

            if not doc.get("build"):
                continue

            # run special caveats on collector
            doc["component"] = caveat_swap_xdcr(doc)
            if caveat_should_skip(doc):
                continue

            if caveat_should_skip_mobile(doc):
                continue

            histKey = doc["name"] + "-" + doc["build"]
            if not first_pass and histKey in buildHist:

                # print "REJECTED- doc already in build results: %s" % doc
                # print buildHist

                # attempt to delete if this record has been stored in couchbase

                try:
                    oldKey = "%s-%s" % (doc["name"], doc["build_id"])
                    if not DEBUG_MODE:
                        oldKey = hashlib.md5(oldKey).hexdigest()
                    client.remove(oldKey)
                    # print "DELETED- %d:%s" % (bid, histKey)
                except:
                    pass

                continue  # already have this build results

            key = "%s-%s" % (doc["name"], doc["build_id"])
            if not DEBUG_MODE:
                key = hashlib.md5(key).hexdigest()

            try:  # get custom claim if exists
                oldDoc = client.get(key)
                customClaim = oldDoc.value.get('customClaim')
            #  if customClaim is not None:
            #      doc["customClaim"] = customClaim
            except:
                pass  # ok, this is new doc

            try:
                client.upsert(key, doc)
                buildHist[histKey] = doc["build_id"]
            except:
                print "set failed, couchbase down?: %s" % (HOST)

            if doc.get("claimedBuilds"):  # rm custom claim
                del doc["claimedBuilds"]

    if first_pass:
        storeTest(jobDoc, view, first_pass=False, lastTotalCount=lastTotalCount, claimedBuilds=claimedBuilds)

def searchString(url,pattern):
    consoleText = str(getURL(url))
    m = re.findall(pattern,consoleText,re.M)
    return m

def retriggerAndDeleteJob(doc, url, defaultKeyName, defaultKey, rerun_param="", isAnyfailedInstall=False, isAnyFailedTest=False):
    print("Re-trigger the failedInstall jenkins job through test_suite_dispatcher...")
    # non default regression poolId or not None addPoolId
    nondefaultcomponents = [
        {"name": "fts", "poolId": "regression", "addPoolId": "elastic-fts"},
        {"name": "ipv6", "poolId": "ipv6", "addPoolId": "None"},
        {"name": "xdcr", "poolId": "regression", "addPoolId": "elastic-xdcr"},
        {"name": "epeng", "poolId": "regression", "addPoolId": "elastic-xdcr"},
    ]
    poolId = "regression"
    try:
        poolId = next(item for item in nondefaultcomponents if item["name"] == doc["component"])["poolId"]
    except:
        pass
    if not poolId:
        poolId = "regression"

    addPoolId = "None"
    try:
        addPoolId = next(item for item in nondefaultcomponents if item["name"] == doc["component"])["addPoolId"]
    except:
        pass
    if not addPoolId:
        addPoolId = "None"

    retry_get_params = ""
    dispatcher = ""
    retries = ""
    try:
        for key, value in retry_doc.iteritems():
            if key != "install_retries" and key != "tests_run_retries":
                retry_get_params = retry_get_params + "&" + key + "=" + value
        dispatcher = retry_doc["dispatcher"]
        install_retries = retry_doc["install_retries"]
        tests_run_retries = retry_doc["tests_run_retries"]

        num_install_retries = int(install_retries)
        num_tests_run_retries = int(tests_run_retries)
        if isAnyfailedInstall:
            num_install_retries = num_install_retries + 1
        if isAnyFailedTest:
            num_tests_run_retries = num_tests_run_retries + 1
        retry_get_params = retry_get_params + "&install_retries=" + str(num_install_retries) + "&tests_run_retries=" + str(num_tests_run_retries)

        if num_install_retries <= MAX_INSTALL_RETRIES_NUM and num_tests_run_retries <= MAX_TESTS_RUN_RETRIES_NUM and retry_get_params != "":
            urlToRun = "http://qa.sc.couchbase.com/job/{1}/buildWithParameters?token={0}". \
            format("extended_sanity", dispatcher)
            urlToRun = urlToRun + retry_get_params
            if len(rerun_param) > 0:
                urlToRun = urlToRun + "&include_tests=" + rerun_param
            print("Re-dispatching URL: " + str(urlToRun))
            response = requests.get(urlToRun, verify=True)
            if not response.ok:
                print("Warning: Error in triggering job")
                print(str(response))

            urlToDelete = url + "/doDelete?token=extended_sanity"
            print("TBD: Deleting failed install jenkins build: " + urlToDelete)
            response = requests.get(urlToDelete)
            if not response.ok:
                print("Warning: error while deleting the jenkins build!")
                print(str(response))
            print("TBD: Removing record from CB...key: " + defaultKeyName)
            # client.remove(defaultKey)
    except Exception as e:
        print str(e)
        pass

def storeTestData(url, view, first_pass=True, lastTotalCount=-1, claimedBuilds=None):

    bucket = view['bucket']
    claimedBuilds = claimedBuilds or {}

    #print("Storing test data from "+url)
    doc={}
    doc["url"]=url

    if url.find("sdkbuilds.couchbase") > -1:
        url = url.replace("sdkbuilds.couchbase", "sdkbuilds.sc.couchbase")

    urlparts = url.split("/")
    bid =  urlparts[len(urlparts)-1]
    doc["build_id"] = bid
    res = getJS(url, {"depth": 0})
    if res is None:
        print("Warning: build response is none!")
        return

    if "result" not in res:
        print("Warning: result is not in build response!")
        return

    doc["result"] = res["result"]
    doc["duration"] = res["duration"]

    if res["result"] not in ["SUCCESS", "UNSTABLE", "FAILURE", "ABORTED"]:
        print("Warning: result is not in SUCCESS,UNSTABLE,FAILURE,ABOORTED!")
        return  # unknown result state

    actions = res["actions"]
    params = getAction(actions, "parameters")
    if skipCollect(params):
        job = getJS(url, {"depth": 0})
        purgeDisabled(job, bucket)
        return

    totalCount = getAction(actions, "totalCount") or 0
    failCount = getAction(actions, "failCount") or 0
    skipCount = getAction(actions, "skipCount") or 0
    doc["claim"] = getClaimReason(actions)
    isAnyfailedInstall = False
    if totalCount == 0:
        if lastTotalCount == -1:
            print("Warning: no tests executed for this build!")
            totalCount = lastTotalCount
            failCount = totalCount
            errors = searchString(url+"/consoleText",r'ERROR - .+$')
            #print(errors)
            doc["failedErrors"] = errors
            isFailedInstall = [(e in 'INSTALL FAILED ON' for e in errors)]
            if bool(isFailedInstall):
                doc["failedInstall"] = True
                isAnyfailedInstall = True
            #return  # no tests ever passed for this build
        else:
            totalCount = lastTotalCount
            failCount = totalCount
    else:
        lastTotalCount = totalCount

    doc["failCount"] = failCount
    doc["totalCount"] = totalCount - skipCount
    passCount = totalCount - failCount

    # Get the failed test names from the consoleText - matching that many failed lines.
    isAnyFailedTest = False
    if failCount >0:
        nextLines = ''
        isAnyFailedTest = True
        for i in range(failCount):
            nextLines += "\s+(\S+)"

        ofailedTests = searchString(url + "/consoleText",
                                   r' , pass '
                                   +str(passCount)+' , fail '+str(failCount)+'\n+failures so far...'+nextLines)

        if failCount==1:
            failedTests = ofailedTests
        else:
            failedTests = list(ofailedTests[0])
        #print(failedTests)
        #print("failed tests count="+str(len(failedTests)))
        doc["failedTests"] = failedTests
        # Get errorstacktraces
        testReport = getJS(url+"/testReport")
        #print(testReport)
        if testReport:
            #doc["failedErrors"] = testReport['suites'][0]['cases']
            listAllCases = []
            for tcase in testReport['suites'][0]['cases']:
                tname = tcase['name']
                tclassName = tcase['className']
                terrorStackTrace = tcase['errorStackTrace']
                if terrorStackTrace != None:
                    listCase = {}
                    listCase["name"] = tname
                    listCase["className"] = tclassName
                    listCase["errorStackTrace"] = terrorStackTrace
                    listAllCases.append(listCase)

                #print("tname="+tname+",tclassName="+tclassName+",terrorStackTrace="+terrorStackTrace)
            doc["failedErrors"] = listAllCases

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
            componentParam = "systest-" + str(os.path.split(testFile)[-1]).replace(".yml", "")

    if componentParam:
        subComponentParam = getAction(params, "name", "subcomponent")
        if subComponentParam is None:
            subComponentParam = "server"
        osParam = getAction(params, "name", "OS") or getAction(params, "name", "os")
        if osParam is None:
            osParam = doc["os"]
        if not componentParam or not subComponentParam or not osParam:
            return

        pseudoName = str(osParam + "-" + componentParam + "_" + subComponentParam)
        doc["name"] = pseudoName
        nameOrig = pseudoName
        _os, _comp = getOsComponent(pseudoName, view)
        if _os and _comp:
            doc["os"] = _os
            doc["component"] = _comp
        if not doc.get("os") or not doc.get("component"):
            return
        if subComponentParam:
            doc["subcomponent"] = subComponentParam

    if bucket == "server":
        doc["build"], doc["priority"] = getBuildAndPriority(params)
    else:
        doc["build"], doc["priority"] = getBuildAndPriority(params, True)

    if doc["build"] is None and doc["priority"] is None and doc['os'] == "K8S":
        res = getJS(url + str(bid), {"depth": 0})
        if "description" in res:
            params = res['description'].split(",")
            try:
                operator_version = params[0].split(":")[1]
                op_major_version = operator_version.split("-")[0]

                cb_version = params[1].split(":")[1]

                if "-" not in cb_version:
                    cb_version = CB_RELEASE_BUILDS[cb_version[0:5]]
                elif "enterprise" in cb_version:
                    cb_version = cb_version.split("-")[1][0:5] + "-" + CB_RELEASE_BUILDS[cb_version.split("-")[1][0:5]]

                upgrade_version = params[2].split(":")[1]

                if "-" not in upgrade_version:
                    upgrade_version = upgrade_version[0:5]
                elif "enterprise" in upgrade_version:
                    upgrade_version = upgrade_version.split("-")[1][0:5]
                else:
                    upgrade_version = upgrade_version.split("-")[0][0:5]

                doc["build"] = cb_version
                doc["priority"] = 'P0'
                doc["name"] = doc["name"] + "-opver-" + op_major_version + "-upver-" + upgrade_version
            except:
                pass

    if not doc.get("build"):
        print("Warning: doc is missing build!")
        return

    # run special caveats on collector
    doc["component"] = caveat_swap_xdcr(doc)
    if caveat_should_skip(doc):
        return

    if caveat_should_skip_mobile(doc):
        return

    histKey = doc["name"] + "-" + doc["build"]

    defaultKeyName = "%s-%s" % (doc["name"], doc["build_id"])
    if not DEBUG_MODE:
        defaultKey = hashlib.md5(defaultKeyName).hexdigest()
    else:
        defaultKey = defaultKeyName

    # new name to have count
    if isAnyfailedInstall or isAnyFailedTest:
        doc["name"] = doc["name"] + ".1"

    key = _generate_document_key(isAnyfailedInstall=isAnyfailedInstall, isAnyFailedTest=isAnyFailedTest,
                                 doc_name=doc["name"],
                                 build=doc["build"], os=doc['os'], component=doc['component'],
                                 subcomponent=doc['subcomponent'], tag=retry_doc['tag'], version="1")

    if extra_fields!= '':
        doc.update(json.loads(extra_fields))
    try:
        #check if doc exists
        client = newClient(bucket)
        try:
            existingKeyVal = client.get(key)
            #print("existing:"+ str(existingKeyVal))
            print("Warning: document key exists")
            oldName = existingKeyVal.value['name']
            newName = oldName
            newCount = 1
            if isAnyfailedInstall or isAnyFailedTest:
                key_template_head = "%s-%s_%s" % (doc['os'], doc['component'], doc['subcomponent'])
                key_template_tail = "%s-%s" % (retry_doc['tag'], doc['build'])

                latest_fail_key = _find_latest_fail_key(client, key_template_head, key_template_tail)
                existingKeyVal = client.get(latest_fail_key)
                # print("existing:"+ str(existingKeyVal))
                print("Warning: document key exists")
                oldName = existingKeyVal.value['name']
                newName = oldName
                if '.' in oldName:
                    nameParts = oldName.split(".")
                    newName = '.'.join(nameParts[0:-1])
                    oldCount = int(nameParts[-1])
                    newCount = oldCount + 1

                doc["name"] = newName + "." + str(newCount)
            key = _generate_document_key(isAnyfailedInstall=isAnyfailedInstall, isAnyFailedTest=isAnyFailedTest,
                                         doc_name=doc["name"],
                                         build=doc["build"], os=doc['os'], component=doc['component'],
                                         subcomponent=doc['subcomponent'], tag=retry_doc['tag'],
                                         version=str(newCount))
        except Exception as e:
            print(e)
            pass

        doc["lastUpdated"] = str(datetime.datetime.utcnow())
        doc["tag"] = retry_doc["tag"]
        if isAnyfailedInstall or isAnyFailedTest:
            doc["type"] = "failedTests" if isAnyFailedTest else "failedInstall"
        print(key, doc)

        if not DEBUG_MODE:
            key = hashlib.md5(key).hexdigest()
        if save != 'no':
            print ("...saving to CB at %s/%s" % (HOST, bucket))
            if save == 'update':
                client.upsert(key, doc)
            else:
                client.insert(key, doc)
        #buildHist[histKey] = doc["build_id"]
    except Exception as e:
        print "CB client failed, couchbase down or key exists?: %s %s" % (HOST,e)

    # Delete and retrigger the jobs
    restart_install_failers = retry_doc['rerun_install_failures'] == 'true'
    restart_test_failers = retry_doc['rerun_test_failures'] == 'true'

    if isAnyfailedInstall and delete_retry != 'none' and restart_install_failers:
        retriggerAndDeleteJob(doc, url, defaultKeyName, defaultKey, isAnyfailedInstall=isAnyfailedInstall)
    elif isAnyfailedInstall:
        print("warning: failedInstall run but not deleting the record and re-triggering the job.")
    elif isAnyFailedTest and delete_retry != 'none' and restart_test_failers:
        restart_test_failers_option = retry_doc['rerun_test_failures_option']
        restart_test_failers_option = restart_test_failers_option.replace('<test_suite_executor_url>', url)
        retriggerAndDeleteJob(doc, url, defaultKeyName, defaultKey, rerun_param=restart_test_failers_option, isAnyFailedTest=True)

def _find_latest_fail_key(client, key_template_head, key_template_tail):
    key = ""
    query = N1QLQuery("select meta().id from {0} where meta().id like '{1}%{2}%' order by lastUpdated desc limit 1".format(str(client.bucket), key_template_head, key_template_tail))
    query.adhoc = False
    for row in client.n1ql_query(query):
        key = row['id']
    return key

def _generate_document_key(isAnyfailedInstall=False, isAnyFailedTest=False, os="", component="", subcomponent="", tag="", build="", version="", doc_name=""):
    # build - cb bulid, build_id - jenkins build
    if isAnyfailedInstall:
        return "%s-%s_%s-failedInstall-%s-%s.%s" % (os, component, subcomponent, tag, build, version)
    elif isAnyFailedTest:
        return "%s-%s_%s-failedTests-%s-%s.%s" % (os, component, subcomponent, tag, build, version)
    else:
        return "%s-%s_%s-%s-%s" % (os, component, subcomponent, tag, build)

def storeBuild(client, run, name, view):
    job = getJS(run["url"], {"depth": 0})
    if not job:
        print "No job info for build"
        return
    result = job.get("result")
    if not result:
        return

    actions = job["actions"]
    totalCount = getAction(actions, "totalCount") or 0
    failCount = getAction(actions, "failCount") or 0
    skipCount = getAction(actions, "skipCount") or 0

    if totalCount == 0:
        return

    params = getAction(actions, "parameters")
    os = getAction(params, "name", "DISTRO") or job["fullDisplayName"].split()[2].split(",")[0]
    version = getAction(params, "name", "VERSION")
    build = getAction(params, "name", "CURRENT_BUILD_NUMBER") or getAction(params, "name", "BLD_NUM")

    if not version or not build:
        return

    build = version + "-" + build.zfill(4)

    name = os + "_" + name
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
    print key + "," + build
    if not DEBUG_MODE:
        key = hashlib.md5(key).hexdigest()

    try:
        if version == "4.1.0":
            # not tracking, remove and ignore
            client.remove(key)
        else:
            client.upsert(key, doc)
    except Exception as ex:
        print "set failed, couchbase down?: %s %s" % (HOST, ex)


def pollBuild(view):
    client = newClient("server", "password")  # using server bucket (for now)

    tJobs = []

    for url in view["urls"]:

        j = getJS(url, {"depth": 0})
        if j is None:
            continue

        name = j["name"]
        for job in j["builds"]:
            build_url = job["url"]
            j = getJS(build_url, {"depth": 0, "tree": "runs[url,number]"})
            if j is None:
                continue

            try:
                t = None
                if not j or 'runs' not in j:
                    # single run job
                    t = Thread(target=storeBuild, args=(client, job, name, view))
                else:
                    # each run is a result
                    for doc in j["runs"]:
                        t = Thread(target=storeBuild, args=(client, doc, name, view))
                t.start()
                tJobs.append(t)
                if len(tJobs) > 10:
                    # intermediate join
                    for t in tJobs:
                        t.join()
                    tJobs = []
            except Exception as ex:
                print ex
                pass
    for t in tJobs:
        t.join()


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

    #    if _os is None:
    #        print "%s: job name has unrecognized os: %s" %  (view["bucket"], name)

    for comp in FEATURES:
        if _os == "K8S" and "SANIT" in comp:
            continue
        tag, _c = comp.split("-")
        docname = name.upper()
        docname = docname.replace("-", "_")
        if tag in docname:
            _comp = _c
            break

    #    if _comp is None:
    #        print "%s: job name has unrecognized component: %s" %  (view["bucket"], name)

    return _os, _comp


def pollTest(view):
    tJobs = []

    for url in view["urls"]:
        j = getJS(url, {"depth": 0, "tree": "jobs[name,url,color]"})
        if j is None or j.get('jobs') is None:
            continue

        for job in j["jobs"]:
            doc = {}
            doc["name"] = job["name"]
            if job["name"] in JOBS:
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

def convert_changeset_to_old_format(new_doc, timestamp):
    old_format = {}
    old_format['timestamp'] = timestamp
    old_format['changeSet'] = {}
    old_format_items = []
    for change in new_doc['log']:
        item = {}
        msg = change['message']
        # to remove the multiple '\n's, now appearing in the comment
        # that mess with greenboard's display of reviewUrl
        item['msg'] = msg[:msg.index('Change-Id')].replace("\n", " ") + \
                      msg[msg.index('Change-Id') - 1:]
        old_format_items.append(item)
    old_format['changeSet']['items'] = old_format_items
    return old_format


def collectBuildInfo(url):
    client = newClient('server')
    res = getJS(url, {"depth": 1, "tree": "builds[number,url]"})
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
            timestamp = job['timestamp']
            build_no = getAction(params, "name", "BLD_NUM")
            if build_no is None:
                continue
            key = version + "-" + build_no.zfill(4)
            try:
                # check if we have key
                client.get(key)
                continue  # already collected changeset
            except:
                pass
            try:
                if version[:3] == "0.0":
                    continue
                if float(version[:3]) > 4.6:
                    changeset_url = CHANGE_LOG_URL + "?ver={0}&from={1}&to={2}". \
                        format(version, str(int(build_no) - 1), build_no)
                    job = getJS(changeset_url, append_api_json=False)
                    key = version + "-" + build_no[1:].zfill(4)
                    job = convert_changeset_to_old_format(job, timestamp)
                client.upsert(key, job)
            except:
                print "set failed, couchbase down?: %s" % (HOST)


def collectAllBuildInfo():
    while True:
        time.sleep(600)
        try:
            for url in BUILDER_URLS:
                collectBuildInfo(url)
        except Exception as ex:
            print "exception occurred during build collection: %s" % (ex)


def newClient(bucket, password="password"):
    client = None
    try:
        client = Bucket(HOST + '/' + bucket)
    except Exception:
        # try rbac style auth
        endpoint = 'couchbase://{0}:{1}?select_bucket=true'.format(HOST, 8091)
        cluster = Cluster(endpoint)
        auther = PasswordAuthenticator("Administrator", password)
        cluster.authenticate(auther)
        client = cluster.open_bucket(bucket)

    return client


if __name__ == "__main__":
    usage = ''
    parser = OptionParser(usage)
    parser.add_option('-d','--host', dest='HOST')
    parser.add_option('-u','--urls', dest='urls', default="")
    parser.add_option('-s','--save', dest='save', default="no")
    parser.add_option('-v','--view', dest='view_name', default="server")
    parser.add_option('-r','--delete_retry', dest='delete_retry', default="none")
    parser.add_option('-e','--extra_fields', dest='extra_fields', default="")
    parser.add_option('-k','--retry_params', dest='retry_params', default="")



    options, args = parser.parse_args()

    HOST = options.HOST
    urls = options.urls
    save = options.save
    view_name = options.view_name
    delete_retry = options.delete_retry
    extra_fields = options.extra_fields
    retry_params = options.retry_params
    retry_doc = json.loads(retry_params)

    if HOST is None or urls == "":
        print "Usage: ",sys.argv[0]," CBhost jenkinsbuildurls [cbsave_flag view_name delete_retry extra_fields]"
        print "Example: ",sys.argv[0],"127.0.0.1", "http://qa.sc.couchbase.com/job/test_suite_executor/179035 update|no server|mobile|build none \'{\"failedInstall\": false, \"failedReason\": \"\", \"failedInstallVMs\": \"\"}'"
        sys.exit(1)

    #urls = ["http://server.jenkins.couchbase.com/job/watson-toy/213"]
    view = SERVER_VIEW

    if view_name == 'server':
        view = SERVER_VIEW
    elif view_name == 'mobile':
        view = MOBILE_VIEW
    elif view_name == 'build':
        view = BUILD_VIEW
    else:
        view_name="server"
    for url in urls.split(','):
        storeTestData(url, view)

