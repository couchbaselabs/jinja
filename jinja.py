import datetime
import hashlib
import json
import os
import pydash
import re
import requests
import subprocess
import sys
import time
import ConfigParser

from threading import Thread
from urlparse import urlparse

from couchbase.bucket import LOCKMODE_WAIT
from couchbase.cluster import Cluster
from couchbase.cluster import PasswordAuthenticator
from couchbase.n1ql import N1QLQuery

from constants import *
from test_collector import TestCaseCollector

import sys
reload(sys)
sys.setdefaultencoding('utf8')

# Object of TestCaseCollector
global test_case_collector

# Hostname of couchbase server
global cb_server_host

# Dicts for jobs and bucket clients
global JOBS, ALLJOBS, CLIENTS


def create_clients(cb_cluster_ip, cb_username, cb_password):
    """
    Creates couchbase server bucket clients and store it to CLIENT dict
    Returns boolean to specify whether the creation of clients succeeded
    """
    client_creation_success = True
    try:
        cb_cluster = Cluster("couchbase://{0}". format(cb_cluster_ip))
        cb_cluster.authenticate(PasswordAuthenticator(cb_username, cb_password))
    except Exception as cluster_err:
        print("Error while connecting to couchbase cluster couchbase://{0} {1}".format(cb_cluster_ip, cluster_err))
        client_creation_success = False
        return client_creation_success

    # Initialize the list of buckets to which client will be created
    buckets_to_create_client = [qeTestSuitesBucketName]
    for tem_view in VIEWS:
        buckets_to_create_client.append(tem_view["bucket"])

    for bucket in buckets_to_create_client:
        try:
            client = cb_cluster.open_bucket(bucket, lockmode=LOCKMODE_WAIT)
            CLIENTS[bucket] = client
        except Exception as cb_bucket_error:
            print("Failed to open bucket {0} {1}".format(bucket, cb_bucket_error))
            client_creation_success = False
            break
    return client_creation_success


def get_build_document(build, bucket_name):
    client = CLIENTS[buildBucketName]
    try:
        doc = client.get(build)
        return doc.value
    except Exception:
        doc = {
            "build": build,
            "totalCount": 0,
            "failCount": 0,
            "type": bucket_name,
            "os": dict()
        }

        platform = []
        features = []
        if bucket_name == "server":
            platform = SERVER_PLATFORMS
            features = SERVER_FEATURES
        elif bucket_name == "mobile":
            platform = MOBILE_PLATFORMS
            features = MOBILE_FEATURES
        elif bucket_name == "sdk":
            platform = SDK_PLATFORMS
            features = SDK_FEATURES
        elif bucket_name == "build":
            doc["type"] = "server"
            platform = SERVER_PLATFORMS
            features = BUILD_FEATURES

        for _platform in platform:
            _features = dict()
            for _feature in features:
                _features[_feature.split('-')[1]] = dict()
            doc['os'][_platform] = _features
        return doc


