# --- Bucket names --- #
serverBucketName = "server"
mobileBucketName = "mobile"
sdkBucketName = "sdk"
buildBucketName = "builds"
qeTestSuitesBucketName = "QE-Test-Suites"

# --- PLATFORMS --- #
SERVER_PLATFORMS = ["UBUNTU", "CENTOS", "DEBIAN", "WIN", "OSX", "MAC", "SUSE", "OEL"]
MOBILE_PLATFORMS = [
    "ANDROID", "CBLITE", "CBLITEIOS", "CEN7", "CEN006",
    "IOS", "JAVA", "MONO", "MACOSX",
    "SYNCGATEWAY", "SYNC-GATEWAY", "WINDOWS"
]
SDK_PLATFORMS = [".NET", "JAVA", "LIBC", "NODE"]

MOBILE_VERSION = ["1.1.0", "1.2.0", "1.3", "1.4"]

# --- FEATURES --- #
SERVER_FEATURES = [
    "_UI-UI",
    "2I-2I_MOI",
    "2I_REBALANCE-2I_REBALANCE",
    "ANALYTIC-ANALYTICS",
    "AUTO-AUTO_FAILOVER",
    "BACK-BACKUP_RECOVERY",
    "BREAKPAD-BREAKPAD",
    "CBSGW-SYNCGW",
    "CERTIFY-OS_CERTIFY",
    "CONNECTION-TOOLS",
    "CONVERG-MOBILE_CONVERGENCE",
    "CLI-CLI",
    "DCP-EP",
    "EEONLY-EEONLY",
    "EPENG-EP",
    "EPHEM-EPHEMERAL",
    "EVENTING-EVENTING",
    "EXPORT-IMPORT_EXPORT",
    "FAILOVER-NSERV",
    "FAST-FAST_FAILOVER",
    "FOREST-FORESTDB",
    "FTS-FTS",
    "GEO-GEO",
    "GOXDCR-GOXDCR",
    "IBR-TOOLS",
    "IMPORT-IMPORT_EXPORT",
    "IPV6-IPV6",
    "LWW-GOXDCR",
    "MEMDB-2I",
    "MOBILE-MOBILE",
    "MOBILEUPGRADE-MOBILE_UPGRADE",
    "N1QL-QUERY",
    "NSERV-NSERV",
    "PAUSE-NSERV",
    "PLASMA-PLASMA",
    "QUERY-QUERY",
    "REB-NSERV",
    "RECOV-BACKUP_RECOVERY",
    "RBAC-RBAC",
    "RQG-RQG",
    "RZA-RZA",
    "SANIT-BUILD_SANITY"
    "SANIT-SANITY",
    "SANITY-SANITY",
    "SDK-SDK",
    "SECU-SECURITY",
    "SMOKE-SANITY",
    "SUBDOC-SUBDOC",
    "SYNC-MOBILE",
    "SYSTEST-SYSTEST",
    "SYSTEM-SYSTEST",
    "TOOLS-TOOLS",
    "TRANSFER-TOOLS",
    "TUNABLE-TUNABLE",
    "TUQ-QUERY",
    "UNIT-UNIT",
    "UPGRA-UPGRADE",
    "UPGRADE-UPGRADE",
    "VIEW-VIEW",
    "XDCR-XDCR",
]

MOBILE_FEATURES = [
    "BUILD-BUILD",
    "CLIENT-CLIENT",
    "CONVERG-MOBILE_CONVERGENCE"
    "FUNCT-FUNCTIONAL",
    "LISTENER-LISTENER",
    "NODE-NODE",
    "SANITY-SANITY",
    "UNIT-UNIT",
    "UPGR-UPGRADE",
]

SDK_FEATURES = [
    "CORE-FEATURE",
    "CLIENT-CLIENT"
    "FEATURE-FEATURE",
    "LONGEVITY-STRESS",
    "SITUATIONAL-SITUATIONAL",
    "SNAPSHOT-CLIENT",
]

