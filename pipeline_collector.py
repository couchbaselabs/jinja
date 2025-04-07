import configparser
import logging
import re
import time
import traceback
import urllib.parse
from datetime import timedelta, datetime, timezone
from logging.handlers import TimedRotatingFileHandler

import requests
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions, QueryOptions

JOBS = {}

JOBS_LOGGER = logging.getLogger("jobs")
JOBS_LOGGER.setLevel(logging.INFO)
jobs_handler = TimedRotatingFileHandler("pipeline_jobs.log", "D",
                                        backupCount=15)
jobs_handler.setLevel(logging.INFO)
jobs_handler.setFormatter(logging.Formatter("%(name)s - %(asctime)s: "
                                            "%(message)s"))
JOBS_LOGGER.addHandler(jobs_handler)

ERROR_LOGGER = logging.getLogger("errors")
ERROR_LOGGER.setLevel(logging.INFO)
error_handler = TimedRotatingFileHandler("pipeline_errors.log", "D",
                                         backupCount=15)
error_handler.setLevel(logging.INFO)
error_handler.setFormatter(logging.Formatter("%(name)s - %(asctime)s: "
                                            "%(message)s"))
ERROR_LOGGER.addHandler(error_handler)

config = configparser.ConfigParser()
config.read("credentials.ini")

HOST = config.get("host", "url")
USERNAME=config.get("host", "username")
PASSWORD=config.get("host", "password")
JENKINS_URL = "http://qe-jenkins1.sc.couchbase.com/"
GITOWNER = 'couchbasecloud'
GITREPO = 'couchbase-cloud'
ENVIRONMENT_PARAMS = ['Environment', 'env']
CP_VERSION_PARAMS = ['pr_commit', 'Version', 'cp_branch', 'pr_commit']
CP_BRANCH_PARAMS = ['GIT_BRANCH']
CB_VERSION_PARAMS = ["server_version"]
CB_BUILD_PARAMS = ['server_build_num', 'cbs_image']
CLOUD_PROVIDER_PARAMS = ['provider', 'Provider', 'CLOUD_SERVICE_PROVIDER']
COMPONENTS_PARAMS = ["component"]
COMPONENTS_DICT = {
    "CP-CLI": "CP-CLI",
    "UI": "UI",
    "SECURITY": "SECURITY",
    "V4": "API_TESTS",
    "TAF" : "FUNCTIONAL",
    "TERRAFORM": "TERRAFORM",
    "VOLUME": "VOLUME",
    "PERF": "PERF",
    "SDK": "SDK",
}


def getJS(url, params=None, retry=5, append_api_json=True):
    res = None
    url = url.rstrip("/")
    try:
        if append_api_json:
            res = requests.get("{0}/{1}".format(url, "api/json"), params=params, timeout=15)
        else:
            res = requests.get("{0}".format(url), params=params, timeout=15)
        if res.status_code == 404:
            print("404 Error for URL: %s" % res.url)
            return None
        elif res.status_code != 200:
            print("[Error] url unreachable: %s" % res.url)
            return None
        data = res.json()
        return data
    except Exception as e:
        print("[Error] url unreachable: %s/api/json" % url)
        print(e)
        traceback.print_exc()
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


def buildFinished(res):
    if res is None or "result" not in res or "building" not in res:
        return False
    if res["result"] not in ["SUCCESS", "UNSTABLE", "FAILURE", "ABORTED"] or res["building"]:
        return False
    return True


def getParameter(paramList, params):
    parameter = None
    for param in paramList:
        parameter = getAction(params, 'name', param)
        if parameter:
            break
    return parameter


def getGitHubtoken():
    token = config.get(f"https://github.com/{GITOWNER}/{GITREPO}"
                         "/", "password")
    return token


