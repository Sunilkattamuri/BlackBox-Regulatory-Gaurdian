import os
import phoenix as px
from phoenix.otel import register
from openinference.instrumentation.langchain import LangChainInstrumentor
from langchain_community.llms import Ollama
from langchain_core.prompts import PromptTemplate

def main():
    print("Initializing Phoenix Tracing...")
    
    # 2. Instrument LangChain (Tell it to send traces to Phoenix)
    # This assumes `phoenix serve` is running in the background on port 4317
    tracer_provider = register(
        project_name="regulatory-guardian",
        endpoint="http://127.0.0.1:4317" # Phoenix OTLP grpc port
    )
    LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
    print("LangChain has been instrumented. All calls will be traced to Phoenix.")

    # 3. Setup Ollama Model (using the environment configuration or defaults)
    ollama_model = os.getenv("LLM_MODEL", "llama3.1")
    ollama_url = os.getenv("LLM_BASE_URL", "http://localhost:11434")
    
    print(f"Connecting to Ollama model: {ollama_model} at {ollama_url}")
    # Initialize the LLM (make sure Ollama is running in the background!)
    try:
        llm = Ollama(model=ollama_model, base_url=ollama_url, temperature=0.0)
    except Exception as e:
        print(f"Failed to initialize Ollama: {e}")
        return
    
    # 4. Create a mock Agent/Chain
    template = """You are a helpful Regulatory Guardian AI. 
User Question: {question}
Please answer concisely."""
    
    prompt = PromptTemplate.from_template(template)
    chain = prompt | llm
    
    # 5. Run the chain with sample questions (this will generate traces)
    questions = [
        "What is the capital of France?",
        "Explain what a regulatory guardian does in one sentence.",
        "How do you ensure data privacy in a banking context?"
    ]
    
    print("\n--- Executing Chain (generating traces) ---")
    for q in questions:
        print(f"\nQuestion: {q}")
        try:
            response = chain.invoke({"question": q})
            print(f"Response: {response}")
        except Exception as e:
            print(f"Error during execution: {e}")
            print("HINT: Make sure Ollama is running and the model is downloaded ('ollama run llama3.1').")
            break
            
    print("\n--- Traces Generated ---")
    print("Check your Phoenix Dashboard (http://localhost:6006) in your browser to view the traces!")

if __name__ == "__main__":
    main()
