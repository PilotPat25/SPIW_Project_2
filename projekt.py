import socket
import subprocess
import sys
import re
import time
import requests
import json
from threading import Thread

PROMETHEUS_ADDR = "192.168.1.210"
PORT = 9090
TIMEOUT = 5


def start_server(host='0.0.0.0', port=65432):
    """Start the socket server to listen for incoming JSON data."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen()
        s.settimeout(30)
        print(f"Server listening on {host}:{port}")

        try:
            while True:
                conn, addr = s.accept()
                data = conn.recv(1024)
                stringdata = data.decode('utf-8')
                #data_json = json.loads(data.decode('utf-8'))
                # Start a new thread to handle the connection
                Thread(target=read_parameters(stringdata), args=(conn, addr)).start()
        except socket.timeout:
            pass
        finally:
            s.settimeout(None)
            s.close()

def read_parameters(stringdata):
    global AMFS0, CPU0, AMFS1, CPU1, AMFS2, CPU2, AMFS3, CPU3 , CPU0LOAD, CPU1LOAD, CPU2LOAD, CPU3LOAD
    try:
            data_json = stringdata.split('{',1)[1]
            data_json = '{' + data_json
            data_json = json.loads(data_json)
            print(data_json)
            AMFS0 = data_json.get("AMFS0", AMFS0)
            CPU0 = data_json.get("CPU0", CPU0)
            CPU0LOAD = data_json.get("CPU0LOAD", CPU0LOAD)
            AMFS1 = data_json.get("AMFS1", AMFS1)
            CPU1 = data_json.get("CPU1", CPU1)
            CPU1LOAD = data_json.get("CPU1LOAD", CPU1LOAD)
            AMFS2 = data_json.get("AMFS2", AMFS2)
            CPU2 = data_json.get("CPU2", CPU2)
            CPU2LOAD = data_json.get("CPU2LOAD", CPU2LOAD)
            AMFS3 = data_json.get("AMFS3", AMFS3)
            CPU3 = data_json.get("CPU3", CPU3)
            CPU3LOAD = data_json.get("CPU3LOAD", CPU3LOAD)
            print(f"New parameters tresholds:\n AMF {AMFS0}<{AMFS1}<{AMFS2}<{AMFS3} \n CPU LOAD {CPU0LOAD}<{CPU1LOAD}<{CPU2LOAD}<{CPU3LOAD} \n CPU Limits {CPU0}<{CPU1}<{CPU2}<{CPU3}")
    except FileNotFoundError:
        print(f"Error: File {data_json} not found.")
    except json.JSONDecodeError:
        print(f"Error: Failed to parse JSON from {data_json}.")


def check_port():
    try:
        # Create socket and attempt connection with timeout
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT)
        result = sock.connect_ex((PROMETHEUS_ADDR, PORT))
        sock.close()

        # If result is 0, port is open
        if result == 0:
            print(f"Connection to {PROMETHEUS_ADDR}:{PORT} succeeded")
            return 0
        else:
            print(f"Connection to {PROMETHEUS_ADDR}:{PORT} failed")
            return 1
    except Exception as e:
        print(f"Error checking port: {e}")
        return 1


# Store the result in response variable (similar to $? in shell)
response = check_port()

#--------------------------------------------------------------------

# Base scan time of the Prometheus in seconds
BASE_SCAN_TIME=30

# Scaled pod/container names (generic, without random suffix)
SCALED_POD_GENERIC_NAME="open5gs-upf"   # Pod name
SCALED_CONTAINER_NAME="open5gs-upf"     # Name of the container in the pod to scale

# Current namespace
def get_current_namespace():
    try:
        namespace = subprocess.check_output(
            f"kubectl config view --minify --output 'jsonpath={{..namespace}}'; echo",
            shell=True, text=True
        ).strip()
        if not namespace:
            namespace = "open5g"
            print(f"choosing open5g namespace")
        return namespace
    except subprocess.CalledProcessError as e:
        print(f"Error getting namespace: {e}")
        return "open5g"

# Get the current namespace
NAMESPACE = get_current_namespace()

#---------------------------------------------------------

#The value of amf_sessions read from Prometheus
amf_sessions=0

#scaling thresholds for the number of AMF sessions and respective CPU limits quotas

AMFS0=0
CPU0="100m" # if AMFS0 <= amf_sessions < AMFS1
AMFS1=4
CPU1="150m" # if AMFS1 <= amf_sessions < AMFS2
AMFS2=8
CPU2="200m" # if AMFS2 <= amf_sessions < AMFS3
AMFS3=12
CPU3="250m" # if AMFS3 <= amf_sessions

CPU0LOAD = 5
CPU1LOAD = 10
CPU2LOAD = 15
CPU3LOAD = 20


def main_function():
    MAX_ITER = -1
    NAMESPACE = get_current_namespace()
    if len(sys.argv) > 1:
        if len(sys.argv) >3:
            print("Too many parameters.")
            sys.exit(1)
        elif len(sys.argv) == 2:
            if sys.argv[1] == "help":
                print("Enter the preferred number of loop iterations, or the namespace of your target deployment, or both (in this order).\n"
                      "If the numer of iterations is not specified an infinite loop will be run.\n"
                      "If the namspace is not specified, the loop will run in current namespace. \n"
                      "Note: in the latter case, current namespace is taken from current context in the kubeconfig file and should be specified there explicitly.")
                sys.exit(0)

            wzor_cyfr = re.compile(r'^[0-9]+$')

            if wzor_cyfr.match(sys.argv[1]):
                MAX_ITER = int(sys.argv[1])
            else:
                NAMESPACE = sys.argv[1]
                try:
                    ns = subprocess.check_output(
                        f"kubectl get namespaces | grep {NAMESPACE} | awk '{{print $1}}'",
                        shell=True, text=True
                    ).strip()
                    if ns != NAMESPACE:
                        print(f"Error: {NAMESPACE} is not a valid number of iterations nor a valid namespace. Check help.", file=sys.stderr)
                        sys.exit(1)
                except subprocess.CalledProcessError as e:
                    print(f"Error checking namespace: {e}", file=sys.stderr)
                    sys.exit(1)

            if MAX_ITER > 0:
                print(f"Running {MAX_ITER} iterations in current namespace.")
            else:
                print(f"Running infinite loop in namespace {NAMESPACE}.")
        else:
            wzor_cyfr = re.compile(r'^[0-9]+$')

            if not wzor_cyfr.match(sys.argv[1]):
                print(f"Error: $1 is not integer. Check help.", file=sys.stderr)
                sys.exit(1)

            MAX_ITER = int(sys.argv[1])
            NAMESPACE = sys.argv[2]

            ns = subprocess.check_output(
                f"kubectl get namespaces | grep {NAMESPACE} | awk '{{print $1}}'",
                shell=True, text=True
            ).strip()

            if ns != NAMESPACE:
                print(f"Error: Invalid namespace {NAMESPACE}. Check help.", file=sys.stderr)
                sys.exit(1)

            print(f"Running {MAX_ITER} iterations in namespace {NAMESPACE}.")
    else:
        print(f"Running infinite loop in namespace {NAMESPACE}.")

    iter = 0
    loop = True

    while loop:
        iter= iter + 1
        query = f'query=amf_session{{service="open5gs-amf-metrics",namespace="{NAMESPACE}"}}'
        print(f"\n query: {query}")

        try:
            amf_sessions = subprocess.check_output(
                f"curl -s {PROMETHEUS_ADDR}:9090/api/v1/query -G -d '{query}' | jq '.data.result[0].value[1]' | tr -d '\"'",
                shell=True, text=True
            ).strip()

            try:
                amf_sessions = float(amf_sessions)
            except ValueError:
                print(f"Error: Could not convert '{amf_sessions}' to float", file=sys.stderr)
                amf_sessions = 0
        except subprocess.SubprocessError as e:
            print(f"Error executing curl command: {e}", file=sys.stderr)
            amf_sessions = 0

        queryCPU=('http://192.168.1.210:9090/api/v1/query?query=100 - (avg by (cpu) (irate(node_cpu_seconds_total{instance="spiw2",mode="idle"}[5m])) * 100)')
        print(f"\n query: {queryCPU}")

        try:
            requestQueryCPU = requests.get(queryCPU)
            responseQueryCPU = requestQueryCPU.json()
            results = responseQueryCPU.get('data', {}).get('result', [])
            total = 0.0
            count = 0
            for cpu_data in results:
                try:
                    # The load value is the second element in the 'value' list
                    load = float(cpu_data['value'][1])
                    total += load
                    count += 1
                except (KeyError, IndexError, ValueError):
                    # Skip malformed entries
                    continue
            cpu_load = total / count

            try:
                cpu_load = float(cpu_load)
            except ValueError:
                print(f"Error: Could not convert '{cpu_load}' to float", file=sys.stderr)
                cpu_load = 0
        except subprocess.SubprocessError as e:
            print(f"Error executing curl command: {e}", file=sys.stderr)
            cpu_load = 0


        # Set default CPU value
        cpu_weight1 = 1

        # Check conditions in ascending order and override if needed
        if amf_sessions >= AMFS1:
            cpu_weight1 = 2

        if amf_sessions >= AMFS2:
            cpu_weight1 = 3

        if amf_sessions >= AMFS3:
            cpu_weight1 = 4

        cpu_weight2 = 1
        if cpu_load >= CPU1LOAD:
            cpu_weight2 = 2
        if cpu_load >= CPU2LOAD:
            cpu_weight2 = 3
        if cpu_load >= CPU3LOAD:
            cpu_weight2 = 4

        cpu = CPU0
        weight = 0.3 * cpu_weight1 + 0.7 * cpu_weight2
        if weight >= 1.5:
            cpu = CPU1
        if weight >= 2.5:
            cpu = CPU2
        if weight >= 3.5:
            cpu = CPU3


        # scale the target

        podname = subprocess.check_output(f"kubectl get pods -n {NAMESPACE} | grep {SCALED_POD_GENERIC_NAME} | awk '{{print $1}}'",
            shell=True, text=True
        ).strip()

        print(f"Iteration {iter}, amf_sessions {amf_sessions}, pod {podname}, scaling resource to {cpu}, current cpu load {cpu_load}")

        subprocess.check_output(
            f"kubectl patch -n {NAMESPACE} pod {podname} --subresource resize --patch "
            f"'{{\"spec\":{{\"containers\":[{{\"name\":\"{SCALED_CONTAINER_NAME}\", \"resources\":{{\"limits\":{{\"cpu\":\"{cpu}\"}}}}}}]}}}}'",
            shell=True, text=True
        )

        if iter != MAX_ITER:
            sleeptime = BASE_SCAN_TIME
            print(f"Going to sleep for {sleeptime} sec.")
            start_server(host='0.0.0.0', port=65432)
            #time.sleep(sleeptime)
        else:
            loop = False

    print("Koniec")

main_function()