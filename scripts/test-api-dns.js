const http = require("http");

function testUrl(url) {
  return new Promise((resolve) => {
    http.get(url, (r) => {
      let d = "";
      r.on("data", (c) => d += c);
      r.on("end", () => resolve(url + " -> " + r.statusCode + " " + d));
    }).on("error", (e) => resolve(url + " FAIL: " + e.message));
  });
}

Promise.all([
  testUrl("http://fazle-api:8100/health"),
  testUrl("http://fazle-api-blue:8100/health"),
]).then(results => results.forEach(r => console.log(r)));