def getCommitDetails(runDate):
    personalAccessToken = getGitHubtoken()
    datetimeTimestamp = datetime.fromtimestamp(
        runDate / 1000, timezone.utc)
    # Convert datetime to ISO 8601 format
    isoTimestamp = datetimeTimestamp.isoformat()
    url = f'https://api.github.com/repos/{GITOWNER}/{GITREPO}/commits'
    # Headers for authentication
    headers = {
        'Authorization': f'token {personalAccessToken}',
        'Accept': 'application/vnd.github.v3+json'
        }

    # Parameters to get commits before the timestamp
    params = {
        'until': isoTimestamp,
        'sha': 'main',
        # or the name of your default branch if it's not 'main'
        'per_page': 1
        # Fetch fewer commits to find the last one before the timestamp
        }
    response = requests.get(url, headers=headers, params=params)
    commits = response.json()
    commitShaShort = None
    commitUrl = None
    if response.status_code == 200 and commits:
        commit = commits[0]  # Since we fetch fewer commits,
        # we directly select the first one
        commitSha = commit['sha']
        commitShaShort = commitSha[:7]
        commitUrl = f"https://github.com/{GITOWNER}/{GITREPO}/commit/" \
                     f"{commitSha}"
    return (commitShaShort, commitUrl)


def getCPVersion(jobParams, runDate):
    cpVersion = getParameter(CP_VERSION_PARAMS, jobParams)
    commitUrl = None
    if not cpVersion:
        cpVersion = "main"
    if cpVersion == "main":
        # Try to get the branch from the job, if present
        branch = getParameter(CP_BRANCH_PARAMS, jobParams)
        if branch:
            pattern = r'^[^-]*-[^-]*-(.*)$'
            match = re.search(pattern, branch)
            if match:
                cpVersion = match.group(1)
            commitUrl = f"https://github.com/{GITOWNER}/" \
                        f"{GITREPO}/tree/{branch}"
        else:
            commitSha, commitUrl = getCommitDetails(runDate)
            cpVersion = commitSha
    return (cpVersion, commitUrl)


def getCBVersion(params):
    cbVersion = "default"
    version = getParameter(CB_VERSION_PARAMS, params)
    if version:
        # Try to get the build param if available
        build = getParameter(CB_BUILD_PARAMS, params)
        if build:
            if "AZURE" in build.upper() or "AWS" in build.upper() or \
                    "GCP" in build.upper():
                # Get the CB build number from the parameter
                pattern = r'\b(\d+(?:\.\d+){2})-?v?(\d+)\b'
                matches = re.search(pattern, build)
                if matches:
                    cbVersion = f"{matches.group(1)}-{matches.group(2)}"
            else:
                cbVersion = f"{version}-{build}"
        else:
            cbVersion = version
    return cbVersion

def getTestResults(url):
    testResultsData = getJS(f"{url}testReport")
    if not testResultsData:
        return ([],[])
    passedTests = []
    failedTests = []
    try:
        suites = testResultsData['suites']
        for suite in suites:
            testSuite = suite['name']
            testCases = suite['cases']
            for testCase in testCases:
                testName = testCase['name']
                className = testCase['className']
                status = testCase['status']
                duration = testCase['duration']
                errorDetails = testCase['errorDetails']
                errorStackTrace = testCase['errorStackTrace']
                test = {
                    "name" : testName,
                    "className": className,
                    "suite": testSuite,
                    "status": status,
                    "duration": duration,
                    "errorDetails": errorDetails,
                    "errorStackTrace": errorStackTrace
                    }
                if status == "PASSED":
                    passedTests.append(test)
                else:
                    failedTests.append(test)
    except Exception as e:
        ERROR_LOGGER.error(e)
    return (passedTests, failedTests)


def newClient():
    user = USERNAME
    password = PASSWORD
    auth = PasswordAuthenticator(user, password)
    options = ClusterOptions(auth)
    options.apply_profile("wan_development")
    cluster = Cluster(HOST, options)
    cluster.wait_until_ready(timedelta(seconds=30))
    return cluster


