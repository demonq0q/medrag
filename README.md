# 小荷 MedRAG

小荷（MedRAG）是一个面向基层医生、药师和患者的医学循证问答助手。项目以现有 `med-rag-data/` 为只读知识源，经过标准化、专业切分和 SQLite FTS5 索引后，通过 FastAPI + LangGraph 提供可追溯、带风险审核的问答服务，前端使用 React + Vite 实现 ChatGPT 风格的医疗工作台。

## 当前状态

- 数据源：Markdown、PDF、结构化 JSON，共 80 个原始文件
- 检索：SQLite FTS5 关键词召回、FAQ、图谱关系、药物相互作用和检验参考值融合
- 生成：无模型密钥时使用可审计的模板回退；后续可接入兼容 OpenAI API 的 LLM Provider
- 安全：急症识别、药物相互作用、剂量无证据阻断、引用存在性和医疗免责声明
- 部署：FastAPI API、React 静态前端、Docker Compose、Caddy 反代配置

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

## 数据边界

`med-rag-data/` 默认只读，生成的 SQLite、索引和报告写入 `artifacts/`。系统定位为医学知识辅助工具，不替代医生诊断、处方或急诊服务。

