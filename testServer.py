import base64, boto3, botocore, logging, os, sys, json, subprocess, shutil, threading, time
from flask import Flask

ACCESS_PATH = "projects/{project}/users/{googleId}/curr.json"
CODE_DIR = "./submission"
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

class timerThread(threading.Thread):
    def __init__(self, dockerId, project, netId):
        threading.Thread.__init__(self)
        self.dockerId = dockerId
        self.project = project
        self.netId = netId
    def run(self):
        dockerTimer(self.dockerId, self.project, self.netId)

def downloadSubmission(projectPath):
    # a project path will look something like this:
    # projects/p0/users/115799594197844895033/curr.json

    userId = projectPath.split('/')[-2]

    # create user dir for download
    logging.info('download to {}'.format(CODE_DIR))
    if os.path.exists(CODE_DIR):
        shutil.rmtree(CODE_DIR)
    os.mkdir(CODE_DIR)

    # download
    response = s3.get_object(Bucket=BUCKET, Key=projectPath)
    submission = json.loads(response['Body'].read().decode('utf-8'))
    fileContents = base64.b64decode(submission.pop('payload'))
    with open(os.path.join(CODE_DIR, submission['filename']), 'wb') as f:
        f.write(fileContents)
    with open(os.path.join(CODE_DIR, 'meta.json'), 'w') as f:
        f.write(json.dumps(submission, indent=2))

def uploadResult(project, studentID, errorLog = None):
    if errorLog:
        serializedResult = json.dumps(errorLog)
    else:
        with open("{}/result.json".format(TEST_DIR), "r") as fr:
            serializedResult = fr.read()
    s3.put_object(
        Bucket=BUCKET,
        Key='ta/grading/{}/{}.json'.format(project, studentID),
        Body=serializedResult.encode('utf-8'),
        ContentType='text/plain')

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
                'Unexpected error when look up Googlg ID:' + e.response['Error']['Code'])
        raise e

def fetchFromS3(project, netId):
    googleId = lookupGoogleId(netId)
    if not googleId:
        return None
    curPath = ACCESS_PATH.format(project=project, googleId=googleId)
    downloadSubmission(curPath)

def containerStatus(dockerId):
    checkCmd = ["docker", "inspect", "-f", "{{.State.ExitCode}} {{.State.Running}}", dockerId]
    output = subprocess.check_output(checkCmd).decode("ascii").replace("\n","")
    response = output.split(' ')
    str2bool = {"false" : False, "true" : True}
    if len(response) == 2:
        return int(response[0]), str2bool[response[1]]
    else:
        logging.warning("Unexpected response when checking the container {} running status. Response: {}".format(dockerId, output))
        return None, None

def dockerTimer(dockerId, project, netId):
    forceKillCmd = ["docker", "rm", "-f", dockerId]
    time.sleep(3)
    exitCode, isRunning = containerStatus(dockerId)
    if isRunning:
        subprocess.run(forceKillCmd)
        uploadResult(project, netId, {"error":"Timeout"})
        logging.info("project: {}, netid: {}, timeout".format(project, netId))
    elif exitCode:
        uploadResult(project, netId, {"error":"ExitCode:" + str(exitCode)})
        logging.info("project: {}, netid: {}, exit with {}".format(project, netId, exitCode))
    else:
        uploadResult(project, netId)
        logging.info("project: {}, netid: {}, docker exit normally".format(project, netId))

def sendToDocker(project, netId):
    # create directory to mount inside a docker container
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    shutil.copytree(CODE_DIR, TEST_DIR)
    shutil.copytree("./io", TEST_DIR + "/io")
    # we can't use shutil.copytree here again because TEST_DIR exists
    testCodePath = "./test/{}".format(project)
    for item in os.listdir(testCodePath):
        src = os.path.join(testCodePath, item)
        dest = os.path.join(TEST_DIR, item)
        if os.path.isdir(src):
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)

    # run tests inside a docker container
    image = 'python:3.7-stretch' # TODO: find/build some anaconda image

    cmd = ['docker', 'run',                           # start a container
           '-d',                                      # detach mode
           '-v', os.path.abspath(TEST_DIR)+':/code',  # share the test dir inside
           '-w', '/code',                             # working dir is w/ code
           image,                                     # what docker image?
           'python3', 'test.py',
           '-p', project,
           '-i', netId]                      # command to run inside
    logging.info("docker cmd:" + ' '.join(cmd))
    dockerId = subprocess.check_output(cmd).decode("ascii").replace("\n","")
    logging.info("docker id:" + dockerId)
    waitDockerCmd = ['docker', 'wait', dockerId]
    timer = timerThread(dockerId, project, netId)
    timer.start()
    subprocess.check_output(waitDockerCmd)

@app.route('/')
def index():
    return "index"

@app.route('/json/<project>/<netId>')
def gradingJson(project, netId):
    try:
        fetchFromS3(project, netId)
        sendToDocker(project, netId)
    except Exception as e:
        logging.warning("Unexpected Error: " + str(e))
    return "{}"
