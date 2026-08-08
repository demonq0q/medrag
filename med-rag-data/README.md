# MedRAG 医学知识库数据集

> 智能医疗问答助手（MedRAG）项目配套知识库，包含临床指南、药品说明书、疾病知识、
> 药物相互作用、医学术语词典、检验参考值、FAQ 问答对、评估测试集等结构化数据。

---

## 数据集总览

| 指标 | 数值 |
|------|------|
| 文件总数 | **82** 个 |
| 总大小 | **25.9 MB** |
| PDF 文档 | 4 个（临床指南） |
| JSON 数据 | 7 个（结构化数据） |
| Markdown 文档 | 64 个（药品说明书 + 疾病知识） |
| 数据来源 | 默沙东诊疗手册、中华医学会、NMPA、清华大学医院、Mayo Clinic |

---

## 目录结构

```
med-rag-data/
├── README.md                        # 本说明文档
│
├── faq/                                     # FAQ 高频问答对 (3 个文件)
│   │   ├── faq_dataset.json
│   │   ├── faq_dataset.json.bak
│   │   ├── faq_dataset.json.fixed_attempt
├── knowledge_graph/                         # 医学知识图谱（实体+关系+药物相互作用） (2 个文件)
│   │   ├── drug_interactions.json
│   │   ├── medical_entities_relations.json
├── processed/                               # 预处理后的疾病知识条目 (1 个文件)
│   │   ├── disease_entries.json
├── reference/                               # 参考词典（术语同义词 + 检验参考值） (2 个文件)
│   │   ├── lab_reference_values.json
│   │   ├── medical_synonyms.json
├── evaluation/                              # 评估测试集 (1 个文件)
│   │   ├── test_set.json
├── raw/
│   ├── guidelines/                              # 临床指南（PDF + 要点摘要） (6 个文件)
│   │   ├── 中国高血压防治指南2024核心要点.md
│   │   ├── 中国2型糖尿病运动治疗指南2024版.pdf
│   │   ├── 中国2型糖尿病防治指南_CMA.pdf
│   │   ├── 中国糖尿病防治指南2024核心要点.md
│   │   ├── 中国糖尿病防治指南2024版_华山医院.pdf
│   │   └── ... 及其他 1 个文件
├── raw/
│   ├── drug_labels/                             # 药品说明书 (8 个文件)
│   │   ├── 华法林钠片说明书.md
│   │   ├── 德谷胰岛素利拉鲁肽注射液_清华医院.md
│   │   ├── 盐酸二甲双胍片_清华医院.md
│   │   ├── 盐酸二甲双胍片说明书.md
│   │   ├── 盐酸二甲双胍肠溶胶囊说明书_NMPA.md
│   │   └── ... 及其他 3 个文件
├── raw/
│   ├── disease_entries/                         # 疾病知识条目（默沙东诊疗手册） (54 个文件)
│   │   ├── 1型糖尿病_专业版.md
│   │   ├── 1型糖尿病_大众版.md
│   │   ├── 2型糖尿病_专业版.md
│   │   ├── 2型糖尿病_大众版.md
│   │   ├── COPD_专业版.md
│   │   └── ... 及其他 49 个文件
└── ...
```

---

## 一、结构化数据（JSON）

这些是手工构建的高质量结构化数据，用于 RAG 各环节。

### 1.1 FAQ 高频问答对

- **文件**: `faq/faq_dataset.json` (49.8 KB)
- **条目数**: **30 条**
- **分类**: 疾病基础、用药指导、检查解读、药物相互作用、饮食生活、特殊人群、急救常识
- **字段**: id, category, question, question_synonyms(同义句扩展), answer, keywords, related_diseases, related_drugs, source, evidence_level
- **用途**: FAQ 精确匹配检索路径；评估集参考

### 1.2 医学知识图谱数据

- **文件**:
  - `knowledge_graph/drug_interactions.json` (29.7 KB)
  - `knowledge_graph/medical_entities_relations.json` (19.8 KB)
- **药物相互作用**: **55 组**（含禁忌/严重/中等/轻度分级）
- **实体总数**: 40 种药品 + 25 种疾病 + 30 个症状 + 20 个检查项目
- **关系总数**: **103 条**（INDICATED_FOR / HAS_SYMPTOM / RECOMMENDED_EXAM / INTERACTS_WITH 等）
- **用途**: 构建 Neo4j 知识图谱 → GraphRAG 多跳检索

### 1.3 疾病知识条目（预处理版）

- **文件**: `processed/disease_entries.json` (41.0 KB)
- **条目数**: **20 种**疾病
- **覆盖科室**: 内分泌科, 心内科, 呼吸科, 消化科, 心内科/内分泌科, 风湿免疫科/内分泌科, 血液科, 精神科, 骨科/内分泌科, 神经内科, 肾内科
- **字段**: 定义、病因、症状（典型/非典型/并发症）、诊断标准、治疗方案、预防、关键药品、关键检查
- **用途**: 疾病基础问答；向量化存储

