import multiprocessing
import re
import sys
import time
import os
import requests
import hashlib
import copy
import configparser
import json

from threading import Thread
from requests.auth import HTTPBasicAuth

from couchbase.cluster import Cluster, ClusterOptions, PasswordAuthenticator
import couchbase.subdocument as SD

from constants import *

UBER_USER = os.environ.get('UBER_USER') or ""
UBER_PASS = os.environ.get('UBER_PASS') or ""

JOBS = {}
HOST = '172.23.98.63'
DEFAULT_BUCKET_STORAGE = "COUCHSTORE"
DEFAULT_GSI_TYPE = "PLASMA"

config = configparser.ConfigParser()
config.read("credentials.ini")

if len(sys.argv) == 2:
    HOST = sys.argv[1]

def get_auth(server):
    auth = None
    for url in config.sections():
        if server.startswith(url):
            try:
                username = config.get(url, "username")
                password = config.get(url, "password")
            except configparser.NoOptionError:
                pass
            else:
                auth = HTTPBasicAuth(username, password)
                break
    return auth

def getJS(url, params=None, retry=5, append_api_json=True):
    res = None
    auth = get_auth(url)
    try:
        if append_api_json:
            res = requests.get("%s/%s" % (url, "api/json"), params=params, timeout=15, auth=auth)
        else:
            res = requests.get("%s" % url, params=params, timeout=15, auth=auth)
        data = res.json()
        return data
    except:
        print("[Error] url unreachable: %s" % url)
        res = None
        if retry:
            retry = retry - 1
            return getJS(url, params, retry)
        else:
            pass

    return res


def getConsoleLog(url):
    res = None
    try:
        res =  requests.get("%s/%s" % (url, "consoleText"), timeout=15)
        if res.status_code == 200:
            return res.content
    except ex:
        print("[Error] url unreachable: %s" % url)
        print("Error: %s" % ex.message)

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

def build_finished(res):
    if res is None or "result" not in res or "building" not in res:
        return False

    if res["result"] not in ["SUCCESS", "UNSTABLE", "FAILURE", "ABORTED"] or res["building"]:
        return False
    
    return True

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
            print("unsupported version_number: " + build)
            return None
        m = re.match("^\d{1,10}", bno)
        if m is None:
            print("unsupported version_number: " + build)
            return None

        build = "%s-%s" % (rel, bno.zfill(4))
    except:
        print("unsupported version_number: " + build)
        return None

    return build

def format_stack_trace(raw_stack_trace, character_limit=1000):
    # remove non ASCII characters
    stack = re.sub(r'[^ -~]+', '', raw_stack_trace.replace("\\n", "")).lstrip("['Traceback (most recent call last):  ")
    return (stack[:character_limit] + '...') if len(stack) > character_limit else stack

def get_servers_from_log(job_url):
    ips = set()
    try:
        auth = get_auth(job_url)
        timeout = 5
        start_download_time = time.time()
        for line in requests.get(job_url + '/consoleText', timeout=timeout, stream=True, auth=auth).iter_lines():
            if time.time() > start_download_time + timeout:
                raise Exception("download timeout")
            # install.py
            if "thread installer-thread-" in line:
                try:
                    ips.add(line.replace("thread installer-thread-", "").replace(" finished", "").strip())
                except Exception:
                    pass
            # new_install.py
            if "INSTALL COMPLETED ON" in line or "INSTALL NOT STARTED ON" in line or "INSTALL FAILED ON" in line:
                try:
                    ips.add(line.split(" ")[-1].strip())
                except Exception:
                    pass
    except Exception:
        print("error downloading console ({})".format(job_url))
    return list(ips)

