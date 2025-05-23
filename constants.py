import os

UBER_USER = os.environ.get('UBER_USER') or ""
UBER_PASS = os.environ.get('UBER_PASS') or ""

## --- PLATFORMS --- ##
SERVER_PLATFORMS = ["UBUNTU", "CENTOS", "DEBIAN", "WIN",
                    "MAC", "SUSE",
                    "OEL", "DOCKER", "RHEL", "AMZN2", "CLOUD"]
SG_PLATFORMS = ["CEN7", "CEN006", "WINDOWS", "MACOSX", "CENTOS"]
SDK_PLATFORMS = [".NET", "JAVA", "LIBC", "NODE"]
MOBILE_VERSION = ["1.1.0", "1.2.0", "1.3", "1.4"]

SG_FILTERS = ["SYNCGATEWAY", "SYNC-GATEWAY"]
OPERATOR_PLATFORMS = ["GKE-GKE", "AKS-AKS", "EKS-EKS" , "OC-OC"]
CAPELLA_PLATFORMS = ["AWS", "GCP", "AZURE"]

## --- FEATURES --- ##
SERVER_FEATURES = [
    "BHIVE-BHIVE",
    "COLUMNAR-COLUMNAR",
    "THROTTLING-THROTTLING",
    "METERING-METERING",
    "TENANT_MGMT-TENANT_MGMT",
    "TENANT_MANAGEMENT-TENANT_MGMT",
    "E2E-E2E",
    "CE_ONLY-CE_ONLY",
    "DURABILITY-DURABILITY",
    "ATOMICITY-ATOMICITY",
    "COMPRESSION-COMPRESSION",
    "IPV6-IPV6",
    "LOGREDACTION-LOG_REDACTION",
    "EVENTING-EVENTING",
    "RBAC-RBAC",
    "PLASMA-PLASMA",
    "IMPORT-IMPORT_EXPORT",
    "EXPORT-IMPORT_EXPORT",
    "CONVERG-MOBILE_CONVERGENCE",
    "ANALYTIC-ANALYTICS",
    "EPHEM-EPHEMERAL",
    "AUTOFAILOVER-AUTO_FAILOVER",
    "FAST-FAST_FAILOVER",
    "SYSTEST-SYSTEST",
    "SYSTEM-SYSTEST",
    "SUBDOC-SUBDOC",
    "FTS-FTS",
    "MOBILEUPGRADE-MOBILE_UPGRADE",
    "EEONLY-EEONLY",
    "SDK-SDK",
    "MOBILE-MOBILE",
    "CERTIFY-OS_CERTIFY",
    "BREAKPAD-BREAKPAD",
    "CBSGW-SYNCGW",
    "SYNC-MOBILE",
    "RZA-RZA",
    "GEO-GEO",
    "EPENG-EP",
    "SECU-SECURITY",
    "TUNABLE-TUNABLE",
    "2I_REBALANCE-2I_REBALANCE",
    "2I-2I_MOI",
    "NSERV-NSERV",
    "RQG-RQG",
    "N1QL-QUERY",
    "TUQ-QUERY",
    "VIEW-VIEW",
    "QUERY-QUERY",
    "GOXDCR-GOXDCR",
    "LWW-GOXDCR",
    "FOREST-FORESTDB",
    "XDCR-XDCR",
    "BACKUP_RECOVERY-BACKUP_RECOVERY",
    "BKRS-BACKUP_RECOVERY",
    "UPGRADE-UPGRADE",
    "UPGRA-UPGRADE",
    "TRANSFER-TOOLS",
    "CLI-CLI",
    "_UI-UI",
    "TOOLS-TOOLS",
    "IBR-TOOLS",
    "CONNECTION-TOOLS",
    "MAGMA-MAGMA",
    "COLLECTIONS-COLLECTIONS",
    "SANITY-SANITY",
    "SANIT-SANITY",
    "SMOKE-SANITY",
    "COUCHSTORE-COUCHSTORE",
    "DCP-EP",
    "UNIT-UNIT", "MEMDB-2I",
    "SANIT-BUILD_SANITY",
    "CBOP-OPERATOR",
    "NUTSHELL-NUTSHELL",
    "BACK-BACKUP_RECOVERY",
    "RECOV-BACKUP_RECOVERY",
    "REB-NSERV",
    "PAUSE-NSERV",
    "FAILOVER-NSERV",
    "GSI-2I_REBALANCE"
]

