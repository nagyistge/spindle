###########################################################################
##
## Copyright (c) 2014 Adobe Systems Incorporated. All rights reserved.
##
## Licensed under the Apache License, Version 2.0 (the "License");
## you may not use this file except in compliance with the License.
## You may obtain a copy of the License at
##
## http://www.apache.org/licenses/LICENSE-2.0
##
## Unless required by applicable law or agreed to in writing, software
## distributed under the License is distributed on an "AS IS" BASIS,
## WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
## See the License for the specific language governing permissions and
## limitations under the License.
##
###########################################################################

import argparse
from urllib.request import urlopen
import yaml
import statistics
import os
import sys
import time
import re
from subprocess import Popen, PIPE
import traceback

scHost = "localhost"
scPort = 8605

class cd:
  def __init__(self, newPath): self.newPath = newPath
  def __enter__(self): self.savedPath = os.getcwd(); os.chdir(self.newPath)
  def __exit__(self, etype, value, traceback): os.chdir(self.savedPath)

def restartServers():
  global scPort
  print("Restarting server.")

  print("---Killing running application.")
  try:
    with cd("/Users/amos/sitecatalyst-spark"):
      p = Popen(["fab", "kill"], stdout=PIPE, stderr=PIPE)
      p.communicate()
  except: pass

  time.sleep(10)

  print("---Checking for running Spark application.")
  try:
    p1 = Popen(['curl', "http://localhost:9090/"], stdout=PIPE)
    p2 = Popen(['grep', 'Running Drivers', '-A', '10'],
        stdin=p1.stdout, stdout=PIPE)
    p3 = Popen(['grep', '<tr>'], stdin=p2.stdout, stdout=PIPE)
    p1.stdout.close(); p2.stdout.close()
    out=p3.communicate()[0].strip()
    print(out)
    restart = len(out) > 0
  except:
    traceback.print_exc()
    restart = True
  if restart:
    print("---Restarting Spark.")
    p = Popen(["fab", "-f",
      "/Users/amos/spark-cluster-deployment/initial-deployment-fabfile.py",
      "stopSparkWorkers", "stopSparkMaster"],
      stdout=PIPE, stderr=PIPE)
    out = p.communicate()
    print(out)
    p = Popen(["fab", "-f",
      "/Users/amos/spark-cluster-deployment/initial-deployment-fabfile.py",
      "startSparkWorkers", "startSparkMaster"],
      stdout=PIPE, stderr=PIPE)
    out = p.communicate()
    print(out)
    time.sleep(20)
  else:
    print("---Not restarting Spark.")

  # forward()
  print("---Starting SiteCatalyst query engine.")
  with cd("/Users/amos/sitecatalyst-spark"):
    p = Popen(["fab", "start"], stdout=PIPE, stderr=PIPE)
    out = [s.decode() for s in p.communicate()]
    print(out)
    port = re.search("DriverServer: server-(\d)", out[0]).group(1)
    scPort = int("860"+port)
    print(scPort)
  time.sleep(20)

def requestURL(req):
  try:
    return urlopen(req).read().decode()
  except:
    print(req)
    raise

def getDataLoadTime():
  global scHost, scPort
  print("Getting data load time.")
  request = "http://" + scHost + ":" + str(scPort) + "/loadTime"
  result = yaml.load(requestURL(request))
  print("  Result: " + str(result[1]['TimeMillis'] - result[0]['TimeMillis']))
  return result

def runQuery(name, start, finish, cache=False, targetPartitionSize=1500000):
  global scHost, scPort
  print("Running " + name + ".")
  print("  Cache: " + str(cache))
  print("  targetPartitionSize: " + str(targetPartitionSize))
  request = "http://" + scHost + ":" + str(scPort) + "/query?name=" + name + \
    "&start_ymd=" + start + "&finish_ymd=" + finish + "&profile=true"
  if cache: request += "&cache=true"
  request += "&targetPartitionSize=" + str(targetPartitionSize)
  result = yaml.load(requestURL(request))
  print("  Result: " + str(result[2]['TimeMillis'] - result[0]['TimeMillis']))
  return result

def restartSparkContext(memory, cores):
  global scHost, scPort
  tries = 0
  while tries < 3:
    print("Restarting with memory=" + memory + " and cores=" + str(cores))
    request = "http://" + scHost + ":" + str(scPort) + \
      "/restartSparkContext?memory=" + memory + "&cores=" + str(cores)
    result = requestURL(request)

    print("---Checking if Spark gave the requested number of cores.")
    p1 = Popen(['curl', "http://localhost:9090/"], stdout=PIPE)
    p2 = Popen(['grep', 'Running Applications', '-A', '12'],
        stdin=p1.stdout, stdout=PIPE)
    p1.stdout.close()
    obtainedCores=int(p2.communicate()[0].decode().split("\n")[-2].strip())
    print(obtainedCores)
    if obtainedCores == cores:
      return result
    print("Spark only provided " + str(obtainedCores) + " cores. Retrying.")
    tries += 1
  raise Exception("Did not obtain the correct number of cores.")