def get_claim_from_log(job_url):
    reasons = set()
    try:
        auth = get_auth(job_url)
        timeout = 5
        start_download_time = time.time()
        for line in requests.get(job_url + '/consoleText', timeout=5, stream=True, auth=auth).iter_lines(decode_unicode=True):
            line = format_stack_trace(line)
            if time.time() > start_download_time + timeout:
                raise Exception("download timeout")
            found = False
            for [claim, causes] in CLAIM_MAP.items():
                if found:
                    break
                for cause in causes:
                    if cause in line:
                        reasons.add (claim + ": " + line)
                        found = True
                        break
    except Exception:
        print("error downloading console ({})".format(job_url))
    if len(reasons) == 0:
        return None
    else:
        return "<br><br>".join(reasons)

# Get all exceptions
def get_claim_from_test_report(job_url):
    reasons = set()
    try:
        auth = get_auth(job_url)
        start_download_time = time.time()
        timeout = 5
        json_str = ""
        for char in requests.get(job_url + "/testReport/api/json", timeout=timeout, auth=auth, stream=True).iter_content(decode_unicode=True):
            if time.time() > start_download_time + timeout:
                raise Exception("download timeout")
            json_str += char
        test_report = json.loads(json_str)
        for suite in test_report["suites"]:
            for case in suite["cases"]:
                if case["status"] == "FAILED":
                    stacktrace = format_stack_trace(case["errorStackTrace"])
                    found = False
                    for [claim, causes] in CLAIM_MAP.items():
                        if found:
                            break
                        for cause in causes:
                            if cause.lower() in stacktrace.lower():
                                reasons.add(claim + ": " + stacktrace)
                                found = True
                                break
                    if not found:
                        reasons.add(stacktrace)
    except Exception as e:
        print(e)
        print("error downloading test report ({})".format(job_url))
    if len(reasons) == 0:
        return None
    else:
        return "<br><br>".join(reasons)

def getClaimReason(actions, analyse_log, analyse_test_report, job_url):
    reason = None

    if getAction(actions, "claimed"):
        reason = getAction(actions, "reason")
        try:
            rep_dict = {m: "<a href=\"https://issues.couchbase.com/browse/{0}\">{1}</a>".
                format(m, m) for m in re.findall(r"([A-Z]{2,4}[-: ]*\d{4,5})", reason)}
            if rep_dict:
                pattern = re.compile('|'.join(rep_dict.keys()))
                reason = pattern.sub(lambda x: rep_dict[x.group()], reason)
        except Exception as e:
            pass
    elif analyse_log:
        if analyse_test_report:
            reason = get_claim_from_test_report(job_url)
        if analyse_log and reason is None:
            reason = get_claim_from_log(job_url)

    return reason or ""


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
    client = newClient().bucket(bucket).default_collection()
    name = job["name"]
    bids = [b["number"] for b in job["builds"]]
    if len(bids) == 0:
        return

    high_bid = bids[0]
    for bid in range(high_bid):
        # reconstruct doc id
        bid = bid + 1
        oldKey = "%s-%s" % (name, bid)
        oldKey = hashlib.md5(oldKey.encode()).hexdigest()
        # purge
        try:
            client.remove(oldKey)
        except Exception as ex:
            pass  # delete ok

def get_expected_total_count(greenboard_bucket, bucket, doc):
    expected_total_count = None
    name = doc.get("displayName") or doc["name"]
    try:
        expected_total_count = int(greenboard_bucket.lookup_in("existing_builds_"+bucket, SD.get(bucket+"."+doc["os"]+"."+doc["component"]+"."+name+".totalCount"))[0])
    except Exception:
        pass
    return expected_total_count

def update_skip_count(greenboard_bucket, view, doc):
    # if job failed or was aborted, get the expected total count and set skip count to expected total count - actual total count
    if doc["result"] in ["FAILURE", "ABORTED"]:
        expected_total_count = get_expected_total_count(greenboard_bucket, view["bucket"], doc)
        # prevent negative skip count
        if expected_total_count is not None and expected_total_count > doc["totalCount"]:
            doc["skipCount"] = expected_total_count - doc["totalCount"]
            doc["totalCount"] = expected_total_count