LITE_FEATURES = ["P2P-P2P",
                 "FUNCT-FUNCTIONAL",
                 "UPGR-UPGRADE",
                 "LISTENER-LISTENER",
                 "SYSTEM-SYSTEM",
                 "DECODER-DECODER",
                 "SANITY-SANITY"]

SG_FEATURES = ["SANITY-SANITY",
               "SANIT-SANITY",
               "FUNCTIONAL-FUNCTIONAL",
               "UPGRADE-UPGRADE"]

SDK_FEATURES = [
    "LONGEVITY-STRESS",
    "SITUATIONAL-SITUATIONAL",
    "FEATURE-FEATURE",
    "CORE-FEATURE",
    "SNAPSHOT-CLIENT",
    "CLIENT-CLIENT"
]

BUILD_FEATURES = ["SANITY-BUILD_SANITY", "UNIX-UNIT", "UNIT-UNIT"]

CAPELLA_FEATURES = [
    "UI-UI",
    "SDK-SDK",
    "CAPELLA_VOLUME-VOLUME",
    "CP_CLI_RUNNER-CP_CLI",
    "DAPI_SANITY-DAPI",
    "NEBULA-DIRECT_NEBULA",
    "PERF-PERF",
    "VOLUME-VOLUME",
    "CHAOS-CHAOS",
    "THROTTLING-THROTTLING",
    "METERING-METERING",
    "TENANT_MGMT-TENANT_MANAGEMENT",
    "TENANT_MANAGEMENT-TENANT_MANAGEMENT",
    "MAGMA-MAGMA",
    "COUCHSTORE-COUCHSTORE",
    "CE_ONLY-CE_ONLY",
    "COLLECTIONS-COLLECTIONS",
    "DURABILITY-DURABILITY",
    "ATOMICITY-ATOMICITY",
    "COMPRESSION-COMPRESSION",
    "IPV6-IPV6",
    "LOGREDACTION-LOG_REDACTION",
    "EVENTING-EVENTING",
    "RBAC-RBAC",
    "PLASMA-PLASMA",
    "IMPORT-IMPORT_EXPORT",
    "EXPORT-IMPORT_EXPORT",
    "CONVERG-MOBILE_CONVERGENCE",
    "ANALYTIC-ANALYTICS",
    "EPHEM-EPHEMERAL",
    "AUTOFAILOVER-AUTO_FAILOVER",
    "FAST-FAST_FAILOVER",
    "SYSTEST-SYSTEST",
    "SYSTEM-SYSTEST",
    "SUBDOC-SUBDOC",
    "FTS-FTS",
    "MOBILEUPGRADE-MOBILE_UPGRADE",
    "EEONLY-EEONLY",
    "SDK-SDK",
    "MOBILE-MOBILE",
    "CERTIFY-OS_CERTIFY",
    "BREAKPAD-BREAKPAD",
    "CBSGW-SYNCGW",
    "SYNC-MOBILE",
    "RZA-RZA",
    "GEO-GEO",
    "EPENG-EP",
    "SECU-SECURITY",
    "TUNABLE-TUNABLE",
    "2I_REBALANCE-2I_REBALANCE",
    "2I-2I_MOI",
    "NSERV-NSERV",
    "RQG-RQG",
    "N1QL-QUERY",
    "TUQ-QUERY",
    "VIEW-VIEW",
    "QUERY-QUERY",
    "GOXDCR-GOXDCR",
    "LWW-GOXDCR",
    "FOREST-FORESTDB",
    "XDCR-XDCR",
    "REB-NSERV",
    "PAUSE-NSERV",
    "BACK-BACKUP_RECOVERY",
    "RECOV-BACKUP_RECOVERY",
    "BKRS-BACKUP_RECOVERY",
    "UPGRADE-UPGRADE",
    "UPGRA-UPGRADE",
    "TRANSFER-TOOLS",
    "CLI-CLI",
    "_UI-UI",
    "TOOLS-TOOLS",
    "IBR-TOOLS",
    "CONNECTION-TOOLS",
    "SANITY-SANITY",
    "SANIT-SANITY",
    "SMOKE-SANITY",
    "DCP-EP",
    "FAILOVER-NSERV",
    "UNIT-UNIT",
    "MEMDB-2I",
    "SANIT-BUILD_SANITY",
    "CBOP-OPERATOR",
    "NUTSHELL-NUTSHELL"
]

