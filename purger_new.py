import os
import time
import requests
from couchbase.bucket import Bucket, LOCKMODE_WAIT
from couchbase.n1ql import N1QLQuery

import sys
reload(sys)
sys.setdefaultencoding('utf8')

UBER_USER = os.environ.get('UBER_USER') or ""
UBER_PASS = os.environ.get('UBER_PASS') or ""
BUCKETS = ['server', 'mobile', 'sdk']
HOST = '172.23.98.63'
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
CLIENTS = {}
BUILDS_BUCKET = "builds"

def create_clients():
    try:
        client = Bucket("couchbase://{0}/{1}".format(HOST, BUILDS_BUCKET), lockmode=LOCKMODE_WAIT)
        CLIENTS[BUILDS_BUCKET] = client
    except Exception:
        print "Error while connecting to {0}/{1}".format(HOST, BUILDS_BUCKET)


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


def purge_job_details(doc_id, type, olderBuild=False):
    client = Bucket(HOST + '/' + type)
    build_client = Bucket(HOST + '/' + 'builds')
    try:
        job = client.get(doc_id).value
        if 'build' not in job:
            return
        build = job['build']
        build_document = build_client.get(build).value
        os = job['os']
        name = job['name']
        build_id = job['build_id']
        component = job['component']
        if (build_document['os'][os][component].__len__() == 0 or name not in build_document['os'][os][component]):
            return
        to_del_job = [t for t in build_document['os'][os][component][name] if t['build_id'] == build_id]
        if to_del_job.__len__() == 0:
            return
        to_del_job = to_del_job[0]
        if olderBuild and not to_del_job['olderBuild']:
            to_del_job['olderBuild'] = True
            build_document['totalCount'] -= to_del_job['totalCount']
            build_document['failCount'] -= to_del_job['failCount']
        elif not olderBuild:
            to_del_job['deleted'] = True
        build_client.upsert(build, build_document)
    except Exception:
        pass

def purge():
    client = CLIENTS[BUILDS_BUCKET]
    query = "SELECT meta().id FROM {0}".format(BUILDS_BUCKET)
    for row in client.n1ql_query(N1QLQuery(query)):
        doc_id = row['id']
        doc = client.get(doc_id).value
	if 'os' not in doc:
		print "OS not in document {}".format(doc_id)
		continue;
        for OS in doc['os']:
            for component in doc['os'][OS]:
                for job in doc['os'][OS][component]:
                    existing_builds = doc['os'][OS][component][job]
                    if not existing_builds:
                        continue
                    latest_build = existing_builds[0]
                    for build in existing_builds:
                        if build['deleted'] or ('disabled' in build and build['disabled']):
                            continue
                        url = build['url']
                        build_id = build['build_id']
                        request = getReq("{0}/{1}".format(url, build_id))
                        if request is not None:
                            if request.status_code != 404:
                                continue
                        if len(existing_builds) <= 1 or build == latest_build:
                            continue
			print "Marking {0}/{1} as deleted in {2}".format(url, build_id, doc_id)
                        build['deleted'] = True
                        if not build['olderBuild']:
                            build['olderBuild'] = True
        update_counts(doc)
        client.upsert(doc_id, doc)


def update_counts(document):
    total_count = 0
    fail_count = 0
    for os in document['os']:
        for component in document['os'][os]:
            for job in document['os'][os][component]:
                existing_jobs = document['os'][os][component][job]
                for build in existing_jobs:
                    if build['olderBuild'] or ('disabled' in build and build['disabled']):
                        continue
                    if build['deleted']:
                        if len(existing_jobs) != 1:
                            continue
                    total_count += build['totalCount']
                    fail_count += build['failCount']
    document['totalCount'] = total_count
    document['failCount'] = fail_count


if __name__ == "__main__":
    create_clients()
    while True:
        try:
            purge()
        except Exception as e:
            print e
        print "Last run " + time.strftime("%c")
        time.sleep(500)
