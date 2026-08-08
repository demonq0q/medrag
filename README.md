# 小荷 MedRAG

小荷（MedRAG）是一个面向基层医生、药师和患者的医学循证问答助手。项目以现有 `med-rag-data/` 为只读知识源，经过标准化、专业切分和 SQLite FTS5 索引后，通过 FastAPI + LangGraph 提供可追溯、带风险审核的问答服务，前端使用 React + Vite 实现 ChatGPT 风格的医疗工作台。

## 当前状态

- 数据源：Markdown、PDF、结构化 JSON；目录原始文件 80 个，其中 78 个有效源文件参与构建
- 检索：SQLite FTS5 关键词召回、FAQ、图谱关系、药物相互作用和检验参考值融合
- 生成：无模型密钥时使用可审计的模板回退；后续可接入兼容 OpenAI API 的 LLM Provider
- 安全：急症识别、药物相互作用、剂量无证据阻断、引用存在性和医疗免责声明
- 部署：FastAPI API、React 静态前端、Docker Compose、Caddy 反代配置
- 公网 Demo：<https://medrag.986889.xyz>

交付文档：

- [开发计划](docs/开发计划.md)
- [设计文档](docs/设计文档.md)
- [使用手册](docs/使用手册.md)
- [评估报告](docs/评估报告.md)
- [安全评估报告](docs/安全评估报告.md)

## 本地开发

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
python -m medrag.cli validate
python -m medrag.cli build
uvicorn medrag.app:app --host 0.0.0.0 --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

## Docker 部署

```bash
docker compose up -d --build
docker compose ps
docker compose port web 80
```

Compose 会为 Web 和 API 分配随机宿主机端口；通过 `docker compose port` 读取实际端口。宿主机已运行 Caddy 时，可执行 `scripts/configure_caddy_host.sh` 自动读取端口并将 `medrag.986889.xyz` 反代到前端容器。

## 质量检查

```bash
pytest tests -q
ruff check src/medrag scripts tests
python scripts/evaluate.py
npm --prefix frontend run build
```

## 数据边界

`med-rag-data/` 默认只读，生成的 SQLite、索引和报告写入 `artifacts/`。系统定位为医学知识辅助工具，不替代医生诊断、处方或急诊服务。