BUILD_FEATURES = [
    "SANITY-BUILD_SANITY",
    "UNIX-UNIT",
    "UNIT-UNIT"
]

# feature-libcouchbase-core-win/

# ---  VIEWS --- #
SERVER_VIEW = {
    "urls": [
        "http://qa.sc.couchbase.com",
        "http://sdkbuilds.sc.couchbase.com/view/JAVA/job/server-build-test-java",
        "http://sdkbuilds.sc.couchbase.com/view/.NET/job/server-build-test-net/",
        "http://sdkbuilds.sc.couchbase.com/view/GO/job/server-build-test-go/",
        "http://sdkbuilds.sc.couchbase.com/view/LCB/job/server-build-test-lcb/",
        "http://sdkbuilds.sc.couchbase.com/view/JAVA/job/server-build-test-java/",
        "http://sdkbuilds.sc.couchbase.com/view/.NET/job/server-build-test-net/",
        "http://sdkbuilds.sc.couchbase.com/view/GO/job/server-build-test-go/",
        "http://sdkbuilds.sc.couchbase.com/view/LCB/job/server-build-test-lcb/",
        "http://sdkbuilds.sc.couchbase.com/job/Fast-failover-Java/",
        "http://sdkbuilds.sc.couchbase.com/job/fastfailover-lcb/",
        "http://sdkbuilds.sc.couchbase.com/view/JAVA/job/feature-java/job/centos-java-integration-test/",
        "http://qa.sc.couchbase.com/view/OS%20Certification/",
        "http://uberjenkins.sc.couchbase.com:8080/"
    ],
    "platforms": SERVER_PLATFORMS,
    "features": SERVER_FEATURES,
    "bucket": serverBucketName
}

MOBILE_VIEW = {
    "urls": [
        "http://uberjenkins.sc.couchbase.com:8080/"
    ],
    "platforms": MOBILE_PLATFORMS,
    "features": MOBILE_FEATURES,
    "bucket": mobileBucketName
}

SDK_VIEW = {
    "urls": [],
    "platforms": SDK_PLATFORMS,
    "features": SDK_FEATURES,
    "bucket": sdkBucketName
}

BUILD_VIEW = {
    "urls": [
        "http://server.jenkins.couchbase.com/job/build_sanity_matrix/",
        "http://cv.jenkins.couchbase.com/view/scheduled-unit-tests/job/unit-simple-test/",
        "http://server.jenkins.couchbase.com/job/watson-unix/"
    ],
    "platforms": SERVER_PLATFORMS,
    "features": BUILD_FEATURES,
    "bucket": buildBucketName
}

VIEWS = [MOBILE_VIEW, SERVER_VIEW, BUILD_VIEW]
BUILDER_URLS = [
    "http://server.jenkins.couchbase.com/job/couchbase-server-build/",
    "http://server.jenkins.couchbase.com/job/watson-build/"
]

CHANGE_LOG_URL = "http://172.23.123.43:8282/changelog"

# misc
DEFAULT_BUILD = "0.0.0-xxxx"
EXCLUDED = []

P0 = "P0"
P1 = "P1"
P2 = "P2"

actual = [
    "CLI", "RZA", "EP", "QUERY", "BUILD_SANITY",
    "RBAC", "2I_MOI", "EPHEMERAL", "SANITY", "UNIT",
    "FTS", "TUNABLE", "NSERV", "SYSTEST", "GEO",
    "MOBILE_CONVERGENCE", "RQG", "MOBILE_UPGRADE",
    "OS_CERTIFY", "GOXDCR", "SDK", "PLASMA",
    "VIEW", "SUBDOC", "BACKUP_RECOVERY", "LWW",
    "MOBILE", "IMPORT_EXPORT", "AUTO_FAILOVER",
    "BREAKPAD", "FORESTDB", "TOOLS", "2I",
    "UPGRADE", "2I_REBALANCE", "ANALYTICS",
    "SECURITY", "EEONLY"
]