def get_manual_triage_and_bugs(triage_history_bucket, bucket, doc):
    triage = ""
    bugs = []

    if doc["result"] != "SUCCESS":
        try:
            major_version = doc["build"].split("-")[0]
            build = int(doc["build"].split("-")[1])
            key = doc["name"] + "_" + major_version + "_" + bucket
            triage_history = triage_history_bucket.get(key).value
            if build >= triage_history["build"]:
                triage = triage_history["triage"]
                bugs = triage_history["bugs"]
        except Exception:
            pass

    return triage, bugs

def get_servers_from_params(params):
    servers = getAction(params, "name", "servers")
    if servers is None:
        return []
    else:
        return [server.strip("\"") for server in servers.split(",")]

def get_servers(params, job_url):
    return get_servers_from_params(params) or get_servers_from_log(job_url)


def get_variant(name, params):
    """
    Get a variant with the specified name from the parameters parameter
    """
    parameters = getAction(params, "name", "parameters")
    if parameters is None:
        return None
    for parameter in parameters.split(","):
        if parameter.startswith(name):
            return parameter.split("=")[1].upper()
    return None


def get_variants(params, component):
    """
    Get the variants from the params, or defaults where applicable
    """
    variants = {}

    # Bucket storage applies to all jobs
    variants["bucket_storage"] = get_variant("bucket_storage", params) or DEFAULT_BUCKET_STORAGE

    # GSI type only applies to jobs that use GSI
    gsi_type = get_variant("gsi_type", params)
    # Only set default if not set and GSI component
    if gsi_type is None:
        if component in ["2I_MOI", "2I_REBALANCE", "PLASMA"]:
            gsi_type = DEFAULT_GSI_TYPE
        else:
            gsi_type = "UNDEFINED"
    variants["GSI_type"] = gsi_type

    return variants


def add_variants_to_name(doc):
    """
    Add the variants to the name of the job. 
    Store the original name in displayName to show on greenboard
    """
    doc["displayName"] = doc["name"]
    for key, value in doc["variants"].items():
        doc["name"] += key + "=" + value


