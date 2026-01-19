import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 20,
  duration: "3m",
};

const host = __ENV.DATABRICKS_HOST;
const endpoint = __ENV.ENDPOINT_NAME;
const token = __ENV.DATABRICKS_TOKEN;

export default function () {
  const url = `${host}/serving-endpoints/${endpoint}/invocations`;

  const payload = JSON.stringify({
    dataframe_split: {
      columns: ["pressure", "flow", "radius"],
      data: [[120.0, 4.2, 0.35]]
    }
  });

  const params = {
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  };

  const res = http.post(url, payload, params);
  check(res, { "status 200": (r) => r.status === 200 });
  sleep(0.1);
}
