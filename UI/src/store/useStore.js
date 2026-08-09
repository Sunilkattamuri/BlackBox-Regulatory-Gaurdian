import { create } from 'zustand'
import { devtools } from 'zustand/middleware'

export const useStore = create(devtools((set) => ({
  contracts: [],
  setContracts: (contracts) => set({ contracts }, false, 'setContracts'),
  
  lrrUpdates: [],
  setLrrUpdates: (updates) => set({ lrrUpdates: updates }, false, 'setLrrUpdates'),
  
  agentMessages: [{ id: 1, text: "Hello! I am your Regulatory Guardian. How can I assist you with contract review or compliance today?", sender: "agent" }],
  addAgentMessage: (message) => set((state) => ({ agentMessages: [...state.agentMessages, message] }), false, 'addAgentMessage'),
  
  activeContract: null,
  setActiveContract: (contract) => set({ activeContract: contract }, false, 'setActiveContract'),
}), { name: 'RegulatoryGuardianStore' }))