def storeTest(input, first_pass=True, lastTotalCount=-1, claimedBuilds=None):
    try:
        jobDoc, view, already_scraped = input

        bucket = view["bucket"]

        claimedBuilds = claimedBuilds or {}
        cluster = newClient()
        client = cluster.bucket(bucket).default_collection()
        greenboard_bucket = cluster.bucket("greenboard").default_collection()
        triage_history_bucket = cluster.bucket("triage_history").default_collection()

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
                # include all jenkins history
                bids = list(range(res["firstBuild"]["number"], res["lastBuild"]["number"] + 1))
                bids.reverse()
            elif first_pass:
                bids.reverse()  # bottom to top 1st pass

            for bid in bids:
                try:
                    doc = copy.deepcopy(jobDoc)
                    oldName = JOBS.get(doc["name"]) is not None
                    if oldName and bid in JOBS[doc["name"]]:
                        continue  # job already stored
                    else:
                        if oldName and first_pass == False:
                            JOBS[doc["name"]].append(bid)

                    doc["build_id"] = bid

                    already_scraped_key = doc["url"] + str(doc["build_id"])

                    if already_scraped_key in already_scraped:
                        continue

                    should_process = False

                    for _ in range(2):
                        res = getJS(url + str(bid), {"depth": 0})
                        if not build_finished(res):
                            break
                        # retry after 10 seconds if jenkins race condition where result and duration have not been updated to reflect test results
                        # e.g. result set to success, test result processed, result updated, duration updated.
                        if res["duration"] == 0:
                            print("Sleeping for 10 seconds, potential Jenkins race condition detected...")
                            time.sleep(10)
                        else:
                            should_process = True
                            break

                    if not should_process:
                        continue

                    doc["result"] = res["result"]
                    doc["duration"] = res["duration"]
                    doc["timestamp"] = res["timestamp"]

                    actions = res["actions"]
                    params = getAction(actions, "parameters")
                    if skipCollect(params):
                        continue

                    if not is_syncgateway and not is_cblite and skipServerCollect(params):
                        continue

                    totalCount = getAction(actions, "totalCount") or 0
                    failCount = getAction(actions, "failCount") or 0
                    skipCount = getAction(actions, "skipCount") or 0
                    # failed or no tests passed
                    should_analyse_logs = res["result"] != "SUCCESS"
                    # at least one test executed
                    should_analyse_report = totalCount > 0 and res["result"] != "SUCCESS"
                    if totalCount == 0:
                        if not isExecutor(doc["name"]):
                            # skip non executor jobs where totalCount == 0 and no lastTotalCount
                            if lastTotalCount == -1:
                                continue
                            else:
                                # only set totalCount to lastTotalCount if this is not an executor job
                                # if this is an executor job, the last run will probably be a completely
                                # different set of tests so lastTotalCount is irrelevant
                                totalCount = lastTotalCount
                                failCount = totalCount
                    else:
                        lastTotalCount = totalCount

                    doc["failCount"] = failCount
                    doc["totalCount"] = totalCount - skipCount
                    doc["skipCount"] = 0
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

                    doc["servers"] = get_servers(params, url + str(bid))

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

                    if not doc.get("build"):
                        continue

                    # run special caveats on collector
                    doc["component"] = caveat_swap_xdcr(doc)
                    if caveat_should_skip(doc):
                        continue

                    if caveat_should_skip_mobile(doc):
                        continue

                    if "additional_fields" in view:
                        for additional_field_key, additional_field_value in view["additional_fields"].items():
                            for value_pairs in additional_field_value:
                                if value_pairs[0].upper() in doc["name"].upper():
                                    doc[additional_field_key] = value_pairs[1].upper()
                                    break

                    if is_cblite_p2p:
                        os_arr = doc["name"].upper()
                        os_arr = os_arr.split("P2P")[1].replace("/", "")
                        os_arr = os_arr.split("-")[1:]
                        ok = False
                        os_to_process = ""
                        for os in os_arr:
                            os = os.upper()
                            if os in view["platforms"]:
                                ok = True
                                os_to_process = os
                                break

                                if not ok:
                                    continue

                        build_no_to_process = ""
                        viable_build_params = [build_param for build_param in view["build_param_name"] if os.upper() in build_param.upper()]
                        for build_param in viable_build_params:
                            param_value = getAction(params, "name", build_param)
                            if param_value:
                                build_no = processBuildValue(param_value)
                                if build_no is not None:
                                    build_no_to_process = build_no

                        if build_no_to_process == "" or os_to_process == "":
                            continue

                        doc["os"] = os_to_process
                        doc["build"] = build_no_to_process

                        doc["claim"] = getClaimReason(actions, should_analyse_logs, should_analyse_report, url + str(bid))
                        update_skip_count(greenboard_bucket, view, doc)
                        doc["triage"], doc["bugs"] = get_manual_triage_and_bugs(triage_history_bucket, view["bucket"], doc)

                        histKey = doc["name"] + "-" + doc["build"] + doc["os"]
                        if not first_pass and histKey in buildHist:
                            try:
                                oldKey = "%s-%s-%s" % (doc["name"], doc["build_id"], doc["os"])
                                oldKey = hashlib.md5(oldKey.encode()).hexdigest()
                                client.remove(oldKey)
                            except:
                                pass

                            continue

                        key = "%s-%s-%s" % (doc["name"], doc["build_id"], doc["os"])
                        key = hashlib.md5(key.encode()).hexdigest()

                        retries = 5
                        while retries > 0:
                            try:
                                client.upsert(key, doc)
                                buildHist[histKey] = doc["build_id"]
                                break
                            except Exception as e:
                                print("set failed, couchbase down?: %s" % (HOST))
                                print(e)
                                retries -= 1
                        if retries == 0:
                            with open("errors.txt", 'a+') as error_file:
                                error_file.writelines(doc.__str__())

                    else:

                        if bucket == "server":
                            # get any test variants (e.g. bucket storage)
                            doc["variants"] = get_variants(params, doc["component"])
                            add_variants_to_name(doc)

                        doc["claim"] = getClaimReason(actions, should_analyse_logs, should_analyse_report, url + str(bid))
                        update_skip_count(greenboard_bucket, view, doc)
                        doc["triage"], doc["bugs"] = get_manual_triage_and_bugs(triage_history_bucket, view["bucket"], doc)

                        histKey = doc["name"] + "-" + doc["build"]
                        if not first_pass and histKey in buildHist:

                            # print "REJECTED- doc already in build results: %s" % doc
                            # print buildHist

                            # attempt to delete if this record has been stored in couchbase

                            try:
                                oldKey = "%s-%s" % (doc["name"], doc["build_id"])
                                oldKey = hashlib.md5(oldKey.encode()).hexdigest()
                                client.remove(oldKey)
                                # print "DELETED- %d:%s" % (bid, histKey)
                            except:
                                pass

                            continue  # already have this build results

                        key = "%s-%s" % (doc["name"], doc["build_id"])
                        key = hashlib.md5(key.encode()).hexdigest()

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
                                already_scraped.append(already_scraped_key)
                                break
                            except Exception as e:
                                print("set failed, couchbase down?: %s" % (HOST))
                                print(e)
                                retries -= 1
                        if retries == 0:
                            with open("errors.txt", 'a+') as error_file:
                                error_file.writelines(doc.__str__())
                        if doc.get("claimedBuilds"):  # rm custom claim
                            del doc["claimedBuilds"]
                except Exception as ex:
                    print("Some unintented exception occured : %s" % ex)
        if first_pass:
            storeTest((jobDoc, view, already_scraped), first_pass=False, lastTotalCount=lastTotalCount, claimedBuilds=claimedBuilds)
    except Exception as ex:
        print("Some unintented exception occured : %s" % ex)

