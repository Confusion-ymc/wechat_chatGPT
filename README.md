# 微信 [公众号/小程序] 对接chatGPT

## 安装运行

### 安装依赖

1.配置中科大加速源 (推荐)

```shell
pip3 config set global.index-url https://pypi.mirrors.ustc.edu.cn/simple/
```

2.安装库

```shell
pip3 install -r requirements.txt
```

### <span id="setings">设置</span>

#### 1.创建配置文件

```
1.复制一份 config.sample.py
2.重名为 config.py
```

#### 2.修改 config.py 的内容

例如：

```
# 公众号加密配置
EncodingAESKey = 'b1rng...'
pub_app_id = 'wx37b...'
pub_app_secret = '...'
app_token = ''

# 小程序配置
MINI_APP_ID = "wx65d3..."
MINI_SECRET = "723f6"
# chatGPT apikey
CHATGPT_KEY = "sk-YrGqyWXf8..."
PROXY = None  

```

### 运行

```
python3 main.py
```

## Docker 运行

1.[设置](#setings)步骤完成后

2.运行
```
docker-compopse up --build -d
```

## Fly.io 部署
### 配置文件
`fly.toml` 具体参考官方文档

```commandline
flyctl launch
```