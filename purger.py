import os
import time
import requests
from couchbase.n1ql import N1QLQuery
from couchbase.bucket import Bucket, AuthError
from couchbase.cluster import Cluster, PasswordAuthenticator

import sys
reload(sys)
sys.setdefaultencoding('utf8')

UBER_USER = os.environ.get('UBER_USER') or ""
UBER_PASS = os.environ.get('UBER_PASS') or ""
BUCKETS = ['server', 'mobile']
#BUCKETS = ['server', 'mobile', 'sdk']
HOST = 'couchbase://172.23.98.63'
VIEW_API = "http://172.23.98.63:8092/"
JENKINS_URLS = ["http://qa.sc.couchbase.com/",
                #"http://qa.hq.northscale.net/",
                "http://ci.sc.couchbase.com/",
                "http://mobile.jenkins.couchbase.com/",
                "http://sdkbuilds.sc.couchbase.com/view/LCB/job/feature/",
                "http://sdkbuilds.sc.couchbase.com/view/LCB/job/sdk-lcb-situational/",
                "http://sdkbuilds.sc.couchbase.com/view/JAVA/job/situational-java/",
                "http://sdkbuilds.sc.couchbase.com/view/.NET/",
                #"http://qa.sc.couchbase.com/view/extended/",
                "http://qa.sc.couchbase.com/view/OS%20Certification/",
                "http://uberjenkins.sc.couchbase.com:8080/"]


def newClient(bucket, password="password"):
    client = None
    try:
        client = Bucket(HOST + '/' + bucket)

    except Exception:

        # try rbac style auth
        endpoint = '{0}:{1}?select_bucket=true'.format(HOST, 8091)
        cluster = Cluster(endpoint)
        auther = PasswordAuthenticator("Administrator", password)
        cluster.authenticate(auther)
        client = cluster.open_bucket(bucket)

    return client

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
        url = url + "api/json"
        r = getReq(url)

        if r is None:
            continue

        if r.status_code == 200:
            data = r.json()
            jobs = data.get("jobs")
            job_names = [str(j['url']) for j in jobs]
            _JOBS.extend(job_names)
        else:
            print "ERROR Jenkins url: (%s, %s)" % (r.status_code, url)

    return _JOBS


def purge(bucket, known_jobs):
    client = newClient(bucket) 
    builds_query = "select distinct `build` from {0} where `build` is not null order by `build`".format(bucket)
    for row in client.n1ql_query(N1QLQuery(builds_query)):
        build = row['build']
        if not build:
            continue
        jobs_by_build_query = "SELECT meta().id,name,os,component,url,totalCount,build_id from {0} " \
                              "where `build` = '{1}'".format(bucket, build)
        # all jobs
        JOBS = {}
        for job in client.n1ql_query(N1QLQuery(jobs_by_build_query)):
            _id = job['id']
            name = job['name']
            os = job['os']
            comp = job['component']
            url = job['url']
            count = job['totalCount']
            bid = job['build_id']
            isExecutor = False
            url_noauth = None
            if url.find("@") > -1:  # url has auth, clean
                url_noauth = "http://" + url.split("@")[1]

            if url.find("test_suite_executor") > -1:
                isExecutor = True

            if comp in ["UNIT", "BUILD_SANITY"]:
                continue  # don't purge build jobs

            # if job is unknown try to manually get url
            url_find = url_noauth or url
            if url_find not in known_jobs and not isExecutor:

                r = getReq(url)
                if r is None:
                    continue
                if r.status_code == 404:
                    try:
                        client.remove(_id)
                        print "****MISSING*** %s_%s: %s:%s:%s (%s,%s)" % (build, _id, os, comp, name, count, bid)
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
                                print "****PURGE-KEEP*** %s_%s: %s:%s:%s (%s,%s < %s)" % (
                                build, _id, os, comp, name, count, bid, oldBid)
                            except:
                                pass
                        else:
                            # bid must exist in prior to purge replace

                            r = getReq(url + "/" + str(bid))
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
                                    print "****PURGE-REPLACE*** %s_%s: %s:%s:%s (%s,%s > %s)" % (
                                    build, _id, os, comp, name, count, bid, oldBid)
                                except:
                                    pass
                        continue
                    else:
                        # append to current comp
                        JOBS[os][comp].append((name, bid, _id))
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