def store_build_details(build_document, bucket_name):
    build = build_document['build']
    doc = get_build_document(build, bucket_name)
    os_type = build_document['os']
    component = build_document['component']
    name = build_document['name']
    sub_component = build_document['subComponent'] if "subComponent" in build_document else ""
    implemented_in = get_implemented_in(component, sub_component)

    if bucket_name not in ALLJOBS:
        ALLJOBS[bucket_name] = dict()

    if os_type not in ALLJOBS[bucket_name]:
        ALLJOBS[bucket_name][os_type] = dict()

    if component not in ALLJOBS[bucket_name][os_type]:
        ALLJOBS[bucket_name][os_type][component] = dict()

    ALLJOBS[bucket_name][os_type][component][name] = {
        "totalCount": build_document['totalCount'],
        "url": build_document['url'],
        "priority": build_document['priority'],
        "implementedIn": implemented_in
    }

    if os_type not in doc['os']:
        doc['os'][os_type] = dict()

    if component not in doc['os'][os_type]:
        doc['os'][os_type][component] = dict()

    existing_builds = doc['os'][os_type][component]
    if name in existing_builds:
        build_exist = [t for t in existing_builds[name] if t['build_id'] == build_document['build_id']]
        if build_exist.__len__() != 0:
            return
    else:
        existing_builds[name] = []

    build_to_store = {
        "build_id": build_document['build_id'],
        "claim": "",
        "totalCount": build_document['totalCount'],
        "result": build_document['result'],
        "duration": build_document['duration'],
        "url": build_document['url'],
        "priority": build_document['priority'],
        "failCount": build_document['failCount'],
        "color": build_document['color'] if 'color' in build_document else '',
        "deleted": False,
        "olderBuild": False,
        "disabled": False
    }

    doc['os'][os_type][component][name].append(build_to_store)
    pydash.sort(doc['os'][os_type][component][name], key=lambda item: item['build_id'], reverse=True)
    existing_builds[name][0]['olderBuild'] = False

    for existing_build in existing_builds[name][1:]:
        existing_build['olderBuild'] = True

    get_total_fail_count(doc)
    client = CLIENTS[buildBucketName]
    client.upsert(build, doc)


def purge_job_details(doc_id, bucket_name, disabled=False):
    client = CLIENTS[bucket_name]
    build_client = CLIENTS[buildBucketName]
    try:
        job = client.get(doc_id).value
        if 'build' not in job:
            return
        build = job['build']
        build_document = build_client.get(build)
        os_type = job['os']
        name = job['name']
        build_id = job['build_id']
        component = job['component']

        if build_document['os'][os_type][component].__len__() == 0 or \
                name not in build_document['os'][os_type][component]:
            return

        to_del_job = [t for t in build_document['os'][os_type][component][name] if t['build_id'] == build_id]
        if to_del_job.__len__() == 0:
            return

        to_del_job = to_del_job[0]
        if disabled and ('disabled' in to_del_job and not to_del_job['disabled']):
            to_del_job['disabled'] = True
            build_document['totalCount'] -= to_del_job['totalCount']
            build_document['failCount'] -= to_del_job['failCount']
        else:
            # jobs_in_name = build_document['os'][os_type][component][name]
            to_del_job['deleted'] = True
            # build_document['totalCount'] -= to_del_job['totalCount']
            # build_document['failCount'] -= to_del_job['failCount']
        build_client.upsert(build, build_document)
    except Exception:
        pass


def store_existing_jobs():
    client = CLIENTS[buildBucketName]
    try:
        stored_builds = client.get("existing_builds")
        if stored_builds != ALLJOBS:
            client.upsert("existing_builds", ALLJOBS)
    except Exception:
        client.upsert("existing_builds", ALLJOBS)


def get_from_bucket_and_store_build(bucket):
    client = CLIENTS[bucket]
    builds_query = "select distinct `build` from {0} where `build` is not null order by `build`".format(bucket)
    for row in client.n1ql_query(N1QLQuery(builds_query)):
        build = row['build']
        if not build:
            continue
        jobs_query = "select * from {0} where `build` = '{1}'".format(bucket, build)
        for job in client.n1ql_query(N1QLQuery(jobs_query)):
            doc = job[bucket]
            store_build_details(doc, bucket)


def get_total_fail_count(document):
    total_count = 0
    fail_count = 0
    for OS, os_type in document['os'].items():
        for COMPONENT, component in os_type.items():
            for JOBNAME, jobName in component.items():
                build = pydash.find(jobName, {"olderBuild": False})
                if build:
                    total_count += build['totalCount']
                    fail_count += build['failCount']
    document['totalCount'] = total_count
    document['failCount'] = fail_count


def sanitize():
    client = CLIENTS[buildBucketName]
    query = "select meta().id from `builds` where `build` is not null"
    for row in client.n1ql_query(N1QLQuery(query)):
        build_id = row['id']
        document = client.get(build_id).value
        for OS, os_type in document['os'].items():
            for COMPONENT, component in os_type.items():
                for JOBNAME, jobName in component.items():
                    pydash.sort(jobName, key=lambda item: item['build_id'], reverse=True)
                    for build in jobName[1:]:
                        build['olderBuild'] = True
        get_total_fail_count(document)
        client.upsert(build_id, document)


