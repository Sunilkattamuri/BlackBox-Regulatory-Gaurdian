# BlackBox Regulatory Guardian - Backend

This is the backend for the Agentic AI Platform for Multi-Modal Banking Contract Review and Automated Regulatory Lifecycle Management (LRR). It is built with FastAPI, LangGraph, FastMCP, and HuggingFace Transformers.

## Features
- **Contract Analysis**: Extracts clauses using Legal-BERT and document layout using LayoutLMv3.
- **Regulatory Lifecycle Management (LRR)**: Monitors regulatory changes and maps obligations.
- **Agentic AI**: Uses LangGraph and FastMCP to provide an autonomous compliance agent.
- **Explainability (XAI) & Guardrails**: Ensures transparent and compliant AI outputs.

## Prerequisites
- Python 3.11+
- NVIDIA GPU (Recommended for training and inference)
- [Ollama](https://ollama.com/) (For running the local Llama 3 model for the Agent)

## Setup & Installation

1. **Install Dependencies**:
   Navigate to the `Backend` directory and install the requirements:
   ```bash
   pip install -r requirements.txt
   ```
   *Note: If using `uv`, you can run `uv pip install -r requirements.txt`.*

2. **Ollama Setup (For Agent)**:
   Ensure Ollama is installed and running locally. Pull the `llama3` model:
   ```bash
   ollama pull llama3
   ```

## Running the Backend

Start the FastAPI server:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
The API documentation will be available at: http://localhost:8000/docs

## Model Training

Before the contract service can use the fine-tuned models, you must prepare the data and run the training scripts:

1. **Prepare Data**:
   ```bash
   python training/data_prep.py
   ```
2. **Train Legal-BERT on CUAD**:
   ```bash
   python training/train_legal_bert.py
   ```
3. **Train LayoutLMv3 on DocLayNet**:
   ```bash
   python training/train_layoutlmv3.py
   ```

*(Note: If the models are not trained, the application will fallback to base models or simulated extraction for development).*

## Debugging Guide

1. **Database Issues**:
   The application uses SQLite (`sql_app.db`). If you encounter schema errors, delete `sql_app.db` and restart the server to recreate the tables.
   
2. **Agent Errors (Connection Refused)**:
   If the agent returns an initialization error, ensure Ollama is running (`ollama serve`) and the `llama3` model is downloaded.

3. **CUDA Out of Memory**:
   If training or inference crashes with OOM errors, reduce the `BATCH_SIZE` in the respective `train_*.py` scripts, or ensure no other heavy GPU processes are running.

4. **MCP Server**:
   The FastMCP tools are directly bound to the LangGraph agent in `app/services/agent_service.py` for simplicity in the prototype. If you wish to run the MCP server standalone:
   ```bash
   python app/services/mcp_server.py
   ```