CLUSTER = newClient()
SERVER_BUCKET = CLUSTER.bucket("greenboard")


def getPipelineDetails(pipelineName, buildId, pipelineUrl):
    docId = f"{pipelineName}_{buildId}"
    pipelineCollection = SERVER_BUCKET.scope('capella').collection(
        'pipeline')
    try:
        pipelineDoc = pipelineCollection.get(docId)
        if pipelineDoc.success:
            pipelineDoc = pipelineDoc.content_as[dict]
            if pipelineDoc['result']:
                return pipelineDoc
            else:
                print(f"Pipeline results weren't captured previously. "
                      f"Collecting data again for {docId}")
    except Exception as e:
        print(f"doc {docId} not found")
    pipelineDetails = getJS(f"{JENKINS_URL}{pipelineUrl}{buildId}")
    if not pipelineDetails:
        print(f"Could not fetch details for {JENKINS_URL}"
              f"{pipelineUrl}{buildId}")
        return None
    actions = pipelineDetails['actions']
    params = getAction(actions, "parameters")
    environment = getParameter(ENVIRONMENT_PARAMS, params)
    if not environment:
        environment = "sbx"
    runDate = pipelineDetails['timestamp']
    cpVersion, commitUrl = getCPVersion(params, runDate)
    cbVersion = getCBVersion(params)
    duration = pipelineDetails['duration']
    description = pipelineDetails['description']
    url = pipelineDetails['url']
    result = pipelineDetails['result']
    pipelineDoc = {
        "name": pipelineName,
        "buildId": buildId,
        "url": url,
        "environment": environment,
        "cpVersion": cpVersion,
        "cbVersion": cbVersion,
        "commitUrl": commitUrl,
        "result": result,
        "runDate": runDate,
        "duration": duration,
        "description": description,
        "jobs": {}
        }
    pipelineCollection.upsert(docId, pipelineDoc)
    return pipelineDoc