def store_test_cases(job_details):
    """
    Store the test cases that were run as part of the Job and their results into test case repository
    :param job_details: Details of the job that was run.
    :return: nothing
    """
    global test_case_collector
    # Return if the job was aborted, since no test results can be obtained from aborted runs.
    if job_details['result'] in ["ABORTED"]:
        return
    url = job_details['url'] + job_details['build_id'].__str__() + "/testReport"
    test_results = get_js(url)

    if (test_results is None) or ("suites" not in test_results):
        return

    for suite in test_results['suites']:
        if 'cases' not in suite:
            continue

        for case in suite['cases']:
            # if "conf_file" not in case['name']:
            #     print(case['name'])
            #     continue
            test_case_collector.store_test_result(case, job_details)


def get_js(url, params=None, retry=5, append_api_json=True):
    try:
        if append_api_json:
            res = requests.get("%s/%s" % (url, "api/json"), params=params, timeout=15)
        else:
            res = requests.get("%s" % url, params=params, timeout=15)
        data = res.json()
        return data
    except Exception as request_err:
        print("[Error] {0} unreachable: {1}".format(url, request_err))
        res = None
        if retry:
            retry = retry - 1
            return get_js(url, params, retry)
    return res


def get_action(actions, key, value=None):
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
            if (a["urlName"] != "robot") and (a["urlName"] != "testReport") and (a["urlName"] != "tapTestReport"):
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


def get_build_and_priority(params, is_mobile=False):
    build = None
    priority = DEFAULT_BUILD

    if params:
        if not is_mobile:
            build = get_action(params, "name", "version_number") or \
                    get_action(params, "name", "cluster_version") or \
                    get_action(params, "name", "build") or \
                    get_action(params, "name", "COUCHBASE_SERVER_VERSION") or \
                    DEFAULT_BUILD
        else:
            build = get_action(params, "name", "SYNC_GATEWAY_VERSION") or \
                    get_action(params, "name", "SYNC_GATEWAY_VERSION_OR_COMMIT") or \
                    get_action(params, "name", "COUCHBASE_MOBILE_VERSION") or \
                    get_action(params, "name", "CBL_iOS_Build")

        priority = get_action(params, "name", "priority") or P1
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
        # check partial rel #
        rlen = len(rel.split("."))
        while rlen < 3:
            rel = rel+".0"
            rlen += 1

        # verify rel, build
        m = re.match("^\d\.\d\.\d{1,5}", rel)
        if m is None:
            print("unsupported version_number: " + build)
            return None, None
        m = re.match("^\d{1,10}", bno)
        if m is None:
            print("unsupported version_number: " + build)
            return None, None

        build = "%s-%s" % (rel, bno.zfill(4))
    except Exception:
        print("unsupported version_number: " + build)
        return None, None

    return build, priority


def get_claim_reason(actions):
    reason = ""

    if not get_action(actions, "claimed"):
        # job not claimed
        return reason

    reason = get_action(actions, "reason") or ""
    try:
        rep_dict = {m: "<a href=\"https://issues.couchbase.com/browse/{0}\">{1}</a>".format(m, m)
                    for m in re.findall(r"([A-Z]{2,4}[-: ]*\d{4,5})", reason)}
        if rep_dict:
            pattern = re.compile('|'.join(rep_dict.keys()))
            reason = pattern.sub(lambda x: rep_dict[x.group()], reason)
    except Exception:
        pass
    return reason


def get_implemented_in(component, sub_component):
    client = CLIENTS[qeTestSuitesBucketName]
    query = "SELECT implementedIn from `QE-Test-Suites` where component = '{0}' and subcomponent = '{1}'". \
            format(component.lower(), sub_component)
    for row in client.n1ql_query(N1QLQuery(query)):
        if 'implementedIn' not in row:
            return ""
        return row['implementedIn']
    return ""