def storeOperator(input, first_pass=True, lastTotalCount=-1,
                  claimedBuilds=None):
    try:
        jobDoc, view, already_scraped = input
        bucket = view["bucket"]

        claimedBuilds = claimedBuilds or {}
        cluster = newClient()
        client = cluster.bucket(bucket).default_collection()
        greenboard_bucket = client.bucket("greenboard").default_collection()

        doc = copy.deepcopy(jobDoc)
        url = doc["url"]
        res = getJS(url, {"depth": 0})

        if res is None:
            return

        # do not process disabled jobs
        if isDisabled(doc):
            purgeDisabled(res, bucket)
            return
        buildHist = {}
        if res.get("lastBuild") is not None:

            bids = [b["number"] for b in res["builds"]]

            if isExecutor(doc["name"]):
                # include all jenkins history
                bids = list(range(res["firstBuild"]["number"],
                                  res["lastBuild"]["number"] + 1))
                bids.reverse()
            elif first_pass:
                bids.reverse()  # bottom to top 1st pass

            for bid in bids:
                try:
                    doc = copy.deepcopy(jobDoc)
                    oldName = JOBS.get(doc["name"]) is not None
                    if oldName and bid in JOBS[doc["name"]]:
                        continue  # job already stored
                    else:
                        if oldName and first_pass == False:
                            JOBS[doc["name"]].append(bid)

                    doc["build_id"] = bid
                    already_scraped_key = doc["url"] + str(doc["build_id"])
                    if already_scraped_key in already_scraped:
                        continue
                    should_process = False

                    for _ in range(2):
                        res = getJS(url + str(bid), {"depth": 0})
                        if not build_finished(res):
                            break
                        # retry after 10 seconds if jenkins race condition
                        # where result and duration have not been updated to
                        # reflect test results
                        # e.g. result set to success, test result processed,
                        # result updated, duration updated.
                        if res["duration"] == 0:
                            print("Sleeping for 10 seconds, potential Jenkins " \
                                  "race condition detected...")
                            time.sleep(10)
                        else:
                            should_process = True
                            break

                    if not should_process:
                        continue

                    doc["result"] = res["result"]
                    doc["duration"] = res["duration"]
                    doc["timestamp"] = res["timestamp"]

                    actions = res["actions"]
                    params = getAction(actions, "parameters")
                    skip_collect = getAction(params, "name", "custom")
                    if skipCollect(params) or skip_collect:
                        continue
                    totalCount = getAction(actions, "totalCount") or 0
                    failCount = getAction(actions, "failCount") or 0
                    skipCount = getAction(actions, "skipCount") or 0
                    should_analyse_logs = res["result"] != "SUCCESS"
                    should_analyse_report = totalCount > 0 and res[
                        "result"] != "SUCCESS"
                    doc["claim"] = getClaimReason(actions,
                                                  should_analyse_logs,
                                                  should_analyse_report,
                                                  url + str(bid))
                    if totalCount == 0:
                        if not isExecutor(doc["name"]):
                            # skip non executor jobs where totalCount == 0
                            # and no lastTotalCount
                            if lastTotalCount == -1:
                                continue
                            else:
                                # only set totalCount to lastTotalCount if
                                # this is not an executor job
                                # if this is an executor job, the last run
                                # will probably be a completely
                                # different set of tests so lastTotalCount is
                                # irrelevant
                                totalCount = lastTotalCount
                                failCount = totalCount
                    else:
                        lastTotalCount = totalCount

                    doc["failCount"] = failCount
                    doc["totalCount"] = totalCount - skipCount
                    doc["skipCount"] = 0
                    kubernetes_version = \
                        processOperatorKubernetesVersion(getAction(
                            params, "name", "kubernetes_version"))
                    if not kubernetes_version:
                        continue
                    doc['component'] = kubernetes_version
                    if not doc['component']:
                        continue
                    doc['build'] = getOperatorBuild(params, "%s%s" % (doc[
                        'url'], doc['build_id']))
                    doc['priority'] = P1
                    serverVersion = getAction(params, "name",
                                                      "server_image")
                    doc["server_version"] = processOperatorServerVersion(serverVersion)
                    if not doc.get("build"):
                        continue

                    doc["name"] = doc["name"] + "_" + doc["server_version"]

                    doc["servers"] = get_servers(params, url + str(bid))

                    doc["claim"] = getClaimReason(actions, should_analyse_logs, should_analyse_report, url + str(bid))
                    update_skip_count(greenboard_bucket, view, doc)

                    histKey = doc["name"] + "-" + doc["build"]
                    if not first_pass and histKey in buildHist:

                        # print "REJECTED- doc already in build results: %s"
                        # % doc
                        # print buildHist

                        # attempt to delete if this record has been stored in
                        # couchbase

                        try:
                            oldKey = "%s-%s" % (doc["name"], doc["build_id"])
                            oldKey = hashlib.md5(oldKey.encode()).hexdigest()
                            client.remove(oldKey)
                            # print "DELETED- %d:%s" % (bid, histKey)
                        except:
                            pass

                        continue  # already have this build results

                    key = "%s-%s" % (doc["name"], doc["build_id"])
                    key = hashlib.md5(key.encode()).hexdigest()

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
                            already_scraped.append(already_scraped_key)
                            print("Collected %s" % already_scraped_key)
                            break
                        except Exception as e:
                            print("set failed, couchbase down?: %s" % (HOST))
                            print(e)
                            retries -= 1
                    if retries == 0:
                        with open("errors.txt", 'a+') as error_file:
                            error_file.writelines(doc.__str__())
                    if doc.get("claimedBuilds"):  # rm custom claim
                        del doc["claimedBuilds"]
                except Exception as ex:
                    print("Some unintented exception occured : %s" % ex)
        if first_pass:
            storeOperator((jobDoc, view, already_scraped),
                          first_pass=False,
                          lastTotalCount=lastTotalCount,
                          claimedBuilds=claimedBuilds)
    except Exception as ex:
        print("Some unintented exception occured : %s" % ex)

