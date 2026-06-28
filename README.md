# BlackBox Regulatory Guardian

Welcome to the **BlackBox Regulatory Guardian**! This is an explainable, Guardrailed Agentic AI Platform designed for Multi-Modal Banking Contract Review and Automated Regulatory Lifecycle Management (LRR). 

The platform consists of two main components:
1. **Backend**: A FastAPI server powered by LangGraph (for multi-agent orchestration), custom NLP models (Legal-BERT and LayoutLMv3), and Pinecone vector database.
2. **UI**: A Vite + React application that provides the interactive dashboard and chatbot interface.

---

## 🚀 How to Run the Project

### 1. Start the Backend

1. Open a new terminal.
2. Navigate to the `Backend` directory:
   ```bash
   cd Backend
   ```
3. Install the Python dependencies (Python 3.11+ is recommended):
   ```bash
   pip install -r requirements.txt
   ```
4. **Ollama Setup**: Ensure [Ollama](https://ollama.com/) is installed and running. Pull the required Llama model (check `.env` for the exact model name, usually `llama3.1`):
   ```bash
   ollama pull llama3.1
   ```
5. Start the FastAPI server:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   *The backend will now be running on `http://localhost:8000`. You can view the API documentation at `http://localhost:8000/docs`.*

### 2. Start the UI

1. Open a separate terminal.
2. Navigate to the `UI` directory:
   ```bash
   cd UI
   ```
3. Install the Node.js dependencies:
   ```bash
   npm install
   ```
4. Start the development server:
   ```bash
   npm run dev
   ```
   *The UI will typically be accessible at `http://localhost:5173`. Open this URL in your browser to interact with the application.*

---

## 📄 Where to Get Sample Contract PDFs for Testing

If you want to test the contract extraction and layout analysis features, you can download real-world sample contracts from the following open-source legal datasets:

1. **CUAD (Contract Understanding Atticus Dataset)** (Highly Recommended)
   - CUAD is the industry standard for contract review. It contains hundreds of commercial legal contracts annotated by legal experts.
   - **Download PDFs**: You can get the raw PDF contracts from the official project page: [Atticus Project CUAD](https://www.atticusprojectai.org/cuad) or via [HuggingFace](https://huggingface.co/datasets/cuad).

2. **SEC EDGAR Database**
   - The US Securities and Exchange Commission (SEC) EDGAR database provides public filings, which include credit agreements, employment agreements, and vendor contracts.
   - **Search here**: [SEC EDGAR](https://www.sec.gov/edgar/search/)

3. **LawInsider**
   - Contains millions of publicly available commercial contracts.
   - **Search here**: [LawInsider](https://www.lawinsider.com/contracts)

You can download any PDF from these sources, upload it through the application's UI, and the system will automatically parse the layout using LayoutLMv3 and extract clauses using Legal-BERT!