SERVERLESS_FEATURES = [
    "CAPELLA_VOLUME-VOLUME",
    "CP_CLI_RUNNER-CP_CLI",
    "DAPI_SANITY-DAPI",
    "NEBULA-DIRECT_NEBULA",
    "PERF-PERF",
    "SDK-SDK",
    "VOLUME-VOLUME",
    "SYSTEM-SYSTEM_TEST",
    "UI-UI",
    "MAGMA-MAGMA",
    "COUCHSTORE-COUCHSTORE",
    "CE_ONLY-CE_ONLY",
    "COLLECTIONS-COLLECTIONS",
    "DURABILITY-DURABILITY",
    "ATOMICITY-ATOMICITY",
    "COMPRESSION-COMPRESSION",
    "IPV6-IPV6",
    "LOGREDACTION-LOG_REDACTION",
    "EVENTING-EVENTING",
    "RBAC-RBAC",
    "PLASMA-PLASMA",
    "IMPORT-IMPORT_EXPORT",
    "EXPORT-IMPORT_EXPORT",
    "CONVERG-MOBILE_CONVERGENCE",
    "ANALYTIC-ANALYTICS",
    "EPHEM-EPHEMERAL",
    "AUTOFAILOVER-AUTO_FAILOVER",
    "FAST-FAST_FAILOVER",
    "SYSTEST-SYSTEST",
    "SYSTEM-SYSTEST",
    "SUBDOC-SUBDOC",
    "FTS-FTS",
    "MOBILEUPGRADE-MOBILE_UPGRADE",
    "EEONLY-EEONLY",
    "SDK-SDK",
    "MOBILE-MOBILE",
    "CERTIFY-OS_CERTIFY",
    "BREAKPAD-BREAKPAD",
    "CBSGW-SYNCGW",
    "SYNC-MOBILE",
    "RZA-RZA",
    "GEO-GEO",
    "EPENG-EP",
    "SECU-SECURITY",
    "TUNABLE-TUNABLE",
    "2I_REBALANCE-2I_REBALANCE",
    "2I-2I_MOI",
    "NSERV-NSERV",
    "RQG-RQG",
    "N1QL-QUERY",
    "TUQ-QUERY",
    "VIEW-VIEW",
    "QUERY-QUERY",
    "GOXDCR-GOXDCR",
    "LWW-GOXDCR",
    "FOREST-FORESTDB",
    "XDCR-XDCR",
    "REB-NSERV",
    "PAUSE-NSERV",
    "BACK-BACKUP_RECOVERY",
    "RECOV-BACKUP_RECOVERY",
    "BKRS-BACKUP_RECOVERY",
    "UPGRADE-UPGRADE",
    "UPGRA-UPGRADE",
    "TRANSFER-TOOLS",
    "CLI-CLI",
    "_UI-UI",
    "TOOLS-TOOLS",
    "IBR-TOOLS",
    "CONNECTION-TOOLS",
    "SANITY-SANITY",
    "SANIT-SANITY",
    "SMOKE-SANITY",
    "DCP-EP",
    "FAILOVER-NSERV",
    "UNIT-UNIT",
    "MEMDB-2I",
    "SANIT-BUILD_SANITY",
    "CBOP-OPERATOR",
    "NUTSHELL-NUTSHELL"
]