def storeBuild(run, name, view):
    cluster = newClient()
    client = cluster.bucket("server").default_collection() # using server bucket (for now)
    greenboard_bucket = cluster.bucket("greenboard").default_collection()
    job = getJS(run["url"], {"depth": 0})
    if not job:
        print("No job info for build")
        return
    result = job.get("result")
    if not result:
        return

    actions = job["actions"]
    totalCount = getAction(actions, "totalCount") or 0
    failCount = getAction(actions, "failCount") or 0

    if totalCount == 0:
        return

    params = getAction(actions, "parameters")
    os = getAction(params, "name", "DISTRO") or job["fullDisplayName"].split()[2].split(",")[0]
    version = getAction(params, "name", "VERSION")
    build = getAction(params, "name", "CURRENT_BUILD_NUMBER") or getAction(params, "name", "BLD_NUM")

    if not version or not build:
        return

    build = version + "-" + build.zfill(4)

    # Fix CBQE-6406
    if name == "build_sanity_matrix":
        node_type = job["fullDisplayName"].split()[2].split(",")[1]
        name = os + "_" + name + "_" + node_type
    else:
        name = os + "_" + name

    if getAction(params, "name", "UNIT_TEST"):
        name += "_unit"

    os, comp = getOsComponent(name, view)
    if not os or not comp:
        return

    duration = int(job["duration"]) or 0

    # Fix CBQE-6376
    if run["url"].endswith(job["id"] + "/"):
        run["url"] = run["url"].rstrip(job["id"] + "/") + "/"

    should_analyse_logs = result != "SUCCESS"
    should_analyse_report = totalCount > 0 and result != "SUCCESS"
    claim = getClaimReason(actions, should_analyse_logs, should_analyse_report, run["url"] + job["id"])
    servers = get_servers(params, run["url"] + job["id"])
    

    # lookup pass count fail count version
    doc = {
        "build_id": int(job["id"]),
        "claim": claim,
        "name": name,
        "url": run["url"],
        "component": comp,
        "failCount": failCount,
        "totalCount": totalCount,
        "skipCount": 0,
        "result": result,
        "duration": duration,
        "priority": "P0",
        "os": os,
        "build": build,
        "servers": servers,
        "timestamp": job["timestamp"]
    }

    update_skip_count(greenboard_bucket, view, doc)

    doc["variants"] = get_variants(params, comp)
    add_variants_to_name(doc)

    key = "%s-%s" % (doc["name"], doc["build_id"])
    print(key + "," + build)
    key = hashlib.md5(key.encode()).hexdigest()
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
            print("set failed, couchbase down?: %s" % (HOST))
            print(e)
            retries -= 1
    if retries == 0:
        with open("errors.txt", 'a+') as error_file:
            error_file.writelines(doc.__str__())