# use case# redefine 'xdcr' as 'goxdcr' 4.0.1+
def caveat_swap_xdcr(doc):
    comp = doc["component"]
    if (doc["build"] >= "4.0.1") and (comp == "XDCR"):
        comp = "GOXDCR"
    return comp


# when build > 4.1.0 and os_type is WIN skip VIEW, TUNEABLE, 2I, NSERV, VIEW, EP
def caveat_should_skip_win(doc):
    skip = False
    os_type = doc["os"]
    comp = doc["component"]
    build = doc["build"]
    if build >= "4.1.0" and os_type == "WIN" and\
        (comp == "VIEW" or comp == "TUNABLE" or comp == "2I" or
         comp == "NSERV" or comp == "VIEW" or comp == "EP"):
        if doc["name"].lower().find("w01") == 0:
            skip = True
    return skip


# when build == 4.1.0 version then skip backup_recovery
def caveat_should_skip_backup_recovery(doc):
    skip = False
    if doc["build"].find("4.1.0") == 0 and doc["component"] == "BACKUP_RECOVERY":
        skip = True
    return skip


def caveat_should_skip(doc):
    return (caveat_should_skip_win(doc)) or (caveat_should_skip_backup_recovery(doc))


def caveat_should_skip_mobile(doc):
    # skip mobile component loading for non cen os
    return (doc["component"].find("MOBILE") > -1) and (doc["os"].find("CEN") == -1)


def is_executor(name):
    return name.find("test_suite_executor") > -1


def skip_collect(params):
    skip_collect_u = get_action(params, "name", "SKIP_GREENBOARD_COLLECT")
    skip_collect_l = get_action(params, "name", "skip_greenboard_collect")
    return skip_collect_u or skip_collect_l


def is_disabled(job):
    status = job.get("color")
    return status and (status == "disabled")


def purge_disabled(job, bucket):
    client = CLIENTS[bucket]
    name = job["name"]
    bids = [b["number"] for b in job["builds"]]
    if len(bids) == 0:
        return

    high_bid = bids[0]
    for bid in xrange(high_bid):
        # reconstruct doc id
        bid = bid + 1
        old_key = "%s-%s" % (name, bid)
        old_key = hashlib.md5(old_key).hexdigest()
        # purge
        try:
            purge_job_details(old_key, bucket, disabled=True)
            client.remove(old_key)
        except Exception:
            # delete ok
            pass


