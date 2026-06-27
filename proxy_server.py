import re
from urllib.parse import urljoin
from flask import Flask, request, Response
import requests
from collections import defaultdict
import re
from urllib.parse import urljoin

app = Flask(__name__)
request_count = defaultdict(int)
session = requests.Session()

HOOK_SCRIPT = """
<script>
(function () {
    console.log("Lv5 Safe Hook Loaded");

function proxyRelative(url) {
    if (typeof url !== "string") return url;

    if (
        url.startsWith("http://") ||
        url.startsWith("https://") ||
        url.startsWith("data:") ||
        url.startsWith("blob:") ||
        url.startsWith("javascript:")
    ) {
        return url;
    }

    try {
        const full = new URL(url, window.location.href).href;
        return "/proxy?url=" + encodeURIComponent(full);
    } catch (e) {
        console.log("proxyRelative parse fail:", url);
        return url;
    }
}

    const oldFetch = window.fetch;

    if (oldFetch) {
        window.fetch = function(resource, options) {
            let url = resource;

            if (typeof resource !== "string") {
                if (resource && resource.url) {
                    url = resource.url;
                }
            }

            const proxied = proxyRelative(url);

            console.log("[FETCH]", url, "=>", proxied);

            return oldFetch(proxied, options);
        };
    }

    const oldOpen = XMLHttpRequest.prototype.open;

    XMLHttpRequest.prototype.open = function(method, url, ...rest) {
        const proxied = proxyRelative(url);

        console.log("[XHR]", method, url, "=>", proxied);

        return oldOpen.call(this, method, proxied, ...rest);
    };
})();
</script>
"""


@app.route("/")
def home():
    return """
    <h1>Proxy Server Running!</h1>
    <p>/proxy?url=https://example.com</p>
    """


@app.route("/proxy", methods=["GET", "POST"])
def proxy():
    url = request.args.get("url")

    if not url:
        return "URLを指定してください", 400

    request_count[url] += 1
    count = request_count[url]

    print()
    print("=" * 60)
    print(f"[{request.method}] [{count}回目] {url}")

    if count >= 3:
        print("⚠ LOOP WARNING")

    try:
        headers = {
            "User-Agent": request.headers.get("User-Agent", "")
        }

        cookie = request.headers.get("Cookie")
        if cookie:
            headers["Cookie"] = cookie
            print("Cookie received")

        if request.method == "POST":
            response = session.post(
                url,
                data=request.form,
                headers=headers,
                timeout=20
            )
        else:
            response = session.get(
                url,
                headers=headers,
                timeout=20
            )

        content_type = response.headers.get("Content-Type", "")
        print("Status:", response.status_code)
        print("Content-Type:", content_type)

        if "text/html" in content_type:
            html = response.text

            # Minimal Rewrite
   def rewrite_attr(match):
    attr = match.group(1)
    quote = match.group(2)
    path = match.group(3)

    if (
        path.startswith("http://")
        or path.startswith("https://")
        or path.startswith("data:")
        or path.startswith("blob:")
        or path.startswith("#")
        or path.startswith("javascript:")
    ):
        return match.group(0)

    absolute = urljoin(url, path)
    proxied = "/proxy?url=" + absolute

    return f'{attr}={quote}{proxied}{quote}'


html = re.sub(
    r'(src|href)=([\"\'])(.*?)\2',
    rewrite_attr,
    html
)

            if "</head>" in html:
                html = html.replace("</head>", HOOK_SCRIPT + "</head>", 1)
                print("Safe hook injected into <head>")
            elif "<body>" in html:
                html = html.replace("<body>", "<body>" + HOOK_SCRIPT, 1)
                print("Safe hook injected into <body>")
            else:
                html = HOOK_SCRIPT + html
                print("Safe hook prepended")

            proxy_response = Response(html, content_type=content_type)

        else:
            proxy_response = Response(
                response.content,
                content_type=content_type
            )

        set_cookie = response.headers.get("Set-Cookie")
        if set_cookie:
            proxy_response.headers["Set-Cookie"] = set_cookie
            print("Set-Cookie forwarded")

        return proxy_response

    except Exception as e:
        print("ERROR:", e)
        return f"エラー: {str(e)}", 500


if __name__ == "__main__":
    print("Starting proxy server...")
    app.run(host="0.0.0.0", port=8080)