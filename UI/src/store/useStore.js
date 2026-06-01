import { create } from 'zustand'

export const useStore = create((set) => ({
  contracts: [],
  setContracts: (contracts) => set({ contracts }),
  
  lrrUpdates: [],
  setLrrUpdates: (updates) => set({ lrrUpdates: updates }),
  
  agentMessages: [{ id: 1, text: "Hello! I am your Regulatory Guardian. How can I assist you with contract review or compliance today?", sender: "agent" }],
  addAgentMessage: (message) => set((state) => ({ agentMessages: [...state.agentMessages, message] })),
  
  activeContract: null,
  setActiveContract: (contract) => set({ activeContract: contract }),
}))