def store_test(job_doc, view, first_pass=True, last_total_count=-1, claimed_builds=None):
    bucket = view["bucket"]

    claimed_builds = claimed_builds or dict()
    client = CLIENTS[bucket]

    doc = job_doc
    name_orig = doc["name"]
    url = doc["url"]

    if url.find("sdkbuilds.couchbase") > -1:
        url = url.replace("sdkbuilds.couchbase", "sdkbuilds.sc.couchbase")

    res = get_js(url, {"depth": 0})

    if res is None:
        return

    # do not process disabled jobs
    if is_disabled(doc):
        purge_disabled(res, bucket)
        return

    # operate as 2nd pass if test_executor
    if is_executor(doc["name"]):
        first_pass = False

    build_hist = dict()
    if res.get("lastBuild") is not None:
        bids = [b["number"] for b in res["builds"]]

        if is_executor(doc["name"]):
            # include more history
            start = bids[0]-500
            if start > 0:
                bids = range(start, bids[0]+1)
            bids.reverse()
        elif first_pass:
            bids.reverse()  # bottom to top 1st pass

        for bid in bids:
            old_name = JOBS.get(doc["name"]) is not None
            if old_name and bid in JOBS[doc["name"]]:
                # job already stored
                continue
            else:
                if old_name and not first_pass:
                    JOBS[doc["name"]].append(bid)

            doc["build_id"] = bid
            res = get_js(url+str(bid), {"depth": 0})
            if res is None:
                continue

            if "result" not in res:
                continue

            doc["result"] = res["result"]
            doc["duration"] = res["duration"]

            if res["result"] not in ["SUCCESS", "UNSTABLE", "FAILURE", "ABORTED"]:
                # unknown result state
                continue

            actions = res["actions"]
            params = get_action(actions, "parameters")
            if skip_collect(params):
                job = get_js(url, {"depth": 0})
                purge_disabled(job, bucket)
                return

            total_count = get_action(actions, "totalCount") or 0
            fail_count = get_action(actions, "failCount") or 0
            skip_count = get_action(actions, "skipCount") or 0
            doc["claim"] = get_claim_reason(actions)
            if total_count == 0:
                if last_total_count == -1:
                    # no tests ever passed for this build
                    continue
                else:
                    total_count = last_total_count
                    fail_count = total_count
            else:
                last_total_count = total_count

            doc["failCount"] = fail_count
            doc["totalCount"] = total_count - skip_count
            if params is None:
                # possibly new api
                if 'keys' not in dir(actions) and len(actions) > 0:
                    # actions is not a dict and has data
                    # then use the first object that is a list
                    for a in actions:
                        if 'keys' not in dir(a):
                            params = a

            component_param = get_action(params, "name", "component")
            if component_param is None:
                test_yml = get_action(params, "name", "test")
                if test_yml and test_yml.find(".yml"):
                    test_file = test_yml.split(" ")[1]
                    component_param = "systest-" + str(os.path.split(test_file)[-1]).replace(".yml", "")

            if component_param:
                sub_component_param = get_action(params, "name", "subcomponent")
                if sub_component_param is None:
                    sub_component_param = "server"
                os_param = get_action(params, "name", "OS") or get_action(params, "name", "os")
                if os_param is None:
                    os_param = doc["os"]
                if (not component_param) or (not sub_component_param) or (not os_param):
                    continue

                pseudo_name = str(os_param + "-" + component_param + "_" + sub_component_param)
                doc['subComponent'] = sub_component_param
                doc["name"] = pseudo_name
                _os, _comp = get_os_component(pseudo_name, view)
                if _os and _comp:
                    doc["os"] = _os
                    doc["component"] = _comp
                if not doc.get("os") or not doc.get("component"):
                    continue

            if bucket == "server":
                doc["build"], doc["priority"] = get_build_and_priority(params)
            else:
                doc["build"], doc["priority"] = get_build_and_priority(params, True)

            if not doc.get("build"):
                continue

            # run special caveats on collector
            doc["component"] = caveat_swap_xdcr(doc)
            if caveat_should_skip(doc):
                continue

            if caveat_should_skip_mobile(doc):
                continue

            #if bucket == "server":
            #    store_test_cases(doc)
            store_build_details(doc, bucket)

            hist_key = doc["name"] + "-" + doc["build"]
            if not first_pass and hist_key in build_hist:
                # print("REJECTED- doc already in build results: %s" % doc)
                # print(build_hist)

                # attempt to delete if this record has been stored in couchbase
                try:
                    old_key = "%s-%s" % (doc["name"], doc["build_id"])
                    old_key = hashlib.md5(old_key).hexdigest()
                    purge_job_details(old_key, bucket)
                    client.remove(old_key)
                except Exception:
                    pass

                # already have this build results
                continue

            key = "%s-%s" % (doc["name"], doc["build_id"])
            key = hashlib.md5(key).hexdigest()

            # get custom claim if exists
            try:
                old_doc = client.get(key)
                custom_claim = old_doc.value.get('customClaim')
                #if custom_claim is not None:
                #   doc["customClaim"] = custom_claim
            except Exception:
                # ok, this is new doc
                pass

            try:
                client.upsert(key, doc)
                build_hist[hist_key] = doc["build_id"]
            except Exception as upsert_err:
                print("set failed, couchbase down?: {0} {1}".format(cb_server_host, upsert_err))

            # Remove custom claim
            if doc.get("claimedBuilds"):
                del doc["claimedBuilds"]

    if first_pass:
        store_test(job_doc, view, first_pass=False, last_total_count=last_total_count, claimed_builds=claimed_builds)


