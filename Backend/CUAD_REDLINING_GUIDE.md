# CUAD Redlining Guide for BlackBox Regulatory Guardian

## Overview

This guide explains how to use the CUAD (Contract Understanding Atticus Dataset) to implement clause redlining in your legal document analysis system.

## What is CUAD?

**CUAD** is a dataset of 510 contracts manually annotated with 41 different clause types by legal experts. It's the largest expert-annotated NLP dataset for legal contract review.

- **Paper**: "CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review" (Hendrycks et al., 2021)
- **Size**: 510 documents, 125K+ clause instances
- **Clause Types**: 41 legal contract clause categories
- **Available**: https://huggingface.co/datasets/pile-of-law/cuad

## Quick Start

### 1. Load the Dataset

```python
from datasets import load_dataset

# Load CUAD
cuad = load_dataset("pile-of-law/cuad")

# Access splits
train_data = cuad['train']
test_data = cuad['test']
```

### 2. Run Redlining on Your PDF

```python
from notebooks.load_cuad import complete_redlining_workflow

# Process a contract PDF
result = complete_redlining_workflow(
    pdf_path='./contracts/sample_agreement.pdf',
    output_dir='./redlined_output'
)

# Output includes:
# - redlined_*.pdf: PDF with highlighted clauses
# - clause_report_*.json: Detailed clause analysis
```

### 3. Integration with FastAPI Backend

```python
# In Backend/main.py
from fastapi import FastAPI, UploadFile
from notebooks.load_cuad import complete_redlining_workflow

app = FastAPI()

@app.post("/api/redline")
async def redline_contract(file: UploadFile):
    # Save uploaded PDF
    pdf_path = f"./temp/{file.filename}"
    with open(pdf_path, 'wb') as f:
        f.write(await file.read())
    
    # Run redlining
    result = complete_redlining_workflow(pdf_path)
    
    return result['summary']
```

## CUAD Clause Types (41 Categories)

### High-Risk Clauses (Focus Areas)
1. **Limitation of Liability** - Caps on damages/liability
2. **Non-Compete** - Restrictions on competing business
3. **Termination for Convenience** - Easy exit clauses
4. **Exclusivity** - Exclusive dealing requirements

### Important Clauses
5. **Confidentiality/Non-Disclosure** - Data protection
6. **Governing Law** - Jurisdiction specification
7. **Indemnification** - Loss compensation terms
8. **Change of Control** - M&A impact clauses

### Financial Clauses
9. **Fees/Charges** - Pricing and costs
10. **Liability Caps** - Maximum liability limits
11. **Minimum Commitments** - Minimum purchase/service levels
12. **Payables and Receivables** - Payment terms

### [Full list of 41 clauses in the notebook]

## Key Features Implemented

### ✅ PDF Text Extraction
- Extracts text from multi-page PDFs
- Preserves page information
- Handles various PDF formats

### ✅ Clause Identification
- Keyword-based matching (baseline)
- Transformer model classification (advanced)
- Context extraction around clauses

### ✅ Redlining & Annotation
- Color-coded highlighting by clause type
- PDF annotations with clause metadata
- Preservation of original document

### ✅ Report Generation
- Summary statistics by clause type
- High-risk clause flagging
- JSON export for downstream processing

## Advanced Implementation

### Fine-Tuning on CUAD Data

```python
from transformers import AutoModelForSequenceClassification, Trainer

# Load pre-trained legal model
model = AutoModelForSequenceClassification.from_pretrained(
    "nlpaueb/legal-bert-base-uncased",
    num_labels=41  # 41 CUAD clause types
)

# Fine-tune on your data
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=cuad['train'],
)

trainer.train()
```

### Using LLM Summarization

```python
from langchain.llms import OpenAI
from langchain.chains.summarize import load_summarize_chain

# Summarize high-risk clauses
llm = OpenAI(temperature=0)
chain = load_summarize_chain(llm, chain_type="map_reduce")

for clause in high_risk_clauses:
    summary = chain.run([clause['context']])
    print(f"Clause: {clause['type']}\nSummary: {summary}")
```

### Multi-Model Ensemble

```python
# Combine multiple models for better accuracy
models = [
    "nlpaueb/legal-bert-base-uncased",
    "distilbert-base-uncased",
    "roberta-base"
]

# Ensemble predictions
predictions = []
for model_name in models:
    pred = classify_with_model(text, model_name)
    predictions.append(pred)

# Aggregate results
final_prediction = aggregate_predictions(predictions)
```

## Project Integration

### Backend (FastAPI)
- Upload PDF contracts
- Run redlining analysis
- Return clause report
- Stream redlined PDF

### UI (React)
- File upload interface
- Visualization of highlighted clauses
- Clause summary view
- Download redlined PDF
- Export report to JSON/Excel

### Data Pipeline
1. PDF Upload → FastAPI
2. Text Extraction
3. Clause Identification
4. Annotation Generation
5. Report Creation
6. Response to UI

## Performance Metrics

When fine-tuning on CUAD:
- **Precision**: Typically 85-90%
- **Recall**: Typically 80-85%
- **F1-Score**: Typically 82-87%

These improve with:
- More training data
- Longer training
- Ensemble models
- Post-processing rules

## Troubleshooting

### PDF Extraction Issues
- Check PDF is not password-protected
- Verify PDF is not corrupted
- Use OCR for scanned documents (easyocr)

### Model Download Failures
- Ensure internet connection
- Set `HF_TOKEN` for private models
- Cache models locally

### Memory Issues
- Process PDFs in batches
- Use smaller batch sizes
- Consider smaller models (distilBERT)

## References

- CUAD Dataset: https://huggingface.co/datasets/pile-of-law/cuad
- LegalBERT: https://huggingface.co/nlpaueb/legal-bert-base-uncased
- PyMuPDF: https://pymupdf.readthedocs.io/
- Transformers: https://huggingface.co/docs/transformers/

## License & Citation

If using CUAD, cite:
```bibtex
@article{hendrycks2021cuad,
  title={CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review},
  author={Hendrycks, Dan and others},
  journal={arXiv preprint arXiv:2103.06268},
  year={2021}
}
```

---

**Last Updated**: April 25, 2026
**Project**: BlackBox Regulatory Guardian
**Status**: Implementation Complete
