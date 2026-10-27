# develop 分支的 Docker 部署

`github-dev` 用于功能开发，`develop` 用于部署。根目录的 `Dockerfile` 将当前
server、SDK 和编译后的 WebUI 装入同一个镜像，server 和 worker 使用同一镜像。
基础镜像为官方 Argilla 2.8.0，不直接用旧版官方前端替代当前代码。

## 构建

在有 Node.js 20、npm 和 Docker 的构建机上执行：

```bash
bash deploy/docker/build.sh
```

前端单独使用生产 TypeScript 配置；仍检查应用类型，排除单元测试及浏览器测试。
不要运行开发服务器作为生产服务。静态前端与 API 共用 6900 端口，浏览器请求
同源 `/api`，无需编译服务器 IP。

## 服务器安装

将本分支放入 `/data/argilla`，或者在服务器只放置 `compose.yaml`、`.env.example`
和 `deploy/docker/init-env.py`，通过 `docker save` / `docker load` 转移已构建镜像。
后者启动时使用 `--no-build`。镜像可以在本机构建，服务器无需 npm 环境。

```bash
cd /data/argilla
python3 deploy/docker/init-env.py
# 编辑 .env 中的端口、HF token 和该服务器上的 CSGHub endpoint/token。
docker compose up -d --no-build
docker compose ps
```

初始化脚本只创建不存在的 `.env`，自动生成管理员密码、API key 和数据库密码，
文件权限为 0600。首次启动创建 `root` 管理员及 `admin` 工作区；已有用户不会
被重置。密码及 API key 保存在 `/data/argilla/.env`，不要提交该文件。

默认入口 `http://服务器IP:6900`；PostgreSQL、Elasticsearch、Redis 均不映射
宿主机端口。全部持久数据在 `/data/argilla/data/` 下，包含 app、postgres、
elasticsearch、redis 四个目录，初始化服务自动设置目录权限。

容器配置 `restart: unless-stopped`，Docker 服务启动后自动恢复。server 等待
数据库健康，worker 等待 server 完成迁移并健康后再启动。停机用
`docker compose stop`，不要删除 `data/`。这是独立部署，不自动复制本机数据。

CSGHub 的公开 endpoint 应填服务器页面地址，例如 `http://10.24.45.22`；若同机
部署 CSGHub，内部 endpoint 可用 `http://host.docker.internal`。需要填写该
CSGHub 实例的用户 token，本机实例的 token 不能直接复用到另一台服务器。

## 验证

确认 `docker compose ps` 中 server、postgres、elasticsearch、redis 为 healthy，
worker 为 running。访问 `/api/v1/version` 和 WebUI 登录页，再用管理员登录。
数据集导入还需确认 worker 完成任务；仅首页可访问不代表导入管线正常。

更新前保留旧镜像标签并备份数据库；构建新镜像后执行
`docker compose up -d --no-build`。数据库迁移与回滚需单独评估。