def store_build(client, run, name, view):
    job = get_js(run["url"], {"depth": 0})
    if not job:
        print("No job info for build")
        return
    result = job.get("result")
    if not result:
        return

    actions = job["actions"]
    total_count = get_action(actions, "totalCount") or 0
    fail_count = get_action(actions, "failCount") or 0
    skip_count = get_action(actions, "skipCount") or 0

    if total_count == 0:
        return

    params = get_action(actions, "parameters")
    os_type = get_action(params, "name", "DISTRO") or job["fullDisplayName"].split()[2].split(",")[0]
    version = get_action(params, "name", "VERSION")
    build = get_action(params, "name", "CURRENT_BUILD_NUMBER") or get_action(params, "name", "BLD_NUM")

    if not version or not build:
        return

    build = version+"-"+build.zfill(4)

    name = os_type + "_" + name
    if get_action(params, "name", "UNIT_TEST"):
        name += "_unit"

    os_type, comp = get_os_component(name, view)
    if not os_type or not comp:
        return

    duration = int(job["duration"]) or 0

    # lookup pass count fail count version
    doc = {
      "build_id": int(job["id"]),
      "claim": "",
      "name": name,
      "url": run["url"],
      "component": comp,
      "failCount": fail_count,
      "totalCount": total_count,
      "result": result,
      "duration": duration,
      "priority": "P0",
      "os": os_type,
      "build": build
    }

    key = "%s-%s" % (doc["name"], doc["build_id"])
    print("{0}, {1}".format(key, build))
    key = hashlib.md5(key).hexdigest()

    store_build_details(doc, "build")
    try:
        if version == "4.1.0":
            # not tracking, remove and ignore
            client.remove(key)
        else:
            client.upsert(key, doc)
    except Exception as upsert_err:
        print("set failed, couchbase down?: {0} {1}".format(cb_server_host, upsert_err))


def poll_build(view):
    # using server bucket (for now)
    client = CLIENTS[serverBucketName]

    for url in view["urls"]:
        j = get_js(url, {"depth": 0})
        if j is None:
            continue

        name = j["name"]
        JOBS[name] = dict()
        for job in j["builds"]:
            build_url = job["url"]

            j = get_js(build_url, {"depth": 0, "tree": "runs[url,number]"})
            if j is None:
                continue

            try:
                if not j:
                    # single run job
                    store_build(client, job, name, view)
                else:
                    # each run is a result
                    for doc in j["runs"]:
                        store_build(client, doc, name, view)
            except Exception as store_build_err:
                print("Exception during store_build: {0}".format(store_build_err))


def get_os_component(name, view):
    _os = _comp = None
    platforms = view["platforms"]
    features = view["features"]

    for os_type in platforms:
        if os_type in name.upper():
            _os = os_type

    if _os is None:
        # attempt partial name lookup
        for os_type in platforms:
            if os_type[:3] == name.upper()[:3]:
                _os = os_type

    if _os is None and view["bucket"] != "mobile":
        # attempt initial name lookup
        for os_type in platforms:
            if os_type[:1] == name.upper()[:1]:
                _os = os_type

    # if _os_type is None:
    #     print("%s: job name has unrecognized os: %s" % (view["bucket"], name))

    for comp in features:
        tag, _c = comp.split("-")
        doc_name = name.upper()
        doc_name = doc_name.replace("-", "_")
        if tag in doc_name:
            _comp = _c
            break

    # if _comp is None:
    #     print("%s: job name has unrecognized component: %s" %  (view["bucket"], name))

    return _os, _comp


