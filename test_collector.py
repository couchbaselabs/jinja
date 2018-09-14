import hashlib
import json
import re
import shutil
import ConfigParser

from difflib import ndiff

from os import path
from os import walk

import git
import pydash

from couchbase import set_json_converters as cb_set_json_converters
from couchbase.bucket import LOCKMODE_WAIT
from couchbase.cluster import Cluster
from couchbase.cluster import PasswordAuthenticator
from couchbase.n1ql import N1QLQuery

cb_set_json_converters(json.dumps, json.loads)


class TestCaseDocument(object):
    def __init__(self, test_name, tc_param_dict):
        self.testName = test_name          # Test case line without parameters. Eg: folder.Class.function_name
        self.testParams = tc_param_dict    # Parameter name as key and value as dictionary value
        self.confFile = []                 # List of conf files under which this case is run
        self.priority = ""                 # Defines the priority of the case
        self.changeHistory = []            # Stores list of git commit wrt to this case

        self.defined = True       # True if the test definition exists
        self.testStatus = dict()  # Key is the conf_file with value is either of Active / Deleted / Commented
        self.os = dict()          # Stores results with OS type as key and list of build num with results json
        self.component = dict()   # Dictionary of component as key and sub-components as list of values

    @staticmethod
    def generate_document_key(test_name, tc_param_dict):
        return test_name + "#" + hashlib.md5(json.dumps(tc_param_dict, sort_keys=True)).hexdigest()

    @staticmethod
    def read_test_params(tc_line):
        tc_param_dict = dict()
        test_line_segments = tc_line.split(",")
        if len(test_line_segments) <= 1:
            return tc_param_dict

        tc_param_str = ",".join(test_line_segments[1:])
        split_params = tc_param_str.split('=')
        split_param_len = len(split_params)
        index = 0
        m_key = m_val = None
        while index < split_param_len:
            inner_split = split_params[index].rsplit(",", 1)
            for tem_split in inner_split:
                if m_key is None:
                    m_key = tem_split
                elif m_val is None:
                    m_val = tem_split

                if m_key and m_val:
                    tc_param_dict[m_key] = m_val
                    m_key = m_val = None
            index += 1
        return tc_param_dict

    @staticmethod
    def append_conf_file(conf_file_name, conf_file_list):
        if conf_file_name not in conf_file_list:
            conf_file_list.append(conf_file_name)

    @staticmethod
    def append_change_history(history_dict, change_history):
        for change_dict in change_history:
            if cmp(history_dict, change_dict) == 0:
                return
        change_history.append(history_dict)

    @staticmethod
    def is_test_line_updated(old_line, new_line):
        # If test definition do not match, return False
        if old_line.split(",")[0] != new_line.split(",")[0]:
            return False

        # Read params from old and new line
        old_tc_params = TestCaseDocument.read_test_params(old_line)
        new_tc_params = TestCaseDocument.read_test_params(new_line)

        # Get keys for old and new param dictionaries
        old_tc_param_keys = old_tc_params.keys()
        new_tc_param_keys = new_tc_params.keys()

        # Return False, if length of dictionary keys is not same
        if len(old_tc_param_keys) != len(new_tc_param_keys):
            return False

        # Return False, if mismatch in key name
        for tem_key in old_tc_param_keys:
            if tem_key not in new_tc_param_keys:
                return False

        return True


