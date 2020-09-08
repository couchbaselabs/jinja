import re
import sys
import time
import os
import requests
import hashlib
import copy

from threading import Thread

from couchbase.bucket import Bucket, AuthError
from couchbase.cluster import Cluster, PasswordAuthenticator

from constants import *

UBER_USER = os.environ.get('UBER_USER') or ""
UBER_PASS = os.environ.get('UBER_PASS') or ""

JOBS = {}
HOST = '172.23.98.63'

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


def getBuildAndPriority(params, build_param_names):
    build = None
    priority = DEFAULT_BUILD
    if params:
        for build_param_name in build_param_names:
            if getAction(params, "name", build_param_name):
                build = getAction(params, "name", build_param_name)
                break

        priority = getAction(params, "name", "priority") or P1
        if priority.upper() not in [P0, P1, P2]:
            priority = P1

    if build is None:
        return None, None

    build = processBuildValue(build)
    if build is None:
        return None, None

    return build, priority


def processBuildValue(build):
    build = build.replace("-rel", "").split(",")[0]
    try:
        _build = build.split("-")
        if len(_build) == 1:
            raise Exception(
                "Invalid Build number: {} Should follow 1.1.1-0000 naming".format(
                    _build))

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
            return None
        m = re.match("^\d{1,10}", bno)
        if m is None:
            print "unsupported version_number: " + build
            return None

        build = "%s-%s" % (rel, bno.zfill(4))
    except:
        print "unsupported version_number: " + build
        return None

    return build


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


