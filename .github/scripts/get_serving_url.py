import os, sys

if __name__ == "__main__":
    endpoint = sys.argv[1]

    host = os.environ.get("DATABRICKS_HOST", "").strip().rstrip("/")
    if not host:
        raise SystemExit("DATABRICKS_HOST env var is empty")

    if not host.startswith("http"):
        host = "https://" + host

    url = f"{host}/serving-endpoints/{endpoint}/invocations"
    print(url)
