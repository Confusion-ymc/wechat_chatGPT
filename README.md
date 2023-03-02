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
TOKEN = "1232sad"  # 请填写你在微信公众平台设置的 Token
EncodingAESKey = 'b1DRHn1B9ZU2K7lUO9DqkWLdi4jAzANnE69YPpc5'
APP_ID = 'wx37b5de69340a4'
chatGPT_KEY = "sk-Ol0g4yeT3BlbkFJpfXHBOv1dLLcXUArFLxK"
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