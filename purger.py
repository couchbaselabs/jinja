import os
import time
import requests
from couchbase.bucket import Bucket

UBER_USER = os.environ.get('UBER_USER') or ""
UBER_PASS = os.environ.get('UBER_PASS') or ""
BUCKETS=['server', 'mobile', 'sdk']
HOST = 'couchbase://172.23.99.54'
VIEW_API="http://172.23.99.54:8092/"
JENKINS_URLS=["http://qa.sc.couchbase.com/",
#             "http://qa.hq.northscale.net/",
             "http://ci.sc.couchbase.com/",
             "http://mobile.jenkins.couchbase.com/",
             "http://sdkbuilds.sc.couchbase.com/view/LCB/job/feature/",
             "http://sdkbuilds.sc.couchbase.com/view/LCB/job/situational-lcb/",
             "http://sdkbuilds.sc.couchbase.com/view/JAVA/job/situational-java/",
             "http://sdkbuilds.sc.couchbase.com/view/.NET/",
             "http://qa.sc.couchbase.com/view/extended/",
             "http://qa.sc.couchbase.com/view/OS%20Certification/",
             "http://uberjenkins.sc.couchbase.com:8080/"]

def getReq(url, timeout=10):

    if url.find("qa.hq.northscale.net") > -1:
       return None  # is down

    rc = None
    try:
       rc = requests.get(url, timeout=timeout)
    except Exception as ex:
       print ex
    return rc

def queryJenkinsJobs():
    _JOBS = []

    for url in JENKINS_URLS:
        url=url+"api/json"
        r = getReq(url) 
    
        if r is None:
           continue 

        if r.status_code == 200:
            data = r.json()
            jobs = data.get("jobs")
            job_names = [str(j['url']) for j in jobs]
            _JOBS.extend(job_names)
        else:
            "ERROR Jenkins url: (%s, %s)" % (r.status_code, url)

    return _JOBS

def purge(bucket, known_jobs):


    client = Bucket(HOST+'/'+bucket)

    DDOC='/'.join([VIEW_API,bucket,'_design',bucket,'_view'])
    BUILDS_Q = DDOC+"/data_by_build?full_set=true&group_level=1&inclusive_end=true&reduce=true&stale=false"
    ALL_PLATFORMS = []
    ALL_COMPONENTS = []

    # purger for all platforms+comonent combo of each build
    r = getReq(BUILDS_Q)
    if r is None:
        return

    data = r.json()
    rows = data.get('rows')
    if rows is None:
       print "No data for: "+bucket 
       return 
    for row in rows:
        build = row['key'][0]
        if not build:
            continue

        url = DDOC+"/jobs_by_build?startkey=%22"+build+"%22&endkey=%22"+build+"_%22&inclusive_end=true&reduce=false&stale=false"

	r = getReq(url)
	if r is None:
            continue

        data = r.json()

        # all jobs
        JOBS = {}
        if not data.get('rows'): continue

        for job in data['rows']:
            _id = str(job['id'])
            val = job['value']
            name = val[0]
            os = val[1]
            comp = val[2]
            url = val[3]
            cnt = val[5]
            bid = val[6]
            isExecutor = False
            url_noauth = None
            if url.find("@") > -1: # url has auth, clean
                url_noauth = "http://"+url.split("@")[1]

            if url.find("test_suite_executor") > -1:
                isExecutor = True 

            if comp in ["UNIT","BUILD_SANITY"]:
                continue # don't purge build jobs

            # if job is unknown try to manually get url
            url_find = url_noauth or url
            if url_find not in known_jobs and not isExecutor:
 
                r = getReq(url)
                if r is None: 
                    continue 
                if r.status_code == 404:
                    try:
                        client.remove(_id)
                        print "****MISSING*** %s_%s: %s:%s:%s (%s,%s)" % (build, _id, os, comp, name, val[5], bid)
                    except:
                        pass
                    continue

            if os in JOBS:
                if comp in JOBS[os]:
                    match = [(i, n) for i, n in enumerate(JOBS[os][comp]) if n[0] == name]
                    if len(match) > 0:
                        idx = match[0][0]
                        oldBid = match[0][1][1]
                        oldDocId = match[0][1][2]
                        if oldBid > bid:
                           # purge this docId because it is less this saved bid
                           try:
                               client.remove(_id)
                               print "****PURGE-KEEP*** %s_%s: %s:%s:%s (%s,%s < %s)" % (build, _id, os, comp, name, val[5], bid, oldBid)
                           except:
                               pass
                        else:
                           # bid must exist in prior to purge replace

                           r = getReq(url+"/"+str(bid))
                           if r is None: 
                               continue 
                           if r.status_code == 404:
                             # delete this newer bid as it no longer exists
                             try:
                                 client.remove(_id)
                             except:
                                 pass
                           else:
                             # purge old docId
                             try:
                                 client.remove(oldDocId)
                                 # use this bid as new tracker
                                 JOBS[os][comp][idx] = (name, bid, _id)
                                 print "****PURGE-REPLACE*** %s_%s: %s:%s:%s (%s,%s > %s)" % (build, _id, os, comp, name, val[5], bid, oldBid)
                             except:
                                 pass
                        continue
                    else:
                        # append to current comp
                        JOBS[os][comp].append((name,bid, _id))
                else:
                    # new comp
                    JOBS[os][comp] = [(name, bid, _id)]
            else:
                # new os
                JOBS[os] = {}
                JOBS[os][comp] = [(name, bid, _id)]

if __name__ == "__main__":
    while True:
        try:
            known_jobs = queryJenkinsJobs()
            for bucket in BUCKETS:
                purge(bucket, known_jobs)
        except Exception as ex:
            print ex
            pass

        print "Last run " + time.strftime("%c")
        time.sleep(500)
