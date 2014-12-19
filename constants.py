## --- PLATFORMS --- ##
SERVER_PLATFORMS = ["UBUNTU","CENTOS","DEBIAN","WIN","OSX","MAC"]
MOBILE_PLATFORMS = ["ANDROID","IOS"]
SDK_PLATFORMS= [".NET","JAVA","LIBCB","NODE"]

## --- FEATURES --- ##
SERVER_FEATURES = [
    "N1QL-N1QL",
    "TUQ-N1QL",
    "QUERY-VIEW",
    "VIEW-VIEW",
    "XDCR-XDCR",
    "REB-REB",
    "PAUSE-REB",
    "BACKUP-TOOLS",
    "UPGRADE-TOOLS",
    "UPGRA-TOOLS",
    "RECOVER-TOOLS",
    "TRANSFER-TOOLS",
    "RZA-TOOLS",
    "CLI-TOOLS",
    "UI-TOOLS",
    "IBR-TOOLS",
    "CONNECTION-TOOLS",
    "SANITY-SANITY",
    "SANIT-SANITY",
    "SMOKE-SANITY",
    "BUCKET-EP",
    "CAS-EP",
    "CHECKPOINT-EP",
    "CWC-EP",
    "COMPACT-EP",
    "CONNECTION-EP",
    "DOCUMENT-EP",
    "DCP-EP",
    "UPR-EP",
    "FAILOVER-REB",
    "FLUSH-EP",
    "HOSTNAME-EP",
    "MOXI-EP",
    "OBSERVE-EP",
    "REPLICA-EP",
    "TUNABLE-EP",
    "WARM-EP",
    "FUNCTIONAL-FUNCTIONAL",
    "UNIT-UNIT"
]
MOBILE_FEATURES = ["FUNCT-FUNCTIONAL",
                   "UNIT-UNIT"]
SDK_FEATURES = [
    "LONGEVITY-STRESS",
    "CORE-CORE",
    "SNAPSHOT-SNAPSHOT",
    "SITUATIONAL-SITUATIONAL"
]

## ---  VIEWS --- ##
SERVER_VIEW = {"urls" : ["http://qa.hq.northscale.net", "http://qa.sc.couchbase.com"],
               "platforms": SERVER_PLATFORMS,
               "features": SERVER_FEATURES,
               "bucket": "server"}

MOBILE_VIEW = {"urls" : ["http://qa.hq.northscale.net", "http://qa.sc.couchbase.com"],
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


