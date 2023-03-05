FROM python:3.11-slim-bullseye as builder

RUN pip config set global.index-url https://pypi.mirrors.ustc.edu.cn/simple/
# Tiktoken requires Rust toolchain, so build it in a separate stage
RUN sed -i s@/deb.debian.org/@/mirrors.aliyun.com/@g /etc/apt/sources.list
RUN apt-get update && apt-get install -y gcc curl
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y && apt-get install --reinstall libc6-dev -y
ENV PATH="/root/.cargo/bin:${PATH}"
RUN pip install --upgrade pip && pip install tiktoken

FROM python:3.11-slim-bullseye

# Copy pre-built packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
# Now install packages as normal — tiktoken will already be installed and skipped if present in requirements.txt
RUN pip config set global.index-url https://pypi.mirrors.ustc.edu.cn/simple/

WORKDIR /code/
ADD requirements.txt /code/
RUN pip install --upgrade pip && pip install -r requirements.txt

ADD . /code

CMD ["python3", "-u", "main.py"]