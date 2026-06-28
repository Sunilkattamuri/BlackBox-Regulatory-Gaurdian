import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, ShieldCheck } from 'lucide-react';
import { useStore } from '../store/useStore';
import api from '../api';

export default function AgentChat() {
  const { agentMessages, addAgentMessage } = useStore();
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [agentMessages, isTyping]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMsg = { id: Date.now(), text: input, sender: 'user' };
    addAgentMessage(userMsg);
    const queryText = input;
    setInput('');
    setIsTyping(true);

    try {
      const response = await api.post('/agent/query', {
        query: queryText,
        run_full_pipeline: false
      });
      
      const agentMsg = { 
        id: Date.now() + 1, 
        text: response.data.response, 
        sender: 'agent' 
      };
      addAgentMessage(agentMsg);
    } catch (error) {
      console.error('Error querying agent:', error);
      const errorMsg = { 
        id: Date.now() + 1, 
        text: "I'm sorry, I encountered an error connecting to the agent system. Please ensure the backend and Ollama are running.", 
        sender: 'agent' 
      };
      addAgentMessage(errorMsg);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto h-[calc(100vh-8rem)] flex flex-col">
      <div className="mb-6 text-center">
        <h2 className="text-3xl font-light text-white">Compliance Agent</h2>
        <p className="text-slate-400 mt-1">Ask questions about contracts, policies, and regulatory updates</p>
      </div>

      <div className="flex-1 bg-slate-900 border border-white/10 rounded-2xl flex flex-col overflow-hidden shadow-2xl relative">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent to-indigo-950/20 pointer-events-none" />
        
        <div className="p-4 border-b border-white/5 bg-slate-950/50 flex justify-between items-center z-10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-indigo-500/20 flex items-center justify-center border border-indigo-500/30">
              <Bot className="w-5 h-5 text-indigo-400" />
            </div>
            <div>
              <p className="font-medium text-slate-200">Regulatory Guardian</p>
              <p className="text-xs text-emerald-400 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> Online
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 px-3 py-1 bg-slate-800 rounded-full border border-white/5">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span className="text-xs font-medium text-slate-300">Guardrails Active</span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6 z-10">
          {agentMessages.map((msg) => (
            <div key={msg.id} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[80%] flex gap-4 ${msg.sender === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                
                <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-1 ${
                  msg.sender === 'user' ? 'bg-slate-700' : 'bg-indigo-600'
                }`}>
                  {msg.sender === 'user' ? <User className="w-4 h-4 text-white" /> : <Bot className="w-4 h-4 text-white" />}
                </div>

                <div className={`p-4 rounded-2xl whitespace-pre-wrap text-sm leading-relaxed ${
                  msg.sender === 'user' 
                    ? 'bg-slate-700 text-white rounded-tr-none' 
                    : 'bg-slate-800 text-slate-200 border border-white/5 rounded-tl-none shadow-lg'
                }`}>
                  {msg.text}
                </div>
              </div>
            </div>
          ))}
          {isTyping && (
            <div className="flex justify-start">
              <div className="flex gap-4">
                <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center shrink-0 mt-1">
                  <Bot className="w-4 h-4 text-white" />
                </div>
                <div className="p-4 rounded-2xl bg-slate-800 border border-white/5 rounded-tl-none flex items-center gap-2">
                  <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" />
                  <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce delay-100" />
                  <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce delay-200" />
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <form onSubmit={handleSend} className="p-4 border-t border-white/5 bg-slate-950/50 z-10">
          <div className="relative">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about regulations, contract risks, or policies..."
              className="w-full bg-slate-900 border border-white/10 text-white placeholder-slate-500 rounded-xl py-4 pl-5 pr-14 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
            />
            <button 
              type="submit"
              disabled={!input.trim() || isTyping}
              className="absolute right-2 top-2 bottom-2 aspect-square bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-500 text-white rounded-lg flex items-center justify-center transition-all"
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