def pollBuild(view):
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
                    t = Thread(target=storeBuild, args=(job, name, view))
                    t.start()
                    tJobs.append(t)
                else:
                    # each run is a result
                    for doc in j["runs"]:
                        t = Thread(target=storeBuild, args=(doc, name, view))
                        t.start()
                        tJobs.append(t)
                if len(tJobs) > 10:
                    # intermediate join
                    for t in tJobs:
                        t.join()
                    tJobs = []
            except Exception as ex:
                print(ex)
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

    if _os is None and view["bucket"] != "sync_gateway" and view["bucket"] != "cblite":
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


def getOperatorPlatform(name, view):
    _platform = None
    PLATFORMS = view["platforms"]
    for platform in PLATFORMS:
        platform = platform.split("-")[0]
        if platform in name.upper():
            _platform = platform
            break
    return _platform


def pollTest(view, already_scraped):
    tJobs = []

    for url in view["urls"]:
        j = getJS(url, {"depth": 0, "tree": "jobs[name,url,color]"})
        if j is None or j.get('jobs') is None:
            continue

        for job in j["jobs"]:

            if is_excluded(view, job):
                print("skipping {} (excluded)".format(job["name"]))
                continue

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

            none_filters_met = True
            if "none_filters" in view:
                for filter_item in view["none_filters"]:
                    if filter_item.upper() in job["name"].upper() and "P2P" not in job["name"].upper():
                        none_filters_met = False

            if not none_filters_met:
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

            tJobs.append((doc, view, already_scraped))

    pool = multiprocessing.Pool()
    pool.map(storeTest, tJobs)
    pool.close()
    pool.join()


