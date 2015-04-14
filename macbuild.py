#aka minja, scraping macbuild like a ninja
import os
import time
import requests
import hashlib
import json
import datetime
from mc_bin_client import MemcachedClient as McdClient
from constants import *
now = datetime.datetime.now()
HOST = "127.0.0.1"
PORT = 11210
TOTAL_COUNT_LOG = {"iOS-Functionaltests": 13,
                   "iOS-UnittestsUnittests": 287}

if os.environ.get('MC_PORT'):
    PORT = int(os.environ.get('MC_PORT'))

def getJS(url):
    res = None
    try:
        res = requests.get(url=url, verify=False,timeout=3).json()
    except:
        print "[Error] url unreachable: %s" % url
        pass

    return res


def poll():
    url = "https://macbuild.hq.couchbase.com/xcode/api/integrations/filter/latest"
    latest = getJS(url)
    now = datetime.datetime.now()
    ts = now.strftime("%Y%m%d")
    build_no  = "%s-%s" % (MOBILE_VERSION, ts[-5:])
    client = McdClient(HOST, PORT)
    client.sasl_auth_plain("mobile", "")

    buildHist = {}
    for build in latest:
        if 'revisionBlueprint' not in latest[build]:
            continue
        key = latest[build]['revisionBlueprint']['DVTSourceControlWorkspaceBlueprintPrimaryRemoteRepositoryKey']
        rev = latest[build]['revisionBlueprint']['DVTSourceControlWorkspaceBlueprintLocationsKey'][key]['DVTSourceControlLocationRevisionKey']
        name = "iOS-"+latest[build]['bot']['name'].replace(" ","")
        build_id = latest[build]['number']
        results = latest[build]['buildResultSummary']
        totalCount = results['testsCount']
        failCount = results['errorCount']
        result = 'SUCCESS'

        if name in  TOTAL_COUNT_LOG:
            if totalCount == 0:
                # use historical value for total count
                totalCount = TOTAL_COUNT_LOG[name]
            elif totalCount != TOTAL_COUNT_LOG:
                # update total count log
                TOTAL_COUNT_LOG[name] = totalCount
        else:
            TOTAL_COUNT_LOG[name] = totalCount

        if (failCount > 0):
            result = 'UNSTABLE'
        component = None
        for feature in MOBILE_FEATURES:
            tag, _c = feature.split("-")
            docname = name.upper()
            docname = docname.replace("-","_")
            if tag in docname:
               component = _c 
        if component:
            doc = {'build_id': build_id,
                   'priority': 'P0',
                   'name': name,
                   'url': url,
                   'component': component,
                   'failCount':  failCount,
                   'totalCount': totalCount,
                   'result': result,
                   'os': 'iOS',
                   'build': build_no}

            key = "%s-%s" % (doc["name"], doc["build_id"])
            val = json.dumps(doc)
            try:
                #print val
                key = hashlib.md5(key).hexdigest()
                print val
                client.set(key, 0, 0, val, 0)
                buildHist[doc["build"]] = doc["build_id"]
            except Exception as ex:
                print ex
                print "set failed, couchbase down?: %s:%s"  % (HOST,PORT)

if __name__ == "__main__":
    while True:
        try:
            poll()
        except:
            pass
        time.sleep(600)

