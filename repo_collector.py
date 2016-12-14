import sys
import time
import requests
from couchbase.bucket import Bucket

BUILDER_URLS = ["http://server.jenkins.couchbase.com/job/watson-build/"]
HOST = '127.0.0.1'
if len(sys.argv) == 2:
    HOST = sys.argv[1]

def getJS(url, params = None, retry = 5):
    res = None

    try:
        res = requests.get("%s/%s" % (url, "api/json"), params = params, timeout=15)
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

def collectBuildInfo(url):

        client = Bucket(HOST+'/builds')
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
                ts = timestamp(int(job["timestamp"])/1000)
                doc = {"ts": ts, "build": key}
                try:
                    print doc
                    client.upsert(key, doc)
                except:
                    print "set failed, couchbase down?: %s"  % (HOST)

def collectAllBuildInfo():
    while True:
       try:
           for url in BUILDER_URLS:
               collectBuildInfo(url)
       except Exception as ex:
           print "exception occurred during build collection: %s" % (ex)

def timestamp(ts):
    ts_date = time.gmtime(ts)
    ts_year = ts_date.tm_year
    ts_month = str(ts_date.tm_mon).zfill(2)
    ts_day = str(ts_date.tm_mday).zfill(2)
    return "%d-%s-%s" % (ts_year, ts_month, ts_day)

if __name__ == "__main__":
   collectAllBuildInfo()