class TestCaseCollector:
    def __init__(self, user_config):
        self.cbServerHost = user_config.get("CouchbaseServer", "hostName")
        self.cbUsername = user_config.get("CouchbaseServer", "username")
        self.cbPassword = user_config.get("CouchbaseServer", "password")

        self.bucketName = user_config.get("TestCollector", "bucketName")
        self.testRunnerDir = user_config.get("TestCollector", "testRunnerDir")
        self.confDir = user_config.get("TestCollector", "confDir")
        self.testDir = user_config.get("TestCollector", "testDir")

        self.client = dict()
        self.testResultLimit = 50

        # Variables used in local scope
        test_runner_branch = user_config.get("TestCollector", "testRunnerBranch")
        test_runner_repo_link = user_config.get("TestCollector", "testRunnerRepo")

        # If exists, pull repo for latest changes, else clone repo locally
        if path.exists(self.testRunnerDir):
            self.testRunnerRepo = git.Repo.init(self.testRunnerDir)
            # origin = self.testRunnerRepo.remotes.origin
            # origin.pull()
        else:
            shutil.rmtree(self.testRunnerDir, ignore_errors=True)
            self.testRunnerRepo = git.Repo.clone_from(test_runner_repo_link, self.testRunnerDir,
                                                      branch=test_runner_branch)

        # Point the head to current repo's head
        self.currentHead = self.testRunnerRepo.head.commit

    def create_client(self):
        client_creation_success = True
        try:
            cb_cluster = Cluster("couchbase://{0}". format(self.cbServerHost))
            cb_cluster.authenticate(PasswordAuthenticator(self.cbUsername, self.cbPassword))
        except Exception as cb_cluster_err:
            print("Error while connecting to cluster couchbase://{0} {1}".format(self.cbServerHost, cb_cluster_err))
            client_creation_success = False
            return client_creation_success

        try:
            client = cb_cluster.open_bucket(self.bucketName, lockmode=LOCKMODE_WAIT)
            self.client[self.bucketName] = client
        except Exception as cb_bucket_err:
            print("Error while creating client for {0} {1}".format(self.bucketName, cb_bucket_err))
            client_creation_success = False
        return client_creation_success

    def get_test_case_from_test_result(self, test_result):
        class_name = test_result["className"]
        test_name = test_result["name"]
        test_case = dict(item.split(":", 1) if ":" in item else [item, ''] for item in test_name.split(",")[1:])
        test_case["testName"] = test_name.split(",")[0]
        test_case["className"] = class_name
        return test_case

    def get_test_cases_from_conf(self, conf_file):
        conf_file_path = path.join(self.testRunnerDir, self.confDir, conf_file)
        test_cases_dict = []
        try:
            with file(conf_file_path, 'r') as f:
                class_name = ""
                for line in f:
                    class_name, test_case = self.get_test_case_from_line(line, class_name)
                    if test_case:
                        test_cases_dict.append(test_case)
        except Exception as e:
            print("Get test case from conf: {0}".format(e))
        return test_cases_dict

    def get_test_case_from_line(self, line, class_name):
        name = line.strip()
        commented = False

        if len(name) <= 0:
            return class_name, None

        if name.startswith("#"):
            commented = True
            name = name.lstrip("#").strip()

        if name.endswith(":"):
            class_name = name.split(":")[0]
            return class_name, None

        if class_name and class_name.lower() == "params":
            return class_name, None
        elif class_name and line.startswith(" "):
            name = class_name + "." + name

        if commented and not TestCaseCollector.check_if_test(name):
            return class_name, None

        test_name = name.split(",")[0]
        class_name = ".".join(test_name.split('.')[0:-1])

        test_case = dict(item.split("=", 1) if "=" in item else [item, ''] for item in name.split(",")[1:])
        if len(class_name) != 0:
            test_case['testLine'] = name[name.find(class_name) + len(class_name) + 1:]
        else:
            test_case['testLine'] = name[name.find(class_name) + len(class_name):]

        test_case['testName'] = test_name
        test_case['className'] = class_name
        test_case['commented'] = commented
        return class_name, test_case

    @staticmethod
    def check_if_test(line_in_conf):
        """
        Check if given test line is a test case present in pytests or not.
        Check if test line fits following patterns:
            1. (moduleName.)+(testName),params
            2. (moduleName)+(testName)
        :param line_in_conf: the line to be tested
        :return: True if test
        """

        # Test case with class name and params
        pattern1 = "([a-zA-Z][\w]+\.)+([a-zA-Z][\w]+){1},[a-zA-Z]"
        pattern2 = "([a-zA-Z][\w]+\.)+([a-zA-Z][\w]+){1}"

        p1_match = re.match(pattern1, line_in_conf)
        p2_match = re.match(pattern2, line_in_conf)

        if p1_match or p2_match:
            return True
        return False

    @staticmethod
    def get_test_case_string(tc_str):
        str_to_return = ""
        char_stack = []
        quote_char_list = ["'", "\""]
        pair_char = dict()
        pair_char["{"] = "}"
        pair_char["("] = ")"
        pair_char["["] = "]"
        for char in list(tc_str):
            if char in ["#", " "]:
                if len(char_stack) == 0:
                    str_to_return = ""
                else:
                    str_to_return += char
            elif char in quote_char_list and str_to_return != "":
                if len(char_stack) != 0:
                    if char_stack[-1] == char:
                        char_stack.pop()
                else:
                    char_stack.append(char)
                str_to_return += char
            elif char in pair_char.keys():
                if len(char_stack) != 0 and str_to_return != "":
                    char_stack.append(char)
                    str_to_return += char
                else:
                    str_to_return = ""
            elif char in pair_char.values():
                if len(char_stack) != 0 and char_stack[-1] == pair_char.keys()[pair_char.values().index(char)]:
                    char_stack.pop()
                    str_to_return += char
                else:
                    str_to_return = ""
            elif char in ["_", ".", "=", ",", ";", ":"]:
                str_to_return += char
            elif char.isalnum():
                str_to_return += char
            else:
                if len(char_stack) != 0:
                    str_to_return += char

        if len(char_stack) != 0:
            str_to_return = ""
        return str_to_return

    @staticmethod
    def get_test_cases_from_blob(blob):
        test_cases = []
        class_name = ""
        for line in blob.splitlines():
            tc_str = line.strip()
            commented = False
            if tc_str.startswith("#"):
                commented = True
                tc_str = tc_str.lstrip("#").strip()

            # Get class name and if class name is 'params' then continue
            if tc_str.endswith(":"):
                class_name = tc_str.split(":")[0]
                continue

            if class_name and class_name.lower() == "params":
                continue

            tc_str = TestCaseCollector.get_test_case_string(tc_str)
            if not tc_str:
                continue
            elif commented and re.search("^[a-zA-Z0-9]+$", tc_str):
                continue

            if class_name and line.startswith(" "):
                tc_str = class_name + "." + tc_str

            if commented:
                tc_str = "# " + tc_str

            # Add test case to list only if non-empty string
            if tc_str:
                test_cases.append(tc_str)
        return test_cases

    def get_conf_from_store(self, test_case_to_find):
        class_name = test_case_to_find['className']
        test_name = test_case_to_find['testName']
        query = "SELECT confFile, testName, className from {0} where testName = '{1}' and className = '{2}'".format(
            self.bucketName, test_name, class_name)
        client = self.client[self.bucketName]
        for row in client.n1ql_query(N1QLQuery(query)):
            conf_files = row['confFile']
            for entry in conf_files:
                test_line = entry['testLine']
                class_name = ".".join(test_line.split(",")[0].split('.')[0:-1])
                test_case = dict(item.split("=", 1) if "=" in item else [item, ''] for item in test_line.split(",")[1:])
                test_case['testName'] = row['testName']
                if len(class_name) != 0:
                    test_case['testLine'] = test_line[test_line.find(class_name) + len(class_name) + 1:]
                else:
                    test_case['testLine'] = test_line[test_line.find(class_name) + len(class_name):]
                test_case['className'] = row['className']
                if set(test_case.items()).issubset(set(test_case_to_find.items())):
                    return entry['conf']
        return None

    def get_test_case_id(self, test_result):
        test_case = self.get_test_case_from_test_result(test_result)
        conf_file = test_case['conf_file'] if 'conf_file' in test_case else self.get_conf_from_store(test_case)
        conf_dir_path = self.confDir + "/"
        if not conf_file:
            return
        if conf_dir_path in conf_file:
            conf_file = conf_file.replace(conf_dir_path, '')
        test_cases = self.get_test_cases_from_conf(conf_file)
        test_cases_clone = pydash.clone_deep(test_cases)

        test_cases_dict_without_groups = pydash.for_each(test_cases_clone, TestCaseCollector.remove_unwanted_fields)
        callback = lambda x: set(x.items()).issubset(set(test_case.items()))
        index = pydash.find_index(test_cases_dict_without_groups, callback)
        if index == -1:
            return None
        name = test_cases[index]
        TestCaseCollector.remove_unwanted_fields(name)
        return hashlib.md5(json.dumps(name, sort_keys=True)).hexdigest()

    def store_test_result(self, test_result, build_details):
        test_case_id = self.get_test_case_id(test_result)
        if not test_case_id:
            return
        client = self.client[self.bucketName]
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
            test = dict()
            test['build_id'] = build_id
            test['build'] = build
            test['result'] = test_result['status']
            test['duration'] = test_result['duration']
            test['errorStackTrace'] = test_result['errorStackTrace']
            test['url'] = build_details['url']
            """ Trim tests to store only TESTS_RESULT_LIMIT tests results"""
            if len(tests) > self.testResultLimit - 1:
                tests = tests[len(tests) - self.testResultLimit + 1:]
            tests.append(test)
            client.upsert(test_case_id, document)
        except Exception as e:
            print("Store test result: {0}".format(e))

    @staticmethod
    def append_test_case_to_bucket_doc(tc_in_bucket_doc, tc_doc_to_append):
        for tem_tc in tc_in_bucket_doc:
            if cmp(tem_tc['testParams'], tc_doc_to_append['testParams']) == 0:
                return
        tc_in_bucket_doc.append(tc_doc_to_append)

    def add_or_remove_test_case(self, test_case, new_commit, conf_file_name, edit_mode):
        client = self.client[self.bucketName]

        history = TestCaseCollector.get_history(new_commit, edit_mode)
        class_name, _test_case = self.get_test_case_from_line(test_case, "")

        if _test_case is None:
            return

        # Read test_params from test case line as dict object
        tc_param_dict = TestCaseDocument.read_test_params(test_case)

        # Generate key for tc_doc
        document_key = TestCaseDocument.generate_document_key(_test_case['testName'], tc_param_dict)

        # Creates / Retrieves the bucket doc as dict based on document_key as key
        try:
            tc_doc = client.get(document_key).value
        except Exception as retrieve_doc_err:
            if edit_mode == "delete":
                print("Failed to retrieve {0} with key {1}: {2}".format(_test_case['testName'], document_key,
                                                                        retrieve_doc_err))
                return
            tc_doc = TestCaseDocument(_test_case['testName'], tc_param_dict).__dict__

        if edit_mode == "create":
            TestCaseDocument.append_conf_file(conf_file_name, tc_doc['confFile'])

        # Set the test case status wrt the conf_file based on edit_mode
        if edit_mode == "create":
            if _test_case['commented']:
                tc_doc['testStatus'][conf_file_name] = "Commented"
            else:
                tc_doc['testStatus'][conf_file_name] = "Active"
        elif edit_mode == "delete":
            tc_doc['testStatus'][conf_file_name] = "Deleted"

        TestCaseDocument.append_change_history(history, tc_doc['changeHistory'])

        # Writes to bucket
        client.upsert(document_key, tc_doc)

    def update_existing_test_case(self, test_case, new_commit, conf_file_name):
        client = self.client[self.bucketName]

        history = TestCaseCollector.get_history(new_commit, "change")
        class_name, _old_test_case = self.get_test_case_from_line(test_case['old_test_line'], "")
        class_name, _new_test_case = self.get_test_case_from_line(test_case['new_test_line'], "")

        if _new_test_case is None:
            return

        # Read test_params from test case line as dict object
        old_tc_param_dict = TestCaseDocument.read_test_params(test_case['old_test_line'])
        new_tc_param_dict = TestCaseDocument.read_test_params(test_case['new_test_line'])

        # Generate key for tc_doc
        old_document_key = TestCaseDocument.generate_document_key(_old_test_case['testName'], old_tc_param_dict)
        new_document_key = TestCaseDocument.generate_document_key(_new_test_case['testName'], new_tc_param_dict)

        try:
            tc_doc = client.get(old_document_key).value
        except Exception:
            tc_doc = TestCaseDocument(_new_test_case['testName'], new_tc_param_dict).__dict__

        # Set the test case status wrt the conf_file based on edit_mode
        if _new_test_case['commented']:
            tc_doc['testStatus'][conf_file_name] = "Commented"
        else:
            tc_doc['testStatus'][conf_file_name] = "Active"

        TestCaseDocument.append_change_history(history, tc_doc['changeHistory'])

        # Writes to bucket
        client.upsert(new_document_key, tc_doc)

    def store_test_cases_in_diffs(self, diffs):
        conf_dir_path = self.confDir + "/"
        for diff in diffs['diff']:
            if not diff.a_blob and not diff.b_blob:
                # if both blobs are not available, just continue with other differences
                continue
            new_commit = diffs['new_commit']
            if not diff.a_blob:
                # If first blob is not available, then this is a new addition of file. Do addition of testcases
                conf = diff.b_path
                conf = conf[conf.find(conf_dir_path) + len(conf_dir_path):]
                b_blob = diff.b_blob.data_stream.read()
                b_test_cases = TestCaseCollector.get_test_cases_from_blob(b_blob)
                for test_case in b_test_cases:
                    self.add_or_remove_test_case(test_case, new_commit, conf, "create")
                continue
            if not diff.b_blob:
                # If second blob is not available, then the conf file was deleted. Do removal of testcases
                conf = diff.a_path
                conf = conf[conf.find(conf_dir_path) + len(conf_dir_path):]
                a_blob = diff.a_blob.data_stream.read()
                a_test_cases = TestCaseCollector.get_test_cases_from_blob(a_blob)
                for test_case in a_test_cases:
                    self.add_or_remove_test_case(test_case, new_commit, conf, "delete")
                continue
            conf = diff.b_path
            conf = conf[conf.find(conf_dir_path) + len(conf_dir_path):]
            a_blob = diff.a_blob.data_stream.read()
            b_blob = diff.b_blob.data_stream.read()
            a_test_cases = TestCaseCollector.get_test_cases_from_blob(a_blob)
            b_test_cases = TestCaseCollector.get_test_cases_from_blob(b_blob)
            a_test_cases = ["{}\n".format(line) for line in a_test_cases if line]
            b_test_cases = ["{}\n".format(line) for line in b_test_cases if line]
            diff_blob = list(ndiff(a_test_cases, b_test_cases))
            test_cases_removed, test_cases_added, test_cases_modified = TestCaseCollector.get_diffs(diff_blob)
            for test_case in test_cases_removed:
                self.add_or_remove_test_case(test_case, new_commit, conf, "delete")
            for test_case in test_cases_added:
                self.add_or_remove_test_case(test_case, new_commit, conf, "create")
            for test_case in test_cases_modified:
                self.update_existing_test_case(test_case, new_commit, conf)

    def store_tests(self):
        for root, sub_dirs, files in walk(path.join(self.testRunnerDir, self.confDir)):
            for conf_file in files:
                if not conf_file.endswith(".conf"):
                    continue

                file_path = path.join(root, conf_file)
                conf_file = path.basename(file_path)
                file_history = list(self.testRunnerRepo.iter_commits(paths=file_path))

                # First commit when conf_file was created
                first_commit = file_history[-1]

                # Previous commit of first_commit in git log
                parent_commit = first_commit.parents[0]

                """
                conf/py-1node-sanity.conf
                =======================================================
                lhs: None
                rhs: 100644 | 794752153a9aa866c150c8b7074a343036bfe99f
                file added in rhs
                """
                first_diff = parent_commit.diff(first_commit, file_path)[0]

                # File blob content with respect to first commit
                initial_blob = first_diff.b_blob.data_stream.read()

                # Returns test case list from the commit change
                initial_test_cases = TestCaseCollector.get_test_cases_from_blob(initial_blob)
                for test_case in initial_test_cases:
                    self.add_or_remove_test_case(test_case, first_commit, conf_file, "create")

                # Now store the rest of the history
                file_history.reverse()
                for index, history in enumerate(file_history[1:]):
                    old_commit = file_history[index]
                    new_commit = history
                    diffs = TestCaseCollector.get_diff_between_commits(old_commit, new_commit, file_path)
                    self.store_test_cases_in_diffs(diffs)

    def check_for_changes(self):
        origin = self.testRunnerRepo.remotes.origin
        self.testRunnerRepo.heads.master.checkout()
        old_head_commit = self.testRunnerRepo.head.commit
        origin.pull()
        current_head_commit = self.testRunnerRepo.head.commit
        if old_head_commit == current_head_commit:
            # No update to repository.
            return False, None
        diff = TestCaseCollector.get_diff_between_commits(old_head_commit, current_head_commit,
                                                          path.join(self.testRunnerDir, self.confDir))
        if not diff:
            return False, None
        return True, diff

    def update_test_case_repository(self):
        updated, diffs = self.check_for_changes()
        if not updated:
            return
        self.store_test_cases_in_diffs(diffs)

    @staticmethod
    def get_history(new_commit, commit_type):
        history = dict()
        history['author'] = new_commit.committer.name
        history['commitDate'] = new_commit.committed_datetime.__str__()
        history['commitTime'] = new_commit.committed_date
        history['commitSha'] = new_commit.hexsha
        history['changeType'] = commit_type
        return history

    @staticmethod
    def get_diffs(diff_blob):
        lines_added = []
        lines_removed = []
        lines_modified = []
        old_lines = []
        new_lines = []
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
                    # change_percentage = SequenceMatcher(None, old_line, new_line).ratio()
                    # if change_percentage > 0.5:
                    is_test_updated = TestCaseDocument.is_test_line_updated(old_line, new_line)
                    if is_test_updated:
                        modified = dict()
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
    def get_diff_between_commits(old_commit, new_commit, file_path):
        diffs = old_commit.diff(new_commit, file_path, create_patch=True)
        if len(diffs) == 0:
            return None
        diff = dict()
        diff['old_commit'] = old_commit
        diff['new_commit'] = new_commit
        diff['diff'] = diffs
        return diff

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

    @staticmethod
    def remove_unwanted_fields(test_case):
        pydash.unset(test_case, "GROUP")


if __name__ == "__main__":
    user_config_file_path = "config.cfg"
    config = ConfigParser.ConfigParser()
    config.read(user_config_file_path)

    test_case_collector = TestCaseCollector(config)
    client_creation_successful = test_case_collector.create_client()
    if client_creation_successful:
        test_case_collector.store_tests()
