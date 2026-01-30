# AI Debug Contract

Goal: validate repo structure + simulate ARCH -> DEV -> QA pipeline.

Rules:
- In dry-run mode, do not call any external LLM API.
- Produce placeholder outputs into output/ as if each stage ran:
  - output/arch_plan.md
  - output/dev_patch.md
  - output/qa_report.md
- Workflow must succeed in dry-run if repo structure is correct.
