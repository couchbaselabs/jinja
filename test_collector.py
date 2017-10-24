from couchbase.bucket import Bucket
from couchbase.n1ql import N1QLQuery
import os
import hashlib
import json
import mmap
import pydash


HOST = '172.23.109.74'
CLIENT = {}
testRunnerDir = "/root/TestRunner/testrunner"
CONF = "conf"
PYTESTS = "pytests"
BUCKET = "test"
TESTS_RESULT_LIMIT = 50

class testCaseDocument(object):
    def __init__(self):
        self.className = ""
        self.testName = ""
        self.priority = ""
        self.component = ""
        self.subComponent = ""
        self.os = {}
        self.confFile = []
        self.changed = False
        self.deleted = False
        self.change_history = []

class TestCaseCollector:

    def create_client(self):
        try:
            client = Bucket("couchbase://{0}/test".format(HOST))
            CLIENT[BUCKET] = client
        except Exception as e:
            print e

    def store_tests(self):
        for root, sub_dirs, files in os.walk(os.path.join(testRunnerDir, "conf")):
            for confFile in files:
                if ".conf" not in confFile:
                    continue
                file_path = os.path.join(root, confFile)
                conf_file = file_path[file_path.find("conf/") + len("conf/"):]
                test_cases = self.get_test_cases_from_conf(file_path)
                for test_case in test_cases:
                    testCase = testCaseDocument()
                    testCase.testName = test_case['testName']
                    testCase.className = test_case['className']
                    conf = {'conf': conf_file, 'commented': test_case['commented'], "testLine": test_case['testLine']}
                    testCase.confFile = [conf]
                    test_case.pop("testLine")
                    document_key = hashlib.md5(json.dumps(test_case, sort_keys=True)).hexdigest()
                    client = CLIENT[BUCKET]
                    existing_document = None
                    try:
                        existing_document = client.get(document_key).value
                    except:
                        pass
                    to_upsert = testCase.__dict__
                    if existing_document:
                        pydash.merge_with(to_upsert, existing_document, TestCaseCollector._merge_dict)
                    client.upsert(document_key, to_upsert)


    def check_if_test(self, line_in_conf):
        """
        Check if given test line is a test case present in pytests or not.
        :param line_in_conf: the line to be tested
        :return: True if test present in pytests else False
        """
        test_module = line_in_conf.split(',')[0]
        if not test_module or " " in test_module or "." not in test_module:
            return False
        if "." in test_module:
            modules = test_module.split(".")
            test_file_path = os.path.join(testRunnerDir, PYTESTS)
            for module in modules[:-1]:
                if os.path.isdir(os.path.join(test_file_path, module)):
                    test_file_path = os.path.join(test_file_path, module)
                elif os.path.isfile(os.path.join(test_file_path, module + ".py")):
                    test_file_path = os.path.join(test_file_path, module + ".py")
                    break
                else:
                    return False
            test_to_check1 = "def {}(".format(modules[-1])
            test_to_check2 = "def {} (".format(modules[-1])
            test_to_check3 = "def {}:".format(modules[-1])
            with open(test_file_path) as f:
                s = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
                if s.find(test_to_check1) != -1 or s.find(test_to_check2) != -1 or s.find(test_to_check3) != -1:
                    return True
                else:
                    return  False

    def get_test_case_from_test_result(self, test_result):
        class_name = test_result["className"]
        test_name = test_result["name"]
        test_case = dict(item.split(":", 1) if ":" in item else [item, ''] for item in test_name.split(",")[1:])
        test_case["testName"] = test_name.split(",")[0]
        test_case["className"] = class_name
        return test_case

    def get_test_cases_from_conf(self, conf_file):
        conf_file_path = os.path.join(testRunnerDir, CONF, conf_file)
        test_cases_dict = []
        try:
            with file(conf_file_path, 'r') as f:
                class_name = ""
                for line in f:
                    stripped = line.strip()
                    if len(stripped) <= 0:
                        continue
                    if stripped.endswith(":"):
                        class_name = stripped.split(":")[0]
                        continue
                    name = stripped
                    commented = False
                    if name.startswith("#"):
                        commented = True
                        name = name.replace("#", '').strip()
                    if class_name and class_name.lower() == "params":
                        continue
                    elif line.startswith(" ") and class_name:
                        name = class_name + "." + name
                    if commented and not self.check_if_test(name):
                        continue
                    class_name = ".".join(name.split(",")[0].split('.')[0:-1])
                    test_case = dict(item.split("=", 1) if "=" in item else [item, ''] for item in name.split(",")[1:])
                    test_case['testName'] = name.split(",")[0]
                    test_case['testLine'] = name[name.find(class_name) + len(class_name) + 1:]
                    test_case['className'] = class_name
                    test_case['commented'] = commented
                    test_cases_dict.append(test_case)
        except Exception as e:
            print e
        return test_cases_dict

    def get_conf_from_store(self, test_case_to_find):
        class_name = test_case_to_find['className']
        test_name = test_case_to_find['testName']
        query = "SELECT confFile, testName, className from {0} where testName = '{1}' and className = '{2}'".format(
            BUCKET, test_name, class_name)
        client = CLIENT[BUCKET]
        for row in client.n1ql_query(N1QLQuery(query)):
            conf_files = row['confFile']
            for entry in conf_files:
                test_line = entry['testLine']
                class_name = ".".join(test_line.split(",")[0].split('.')[0:-1])
                test_case = dict(item.split("=", 1) if "=" in item else [item, ''] for item in test_line.split(",")[1:])
                test_case['testName'] = row['testName']
                test_case['testLine'] = test_line[test_line.find(class_name) + len(class_name) + 1:]
                test_case['className'] = row['className']
                if set(test_case.items()).issubset(set(test_case_to_find.items())):
                    return entry['conf']
        return None

    def get_test_case_id(self, test_result):
        test_case = self.get_test_case_from_test_result(test_result)
        conf_file = test_case['conf_file'] if 'conf_file' in test_case else self.get_conf_from_store(test_case)
        if not conf_file:
            return
        if "conf/" in conf_file:
            conf_file = conf_file.replace("conf/", '')
        test_cases = self.get_test_cases_from_conf(conf_file)
        test_cases_clone = pydash.clone_deep(test_cases)
        def remove_group(x):
            pydash.unset(x, 'GROUP')
            pydash.unset(x, 'commented')
            pydash.unset(x, 'testLine')
        test_cases_dict_without_groups = pydash.for_each(test_cases_clone, remove_group)
        callback = lambda x: set(x.items()).issubset(set(test_case.items()))
        index = pydash.find_index(test_cases_dict_without_groups, callback)
        if index == -1:
            return None
        name = test_cases[index]
        name.pop("testLine")
        return hashlib.md5(json.dumps(name, sort_keys=True)).hexdigest()

    def store_test_result(self, test_result, build_details):
        test_case_id = self.get_test_case_id(test_result)
        if not test_case_id:
            return
        client = CLIENT['test']
        try:
            document = client.get(test_case_id).value
            os = build_details['os']
            if os not in document['os']:
                document['os'][os] = []
            if not document['component']:
                document['component'] = build_details['component']
            if not document['subComponent'] and 'subComponent' in build_details:
                document['subComponent'] = build_details['subComponent']
            tests = document['os'][os]
            """ Check if already updated, return if true """
            build = build_details['build']
            build_id = build_details['build_id']
            already_updated = pydash.some(tests, lambda test: test['build'] == build and test['build_id'] == build_id)
            if already_updated:
                return
            test = {}
            test['build_id'] = build_id
            test['build'] = build
            test['result'] = test_result['status']
            test['duration'] = test_result['duration']
            test['errorStackTrace'] = test_result['errorStackTrace']
            test['url'] = build_details['url']
            """ Trim tests to store only TESTS_RESULT_LIMIT tests results"""
            if len(tests) > TESTS_RESULT_LIMIT - 1:
                tests = tests[len(tests) - TESTS_RESULT_LIMIT + 1:]
            tests.append(test)
            client.upsert(test_case_id, document)
        except Exception as e:
            print e

    @staticmethod
    def _merge_dict(obj_value, src_value, key, obj, source):
        if isinstance(obj_value, list):
            new_array = pydash.union(obj_value, src_value)
            return new_array
        if isinstance(obj_value, str):
            return obj_value
        if isinstance(obj_value, dict):
            return pydash.merge_with(obj_value, src_value, TestCaseCollector._merge_dict)
        return obj_value


        #
# if __name__ == "__main__":
#     test_case_collector = TestCaseCollector()
#     #create_client()
#     test_case_collector.store_tests()