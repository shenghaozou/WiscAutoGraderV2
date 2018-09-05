# UW-Madison CS301 Test Script
import argparse
import boto3
from io import StringIO
import json
import os
import resource
import subprocess
import sys

def uploadResult(project, studentID, errorLog={}):
    session = boto3.Session(profile_name='cs301ta')
    s3 = session.client('s3')
    bucket = 'caraza-harter-cs301'
    if errorLog:
        serializedResult = json.dumps({'error': errorLog})
    else:
        with open("result.json", "r") as fr:
            serializedResult = fr.read()
    s3.put_object(
        Bucket=bucket,
        Key='ta/grading/{}/{}.txt'.format(project, studentID),
        Body=serializedResult.encode('utf-8'),
        ContentType='text/plain')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='CS301 test monitor')
    parser.add_argument('-i', '--id', help='set student id', required=True)
    parser.add_argument('-p', '--project', help='set project name', required=True)
    args = parser.parse_args()

    try:
        os.remove("result.json")
    except OSError:
        pass

    # some self-defined error code list:
    # 504 Timeout
    # 404 Result.json not generated
    # 503 Infra error
    errorLog = {}
    try:
        subprocess.check_output(
            ["python3", "-m", "unittest", "testCore"],
            universal_newlines=True,
            stdin=open("default.txt", "r"), # default.txt is an empty file
            stderr=subprocess.STDOUT,
            timeout=3) # timeout: 3s
    except subprocess.CalledProcessError as err:
        errorLog = {'errorCode': err.returncode,
                    'output': err.output}
    except subprocess.TimeoutExpired as err:
        errorLog = {'errorCode': 504} # Use 504 here for timeout
    except Exception as e:
        errorLog = {'errorCode': 503,
                    'output': str(e)}
    # check the existence of result.json
    if not os.path.exists("result.json"):
        errorLog = {'errorCode': 404}

    uploadResult(args.project, args.id, errorLog)
