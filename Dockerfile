FROM python:3.7.6

WORKDIR /code/

RUN pip config set global.index-url https://pypi.mirrors.ustc.edu.cn/simple/

ADD requirements.txt /code/
RUN pip3 install -r requirements.txt

ADD . /code

CMD ["python3", "-u", "main.py"]