### 1.4 医学参考词典

- **医学术语同义词词典**: `reference/medical_synonyms.json` — **102 组**映射
  - 覆盖: 疾病名称 / 药品名称 / 检查项目 / 症状描述 / 缩写术语
  - 含 ICD-10 编码和 ATC 编码
  - **用途**: BM25 检索时术语标准化 + 查询扩展

- **检验项目参考值表**: `reference/lab_reference_values.json` — **45 项**检验指标
  - 覆盖: 血糖代谢 / 肝功能 / 肾功能 / 血脂 / 甲状腺功能 / 血常规 / 炎症指标 / 电解质 / 心肌标志物 等
  - 含正常范围、危急值、临床意义、影响因素
  - **用途**: 检查指标解读问答

### 1.5 评估测试集

- **文件**: `evaluation/test_set.json` (30.3 KB)
- **条目数**: **50 条**
- **分类分布**: 疾病基础(8), 用药指导(12), 检查解读(8), 药物相互作用(8), 饮食生活(5), 特殊人群(5), 急救常识(4)
- **难度分布**: easy(15), medium(20), hard(15)
- **字段**: question, expected_answer_summary, ground_truth_docs, key_entities, expected_drugs, test_type
- **用途**: RAGAS 端到端评估；检索准确率 / 生成质量 / 安全合规测试

---

## 二、原始文档（raw/）

通过爬虫采集或手工整理的原始医学文档，可直接用于文档切分（Chunking）和向量化。

### 2.1 临床指南

共 **6** 个文件（4 个 PDF + 2 个 Markdown 要点摘要）。

| 文件名 | 大小 | 格式 | 来源 |
|--------|------|------|------|
| 中国2型糖尿病防治指南_CMA.pdf | 14 MB | PDF | 中华医学会 |
| 中国糖尿病防治指南2024版_华山医院.pdf | 5.9 MB | PDF | 复旦大学附属华山医院 |
| 中国2型糖尿病运动治疗指南2024版.pdf | 4.3 MB | PDF | 中国全科医学杂志 |
| 中国糖尿病防治指南2024版_解读.pdf | 681 KB | PDF | 重庆医科大学学报 |
| 中国糖尿病防治指南2024核心要点.md | 9 KB | Markdown | 手工整理要点 |
| 中国高血压防治指南2024核心要点.md | 7 KB | Markdown | 手工整理要点 |

### 2.2 药品说明书

共 **8** 个药品说明书。

| 药品名称 | 大小 | 来源 |
|---------|------|------|
| 达格列净片_清华医院.md | 23 KB | 清华大学医院 |
| 德谷胰岛素利拉鲁肽注射液_清华医院.md | 23 KB | 清华大学医院 |
| 盐酸二甲双胍片_清华医院.md | 12 KB | 清华大学医院 |
| 盐酸二甲双胍片说明书.md | 7 KB | 综合整理（格华止等多厂家） |
| 苯磺酸氨氯地平片说明书.md | 5 KB | 综合整理（络活喜等） |
| 阿司匹林肠溶片说明书.md | 6 KB | 综合整理（拜阿司匹灵等） |
| 华法林钠片说明书.md | 7 KB | 综合整理（Coumadin） |
| 盐酸二甲双胍肠溶胶囊说明书_NMPA.md | 3 KB | NMPA 官方 |

每个说明书包含完整字段：【药品名称】【成份】【性状】【适应症】【规格】【用法用量】【不良反应】
【禁忌症】【注意事项】【药物相互作用】【药理毒理】【药代动力学】

### 2.3 疾病知识条目

共 **54** 个疾病/医学知识页面，主要采集自默沙东诊疗手册专业版。

| 科室 | 条目数 | 代表疾病 |
|------|--------|---------|
| 内分泌科 | 24 | 糖尿病(1型/2型)、低血糖、垂体激素(TSH/ACTH/GH/ADH/LH/FSH/催乳素/催产素)、内分泌系统概述... |
| 心内科 | 8 | 高血压、心力衰竭、心脏病患者简介、体格检查、病史、心脏听诊、心血管检查... |
| 呼吸科 | 4 | 支气管哮喘、COPD、成人咳嗽、肺部疾病诊疗方法... |
| 消化科 | 5 | 胃食管反流病、消化科患者评估、肠-脑相互作用障碍、慢性腹痛、胃肠道症状... |
| 神经内科 | 2 | 走近神经疾病患者、神经传递... |
| 精神科 | 3 | 初步精神病评估、精神症状医学评估、急诊行为问题... |
| 骨科 | 7 | 手/肘/肩/膝/髋/足/踝关节评估... |
| 肾内科 | 1 | 肾脏疾病患者评估... |

