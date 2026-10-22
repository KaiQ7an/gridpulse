# Local viewing through MAMP PRO

GridPulse is a Streamlit application. MAMP's Apache server can provide a local site name and
HTTPS entry while forwarding requests to the Python process; the PHP/WSGI site handlers do not run Streamlit.

Start the backend from the checkout (with dependencies already installed):

```sh
.venv/bin/python -m streamlit run gridpulse/pitwall/app.py --server.address 127.0.0.1 --server.port 8501
```

Keep that terminal running. In MAMP PRO, create a separate `gridpulse.localhost` site with an empty
site folder outside the repository. Enable Apache's `proxy_module` and `proxy_http_module` under
Settings → Server → Apache, then use these site-specific **VirtualHost** additional parameters:

```apache
ProxyRequests Off
ProxyPreserveHost On
ProxyPass / http://127.0.0.1:8501/ upgrade=websocket
ProxyPassReverse / http://127.0.0.1:8501/
```

Save and restart Apache. These directives support Apache 2.4.47+ WebSocket upgrades, which are
needed for Streamlit's controls and reruns. Do not serve the repository as the document root or enable
forward-proxy requests. Other MAMP sites retain their own document roots and parameters.

On the configured development machine, MAMP uses HTTP port **8888** and HTTPS port **8890**,
with its site certificate and HTTP-to-HTTPS redirect enabled:

- Entry: `http://gridpulse.localhost:8888/`
- Resolved site: `https://gridpulse.localhost:8890/`
- Guided example: `https://gridpulse.localhost:8890/learn`

MAMP and the Python process must both be running. If the backend has stopped, Apache will return
a proxy error; start the command above again. The local site does not publish anything to Streamlit Cloud.

Verified with MAMP PRO's Apache 2.4.66 on 22 October 2026: home → guide → lap-19/lap-21 choice
updated the estimate without leaving the MAMP hostname. The DTM page and native page links also loaded there.

References: [MAMP site parameters](https://documentation.mamp.info/en/MAMP-PRO-Mac/Sites/Site/Web-Server/Apache/),
[Apache HTTP proxy WebSocket upgrades](https://httpd.apache.org/docs/2.4/mod/mod_proxy_http.html#websocket).
