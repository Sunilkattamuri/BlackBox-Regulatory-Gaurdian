import React, { useState } from 'react';
import Sidebar from './components/Sidebar';
import ContractDashboard from './components/ContractDashboard';
import LRRDashboard from './components/LRRDashboard';
import AgentChat from './components/AgentChat';
import './index.css';

function App() {
  const [activeTab, setActiveTab] = useState('contracts');

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 font-sans">
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />
      
      <main className="flex-1 flex flex-col overflow-hidden relative">
        {/* Dynamic Background */}
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-900/20 to-purple-900/20 pointer-events-none" />
        
        <header className="h-16 flex items-center px-8 border-b border-white/10 bg-slate-950/50 backdrop-blur-md z-10">
          <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 to-purple-400">
            BlackBox Regulatory Guardian
          </h1>
        </header>

        <div className="flex-1 overflow-auto p-8 z-10">
          {activeTab === 'contracts' && <ContractDashboard />}
          {activeTab === 'lrr' && <LRRDashboard />}
          {activeTab === 'agent' && <AgentChat />}
        </div>
      </main>
    </div>
  );
}

export default App;
