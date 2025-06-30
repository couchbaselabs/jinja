# jinja
QE dashboard tool for scraping jenkins, ninja style

Recommended python version: 3.11.2

```bash
screen -S collector
python3.11 -m venv env
source env/bin/activate
pip install -r requirements.txt
python jinja.py

Ctrl + A, then D
```

To scrape a single jenkins build url, use the below.
python jinjasingle.py

* Pre-req: script expects 4 buckets named 'cblite', 'sync_gateway', 'server' and 'sdk' prior to running
