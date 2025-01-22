FROM python:3.12-alpine

WORKDIR /work
COPY docker/editem/requirements.txt .
RUN python3 -m pip install -r requirements.txt

COPY untanngle/__init__.py untanngle/__init__.py
COPY untanngle/textfabric.py untanngle/textfabric.py
COPY untanngle/camel_casing.py untanngle/camel_casing.py
COPY untanngle/utils.py untanngle/utils.py
COPY scripts/editem-watm-untangler.py .
COPY docker/editem/untangle-watm.sh .

CMD ["./untangle-watm.sh"]