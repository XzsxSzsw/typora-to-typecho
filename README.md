# Typora 到 Typecho 自动发布工具

这是一个强大的 Python 工具，用于将 Typora 编辑的 Markdown 文件自动发布到 Typecho 博客平台，支持批量处理、图片上传和格式转换等功能。

## 功能特点

- 🚀 **批量发布**：一次性选择并发布多个 Markdown 文章
- 🖼️ **智能图片处理**：自动处理文章中的图片，支持本地图片上传到 FTP 服务器
- 🔗 **自动链接更新**：文章发布后自动更新图片链接
- 🎯 **分类管理**：自动获取博客分类，支持多分类选择
- 🔄 **错误回滚**：发布失败时自动回滚已发布的文章和上传的图片
- 📝 **格式优化**：自动清洗 Markdown 格式，确保在 Typecho 中正确显示
- 🔐 **安全登录**：模拟浏览器登录，保持会话状态
- ⚙️ **YAML 配置**：使用 YAML 配置文件，支持多层插值，便于管理各种设置

## 系统要求

- Python 3.6 或更高版本
- 必须的 Python 库：
  - `requests`
  - `PyYAML`
  - `brotli`
  - `urllib3`

安装依赖：
```bash
pip install requests PyYAML brotli urllib3
```

## 配置说明

在使用工具前，需要编辑 `config.yaml` 文件，配置以下关键信息：

### 全局配置
```yaml
global:
  domain: www.yourdomain.com      # 站点域名
  timezone: 28800                # 时区设置（东八区为 28800）
```

### 站点配置
```yaml
site:
  home_url: "https://${global.domain}"
  login_page: "${site.home_url}/admin/login.php"
  admin_url: "${site.home_url}/admin/"
  write_post_url: "${site.home_url}/admin/write-post.php"
  manage_posts_url: "${site.home_url}/admin/manage-posts.php"
  manage_categories_url: "${site.home_url}/admin/manage-categories.php"
  delete_post_url: "${site.home_url}/index.php/action/contents-post-edit"
```

### 登录配置
```yaml
login:
  username: your_username         # Typecho 后台登录用户名
  password: "your_password"       # Typecho 后台登录密码
  cookie_prefix: "your_cookie_prefix"  # Cookie 前缀
```

### 图片配置
```yaml
image:
  processed_img_root: D:/path/to/processed/images/  # 处理后图片存储路径
  server_img_url: "${site.home_url}/img/"         # 图片服务器访问 URL
  space_replace_char: "_"                           # 空格替换字符
```

### FTP 配置
```yaml
ftp:
  host: ftp.yourdomain.com       # FTP 服务器地址
  port: 21                       # FTP 端口
  user: your_ftp_user           # FTP 用户名
  password: "your_ftp_password"  # FTP 密码
  base_path: "/"                # FTP 根目录
  timeout: 30                   # 连接超时时间（秒）
  passive: true                  # 是否使用被动模式
```

### 请求配置
```yaml
request:
  user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
  min_delay: 1.0                # 最小请求延迟（秒）
  max_delay: 2.0                # 最大请求延迟（秒）
  batch_delay: 2.0              # 批量处理文件间的延迟（秒）
```

### 分类配置
```yaml
category:
  default_category_id: 1        # 默认分类 ID
```

## 使用方法

1. 将 Markdown 文件放在一个文件夹中
2. 运行命令：
   ```bash
   python typora-to-typecho.py "D:/path/to/your/markdown/folder"
   ```
3. 按照提示选择要发布的文件和分类
4. 等待发布完成

## 工作流程

1. **登录验证**：自动登录 Typecho 后台并验证会话
2. **分类抓取**：获取博客所有分类供用户选择
3. **格式处理**：清洗 Markdown 格式并处理图片路径
4. **文章发布**：将文章发布到 Typecho 并验证发布结果
5. **图片上传**：上传文章中的图片到 FTP 服务器并更新链接
6. **资源释放**：关闭所有连接并清理临时文件

## 注意事项

1. 确保 `config.yaml` 文件中的配置信息正确无误
2. 图片处理会占用本地磁盘空间，工具会自动清理处理后的临时文件
3. 如果发布失败，工具会自动尝试回滚已发布的文章和上传的图片
4. 首次使用时建议先测试单个文件发布，确认无误后再进行批量处理

## 故障排除

- **登录失败**：检查用户名、密码和 Cookie 前缀是否正确
- **图片上传失败**：检查 FTP 配置和网络连接
- **文章发布失败**：检查文章格式和分类 ID 是否正确
- **权限问题**：确保 FTP 服务器有足够的权限写入文件

## 许可证

本项目采用 MIT 许可证，详情请参阅 [LICENSE](LICENSE) 文件。

## 贡献

欢迎提交 Issue 和 Pull Request 来改进这个项目！

## 更新日志

### v1.0.0
- 初始版本发布
- 支持批量发布 Markdown 文章
- 支持图片自动上传和处理
- 支持分类选择和管理
- 实现错误回滚机制
