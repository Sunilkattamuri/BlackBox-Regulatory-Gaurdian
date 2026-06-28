import React from 'react';
import { NavLink } from 'react-router-dom';
import { FileText, ShieldAlert, Bot } from 'lucide-react';
import { useStore } from '../store/useStore';

export default function Sidebar() {
  const { setActiveContract } = useStore();
  const tabs = [
    { id: 'contracts', icon: FileText, label: 'Contracts' },
    { id: 'lrr', icon: ShieldAlert, label: 'Regulatory (LRR)' },
    { id: 'agent', icon: Bot, label: 'Compliance Agent' },
  ];

  return (
    <aside className="w-64 bg-slate-900 border-r border-white/5 flex flex-col">
      <div className="p-6">
        <div className="w-12 h-12 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center shadow-lg shadow-indigo-500/20 mb-2">
          <ShieldAlert className="text-white w-6 h-6" />
        </div>
        <h2 className="text-sm font-semibold tracking-wider text-slate-400 uppercase mt-4">Modules</h2>
      </div>
      
      <nav className="flex-1 px-4 space-y-2">
        {tabs.map(tab => (
          <NavLink
            key={tab.id}
            to={`/${tab.id}`}
            onClick={() => {
              if (tab.id === 'contracts') {
                setActiveContract(null);
              }
            }}
            className={({ isActive }) => `w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 ${
              isActive 
                ? 'bg-indigo-500/10 text-indigo-300 border border-indigo-500/20' 
                : 'text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent'
            }`}
          >
            <tab.icon className="w-5 h-5" />
            <span className="font-medium">{tab.label}</span>
          </NavLink>
        ))}
      </nav>
      
      <div className="p-6 border-t border-white/5">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center border border-white/10">
            <span className="text-xs font-bold text-slate-300">SK</span>
          </div>
          <div className="text-sm">
            <p className="text-slate-200 font-medium">Sunil Kumar</p>
            <p className="text-slate-500 text-xs">Legal Ops</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
