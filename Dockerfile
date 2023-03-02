FROM python:3.11

WORKDIR /code/

RUN pip config set global.index-url https://pypi.mirrors.ustc.edu.cn/simple/

ADD requirements.txt /code/
RUN pip install -r requirements.txt

ADD . /code

CMD ["python3", "-u", "main.py"]