def is_excluded(view, job):
    if "exclude" in view:
        for name in view["exclude"]:
            if re.search(name, job["name"]) is not None:
                return True
    return False


def polloperator(view, already_scraped):
    tJobs = []

    for url in view["urls"]:
        j = getJS(url, {"depth": 0, "tree": "jobs[name,url,color]"})
        if j is None or j.get('jobs') is None:
            continue

        for job in j["jobs"]:

            if is_excluded(view, job):
                print("skipping {} (excluded)".format(job["name"]))
                continue

            doc = {}
            doc["name"] = job["name"]
            if job["name"] in JOBS:
                continue
            JOBS[job["name"]] = []
            platform = getOperatorPlatform(job["name"], view)
            if not platform:
                continue
            doc['os'] = platform
            doc["url"] = job["url"]
            doc["color"] = job.get("color")
            tJobs.append((doc, view, already_scraped))
    pool = multiprocessing.Pool()
    pool.map(storeOperator, tJobs)
    pool.close()
    pool.join()


def getOperatorBuild(params, url):
    version = getAction(params, "name", "operator_image")
    if not version:
        return None
    slices = version.split(":")
    if slices.__len__() < 2:
        return None
    version = slices[1]
    if "latest" in version or "-" not in version:
        consoleText = getConsoleLog(url)
        if not consoleText:
            return None
        _version = re.findall("{\"version\":.*$", consoleText,
                              re.MULTILINE)
        if _version.__len__() == 0:
            return None
        try:
            version = json.loads(_version[0])
            version = version['version']
            slices = version.split(" ")
            version = "%s-%s" % (slices[0], slices[2][:-1])
        except:
            version = None
    return version


def processOperatorServerVersion(serverVersion):
    cb_version = serverVersion.split(":")
    if cb_version.__len__() > 1:
        cb_version = cb_version[1]
    else:
        return "N/A"
    return cb_version


def processOperatorKubernetesVersion(kubernetesVersion):
    """Return only the major version of kubernetes"""
    if not kubernetesVersion:
        return None
    slices = kubernetesVersion.split(".")
    if slices.__len__() < 2:
        return None
    return "%s.%s" % (slices[0], slices[1])

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
    cluster = newClient()
    client = cluster.bucket("server").default_collection()
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
                    print("set failed, couchbase down?: %s" % (HOST))
                    print(e)
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
            print("exception occurred during build collection: %s" % (ex))


def newClient(password="password"):
    cluster = Cluster("couchbase://" + HOST, ClusterOptions(PasswordAuthenticator("Administrator", password)))
    return cluster


if __name__ == "__main__":

    # run build collect info thread
    tBuild = Thread(target=collectAllBuildInfo)
    tBuild.daemon = True
    tBuild.start()

    manager = multiprocessing.Manager()
    already_scraped = {}

    while True:
        try:
            for view in VIEWS:
                JOBS = {}
                if view["bucket"] not in already_scraped:
                    already_scraped[view["bucket"]] = manager.list()
                if view["bucket"] == "build":
                    pollBuild(view)
                elif view["bucket"] == "operator":
                    polloperator(view, already_scraped[view["bucket"]])
                else:
                    pollTest(view, already_scraped[view["bucket"]])
        except Exception as ex:
            print("exception occurred during job collection: %s" % (ex))
        time.sleep(120)

