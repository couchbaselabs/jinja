## --- PLATFORMS --- ##
SERVER_PLATFORMS = ["UBUNTU","CENTOS","DEBIAN","WIN","OSX","MAC", "SUSE", "OEL"]
MOBILE_PLATFORMS = ["CBLITE", "ANDROID","IOS", "JAVA", "NET", "SYNCGATEWAY"]
SDK_PLATFORMS= [".NET","JAVA","LIBC","NODE"]
MOBILE_VERSION = ["1.1.0", "1.2.0"]

## --- FEATURES --- ##
SERVER_FEATURES = [
    "FTS-FTS",
    "SYSTEST-SYSTEST",
    "SYSTEM-SYSTEST",
    "MOBILEUPGRADE-MOBILE_UPGRADE",
    "EEONLY-EEONLY",
    "SDK-SDK",
    "MOBILE-MOBILE",
    "SANITY_EXT-SANITY_EXT",
    "EXTENDED-SANITY_EXT",
    "BREAKPAD-BREAKPAD",
    "CBSGW-SYNCGW",
    "FOREST-FORESTDB",
    "RZA-RZA",
    "GEO-GEO",
    "EPENG-EP",
    "SECU-SECURITY",
    "TUNABLE-TUNABLE",
    "2I-2I",
    "NSERV-NSERV",
    "RQG-RQG",
    "N1QL-QUERY",
    "TUQ-QUERY",
    "VIEW-VIEW",
    "QUERY-QUERY",
    "GOXDCR-GOXDCR",
    "XDCR-XDCR",
    "REB-NSERV",
    "PAUSE-NSERV",
    "BACK-BACKUP_RECOVERY",
    "RECOV-BACKUP_RECOVERY",
    "UPGRADE-UPGRADE",
    "UPGRA-UPGRADE",
    "TRANSFER-TOOLS",
    "CLI-TOOLS",
    "_UI-UI",
    "TOOLS-TOOLS",
    "IBR-TOOLS",
    "CONNECTION-TOOLS",
    "SANITY-SANITY",
    "SANIT-SANITY",
    "SMOKE-SANITY",
    "DCP-EP",
    "FAILOVER-NSERV",
    "UNIT-UNIT"
]
MOBILE_FEATURES = ["FUNCT-FUNCTIONAL",
                   "UPGR-UPGRADE",
                   "SANITY-SANITY",
                   "BUILD-BUILD",
                   "UNIT-UNIT"]
SDK_FEATURES = [
    "LONGEVITY-STRESS",
    "SITUATIONAL-SITUATIONAL",
    "FEATURE-FEATURE",
    "CORE-FEATURE",
    "SNAPSHOT-CLIENT",
    "CLIENT-CLIENT"
]

BUILD_FEATURES = ["SANITY-BUILD_SANITY"]

#feature-libcouchbase-core-win/

## ---  VIEWS --- ##
SERVER_VIEW = {"urls" : [ "http://qa.sc.couchbase.com", "http://sdkbuilds.couchbase.com/view/LCB/job/situational-lcb/", "http://sdkbuilds.couchbase.com/view/JAVA/job/situational-java/", "http://sdkbuilds.couchbase.com/view/.NET/", "http://qa.hq.northscale.net/", "http://ci.sc.couchbase.com", "http://qa.sc.couchbase.com/view/extended/"],
               "platforms": SERVER_PLATFORMS,
               "features": SERVER_FEATURES,
               "bucket": "server"}
MOBILE_VIEW = {"urls" : ["http://qa.hq.northscale.net/", "http://qa.sc.couchbase.com/", "http://mobile.jenkins.couchbase.com/"],
               "platforms": MOBILE_PLATFORMS,
               "features": MOBILE_FEATURES,
               "bucket": "mobile"}
SDK_VIEW    = {"urls" : ["http://sdkbuilds.couchbase.com", "http://sdkbuilds.couchbase.com/view/LCB/job/feature/", "http://sdkbuilds.couchbase.com/view/LCB/job/situational-lcb/"],
               "platforms": SDK_PLATFORMS,
               "features": SDK_FEATURES,
               "bucket": "sdk"}
BUILD_VIEW = {"urls": ["http://server.jenkins.couchbase.com/job/build_sanity_matrix/"],
              "platforms": SERVER_PLATFORMS,
              "features": BUILD_FEATURES,
              "bucket": "build"}

VIEWS = [MOBILE_VIEW, SDK_VIEW, SERVER_VIEW, BUILD_VIEW]


## misc
DEFAULT_BUILD = "0.0.0-xxxx"
EXCLUDED = []

P0 = "P0"
P1 = "P1"
P2 = "P2"

