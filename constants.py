## --- PLATFORMS --- ##
SERVER_PLATFORMS = ["UBUNTU","CENTOS","DEBIAN","WIN","OSX","MAC", "SUSE", "OEL"]
MOBILE_PLATFORMS = ["CBLITE", "ANDROID","IOS", "JAVA"]
SDK_PLATFORMS= [".NET","JAVA","LIBC","NODE"]
MOBILE_VERSION = "1.1"

## --- FEATURES --- ##
SERVER_FEATURES = [
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
    "N1QL-QUERY",
    "TUQ-QUERY",
    "VIEW-VIEW",
    "QUERY-QUERY",
    "GOXDCR-GOXDCR",
    "XDCR-XDCR",
    "REB-NSERV",
    "PAUSE-NSERV",
    "BACKUP-TOOLS",
    "UPGRADE-UPGRADE",
    "UPGRA-UPGRADE",
    "RECOVER-TOOLS",
    "TRANSFER-TOOLS",
    "CLI-TOOLS",
    "_UI-UI",
    "TOOLS-TOOLS",
    "IBR-TOOLS",
    "CONNECTION-TOOLS",
    "EXTENDED-SANITY_EXT",
    "SANITY-SANITY",
    "SANIT-SANITY",
    "SMOKE-SANITY",
    "DCP-EP",
    "FAILOVER-NSERV",
    "UNIT-UNIT"
]
MOBILE_FEATURES = ["FUNCT-FUNCTIONAL",
                   "CBLITE-CBLITE",
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

#feature-libcouchbase-core-win/

## ---  VIEWS --- ##
SERVER_VIEW = {"urls" : ["http://qa.hq.northscale.net", "http://qa.sc.couchbase.com", "http://ci.sc.couchbase.com"],
               "platforms": SERVER_PLATFORMS,
               "features": SERVER_FEATURES,
               "bucket": "server"}

MOBILE_VIEW = {"urls" : [ "http://mobile.jenkins.couchbase.com/", "http://qa.hq.northscale.net", "http://qa.sc.couchbase.com"],
               "platforms": MOBILE_PLATFORMS,
               "features": MOBILE_FEATURES,
               "bucket": "mobile"}
SDK_VIEW    = {"urls" : ["http://sdkbuilds.couchbase.com", "http://sdkbuilds.couchbase.com/view/LCB/job/feature/"],
               "platforms": SDK_PLATFORMS,
               "features": SDK_FEATURES,
               "bucket": "sdk"}

VIEWS = [MOBILE_VIEW, SDK_VIEW, SERVER_VIEW]

## misc
DEFAULT_BUILD = "0.0.0-xxxx"
EXCLUDED = []

P0 = "P0"
P1 = "P1"
P2 = "P2"
JOBS = {}


