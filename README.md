# 微信公众号对接chatGPT

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
# chatGPT apikey
chatGPT_apikey = "sk-Ol0g4yBAohi51TdOmpfXHBOv1dLLcXUArFLxK"
# chatGPT接口使用的代理
PROXY = "socks5h://192.168.1.104:10801"
# 公众号设置
pub_app_id = 'wx37b939340a4'
pub_app_secret = '0ec16ab7f35d0cff34524c91'

# 公众号加密配置
pub_token = "yasdasd9"  # 请填写你在微信公众平台设置的 Token
EncodingAESKey = 'b1rngzANnE69YPpc5'

# 小程序配置
we_app_id = 'wx65db5e0e17'
we_secret = '723f69bedfe7f873c'
app_token = ''  

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