def skipServerCollect(params):
    skip_collect_u = getAction(params, "name", "SKIP_SERVER_GREENBOARD_COLLECT")
    skip_collect_l = getAction(params, "name", "skip_server_greenboard_collect")
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

    is_cblite = False
    is_syncgateway = False
    is_cblite_p2p = False

    if bucket == "cblite":
        is_cblite = True
    elif bucket == "sync_gateway":
        is_syncgateway = True

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
                continue

            if not is_syncgateway and not is_cblite and skipServerCollect(params):
                continue

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

            if doc["component"] == "P2P":
                is_cblite_p2p = True

            doc["build"], doc["priority"] = getBuildAndPriority(params, view["build_param_name"])

            if is_syncgateway:
                doc["server_version"] = getAction(params, "name",
                                                  "COUCHBASE_SERVER_VERSION")
            elif is_cblite_p2p:
                doc["server_version"] = "N/A"
                doc["sync_gateway_version"] = "N/A"
            elif is_cblite:
                doc["server_version"] = getAction(params, "name",
                                                  "COUCHBASE_SERVER_VERSION")
                doc["sync_gateway_version"] = getAction(params, "name",
                                                                "SYNC_GATEWAY_VERSION")


            if is_syncgateway or is_cblite or is_cblite_p2p:
                if "server_version" not in doc or doc["server_version"] is None:
                    doc["server_version"] = "Unknown"

            if is_cblite or is_cblite_p2p:
                if "sync_gateway_version" not in doc or doc["sync_gateway_version"] is None:
                    doc["sync_gateway_version"] = "Unknown"

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

            if is_cblite_p2p:
                os_arr = doc["name"].upper()
                os_arr = os_arr.split("P2P")[1].replace("/", "")
                os_arr = os_arr.split("-")[1:]
                ok = True
                for os in os_arr:
                    os = os.upper()
                    if os not in view["platforms"]:
                        ok = False
                        break

                if not ok:
                    continue

                # In the event its p2p to itself, remove dupe
                os_arr = list(dict.fromkeys(os_arr))
                build_no_arr = []

                for i in range (len(os_arr)):
                    os = os_arr[i]
                    viable_build_params = [build_param for build_param in view["build_param_name"] if os.upper() in build_param.upper()]
                    for build_param in viable_build_params:
                        param_value = getAction(params, "name", build_param)
                        if param_value:
                            build_no = processBuildValue(param_value)
                            if build_no is not None:
                                build_no_arr.append(build_no)
                            break

                if len(build_no_arr) != len(os_arr) or len(os_arr) < 1:
                    continue

                for i in range(len(os_arr)):
                    os = os_arr[i]
                    build_no = build_no_arr[i]

                    doc["os"] = os
                    doc["build"] = build_no

                    histKey = doc["name"] + "-" + doc["build"] + doc["os"]
                    if not first_pass and histKey in buildHist:
                        try:
                            oldKey = "%s-%s-%s" % (doc["name"], doc["build_id"], doc["os"])
                            oldKey = hashlib.md5(oldKey).hexdigest()
                            client.remove(oldKey)
                        except:
                            pass

                        continue

                    key = "%s-%s-%s" % (doc["name"], doc["build_id"], doc["os"])
                    key = hashlib.md5(key).hexdigest()

                    retries = 5
                    while retries > 0:
                        try:
                            client.upsert(key, doc)
                            buildHist[histKey] = doc["build_id"]
                            break
                        except Exception as e:
                            print "set failed, couchbase down?: %s" % (HOST)
                            print e
                            retries -= 1
                    if retries == 0:
                        with open("errors.txt", 'a+') as error_file:
                            error_file.writelines(doc.__str__())

            else:
                histKey = doc["name"] + "-" + doc["build"]
                if not first_pass and histKey in buildHist:

                    # print "REJECTED- doc already in build results: %s" % doc
                    # print buildHist

                    # attempt to delete if this record has been stored in couchbase

                    try:
                        oldKey = "%s-%s" % (doc["name"], doc["build_id"])
                        oldKey = hashlib.md5(oldKey).hexdigest()
                        client.remove(oldKey)
                        # print "DELETED- %d:%s" % (bid, histKey)
                    except:
                        pass

                    continue  # already have this build results

                key = "%s-%s" % (doc["name"], doc["build_id"])
                key = hashlib.md5(key).hexdigest()

                try:  # get custom claim if exists
                    oldDoc = client.get(key)
                    customClaim = oldDoc.value.get('customClaim')
                #  if customClaim is not None:
                #      doc["customClaim"] = customClaim
                except:
                    pass  # ok, this is new doc
                retries = 5
                while retries > 0:
                    try:
                        client.upsert(key, doc)
                        buildHist[histKey] = doc["build_id"]
                        break
                    except Exception as e:
                        print "set failed, couchbase down?: %s" % (HOST)
                        print e
                        retries -= 1
                if retries == 0:
                    with open("errors.txt", 'a+') as error_file:
                        error_file.writelines(doc.__str__())
                if doc.get("claimedBuilds"):  # rm custom claim
                    del doc["claimedBuilds"]

    if first_pass:
        storeTest(jobDoc, view, first_pass=False, lastTotalCount=lastTotalCount, claimedBuilds=claimedBuilds)


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
    key = hashlib.md5(key).hexdigest()
    retries = 5
    while retries > 0:
        try:
            if version == "4.1.0":
                # not tracking, remove and ignore
                client.remove(key)
            else:
                client.upsert(key, doc)
            break
        except Exception as e:
            print "set failed, couchbase down?: %s" % (HOST)
            print e
            retries -= 1
    if retries == 0:
        with open("errors.txt", 'a+') as error_file:
            error_file.writelines(doc.__str__())


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
            break

    if _os is None:
        # attempt partial name lookup
        for os in PLATFORMS:
            if os[:3] == name.upper()[:3]:
                _os = os
                break

    if (_os is None and view["bucket"] != "sync_gateway" and view["bucket"] != "cblite"):
        # attempt initial name lookup
        for os in PLATFORMS:
            if os[:1] == name.upper()[:1]:
                _os = os
                break

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

            filters_met = False
            if "filters" in view:
                for filter_item in view["filters"]:
                    if filter_item.upper() in job["name"].upper():
                        filters_met = True
            else:
                filters_met = True

            if not filters_met:
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
            retries = 5
            if version[:3] == "0.0":
                continue
            if float(version[:3]) > 4.6:
                changeset_url = CHANGE_LOG_URL + "?ver={0}&from={1}" \
                                                 "&to={2}".format(
                    version, str(int(build_no) - 1), build_no)
                job = getJS(changeset_url, append_api_json=False)
                key = version + "-" + build_no[1:].zfill(4)
                job = convert_changeset_to_old_format(job, timestamp)
            while retries > 0:
                try:
                    client.upsert(key, job)
                    break
                except Exception as e:
                    print "set failed, couchbase down?: %s" % (HOST)
                    print e
                    retries -= 1
            if retries == 0:
                with open("errors.txt", 'a+') as error_file:
                    error_file.writelines(job.__str__())


def collectAllBuildInfo():
    while True:
        time.sleep(600)
        try:
            for url in BUILDER_URLS:
                collectBuildInfo(url)
        except Exception as ex:
            print "exception occurred during build collection: %s" % (ex)


def newClient(bucket, password="password"):
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

    # run build collect info thread
    tBuild = Thread(target=collectAllBuildInfo)
    tBuild.daemon = True
    tBuild.start()

    while True:
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

