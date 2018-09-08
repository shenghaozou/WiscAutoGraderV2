import base64, boto3, botocore, logging, os, sys, json, subprocess, shutil
from flask import Flask

ACCESS_PATH = "projects/{project}/users/{googleId}/curr.json"
CODE_PATH = "./submission"
TEST_DIR = "/tmp/test"

SUBMISSIONS = 'submissions'
BUCKET = 'caraza-harter-cs301'
session = boto3.Session(profile_name='cs301ta')
s3 = session.client('s3')

app = Flask(__name__)

logging.basicConfig(
    handlers=[
        logging.FileHandler("testServer.log"),
        logging.StreamHandler()
    ],
    level=logging.INFO)

def downloadSubmission(projectPath):
    # a project path will look something like this:
    # projects/p0/users/115799594197844895033/curr.json

    userId = projectPath.split('/')[-2]

    # create user dir for download
    logging.info('download to {}'.format(CODE_PATH))
    if not os.path.exists(CODE_PATH):
        os.mkdir(CODE_PATH)

    # download
    response = s3.get_object(Bucket=BUCKET, Key=projectPath)
    submission = json.loads(response['Body'].read().decode('utf-8'))
    fileContents = base64.b64decode(submission.pop('payload'))
    with open(os.path.join(CODE_PATH, submission['filename']), 'wb') as f:
        f.write(fileContents)
    with open(os.path.join(CODE_PATH, 'meta.json'), 'w') as f:
        f.write(json.dumps(submission, indent=2))

def lookupGoogleId(netId):
    path = 'users/net_id_to_google/%s.txt' % netId
    try:
        response = s3.get_object(Bucket=BUCKET, Key=path)
        net_id = response['Body'].read().decode('utf-8')
        return net_id
    except botocore.exceptions.ClientError as e:
        if not e.response['Error']['Code'] == "NoSuchKey":
            # unexpected error
            logging.warning(
                'Unexpected error when look up Googlg ID: %s' % e.response['Error']['Code'])
        return None

def fetchFromS3(project, netId):
    googleId = lookupGoogleId(netId)
    if not googleId:
        return None
    curPath = ACCESS_PATH.format(project=project, googleId=googleId)
    downloadSubmission(curPath)

def sendToDocker(project, netId):
    # create directory to mount inside a docker container
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    shutil.copytree(CODE_PATH, TEST_DIR)
    shutil.copytree("./io", TEST_DIR + "/io")
    logging.warning(TEST_DIR + "/io")
    shutil.copy('./test/testCore.py', TEST_DIR)
    shutil.copy('./test/testMain.py', TEST_DIR)

    # run tests inside a docker container

    image = 'python:3.7-stretch' # TODO: find/build some anaconda image

    cmd = ['docker', 'run',                           # start a container
           '-v', os.path.abspath(TEST_DIR)+':/code',  # share the test dir inside
           '-w', '/code',                             # working dir is w/ code
           image,                                     # what docker image?
           'python3', 'testMain.py',
           '-p', project,
           '-i', netId]                      # command to run inside
    logging.info("docker cmd:" + ' '.join(cmd))
    output = subprocess.check_output(cmd)
    print(output)
    with open(TEST_DIR + '/result.json') as fr:
        result = fr.read()
    return result

@app.route('/')
def index():
    return "grading URL: /grading/\<project\>/\<netId\>"

@app.route('/json/<project>/<netId>')
def gradingJson(project, netId):
    fetchFromS3(project, netId)
    return sendToDocker(project, netId)

@app.route('/html/<project>/<netId>')
def gradingHtml(project, netId):
    result = json.loads(gradingJson(project, netId))
    display = ""
    if "result" in result:
        display +=  "<h2>Unit Test Output</h2><p>{}</p>".format(
            result["result"].replace("\n", "<br>"))
    if "CS301Test" in result:
        detail = result["CS301Test"]
        detailDisplay = ""
        for resultType in detail:
            if detail[resultType]:
                    detailDisplay += "<li>{}: {}</li>".format(
                        resultType, ", ".join(detail[resultType]))
        if detailDisplay:
            display += "<h2>Unit Test Result</h2><ul>{}</ul>".format(detailDisplay)
    if "grade" in result:
        display += "<h2>Grade</h2><p>{}</p>".format(result["grade"])

    if "error" in result:
        errorReport = result["error"]
        if "output" in errorReport:
            display += "<h2>Unit Test Error Report</h2><p>{}</p>".format(
                errorReport["output"].replace("\n", "<br>"))
    return display
