# Simple File Server / 简易文件服务器

[English](#english) | [中文](#中文)

---

<a name="english"></a>
## English

A lightweight, secure, and modern web-based file server built with Python and Flask. It features an Nginx-style interface, anonymous browsing, and password-protected file management operations.

### Features

*   **Clean Interface**: Nginx-inspired, responsive design with adaptive columns.
*   **Anonymous Access**: Browse and download files without login.
*   **Secure Management**: Login to upload, create folders, rename, and delete files.
*   **Security**: 
    *   Path traversal protection.
    *   Password hashing (SHA-256 with salt).
    *   Session management.
*   **Configuration**: Simple `config.json` for port, password, and root directory settings.

### Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/yourusername/simple-file-server.git
    cd simple-file-server
    ```

2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

### Usage

1.  Start the server:
    ```bash
    python app.py
    ```

2.  Open your browser and navigate to `http://localhost:5000`.

3.  **Default Credentials**:
    *   The default password is `admin`.
    *   On first run, the server will hash this password in `config.json`.

### Configuration

The `config.json` file is automatically created on first run. You can customize:

*   `port`: The port to run the server on (default: `5000`).
*   `password`: The admin password. (If you change this to plain text, restart the server to re-hash it).
*   `root_dir`: The directory to serve files from (default: `./files_root`).

### License

MIT License

---

<a name="中文"></a>
## 中文

基于 Python 和 Flask 构建的轻量级、安全且现代的 Web 文件服务器。它拥有 Nginx 风格的简洁界面，支持匿名浏览，以及受密码保护的文件管理操作。

### 功能特性

*   **简洁界面**：受 Nginx 启发的设计，响应式布局，列宽自适应。
*   **匿名访问**：无需登录即可浏览和下载文件。
*   **安全管理**：登录后支持上传文件、创建文件夹、重命名和删除文件。
*   **安全性**：
    *   路径遍历保护。
    *   密码哈希存储（SHA-256 加盐）。
    *   会话管理。
*   **简单配置**：通过 `config.json` 文件配置端口、密码和根目录。

### 安装步骤

1.  克隆仓库：
    ```bash
    git clone https://github.com/yourusername/simple-file-server.git
    cd simple-file-server
    ```

2.  安装依赖：
    ```bash
    pip install -r requirements.txt
    ```

### 使用方法

1.  启动服务器：
    ```bash
    python app.py
    ```

2.  打开浏览器并访问 `http://localhost:5000`。

3.  **默认凭据**：
    *   默认密码为 `admin`。
    *   首次运行时，服务器会将 `config.json` 中的明文密码自动转换为哈希值。

### 配置说明

`config.json` 文件会在首次运行时自动创建。您可以自定义以下项：

*   `port`：服务器运行端口（默认：`5000`）。
*   `password`：管理员密码。（如果您将其修改为明文，重启服务器后会自动重新哈希）。
*   `root_dir`：文件服务根目录（默认：`./files_root`）。

### 许可证

MIT License