每个页面均带有 YAML 元数据头（source_url / title / scrape_date / doc_type / department），便于按科室过滤。

---

## 三、数据使用指南

### 3.1 RAG 各环节对应的数据文件

| RAG 环节 | 使用的数据文件 | 处理方式 |
|---------|--------------|---------|
| **文档解析** | `raw/guidelines/*.pdf` | 用 `pdfplumber` 提取 PDF 文本 + 表格 |
| **文档切分** | `raw/**/*.md`, `processed/*.json` | 按段落/标题层级切分，保留元数据 |
| **BM25 索引** | `reference/medical_synonyms.json` | 将同义词加入 jieba 自定义词典 |
| **向量索引** | 所有 `.md` 和 `.json` 中的文本 | Embedding 后存入 Milvus/Chroma |
| **知识图谱** | `knowledge_graph/*.json` | 构建 Neo4j 图（实体 + 关系） |
| **FAQ 匹配** | `faq/faq_dataset.json` | 向量化 question+answer，按语义匹配 |
| **查询改写** | `reference/medical_synonyms.json` | 术语标准化 + 同义词扩展 |
| **检查解读** | `reference/lab_reference_values.json` | 结构化查询检验正常值 |
| **GraphRAG** | `knowledge_graph/medical_entities_relations.json` | 多跳图查询（疾病→药品→相互作用） |
| **安全审核** | `knowledge_graph/drug_interactions.json` | 检索药物相互作用，生成警告 |
| **评估** | `evaluation/test_set.json` | 自动化 RAGAS 评估 |

### 3.2 数据加载示例

```python
import json

# 1. 加载 FAQ 问答对
with open('faq/faq_dataset.json', encoding='utf-8') as f:
    faq_data = json.load(f)
for item in faq_data['faq_entries']:
    print(item['question'], '->', item['answer'][:50])

# 2. 加载医学术语同义词
with open('reference/medical_synonyms.json', encoding='utf-8') as f:
    syn_data = json.load(f)
def normalize(term: str) -> str:
    for g in syn_data['synonym_groups']:
        if term in g['synonyms']:
            return g['standard_term']
    return term

normalize('感冒')    # -> '上呼吸道感染'
normalize('DM2')     # -> '2型糖尿病'
normalize('血压高')  # -> '高血压'

# 3. 加载药物相互作用（用于安全审核）
with open('knowledge_graph/drug_interactions.json', encoding='utf-8') as f:
    ddi_data = json.load(f)

def check_interaction(drug_a: str, drug_b: str):
    for ddi in ddi_data['drug_interactions']:
        if (ddi['drug_a'] == drug_a and ddi['drug_b'] == drug_b) or \
           (ddi['drug_a'] == drug_b and ddi['drug_b'] == drug_a):
            return ddi
    return None

check_interaction('华法林', '阿司匹林')
# -> {'interaction_level': '严重', 'mechanism': '...', 'clinical_advice': '...'}
```

---

## 四、数据来源

| 来源 | 类型 | 网址 |
|------|------|------|
| 默沙东诊疗手册（专业版/大众版） | 疾病知识 | https://www.msdmanuals.cn |
| 中华医学会糖尿病学分会 | 临床指南 | https://diab.cma.org.cn |
| 复旦大学附属华山医院 | 临床指南 | https://www.huasan.net |
| 国家药品监督管理局 (NMPA) | 药品说明书 | https://www.nmpa.gov.cn |
| 清华大学医院 | 药品说明书 | https://xyy.tsinghua.edu.cn |
| Mayo Clinic 妙佑医疗国际 | 疾病/药物知识 | https://www.mayoclinic.org/zh-hans |
| DrugBank | 药物相互作用 | https://go.drugbank.com |

> **声明**: 所有数据仅供教学科研使用。医学信息仅供参考，不构成医疗建议。

---

## 五、配套脚本与工具

| 文件 | 说明 |
|------|------|
| `scrape_medical_docs.py` | 医学数据采集脚本（PDF 下载 + 网页爬取 + 自动发现） |
| `requirements_scrape.txt` | 爬虫依赖包 |

### 重新采集数据

```bash
pip install -r requirements_scrape.txt
python scrape_medical_docs.py
```

脚本会自动跳过已采集的文件（断点续传），采集完成后生成 `scrape_report.json`。

---

## 六、更新日志

| 日期 | 更新内容 |
|------|---------|
| 2026-06-14 | 初始版本：82 个文件，25.9 MB；含 30 条 FAQ、55 组药物相互作用、20 种疾病条目、102 组术语同义词、45 项检验参考值、50 条评估测试；采集 6 份指南 + 8 份药品说明书 + 54 份疾病知识页面 |
