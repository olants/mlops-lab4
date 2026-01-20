import json, subprocess, sys

def sh(cmd):
    return subprocess.check_output(cmd, text=True)

if __name__ == "__main__":
    endpoint = sys.argv[1]
    # new CLI has "serving-endpoints get"
    out = sh(["databricks", "serving-endpoints", "get", endpoint, "--output", "json"])
    data = json.loads(out)

    # endpoint_url may not always exist; build from host + invocations
    host = subprocess.check_output(["bash", "-lc", "echo $DATABRICKS_HOST"], text=True).strip().rstrip("/")
    url = f"{host}/serving-endpoints/{endpoint}/invocations"
    print(url)
