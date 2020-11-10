import os

UBER_USER = os.environ.get('UBER_USER') or ""
UBER_PASS = os.environ.get('UBER_PASS') or ""

## --- PLATFORMS --- ##
SERVER_PLATFORMS = ["UBUNTU", "CENTOS", "DEBIAN", "WIN", "OSX", "MAC", "SUSE",
                    "OEL", "DOCKER", "K8S"]
SG_PLATFORMS = ["CEN7", "CEN006", "WINDOWS", "MACOSX", "CENTOS"]
SDK_PLATFORMS = [".NET", "JAVA", "LIBC", "NODE"]
MOBILE_VERSION = ["1.1.0", "1.2.0", "1.3", "1.4"]

SG_FILTERS = ["SYNCGATEWAY", "SYNC-GATEWAY"]


## --- FEATURES --- ##
SERVER_FEATURES = [
    "MAGMA-MAGMA",
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
    "UNIT-UNIT", "MEMDB-2I",
    "SANIT-BUILD_SANITY",
    "CBOP-OPERATOR"
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

## ---  VIEWS --- ##
SERVER_VIEW = {"urls": ["http://qa.sc.couchbase.com", "http://qa.sc.couchbase.com/view/Cloud", "http://sdkbuilds.sc.couchbase.com/view/JAVA/job/server-build-test-java", "http://sdkbuilds.sc.couchbase.com/view/.NET/job/server-build-test-net/", "http://sdkbuilds.sc.couchbase.com/view/GO/job/server-build-test-go/", "http://sdkbuilds.sc.couchbase.com/view/LCB/job/server-build-test-lcb/", "http://sdkbuilds.sc.couchbase.com/view/JAVA/job/server-build-test-java/", "http://sdkbuilds.sc.couchbase.com/view/.NET/job/server-build-test-net/", "http://sdkbuilds.sc.couchbase.com/view/GO/job/server-build-test-go/", "http://sdkbuilds.sc.couchbase.com/view/LCB/job/server-build-test-lcb/","http://sdkbuilds.sc.couchbase.com/job/Fast-failover-Java/","http://sdkbuilds.sc.couchbase.com/job/fastfailover-lcb/", "http://sdkbuilds.sc.couchbase.com/view/JAVA/job/feature-java", "http://qa.sc.couchbase.com/view/OS%20Certification/", "http://uberjenkins.sc.couchbase.com:8080/", "http://sdkbuilds.sc.couchbase.com/view/IPV6"],
               "platforms": SERVER_PLATFORMS,
               "features": SERVER_FEATURES,
               "build_param_name": ["version_number", "cluster_version",
                                    "build", "COUCHBASE_SERVER_VERSION"],
               "bucket": "server"}

SG_VIEW = {"urls": ["http://uberjenkins.sc.couchbase.com:8080/"],
           "platforms": SG_PLATFORMS,
           "filters": SG_FILTERS,
           "features": SG_FEATURES,
           "build_param_name": ["SYNC_GATEWAY_VERSION",
                                "SYNC_GATEWAY_VERSION_OR_COMMIT"],
           "bucket": "sync_gateway"}

CBLITE_JAVA_VIEW = {
    "urls": ["http://uberjenkins.sc.couchbase.com:8080/"],
    "platforms": ["JAVA"],
    "features": LITE_FEATURES,
    "build_param_name": ["UPGRADED_CBLITE_VERSION", "COUCHBASE_MOBILE_VERSION",
                         "LITE_JAVA_VERSION", "LITE_JAVAWS_VERSION"],
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
                         "LITE_ANDROID_VERSION"],
    "none_filers": ["DOTNET", "XAMARIN"],
    "bucket": "cblite"
}

CBLITE_IOS_VIEW = {
    "urls": ["http://uberjenkins.sc.couchbase.com:8080/"],
    "platforms": ["IOS"],
    "features": LITE_FEATURES,
    "build_param_name": ["UPGRADED_CBLITE_VERSION", "COUCHBASE_MOBILE_VERSION",
                         "CBL_iOS_Build", "LITE_IOS_VERSION",
                         "XAMARIN_IOS_VERSION"],
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


BUILD_VIEW = {"urls": ["http://server.jenkins.couchbase.com/job/build_sanity_matrix/", "http://cv.jenkins.couchbase.com/view/scheduled-unit-tests/job/unit-simple-test/", "http://server.jenkins.couchbase.com/job/watson-unix/"],
              "platforms": SERVER_PLATFORMS,
              "features": BUILD_FEATURES,
              "bucket": "build"}


VIEWS = [SERVER_VIEW, BUILD_VIEW, SG_VIEW, CBLITE_DOTNET_VIEW,
         CBLITE_JAVA_VIEW, CBLITE_ANDROID_VIEW, CBLITE_IOS_VIEW]


BUILDER_URLS = ["http://server.jenkins.couchbase.com/job/couchbase-server-build/",
                "http://server.jenkins.couchbase.com/job/watson-build/"]

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
                     "6.0.2":"2413", "6.0.3":"0000", "6.5.0":"0000"}