## ---  VIEWS --- ##
CAPELLA_VIEW = {
    "urls": ["http://qe-jenkins1.sc.couchbase.com/view/Cloud/", "http://qa.sc.couchbase.com/view/Capella"],
    "platforms": CAPELLA_PLATFORMS,
    "features": CAPELLA_FEATURES,
    "build_param_name": ["version_number", "cluster_version", "build", "COUCHBASE_SERVER_VERSION", "CB_VERSION"],
    "image_param_name": ["IMAGE", "image", "image_name", "cbs_image", "cb_image"],
    "env-param-name": ["CYPRESS_BASE_URL", "Environment", "CP_CLI_APIURL", "capella_api_url", "ENV_URL", "CP_API_URL",
                       "public_api_url", "CP_URL", "URL", "url"],
    "bucket": "capella",
    "exclude": ["t[e]?mp(_|-)", "(_|-)t[e]?mp"],
}

SERVERLESS_VIEW = {
    "urls": ["http://qe-jenkins1.sc.couchbase.com/view/Cloud/"],
    "platforms": ["SERVERLESS"],
    "features": SERVERLESS_FEATURES,
    "build_param_name": ["version_number", "cluster_version", "build", "COUCHBASE_SERVER_VERSION", "CB_VERSION"],
    "image_param_name": ["IMAGE", "image", "image_name", "cbs_image", "cb_image"],
    "env-param-name": ["CYPRESS_BASE_URL", "Environment", "CP_CLI_APIURL", "capella_api_url", "ENV_URL", "CP_API_URL",
                       "public_api_url", "CP_URL", "URL", "url"],
    "bucket": "serverless",
    "exclude": ["t[e]?mp(_|-)", "(_|-)t[e]?mp"],
    "job": "cloud"
}

SERVER_VIEW = {
    "urls": [
        "http://qa.sc.couchbase.com",
        "http://qa.sc.couchbase.com/view/Cloud",
        "http://sdkbuilds.sc.couchbase.com/view/JAVA/job/server-build-test-java",
        "http://sdkbuilds.sc.couchbase.com/view/.NET/job/server-build-test-net/",
        "http://sdkbuilds.sc.couchbase.com/view/GO/job/server-build-test-go/",
        "http://sdkbuilds.sc.couchbase.com/view/JAVA/job/server-build-test-java/",
        "http://sdkbuilds.sc.couchbase.com/view/.NET/job/server-build-test-net/",
        "http://sdkbuilds.sc.couchbase.com/view/GO/job/server-build-test-go/",
        "http://sdkbuilds.sc.couchbase.com/job/Fast-failover-Java/",
        "http://sdkbuilds.sc.couchbase.com/job/fastfailover-lcb/",
        "http://sdkbuilds.sc.couchbase.com/view/JAVA/job/feature-java",
        "http://qa.sc.couchbase.com/view/OS%20Certification/",
        "http://uberjenkins.sc.couchbase.com:8080/",
        "http://sdkbuilds.sc.couchbase.com/view/IPV6",
        "http://sdk.jenkins.couchbase.com/view/Greenboard/"
    ],
    "platforms": SERVER_PLATFORMS,
    "features": SERVER_FEATURES,
    "build_param_name": ["version_number", "cluster_version", "build", "cbs_ver", "COUCHBASE_SERVER_VERSION", "CB_VERSION"],
    "bucket": "server",
    "exclude": ["t[e]?mp(_|-)", "(_|-)t[e]?mp"]
}

SERVER_VIEW_2 = {"urls" : ["http://qe-jenkins1.sc.couchbase.com"],
                 "platforms": SERVER_PLATFORMS,
                 "features": SERVER_FEATURES,
                 "build_param_name": ["version_number",
                                      "cluster_version",
                                      "build",
                                      "COUCHBASE_SERVER_VERSION"],
                 "bucket": "server",
                 "exclude": ["t[e]?mp(_|-)", "(_|-)t[e]?mp"]
                 }

SG_VIEW = {"urls": ["http://uberjenkins.sc.couchbase.com:8080/"],
           "platforms": SG_PLATFORMS,
           "filters": SG_FILTERS,
           "features": SG_FEATURES,
           "build_param_name": ["SYNC_GATEWAY_VERSION","sgw_ver",
                                "SYNC_GATEWAY_VERSION_OR_COMMIT"],
           "bucket": "sync_gateway"}