def poll_test(view):
    tem_jobs = []

    for url in view["urls"]:
        j = get_js(url, {"depth": 0, "tree": "jobs[name,url,color]"})
        if j is None or j.get('jobs') is None:
            continue

        for job in j["jobs"]:
            doc = dict()
            doc["name"] = job["name"]
            if job["name"] in JOBS:
                # already processed
                continue

            os_type, comp = get_os_component(doc["name"], view)
            if not os_type or not comp:
                if not is_executor(job["name"]):
                    # does not match os_type or comp and is not executor
                    continue

            JOBS[job["name"]] = []
            doc["os"] = os_type
            doc["component"] = comp
            doc["url"] = job["url"]
            doc["color"] = job.get("color")

            name = doc["name"]
            t = Thread(target=store_test, args=(doc, view))
            t.start()
            tem_jobs.append(t)

            if len(tem_jobs) > 10:
                # intermediate join
                for t in tem_jobs:
                    t.join()
                tem_jobs = []

        for t in tem_jobs:
            t.join()


def convert_changeset_to_old_format(new_doc, timestamp):
    old_format = dict()
    old_format['timestamp'] = timestamp
    old_format['changeSet'] = dict()
    old_format_items = []
    for change in new_doc['log']:
        item = dict()
        msg = change['message']
        # to remove the multiple '\n's, now appearing in the comment
        # that mess with Greenboard's display of reviewUrl
        item['msg'] = msg[:msg.index('Change-Id')].replace("\n", " ") + msg[msg.index('Change-Id') - 1:]
        old_format_items.append(item)
    old_format['changeSet']['items'] = old_format_items
    return old_format


def collect_build_info(url):
    client = CLIENTS[serverBucketName]
    res = get_js(url, {"depth": 1, "tree": "builds[number,url]"})
    if res is None:
        return

    builds = res['builds']
    for b in builds:
        url = b["url"]
        job = get_js(url)
        if job is not None:
            actions = job["actions"]
            params = get_action(actions, "parameters")
            version = get_action(params, "name", "VERSION")
            timestamp = job['timestamp']
            build_no = get_action(params, "name", "BLD_NUM")
            if build_no is None:
                continue
            key = version + "-" + build_no.zfill(4)
            try:
                # check if we have key
                client.get(key)
                # already collected change set
                continue
            except Exception:
                pass
            try:
                if version[:3] == "0.0":
                    continue
                if float(version[:3]) > 4.6:
                    changeset_url = CHANGE_LOG_URL+"?ver={0}&from={1}&to={2}".format(version,
                                                                                     str(int(build_no)-1), build_no)
                    job = get_js(changeset_url, append_api_json=False)
                    key = version + "-" + build_no[1:].zfill(4)
                    job = convert_changeset_to_old_format(job, timestamp)
                client.upsert(key, job)
            except Exception as set_err:
                print("set failed, couchbase down?: {0} {1}".format(cb_server_host, set_err))


def collect_all_build_info():
    while True:
        time.sleep(600)
        try:
            for url in BUILDER_URLS:
                collect_build_info(url)
        except Exception as collect_err:
            print("exception occurred during build collection: {0}".format(collect_err))


if __name__ == "__main__":
    JOBS = dict()
    ALLJOBS = dict()
    CLIENTS = dict()

    user_config_file_path = "config.cfg"
    config = ConfigParser.ConfigParser()
    config.read(user_config_file_path)

    cb_server_host = config.get("CouchbaseServer", "hostName")
    cb_server_user = config.get("CouchbaseServer", "username")
    cb_server_pass = config.get("CouchbaseServer", "password")

    client_creation_successful = create_clients(cb_server_host, cb_server_user, cb_server_pass)
    if not client_creation_successful:
        exit(1)

    """
    # run build collect info thread
    tBuild = Thread(target=collect_all_build_info)
    tBuild.start()

    sanitize()
    get_from_bucket_and_store_build("mobile")
    get_from_bucket_and_store_build("server")

    test_case_collector = TestCaseCollector(config)
    client_creation_successful = test_case_collector.create_client()
    if client_creation_successful:
        test_case_collector.store_tests()
    else:
        print(exception)
    """

    while True:
        try:
            for temView in VIEWS:
                JOBS = dict()
                if temView["bucket"] == buildBucketName:
                    poll_build(temView)
                else:
                    poll_test(temView)
            store_existing_jobs()
        except Exception as e:
            print("Exception during job collection: {0}".format(e))
        time.sleep(120)
