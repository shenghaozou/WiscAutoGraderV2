# UW-Madison CS301 Test Script
# Assignment: Demo 2

from io import StringIO
import sys
import unittest
import os
import json

# May add try/except in the future
from demo import gcd

OK = 'pass'
FAIL = 'fail'
ERROR = 'error'
SKIP = 'skip'

# https://www.pythonsheets.com/notes/python-tests.html
class JsonTestResult(unittest.TextTestResult):
    def __init__(self, stream, descriptions, verbosity):
        super_class = super(JsonTestResult, self)
        super_class.__init__(stream, descriptions, verbosity)

        # TextTestResult has no successes attr
        self.successes = []

    def addSuccess(self, test):
        # addSuccess do nothing, so we need to overwrite it.
        super(JsonTestResult, self).addSuccess(test)
        self.successes.append(test)

    def json_append(self, test, result, out):
        suite = test.__class__.__name__
        if suite not in out:
            out[suite] = {OK: [], FAIL: [], ERROR:[], SKIP: []}
        if result is OK:
            out[suite][OK].append(test._testMethodName)
        elif result is FAIL:
            out[suite][FAIL].append(test._testMethodName)
        elif result is ERROR:
            out[suite][ERROR].append(test._testMethodName)
        elif result is SKIP:
            out[suite][SKIP].append(test._testMethodName)
        else:
            raise KeyError("No such result: {}".format(result))
        return out

    def jsonify(self):
        json_out = dict()
        for t in self.successes:
            json_out = self.json_append(t, OK, json_out)

        for t, _ in self.failures:
            json_out = self.json_append(t, FAIL, json_out)

        for t, _ in self.errors:
            json_out = self.json_append(t, ERROR, json_out)

        for t, _ in self.skipped:
            json_out = self.json_append(t, SKIP, json_out)

        return json_out

# Please don't change the test class name,
# Please only use one unittest class at least for now
class CS301Test(unittest.TestCase):
    def testFunction1(self):
        self.assertEqual(gcd(12, 4), 4)
    def testFunction2(self):
        self.assertEqual(gcd(17, 23), 2)
    def testFunction3(self):
        with self.assertRaises(TypeError):
            gcd("a", True)

def calcGrade(jsonResult):
    grade = 0
    passedTest = jsonResult["CS301Test"][OK]
    if "testFunction1" and "testFunction2" in passedTest:
        grade += 2
    if "testFunction3" in passedTest:
        grade += 1
    return grade

if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(CS301Test)
    capturedOut = StringIO()
    runner = unittest.TextTestRunner(stream=capturedOut)
    runner.resultclass = JsonTestResult
    result = runner.run(suite)
    jsonOutput = result.jsonify()
    if not os.environ.get('DISABLE_DISPLAY'):
        print(capturedOut.getvalue())
    jsonOutput['result'] = capturedOut.getvalue()
    jsonOutput['grade'] = calcGrade(jsonOutput)
    if os.environ.get("ENABLE_LOG"):
        with open("result.json","w") as fw:
            json.dump(jsonOutput, fw)
    else:
        print("\nYour grade:{}".format(jsonOutput['grade']))
