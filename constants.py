## --- PLATFORMS --- ##
SERVER_PLATFORMS = ["UBUNTU","CENTOS","DEBIAN","WIN","OSX","MAC"]
MOBILE_PLATFORMS = ["ANDROID","IOS", "SGW"]
SDK_PLATFORMS= [".NET","JAVA","LIBCB","NODE"]

## --- FEATURES --- ##
SERVER_FEATURES = [
    "GEO-GEO",
    "EPENG-EP",
    "SECU-SECURITY",
    "2I-2I",
    "NSERV-NSERV",
    "N1QL-QUERY",
    "TUQ-QUERY",
    "VIEW-VIEW",
    "QUERY-QUERY",
    "XDCR-XDCR",
    "REB-NSERV",
    "PAUSE-NSERV",
    "BACKUP-TOOLS",
    "UPGRADE-UPGRADE",
    "UPGRA-UPGRADE",
    "RECOVER-TOOLS",
    "TRANSFER-TOOLS",
    "RZA-TOOLS",
    "CLI-TOOLS",
    "UI-UI",
    "IBR-TOOLS",
    "CONNECTION-TOOLS",
    "SANITY-SANITY",
    "SANIT-SANITY",
    "SMOKE-SANITY",
#    "BUCKET-EP",
#    "CAS-EP",
#    "CHECKPOINT-EP",
#    "CWC-EP",
#    "COMPACT-EP",
#    "CONNECTION-EP",
#    "DOCUMENT-EP",
    "DCP-EP",
#    "UPR-EP",
    "FAILOVER-NSERV",
#    "FLUSH-EP",
#    "HOSTNAME-EP",
#   "MOXI-EP",
#   "OBSERVE-EP",
#   "REPLICA-EP",
    "TUNABLE-TUNABLE",
#    "WARM-EP",
    "FUNCTIONAL-FUNCTIONAL",
    "UNIT-UNIT",
    "CBSGW-GATEWAY"
]
MOBILE_FEATURES = ["FUNCT-FUNCTIONAL",
                   "REGRESSION-REGRESSION",
                   "GATEWAY-SYNC",
                   "DASH-PERF",
                   "UNIT-UNIT"]
SDK_FEATURES = [
    "LONGEVITY-STRESS",
    "SITUATIONAL-SITUATIONAL",
    "CORE-CLIENT",
    "SNAPSHOT-CLIENT",
    "CLIENT-CLIENT"
]

## ---  VIEWS --- ##
SERVER_VIEW = {"urls" : ["http://qa.hq.northscale.net", "http://qa.sc.couchbase.com"],
               "platforms": SERVER_PLATFORMS,
               "features": SERVER_FEATURES,
               "bucket": "server"}

MOBILE_VIEW = {"urls" : ["http://qa.hq.northscale.net", "http://qa.sc.couchbase.com", "http://ci.sc.couchbase.com"],
               "platforms": MOBILE_PLATFORMS,
               "features": MOBILE_FEATURES,
               "bucket": "mobile"}
SDK_VIEW    = {"urls" : ["http://sdkbuilds.couchbase.com"],
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