def getDispatcherDetails(jobName, buildId):
    docId = f"{jobName}_{buildId}"
    dispatcherCollection = SERVER_BUCKET.scope('capella').collection(
        'dispatcher')
    try:
        jobDoc = dispatcherCollection.get(docId)
        if jobDoc.success:
            print(f"{jobName} already collected for {buildId}. "
                  f"Continue with rest of collection")
            return jobDoc.content_as[dict]
    except:
        pass
    jobDetails = getJS(f"{JENKINS_URL}/job/{jobName}/{buildId}")
    if not jobDetails:
        print(f"Could not find details for {JENKINS_URL}{jobName}/{buildId}")
        return None
    if not buildFinished(jobDetails):
        print(f"Jobs {JENKINS_URL}/job/{jobName}/{buildId} is still "
              f"running.")
        return None
    actions = jobDetails['actions']
    causes = getAction(actions, "causes")
    pipelineJobName = getAction(causes, "upstreamProject")
    if pipelineJobName == jobName:
        # This is rebuild from same job. Skipping collection for now
        print(f"This is rebuild from same job. Skipping collection "
              f"for {jobName}/{buildId} now")
        return None
    if not pipelineJobName:
        print(f"This is direct run from job. Skipping collection for "
              f"{jobName}/{buildId} now")
        return None
    pipelineBuildId = getAction(causes, "upstreamBuild")
    pipelineUrl = getAction(causes, "upstreamUrl")
    getPipelineDetails(pipelineJobName, pipelineBuildId, pipelineUrl)
    consoleTextUrl = f"{JENKINS_URL}/job/{jobName}/" \
                     f"{buildId}/consoleText"
    consoleText = None
    try:
        res = requests.get(consoleTextUrl, timeout=30)
        if res.status_code == 200:
            consoleText = res.content
    except Exception as e:
        print(e)
    if not consoleText:
        return None
    # get all links from the console text
    urls = re.findall(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%['
        r'0-9a-fA-F][0-9a-fA-F]))+',
        consoleText.__str__())
    descriptors = []
    for url in urls:
        # Parse the URL's query string
        query_string = urllib.parse.urlparse(url).query
        # Parse the query parameters into a dictionary
        params = urllib.parse.parse_qs(query_string)
        # Check if the 'descriptor' parameter is in the params
        if 'descriptor' in params:
            # Decode the first 'descriptor' value (assuming there can
            # be multiple instances)
            descriptor_value = urllib.parse.unquote(
                params['descriptor'][0])
            descriptors.append(descriptor_value)
    dispatcherDoc = {
        "pipelineJob": pipelineJobName,
        "pipelineJobUrl": pipelineUrl,
        "pipelineJobID": pipelineBuildId,
        "dispatched": descriptors
        }
    dispatcherCollection.upsert(docId, dispatcherDoc)
    return dispatcherDoc


def getJobDetails(jobName, buildId):
    docId = f"{jobName}_{buildId}"
    jobsCollection = SERVER_BUCKET.scope('capella').collection(
        'jobs')
    try:
        jobDoc = jobsCollection.get(docId)
        if jobDoc.success:
            print(f"{jobName} already collected for {buildId}. "
                  f"Continue with rest of collection")
            return jobDoc.content_as[dict]
    except Exception as e:
        print(f"doc {docId} not found")
    jobDetails = getJS(f"{JENKINS_URL}/job/{jobName}/{buildId}")
    if not jobDetails:
        print(f"Could not find details for {JENKINS_URL}{jobName}/{buildId}")
        return None
    if not buildFinished(jobDetails):
        print(f"Jobs {JENKINS_URL}/job/{jobName}/{buildId} is still "
              f"running.")
        return None
    actions = jobDetails['actions']
    params = getAction(actions, "parameters")
    if "test_suite_executor" in jobDetails['url']:
        descriptor = getParameter(['descriptor'], params)
        query = "SELECT pipelineJob, pipelineJobUrl, pipelineJobID FROM " \
                "`greenboard`.`capella`.`dispatcher` " \
                "where $1 in dispatched"
        queryResult = CLUSTER.query(query, QueryOptions(
            positional_parameters=[descriptor]))
        pipelineJobName = None
        for row in queryResult.rows():
            pipelineJobName = row['pipelineJob']
            pipelineUrl = row['pipelineJobUrl']
            pipelineBuildId = row['pipelineJobID']
        if not pipelineJobName:
            print(f"Dispatcher job for this job not found. The "
                  f"Dispatcher might still be running. Skipping job "
                  f"collection for now. {jobName}/{buildId}")

    else:
        causes = getAction(actions, "causes")
        pipelineJobName = getAction(causes, "upstreamProject")
        pipelineBuildId = getAction(causes, "upstreamBuild")
        pipelineUrl = getAction(causes, "upstreamUrl")
    if pipelineJobName == jobName:
        # This is rebuild from same job. Skipping collection for now
        print(f"This is rebuild from same job. Skipping collection "
              f"for {jobName}/{buildId} now")
        return None
    if not pipelineJobName:
        print(f"This is direct run from job. Skipping collection for "
              f"{jobName}/{buildId} now")
        return None
    pipelineDoc = getPipelineDetails(pipelineJobName,
                                     pipelineBuildId, pipelineUrl)
    if not pipelineDoc:
        print(f"Could not retreive pipeline job details for "
              f"{pipelineJobName}/{pipelineBuildId}. Not storing the "
              f"job details for {jobName}/{buildId}")
        return None

    result = jobDetails['result']
    totalCount = getAction(actions, 'totalCount') or 0
    failCount = getAction(actions, "failCount") or 0
    runDate = jobDetails['timestamp']
    duration = jobDetails['duration']
    url = jobDetails['url']
    pipelineId = f"{pipelineJobName}_{pipelineBuildId}"
    # Show the spec that ran if UI jobs
    if "UI" in jobName.upper() or "CP-CLI" in jobName.upper():
        spec = getParameter(['SPEC', "SCENARIO"], params)
        if spec:
            try:
                spec = spec.rstrip("/").split("/")
                spec = "_".join(spec[-2:]).rstrip(".yaml")
                jobName = f"{jobName}_{spec}"
            except Exception as e:
                ERROR_LOGGER.error(e)
    provider = getParameter(CLOUD_PROVIDER_PARAMS, params)
    if not provider:
        checkName = ""
        if "CP-CLI" in jobName.upper():
            spec = getParameter(['SPEC', "SCENARIO"], params)
            if spec:
                checkName = spec.upper()
        else:
            checkName = jobName.upper()
        if "AWS" in checkName:
            provider = "aws"
        elif "GCP" in checkName:
            provider = "gcp"
        elif "AZURE" in checkName:
            provider = "azure"
        else:
            provider = "aws" # Default to aws
    # Get the component for the job
    component = getParameter(COMPONENTS_PARAMS, params)
    if not component:
        # Try to get the component from job name instead
        for key in COMPONENTS_DICT.keys():
            value = COMPONENTS_DICT[key]
            if key in jobName.upper():
                component = value
                if key != "TAF":
                    break # Continue only if TAF comes first in the list
                    # to try and get exact component

    if "test_suite_executor" in url:
        subcomponent = getParameter(['subcomponent'], params)
        if subcomponent:
            # Update job name to more specific name in case the job
            # is test suite executor
            jobName = f"{provider}-{component}-{subcomponent}"
    pipelineDocChanged = False
    if jobName in pipelineDoc['jobs']:
        jobs = pipelineDoc['jobs'][jobName]
        if buildId not in jobs:
            jobs.append(buildId)
            jobs.sort()
            pipelineDocChanged = True
    else:
        pipelineDoc['jobs'][jobName] = [buildId]
        pipelineDocChanged = True
    [passedTests, failedTests] = getTestResults(url)
    jobName = f"{provider}_{jobName}"
    jobDoc = {
        "name": jobName,
        "buildId": buildId,
        "url": url,
        "result": result,
        "totalCount": totalCount,
        "failCount": failCount,
        "passCount": totalCount - failCount,
        "pipelineID": pipelineId,
        "pipelineJob": pipelineJobName,
        "pipelineJobUrl": pipelineDoc['url'],
        "runDate": runDate,
        "duration": duration,
        "provider": provider,
        "component": component,
        "passedTests" : passedTests,
        "failedTests": failedTests
        }
    jobsCollection.upsert(docId, jobDoc)
    if pipelineDocChanged:
        pipelineCollection = SERVER_BUCKET.scope('capella').collection(
            'pipeline')
        pipelineCollection.upsert(pipelineId, pipelineDoc)
    return jobDoc

def collectPipelineJobs():
    pipelineJobsDetails = getJS(f"{JENKINS_URL}view/PipelineJobs")
    if not pipelineJobsDetails:
        return
    jobs = pipelineJobsDetails['jobs']
    try:
        for job in jobs:
            jobName = job['name']
            jobUrl = job['url']
            jobDetails = getJS(jobUrl)
            if not jobDetails:
                print(f"Couldn't fetch details for {jobUrl}")
            builds = jobDetails['builds']
            for build in builds:
                buildId = build['number']
                if "dispatcher" in jobName:
                    dispatchDoc = getDispatcherDetails(jobName, buildId)
                    if dispatchDoc:
                        JOBS_LOGGER.info(f"Collected dispatcher "
                                         f"details for {jobName}/{buildId}")
                else:
                    jobDoc = getJobDetails(jobName, buildId)
                    if jobDoc:
                        JOBS_LOGGER.info(
                            f"Collected for {jobName}/{buildId}")
    except Exception as e:
        ERROR_LOGGER.error(e)
        ERROR_LOGGER.error(traceback.format_exc())


if __name__ == "__main__":
    while True:
        collectPipelineJobs()
        time.sleep(60)