# wx-fetch

微信公众号文章抓取工具，支持 Markdown / 纯文本 / JSON / Word 输出。

## 特性

- ✅ 移动 UA 优先，命中率高
- ✅ 支持静态页和 JS 渲染页（自动检测）
- ✅ 输出 Markdown / txt / JSON / docx
- ✅ 单文件，零配置

## 安装

```bash
# 直接下载
curl -O https://raw.githubusercontent.com/polaris-smart/wx-fetch/main/wx-fetch.py
chmod +x wx-fetch.py

# 或 alias
alias wx-fetch='python3 /path/to/wx-fetch.py'
```

## 依赖

```bash
pip install requests beautifulsoup4
```

## 用法

```bash
# Markdown 到 stdout
python3 wx-fetch.py "https://mp.weixin.qq.com/s/xxx"

# 纯文本存文件
python3 wx-fetch.py "https://mp.weixin.qq.com/s/xxx" --txt -o article.txt

# JSON（标题/公众号/时间/正文）
python3 wx-fetch.py "https://mp.weixin.qq.com/s/xxx" --json

# Word（需 python-docx）
python3 wx-fetch.py "https://mp.weixin.qq.com/s/xxx" --docx -o article.docx

# 批量
python3 wx-fetch.py urls.txt --batch -o ./output/
```

## 限制

- 微信不提供公开的历史文章列表接口，单篇正文可抓
- 部分 JS 渲染页需要 lightpanda 或真浏览器兜底

## License

MIT
