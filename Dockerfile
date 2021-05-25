FROM python:3.9.5-slim

ENV PIP_NO_CACHE_DIR=false

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .

CMD ["python3", "./oaf/oaf.py"]