CBLITE_JAVA_VIEW = {
    "urls": ["http://uberjenkins.sc.couchbase.com:8080/"],
    "platforms": ["JAVA"],
    "features": LITE_FEATURES,
    "build_param_name": ["UPGRADED_CBLITE_VERSION", "COUCHBASE_MOBILE_VERSION",
                         "LITE_JAVA_VERSION", "LITE_JAVAWS_VERSION", "lite_java"],
    "additional_fields": {
        "secondary_os": [["CENTOS-7", "CENTOS 7"], ["CENTOS-6", "CENTOS 6"],
                         ["CENTOS7", "CENTOS 7"], ["CENTOS6", "CENTOS 6"],
                         ["WINDOWS", "WINDOWS"], ["UBUNTU", "UBUNTU"],
                         ["CENTOS-8", "CENTOS 8"], ["RHEL-7", "RHEL 7"],
                         ["RHEL-8", "RHEL 8"], ["SANITY", "Common"],
                         ["UPGRADE", "Common"]],
        "build_type": [["webservice", "Web Service"], ["desktop", "Desktop"]]
    },
    "bucket": "cblite"
}

CBLITE_ANDROID_VIEW = {
    "urls": ["http://uberjenkins.sc.couchbase.com:8080/"],
    "platforms": ["ANDROID"],
    "features": LITE_FEATURES,
    "build_param_name": ["UPGRADED_CBLITE_VERSION", "COUCHBASE_MOBILE_VERSION",
                         "LITE_ANDROID_VERSION", "a_ver"],
    "none_filters": ["DOTNET", "XAMARIN"],
    "bucket": "cblite"
}

CBLITE_IOS_VIEW = {
    "urls": ["http://uberjenkins.sc.couchbase.com:8080/"],
    "platforms": ["IOS"],
    "features": LITE_FEATURES,
    "build_param_name": ["UPGRADED_CBLITE_VERSION", "COUCHBASE_MOBILE_VERSION",
                         "CBL_iOS_Build", "LITE_IOS_VERSION",
                         "XAMARIN_IOS_VERSION"],
    "none_filters": ["DOTNET", "XAMARIN"],
    "bucket": "cblite"
}

CBLITE_DOTNET_VIEW = {
    "urls": ["http://uberjenkins.sc.couchbase.com:8080/"],
    "platforms": ["DOTNET"],
    "features": LITE_FEATURES,
    "build_param_name": ["UPGRADED_CBLITE_VERSION", "COUCHBASE_MOBILE_VERSION",
                         "LITE_DOTNET_VERSION", "XAMARIN_IOS_VERSION",
                         "LITE_NET_VERSION"],
    "additional_fields": {
        "secondary_os": [["ANDROID", "ANDROID"], ["IOS", "IOS"],
                         ["WINDOWS", "WINDOWS"], ["SANITY", "Common"],
                         ["UPGRADE", "Common"]],
    },
    "bucket": "cblite"
}

CBLITE_CLIB_VIEW = {
    "urls": ["http://uberjenkins.sc.couchbase.com:8080/"],
    "platforms": ["CLIB"],
    "features": LITE_FEATURES,
    "build_param_name": ["LITE_NET_VERSION", "LITE_CLIB_VERSION",
                         "LITE_ANDROID_VERSION", "LITE_IOS_VERSION"],
    "additional_fields": {
        "secondary_os": [["ANDROID", "ANDROID"], ["IOS", "IOS"],
                         ["WINDOWS", "WINDOWS"], ["WIN", "WINDOWS"],
                         ["DEBIAN", "DEBIAN9"], ["UBUNTU", "UBUNTU"],
                         ["Rasbian2", "Rasbian2"], ["Rasbian3", "Rasbian3"],
                         ["MACOS", "MACOS"],
                         ["SANITY", "Common"], ["UPGRADE", "Common"]],
    },
    "bucket": "cblite"
}


