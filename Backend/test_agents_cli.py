import os
import sys

# Ensure backend folder is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.agent_service import agent_service

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def main():
    while True:
        clear_screen()
        print("==================================================")
        print("  BlackBox Regulatory Guardian - Agent CLI Tester")
        print("==================================================")
        print(f" LLM Provider: {agent_service.llm.__class__.__name__ if agent_service.llm else 'None (Fallback Mode)'}")
        print(f" Initialization Status: {'INITIALIZED' if agent_service._initialized else 'FALLBACK (LLM Offline)'}")
        if agent_service._init_error:
            print(f" Init Notice: {agent_service._init_error}")
        print("--------------------------------------------------")
        print("Select an agent or flow to test:")
        print("1. [Supervisor Routing] Send a general query (Let Supervisor decide)")
        print("2. [Regulatory Monitor] Test RBI Update Fetching")
        print("3. [Obligation Extractor] Test Extracting Actionable Obligations")
        print("4. [Impact Assessor] Test Mapping and Risk Assessment on Policies")
        print("5. [Compliance Reporter] Test Report Generation")
        print("6. [Full Pipeline] Run sequentially: Monitor -> Extract -> Assess -> Report")
        print("7. [System Check] Run diagnostics and check available tools")
        print("8. Exit")
        print("--------------------------------------------------")
        
        choice = input("Enter choice (1-8): ").strip()
        
        if choice == "8":
            print("\nExiting. Good luck with your dissertation!")
            break
            
        elif choice == "7":
            print("\n--- System Check & Diagnostics ---")
            print(f"LLM Available: {'Yes' if agent_service.llm else 'No'}")
            print("Specialist Agents Configured:")
            for a in agent_service.get_agents_info():
                print(f"\n  • {a['name'].upper()}: {a['description']}")
                print(f"    Capabilities: {', '.join(a['capabilities'])}")
                print(f"    Tools: {', '.join(a['tools'])}")
            input("\nPress Enter to return to menu...")
            
        elif choice == "1":
            query = input("\nEnter your query for the Supervisor (e.g. 'What are the latest RBI regulations?'): ").strip()
            if not query:
                continue
            print(f"\nProcessing: '{query}'...")
            result = agent_service.process_query(query)
            print("\n================== RESPONSE ==================")
            print(result.get("response"))
            print("==============================================")
            print(f"Agent Executed: {result.get('agent_used')}")
            print(f"Sources: {result.get('sources')}")
            input("\nPress Enter to return to menu...")
            
        elif choice == "2":
            query = "Fetch and summarize the latest circulars from the Reserve Bank of India (RBI)."
            print(f"\nTriggering Regulatory Monitor Agent...")
            print(f"Query: '{query}'")
            result = agent_service.process_query(query)
            print("\n================== RESPONSE ==================")
            print(result.get("response"))
            print("==============================================")
            input("\nPress Enter to return to menu...")
            
        elif choice == "3":
            snippet = (
                "The primary cooperative banks shall maintain a minimum leverage ratio of 4% "
                "and must submit monthly regulatory reporting forms to the regional supervisor."
            )
            print(f"\nTriggering Obligation Extractor Agent...")
            print(f"Analysing Snippet: '{snippet}'")
            result = agent_service.process_query(f"Extract obligations from this text: '{snippet}'")
            print("\n================== RESPONSE ==================")
            print(result.get("response"))
            print("==============================================")
            input("\nPress Enter to return to menu...")
            
        elif choice == "4":
            query = "Assess how Digital Lending regulations impact our internal Data Protection policy."
            print(f"\nTriggering Impact Assessor Agent...")
            print(f"Query: '{query}'")
            result = agent_service.process_query(query)
            print("\n================== RESPONSE ==================")
            print(result.get("response"))
            print("==============================================")
            input("\nPress Enter to return to menu...")
            
        elif choice == "5":
            query = "Generate a comprehensive compliance report based on active digital lending obligations."
            print(f"\nTriggering Compliance Reporter Agent...")
            print(f"Query: '{query}'")
            result = agent_service.process_query(query)
            print("\n================== RESPONSE ==================")
            print(result.get("response"))
            print("==============================================")
            input("\nPress Enter to return to menu...")
            
        elif choice == "6":
            print(f"\nTriggering Full Multi-Agent Pipeline Cycle...")
            result = agent_service.process_query("Run the full compliance check pipeline.", run_full_pipeline=True)
            print("\n================== FINAL COMPLIANCE REPORT ==================")
            print(result.get("response"))
            print("=============================================================")
            print("\nProcessing Steps Executed:")
            for step in result.get("processing_steps", []):
                print(f"  [x] Step: {step.get('step')} | Status: {step.get('status')}")
            input("\nPress Enter to return to menu...")
            
        else:
            print("\nInvalid choice. Press Enter to try again.")
            input()

if __name__ == "__main__":
    main()
