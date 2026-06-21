# proxy_server.py (Lv6-B skeleton)
# NOTE: This is a condensed full file due to chat limits.
import os, re
from collections import defaultdict
from urllib.parse import urljoin
import requests
from flask import Flask, request, Response

app = Flask(__name__)
session = requests.Session()
request_count = defaultdict(int)

HOOK_SCRIPT = '''
<script>
(function(){
 function proxy(u){
   if(!u||typeof u!=="string") return u;
   if(u.startsWith("/proxy?url=")) return u;
   if(u.startsWith("data:")||u.startsWith("blob:")||u.startsWith("javascript:")) return u;
   try{
      let abs=new URL(u, window.location.href).href;
      return "/proxy?url="+encodeURIComponent(abs);
   }catch(e){return u;}
 }
 const oldFetch=window.fetch;
 window.fetch=function(input, init){
   if(typeof input==="string") input=proxy(input);
   return oldFetch.call(this,input,init);
 };
 const oldOpen=XMLHttpRequest.prototype.open;
 XMLHttpRequest.prototype.open=function(m,u){
   return oldOpen.call(this,m,proxy(u),...Array.prototype.slice.call(arguments,2));
 };
 const oldWO=window.open;
 window.open=function(u){
   if(u) location.href=proxy(u);
   return null;
 };
 Object.defineProperty(window,"top",{get(){return window;}});
})();
</script>
'''

def rewrite_html(html, base_url):
    def repl(m):
        attr, q, path = m.group(1), m.group(2), m.group(3)
        if path.startswith(("http://","https://","data:","blob:","#","javascript:","/proxy?url=")):
            return m.group(0)
        abs_url = urljoin(base_url, path)
        return f'{attr}={q}/proxy?url={abs_url}{q}'
    html = re.sub(r'(src|href|action)=([\'\"])(.*?)\2', repl, html)
    if "</head>" in html:
        html = html.replace("</head>", HOOK_SCRIPT + "</head>")
    else:
        html = HOOK_SCRIPT + html
    return html

@app.route("/")
def home():
    return "<h1>Proxy Server Running!</h1><p>/proxy?url=https://example.com</p>"

@app.route("/proxy", methods=["GET","POST"])
def proxy():
    url = request.args.get("url")
    if not url:
        return "URL required", 400
    request_count[url]+=1
    headers={"User-Agent": request.headers.get("User-Agent","")}
    try:
        if request.method=="POST":
            r=session.post(url, data=request.form, headers=headers, timeout=20)
        else:
            r=session.get(url, headers=headers, timeout=20)
        ct=r.headers.get("Content-Type","")
        if "text/html" in ct:
            html = rewrite_html(r.text, url)
            resp = Response(html, content_type=ct)
        else:
            resp = Response(r.content, content_type=ct)
        return resp
    except Exception as e:
        return f"Error: {e}", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
