# Sample Data for AI-HR Bridge Platform

This directory contains clean sample data for testing and demo purposes.

## Directory Structure

```
sample_data/
├── interviews/          ← 4 interview transcripts
│   ├── interview_wang_jun_jie_senior_python_dev.txt      ★ GOOD - Strong technical candidate
│   ├── interview_lin_yi_jun_product_manager.txt          ★ GOOD - Strong product candidate
│   ├── interview_chen_mei_hua_junior_dev.txt             ✗ BAD - Weak technical candidate
│   └── interview_huang_li_chun_sales_rep.txt             ✗ BAD - Weak sales candidate
├── resumes/             ← 2 JD folders with CVs
│   ├── Senior Python Developer/    (JD + 10 matching CVs)
│   └── Data Scientist/             (JD + 10 matching CVs)
└── README.md
```

## Interview Transcripts (for Interview Assistant)

Copy a transcript into the **Interview Assist** section → paste JD → paste transcript → analyze.

| File | Candidate | Assessment |
|------|-----------|------------|
| `interview_wang_jun_jie_senior_python_dev.txt` | Wang Jun-Jie | ✅ STRONG — detailed technical answers, leadership, system design |
| `interview_lin_yi_jun_product_manager.txt` | Lin Yi-Jun | ✅ STRONG — strategic thinking, stakeholder management, data-driven |
| `interview_chen_mei_hua_junior_dev.txt` | Chen Mei-Hua | ❌ WEAK — lacks preparation, poor technical knowledge |
| `interview_huang_li_chun_sales_rep.txt` | Huang Li-Chun | ❌ WEAK — lacks initiative, poor communication, no research |

## Resumes (for CV Screening)

Two job categories, each with a job description and 10 matching CVs:

### Senior Python Developer
| # | File | Candidate | Profile |
|---|------|-----------|---------|
| 1 | `zhang_wei_senior_python_dev.txt` | Zhang Wei | 8yr, FastAPI, Kafka, K8s |
| 2 | `chen_ming_backend_architect.txt` | Chen Ming | 10yr, Distributed Systems, AWS |
| 3 | `lin_yi_jun_data_pipeline_engineer.txt` | Lin Yi-Jun | 6yr, Beam, Kafka, BigQuery |
| 4 | `huang_ya_ting_full_stack_dev.txt` | Huang Ya-Ting | 5yr, React, Python, GraphQL |
| 5 | `li_mei_ling_devops_engineer.txt` | Lee Mei-Ling | 7yr, K8s, Terraform, CI/CD |
| 6 | `liu_wei_cheng_python_backend_dev.txt` | Liu Wei-Cheng | 4yr, Django, FastAPI |
| 7 | `tsai_ching_yi_api_developer.txt` | Tsai Ching-Yi | 5yr, GraphQL, Microservices |
| 8 | `hsu_chia_chi_software_engineer.txt` | Hsu Chia-Chi | 3yr, Python, Java, Docker |
| 9 | `hsieh_wen_hsiung_cloud_engineer.txt` | Hsieh Wen-Hsiung | 6yr, AWS, K8s, Serverless |
| 10 | `kuo_tsung_han_senior_python_dev.txt` | Kuo Tsung-Han | 7yr, FastAPI, Microservices |

### Data Scientist
| # | File | Candidate | Profile |
|---|------|-----------|---------|
| 1 | `chen_ming_data_scientist.txt` | Chen Ming | 5yr, PyTorch, NLP, Transformers |
| 2 | `wang_jun_jie_ml_engineer.txt` | Wang Jun-Jie | 6yr, TensorFlow, MLflow |
| 3 | `wu_shu_fen_nlp_scientist.txt` | Wu Shu-Fen | 4yr, HuggingFace, RAG |
| 4 | `yang_kuo_hua_analytics_manager.txt` | Yang Kuo-Hua | 8yr, Airflow, dbt, Tableau |
| 5 | `hung_hui_ju_senior_data_scientist.txt` | Hung Hui-Ju | 6yr, XGBoost, A/B Testing |
| 6 | `lai_wan_ting_bi_analyst.txt` | Lai Wan-Ting | 3yr, SQL, Power BI |
| 7 | `yeh_pei_shan_research_scientist.txt` | Yeh Pei-Shan | 5yr, Computer Vision, YOLO |
| 8 | `liao_hsin_hung_ml_engineer.txt` | Liao Hsin-Hung | 4yr, Kubeflow, ML Pipelines |
| 9 | `cheng_ya_lin_data_analyst.txt` | Cheng Ya-Lin | 3yr, R, Statistical Analysis |
| 10 | `ho_chia_hao_deep_learning_engineer.txt` | Ho Chia-Hao | 5yr, GANs, Transformers |
