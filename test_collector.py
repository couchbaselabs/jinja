import difflib
import hashlib
import json
import os
import re
import shutil
from difflib import SequenceMatcher

import git
import pydash
from couchbase.bucket import Bucket, LOCKMODE_WAIT
from couchbase.n1ql import N1QLQuery

HOST = '10.111.170.102'
#HOST = '172.23.109.74'
CLIENT = {}
testRunnerDir = "/tmp/TestRunner/testrunner"
testRunnerRepo = "http://github.com/couchbase/testrunner"
CONF = "conf"
PYTESTS = "pytests"
BUCKET = "test"
TESTS_RESULT_LIMIT = 50

class TestCaseDocument(object):
    def __init__(self):
        self.className = ""
        self.testName = ""
        self.priority = ""
        self.component = ""
        self.subComponent = ""
        self.os = {}
        self.confFile = []
        self.changed = False
        self.newChangedDocId = ""
        self.oldChangedDocId = ""
        self.deleted = False
        self.change_history = []

class TestCaseCollector:

    def __init__(self):
        if os.path.exists(testRunnerDir):
            #shutil.rmtree(testRunnerDir)
            self.testRunnerRepo = git.Repo.init(testRunnerDir)
        else:
            self.testRunnerRepo = git.Repo.clone_from(testRunnerRepo, testRunnerDir)
        self.currentHead = self.testRunnerRepo.head.commit

    def create_client(self):
        try:
            client = Bucket("couchbase://{0}/test".format(HOST), lockmode=LOCKMODE_WAIT)
            CLIENT[BUCKET] = client
        except Exception as e:
            print e

    # def store_tests(self):
    #     for root, sub_dirs, files in os.walk(os.path.join(testRunnerDir, "conf")):
    #         for confFile in files:
    #             if ".conf" not in confFile:
    #                 continue
    #             file_path = os.path.join(root, confFile)
    #             conf_file = file_path[file_path.find("conf/") + len("conf/"):]
    #             file_history = list(self.testRunnerRepo.iter_commits(file_path))
    #             test_cases = self.get_test_cases_from_conf(file_path)
    #             for test_case in test_cases:
    #                 testCase = TestCaseDocument()
    #                 testCase.testName = test_case['testName']
    #                 testCase.className = test_case['className']
    #                 conf = {'conf': conf_file, 'commented': test_case['commented'], "testLine": test_case['testLine']}
    #                 testCase.confFile = [conf]
    #                 self.remove_unwanted_fields(test_case)
    #                 history = {}
    #                 history['author'] = file_history[-1].committer.name
    #                 history['commit_date'] = file_history[-1].committed_datetime.__str__()
    #                 history['commit_time'] = file_history[-1].committed_date
    #                 testCase.change_history = [history]
    #                 document_key = hashlib.md5(json.dumps(test_case, sort_keys=True)).hexdigest()
    #                 client = CLIENT[BUCKET]
    #                 existing_document = None
    #                 try:
    #                     existing_document = client.get(document_key).value
    #                 except:
    #                     pass
    #                 to_upsert = testCase.__dict__
    #                 if existing_document:
    #                     pydash.merge_with(to_upsert, existing_document, TestCaseCollector._merge_dict)
    #                 client.upsert(document_key, to_upsert)
    #

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
                    class_name, test_case = self.get_test_case_from_line(line, class_name)
                    if test_case:
                        test_cases_dict.append(test_case)
        except Exception as e:
            print e
        return test_cases_dict

    def get_test_case_from_line(self, line, class_name):
        stripped = line.strip()
        if len(stripped) <= 0:
            return class_name, None
        name = stripped
        commented = False
        if name.startswith("#"):
            commented = True
            name = name.replace("#", '', 1).strip()
        if name.endswith(":"):
            class_name = name.split(":")[0]
            return class_name, None
        if class_name and class_name.lower() == "params":
            return class_name, None
        elif line.startswith(" ") and class_name:
            name = class_name + "." + name
        if commented and not self.check_if_test(name):
            return class_name, None
        class_name = ".".join(name.split(",")[0].split('.')[0:-1])
        test_case = dict(item.split("=", 1) if "=" in item else [item, ''] for item in name.split(",")[1:])
        test_case['testName'] = name.split(",")[0]
        test_case['testLine'] = name[name.find(class_name) + len(class_name) + 1:]
        test_case['className'] = class_name
        test_case['commented'] = commented
        return class_name, test_case

    def check_if_test(self, line_in_conf):
        """
        Check if given test line is a test case present in pytests or not.
        Check if test line fits following patterns:
            1. (moduleName.)+(testName),params
            2. (moduleName)+(testName)
        :param line_in_conf: the line to be tested
        :return: True if test
        """
        pattern1 = "([a-zA-Z][\w]+\.)+([a-zA-Z][\w]+){1},[a-zA-Z]"
        pattern2 = "([a-zA-Z][\w]+\.)+([a-zA-Z][\w]+){1}"
        match = re.match(pattern1, line_in_conf)
        if match and match.start() == 0 and match.end() < len(line_in_conf):
            return True
        match = re.match(pattern2, line_in_conf)
        if match and match.start() == 0 and match.end() == len(line_in_conf) - 1:
            return True
        return False

    def get_test_cases_from_blob(self, blob):
        test_cases = []
        class_name = ""
        for line in blob.splitlines():
            stripped = line.strip()
            name = stripped
            commented = False
            if name.startswith("#"):
                commented = True
                name = name.replace("#", "", 1).strip()
            if name.endswith(":"):
                class_name = name.split(":")[0]
                continue
            if class_name and class_name.lower() == "params":
                continue
            if line.startswith(" ") and class_name:
                name = class_name + "." + name
            if commented and not self.check_if_test(name):
                continue
            class_name = ".".join(name.split(",")[0].split('.')[0:-1])
            if commented:
                name = "#{}".format(name)
            if name:
                test_cases.append(name)
        return test_cases

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

    def store_tests(self):
        for root, sub_dirs, files in os.walk(os.path.join(testRunnerDir, "conf")):
            for confFile in files:
                if ".conf" not in confFile:
                    continue
                file_path = os.path.join(root, confFile)
                conf_file = file_path[file_path.find("conf/") + len("conf/"):]
                file_history = list(self.testRunnerRepo.iter_commits(paths=file_path))
                # Store the first commit
                first_commit = file_history[-1]
                parent_commit = first_commit.parents[0]
                first_diff = parent_commit.diff(first_commit, file_path)[0]
                inital_blob = first_diff.b_blob.data_stream.read()
                initial_test_cases = self.get_test_cases_from_blob(inital_blob)
                for test_case in initial_test_cases:
                    self.update_new_test_case(test_case, first_commit, conf_file)
                # Now store the rest of the history
                file_history.reverse()
                for index, history in enumerate(file_history[1:]):
                    old_commit = file_history[index]
                    new_commit = history
                    diffs = self.get_diff_between_commits(old_commit, new_commit, file_path)
                    self.store_test_cases_in_diffs(diffs)

    def get_diff_between_commits(self, old_commit, new_commit, path):
        diffs = old_commit.diff(new_commit, path, create_patch=True)
        if len(diffs) == 0:
            return None
        diff = {}
        diff['old_commit'] = old_commit
        diff['new_commit'] = new_commit
        diff['diff'] = diffs
        return diff

    def store_test_cases_in_diffs(self, diffs):
        for diff in diffs['diff']:
            if not diff.a_blob and not diff.b_blob:
                # if both blobs are not available, just continue with other differences
                continue
            new_commit = diffs['new_commit']
            if not diff.a_blob:
                # If first blob is not available, then this is a new addition of file. Do addition of testcases
                conf = diff.b_path
                conf = conf[conf.find("conf/") + len("conf/"):]
                b_blob = diff.b_blob.data_stream.read()
                b_test_cases = self.get_test_cases_from_blob(b_blob)
                for test_case in b_test_cases:
                    self.update_new_test_case(test_case, new_commit, conf)
                continue
            if not diff.b_blob:
                # If second blob is not available, then the conf file was deleted. Do removal of testcases
                conf = diff.a_path
                conf = conf[conf.find("conf/") + len("conf/"):]
                a_blob = diff.a_blob.data_stream.read()
                a_test_cases = self.get_test_cases_from_blob(a_blob)
                for test_case in a_test_cases:
                    self.update_deleted_test_case(test_case, new_commit, conf)
                continue
            conf = diff.b_path
            conf = conf[conf.find("conf/") + len("conf/"):]
            a_blob = diff.a_blob.data_stream.read()
            b_blob = diff.b_blob.data_stream.read()
            a_test_cases = self.get_test_cases_from_blob(a_blob)
            b_test_cases = self.get_test_cases_from_blob(b_blob)
            a_test_cases = ["{}\n".format(line) for line in a_test_cases if line]
            b_test_cases = ["{}\n".format(line) for line in b_test_cases if line]
            diff_blob = list(difflib.ndiff(a_test_cases, b_test_cases))
            test_cases_removed, test_cases_added, test_cases_modified = TestCaseCollector.get_diffs(diff_blob)
            for test_case_removed in test_cases_removed:
                self.update_deleted_test_case(test_case_removed, new_commit, conf)
            for test_case_added in test_cases_added:
                self.update_new_test_case(test_case_added, new_commit, conf)
            for test_case_modified in test_cases_modified:
                self.update_changed_test_case(test_case_modified, new_commit, conf)

    def check_for_changes(self):
        origin = self.testRunnerRepo.remotes.origin
        self.testRunnerRepo.heads.master.checkout()
        old_head_commit = self.testRunnerRepo.head.commit
        origin.pull()
        current_head_commit = self.testRunnerRepo.head.commit
        if old_head_commit == current_head_commit:
            # No update to repository.
            return False, None
        diff = self.get_diff_between_commits(old_head_commit, current_head_commit, os.path.join(testRunnerDir, "conf"))
        if not diff:
            return False, None
        return True, diff

    def update_test_case_repository(self):
        updated, diffs = self.check_for_changes()
        if not updated:
            return
        self.store_test_cases_in_diffs(diffs)

    def get_test_cases_document(self, test_case, conf):
        t = TestCaseDocument()
        t.className = test_case['className']
        t.testName = test_case['testName']
        conf = {'conf': conf, 'commented': test_case['commented'], "testLine": test_case['testLine']}
        t.confFile = [conf]
        return t

    def get_history(self, new_commit, commit_type):
        history = {}
        history['author'] = new_commit.committer.name
        history['commitDate'] = new_commit.committed_datetime.__str__()
        history['commitTime'] = new_commit.committed_date
        history['commitSha'] = new_commit.hexsha
        history['changeType'] = commit_type
        return history

    def update_deleted_test_case(self, test_case, new_commit, conf):
        class_name, _test_case = self.get_test_case_from_line(test_case, "")
        t = self.get_test_cases_document(_test_case, conf)
        t.deleted = True
        history = self.get_history(new_commit, "delete")
        t.change_history = [history]
        self.remove_unwanted_fields(_test_case)
        document_key = hashlib.md5(json.dumps(_test_case, sort_keys=True)).hexdigest()
        client = CLIENT[BUCKET]
        try:
            existing_document = client.get(document_key).value
            to_upsert = t.__dict__
            new_conf = pydash.clone_deep(to_upsert['confFile'])
            pydash.merge_with(to_upsert, existing_document, TestCaseCollector._merge_dict)
            TestCaseCollector._flatten_conf(to_upsert['confFile'], new_conf)
            client.upsert(document_key, to_upsert)
        except Exception as e:
            print e

    def remove_unwanted_fields(self, test_case):
        pydash.unset(test_case, "testLine")
        pydash.unset(test_case, "commented")
        pydash.unset(test_case, "GROUP")

    def update_new_test_case(self, test_case, new_commit, conf):
        class_name, _test_case = self.get_test_case_from_line(test_case, "")
        t = self.get_test_cases_document(_test_case, conf)
        history = self.get_history(new_commit, "create")
        t.change_history = [history]
        self.remove_unwanted_fields(_test_case)
        document_key = hashlib.md5(json.dumps(_test_case, sort_keys=True)).hexdigest()
        client = CLIENT[BUCKET]
        existing_document = None
        try:
            existing_document = client.get(document_key).value
        except:
            pass
        to_upsert = t.__dict__
        if existing_document:
            new_conf = pydash.clone_deep(to_upsert['confFile'])
            pydash.merge_with(to_upsert, existing_document, TestCaseCollector._merge_dict)
            TestCaseCollector._flatten_conf(to_upsert['confFile'], new_conf)
        client.upsert(document_key, to_upsert)

    def update_changed_test_case(self, test_case, new_commit, conf):
        old_test_case = test_case['old_test_line']
        new_test_case = test_case['new_test_line']
        class_name, _old_test_case = self.get_test_case_from_line(old_test_case, "")
        class_name, _new_test_case = self.get_test_case_from_line(new_test_case, "")
        old_t = self.get_test_cases_document(_old_test_case, conf)
        new_t = self.get_test_cases_document(_new_test_case, conf)
        self.remove_unwanted_fields(_old_test_case)
        self.remove_unwanted_fields(_new_test_case)
        history = self.get_history(new_commit, "change")
        old_document_key = hashlib.md5(json.dumps(_old_test_case, sort_keys=True)).hexdigest()
        new_document_key = hashlib.md5(json.dumps(_new_test_case, sort_keys=True)).hexdigest()
        client = CLIENT[BUCKET]
        try:
            old_document = client.get(old_document_key).value
        except:
            old_document = None
        if old_document_key == new_document_key:
            new_t.change_history = [history]
            to_upsert = new_t.__dict__
            new_conf = pydash.clone_deep(to_upsert['confFile'])
            pydash.merge_with(to_upsert, old_document, TestCaseCollector._merge_dict)
            TestCaseCollector._flatten_conf(to_upsert['confFile'], new_conf)
            client.upsert(old_document_key, to_upsert)
        else:
            old_t.change_history = [history]
            new_t.change_history = [history]
            old_t.changed = True
            new_t.changed = True
            old_t.newChangedDocId = new_document_key
            new_t.oldChangedDocId = old_document_key
            old_to_upsert = old_t.__dict__
            new_to_upsert = new_t.__dict__
            if old_document:
                new_conf = pydash.clone_deep(old_to_upsert['confFile'])
                old_to_upsert = pydash.merge_with(old_to_upsert, old_document, TestCaseCollector._merge_dict)
                TestCaseCollector._flatten_conf(old_to_upsert['confFile'], new_conf)
            try:
                new_document = client.get(new_document_key).value
            except:
                new_document = None
            if new_document:
                new_to_upsert = pydash.merge_with(new_to_upsert, new_document, TestCaseCollector._merge_dict)
            new_conf = pydash.clone_deep(new_to_upsert['confFile'])
            new_to_upsert = pydash.merge_with(new_to_upsert, old_document, TestCaseCollector._merge_dict)
            TestCaseCollector._flatten_conf(new_to_upsert['confFile'], new_conf)
            client.upsert(old_document_key, old_to_upsert)
            client.upsert(new_document_key, new_to_upsert)


    @staticmethod
    def get_diffs(diff_blob):
        lines_added = []
        lines_removed = []
        old_lines = []
        new_lines = []
        lines_modified = []
        removed = False
        for line in diff_blob:
            if line.startswith("-"):
                old_lines.append(line.replace("-", "", 1).strip())
                removed = True
                continue
            elif line.startswith("+"):
                new_lines.append(line.replace("+", "", 1).strip())
                if not removed:
                    continue
                else:
                    removed = False
                    old_line = old_lines.pop()
                    new_line = new_lines.pop()
                    change_percentage = SequenceMatcher(None, old_line, new_line).ratio()
                    if change_percentage > 0.5:
                        modified = {}
                        modified['old_test_line'] = old_line
                        modified['new_test_line'] = new_line
                        lines_modified.append(modified)
                    else:
                        lines_removed.append(old_line)
                        lines_added.append(new_line)
            elif line.startswith("?"):
                continue
            else:
                removed = False
                continue
        lines_removed.extend(old_lines)
        lines_added.extend(new_lines)
        return lines_removed, lines_added, lines_modified

    @staticmethod
    def get_diff(diff_blob):
        lines = diff_blob.split("\n")
        header_pattern = "@@ -\d+,\d+ \+\d+,\d+ @@"
        lines_added = []
        old_lines = []
        lines_removed = []
        lines_modified = []
        removed = False
        for line in lines:
            if re.match(header_pattern, line):
                # Header line in diff. Append all older lines to removed lines, if any
                removed = False
                lines_removed.extend(old_lines)
                old_lines = []
                continue
            if not line.startswith("-") and not line.startswith("+"):
                # not changed lines. Add remaining old lines to removed lines, if any
                removed = False
                lines_removed.extend(old_lines)
                old_lines = []
                continue
            if line.startswith("-"):
                # Older lines.
                removed = True
                removed_line = line.replace("-", "", 1)
                old_lines.append(removed_line)
            if line.startswith("+"):
                # Newer lines
                new_line = line.replace("+", "", 1)
                if removed:
                    # Could be line modification
                    old_line = old_lines.pop(0)
                    changed_percentage = SequenceMatcher(None, old_line, new_line).ratio()
                    if changed_percentage > 0.5:
                        modified = {}
                        modified['old_line'] = old_line
                        modified['new_line'] = new_line
                        lines_modified.append(modified)
                    else:
                        lines_removed.append(old_line)
                        lines_added.append(new_line)
                else:
                    # It's just addition of lines
                    lines_added.append(new_line)
        return lines_removed, lines_added, lines_modified

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

    @staticmethod
    def _flatten_conf(conf, new_conf):
        for _new_conf in new_conf:
            pydash.remove(conf, lambda x: x['conf'] == _new_conf['conf'])
        conf.extend(new_conf)

        #
# if __name__ == "__main__":
#     test_case_collector = TestCaseCollector()
#     #create_client()
#     test_case_collector.store_tests()