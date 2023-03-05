FROM python:3.11-slim-bullseye

# Now install packages as normal — tiktoken will already be installed and skipped if present in requirements.txt
RUN pip config set global.index-url https://pypi.mirrors.ustc.edu.cn/simple/

WORKDIR /code/
ADD requirements.txt /code/
RUN pip install --upgrade pip && pip install -r requirements.txt

ADD . /code

CMD ["python3", "-u", "main.py"]