BUILD_VIEW = {"urls": ["https://server.jenkins.couchbase.com/job/build_sanity_matrix/", "http://cv.jenkins.couchbase.com/view/scheduled-unit-tests/job/unit-simple-test/", "http://server.jenkins.couchbase.com/job/watson-unix/"],
              "platforms": SERVER_PLATFORMS,
              "features": BUILD_FEATURES,
              "bucket": "build"}

OPERATOR_VIEW = {"urls": ["http://qa.sc.couchbase.com/view/Cloud"],
                 "platforms":OPERATOR_PLATFORMS,
                 "features": [],
                 "build_param_name": ["operator_image"],
                 "bucket": "operator"
                 }


VIEWS = [SERVER_VIEW_2, SERVER_VIEW, BUILD_VIEW, SG_VIEW, CBLITE_CLIB_VIEW,
         CBLITE_DOTNET_VIEW, CBLITE_JAVA_VIEW, CBLITE_ANDROID_VIEW, CBLITE_IOS_VIEW, OPERATOR_VIEW]


BUILDER_URLS = ["https://server.jenkins.couchbase.com/job/couchbase-server-build/",
                "https://server.jenkins.couchbase.com/job/watson-build/"]

CHANGE_LOG_URL = "http://172.23.123.43:8282/changelog"

## misc
DEFAULT_BUILD = "0.0.0-xxxx"
EXCLUDED = []

P0 = "P0"
P1 = "P1"
P2 = "P2"

CB_RELEASE_BUILDS = {"0.0.0":"0000",
                     "2.1.1":"764", "2.2.0":"821", "2.5.0":"1059", "2.5.1":"1083",
                     "2.5.2":"1154", "3.0.3":"1716", "3.1.5":"1859", "3.1.6":"1904",
                     "4.0.0":"4051", "4.1.0":"5005", "4.1.1":"5914", "4.1.2":"6088",
                     "4.5.0":"2601", "4.5.1":"2844", "4.6.0":"3573", "4.6.1":"3652",
                     "4.6.2":"3905", "4.6.3":"4136", "4.6.4":"4590", "4.7.0":"0000",
                     "4.6.5":"4742", "5.0.0":"3519", "5.0.1":"5003", "5.0.2":"5509",
                     "5.1.0":"5552", "5.1.1":"5723", "5.1.2":"6030", "5.1.3":"6212",
                     "5.5.0":"2958", "5.5.1":"3511", "5.5.2":"3733", "5.5.3":"4041",
                     "5.5.4":"4338", "5.5.5":"4521", "6.0.0":"1693", "6.0.1":"2037",
                     "6.0.2":"2413", "6.0.3":"0000", "6.5.0":"0000",
                     "6.6.0": "7899"}

CLAIM_MAP = {
    "git error": ["hudson.plugins.git.GitException", "python3: can't open file 'testrunner.py': [Errno 2] No such file or directory"],
    "SSH error": ["paramiko.ssh_exception.SSHException", "Exception SSH session not active occurred on"],
    "IPv6 test on IPv4 host": ["Cannot enable IPv6 on an IPv4 machine"],
    "Python SDK error (CBQE-6230)": ["ImportError: cannot import name 'N1QLQuery' from 'couchbase.n1ql'"],
    "Syntax error": ["KeyError:", "TypeError:"],
    "json.decoder.JSONDecodeError:": ["json.decoder.JSONDecodeError:"],
    "ServerUnavailableException: unable to reach the host": ["ServerUnavailableException: unable to reach the host"],
    "Node already added to cluster": ["ServerAlreadyJoinedException:"],
    "CBQ Error": ["membase.api.exception.CBQError:", "CBQError: CBQError:"],
    "RBAC error": ["Exception: {\"errors\":{\"roles\":\"Cannot assign roles to user because the following roles are unknown, malformed or role parameters are undefined: [security_admin]\"}}"],
    "Rebalance error": ["membase.api.exception.RebalanceFailedException"],
    "Build download failed": ["Unable to copy build to", "Unable to download build in"],
    "install not started": ["INSTALL NOT STARTED ON"],
    "install failed": ["INSTALL FAILED ON"],
    "No test report xml": ["No test report files were found. Configuration error?"]
}
