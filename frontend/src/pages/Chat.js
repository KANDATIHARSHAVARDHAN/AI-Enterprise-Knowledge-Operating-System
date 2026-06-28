import React, { useState, useEffect, useRef } from 'react';
import { queryService } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { 
  Send, Sparkles, AlertCircle, Bookmark, Compass, RefreshCw, AlertOctagon, Info
} from 'lucide-react';

const Chat = () => {
  const { user } = useAuth();
  const [conversations, setConversations] = useState([]);
  const [activeConv, setActiveConv] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeTrace, setActiveTrace] = useState(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    fetchConversations();
  }, []);

  useEffect(() => {
    if (activeConv) {
      fetchMessages(activeConv.id);
    }
  }, [activeConv]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const fetchConversations = async () => {
    try {
      const data = await queryService.getConversations();
      setConversations(data.conversations || []);
      if (data.conversations?.length > 0 && !activeConv) {
        setActiveConv(data.conversations[0]);
      }
    } catch (err) {
      console.error('Failed to load conversations:', err);
    }
  };

  const fetchMessages = async (convId) => {
    try {
      const data = await queryService.getMessages(convId);
      setMessages(data.messages || []);
      setActiveTrace(null);
    } catch (err) {
      console.error('Failed to fetch messages:', err);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userQuery = input;
    setInput('');
    setLoading(true);

    // Optimistically add user message
    const tempUserMsg = {
      id: Date.now(),
      role: 'user',
      content: userQuery,
      created_at: new Date().toISOString()
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const res = await queryService.ask(userQuery, activeConv?.id);
      
      // Update messages list
      if (!activeConv) {
        // Created a new conversation, refresh the sidebar list
        await fetchConversations();
        const nextConvs = await queryService.getConversations();
        const matchingConv = nextConvs.conversations?.find(c => c.id === res.conversation_id);
        if (matchingConv) {
          setActiveConv(matchingConv);
        }
      } else {
        await fetchMessages(activeConv.id);
      }
    } catch (err) {
      const errorMsg = {
        id: Date.now() + 1,
        role: 'system',
        content: `Error: ${err.response?.data?.detail || 'Something went wrong while executing the multi-agent system.'}`
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const selectConversation = (conv) => {
    setActiveConv(conv);
  };

  const startNewConversation = () => {
    setActiveConv(null);
    setMessages([]);
    setActiveTrace(null);
  };

  return (
    <div className="chat-interface-wrapper animate-fadeIn">
      {/* Conversations Sidebar */}
      <div className="chat-conversations-panel glass">
        <div className="panel-header">
          <button className="btn-primary w-full" onClick={startNewConversation}>
            + New Thread
          </button>
        </div>
        <div className="conversations-list">
          {conversations.map((conv) => (
            <button 
              key={conv.id}
              className={`conv-item-btn ${activeConv?.id === conv.id ? 'active' : ''}`}
              onClick={() => selectConversation(conv)}
            >
              <Bookmark size={16} className="text-slate-400" />
              <span className="truncate">{conv.title}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Main Chat Stream */}
      <div className="chat-main-panel glass">
        <div className="chat-header-bar">
          <h3>{activeConv ? activeConv.title : 'New Investigation Thread'}</h3>
          {loading && (
            <div className="agent-status-ticker flex items-center gap-2">
              <RefreshCw size={14} className="animate-spin text-cyan" />
              <span className="text-xs text-slate-400">Orchestrating Specialist Agents...</span>
            </div>
          )}
        </div>

        <div className="chat-messages-scroll-area">
          {messages.length === 0 ? (
            <div className="chat-welcome-state">
              <Compass size={48} className="text-slate-600 mb-4 animate-bounce" />
              <h2>Investigate Enterprise System</h2>
              <p>Ask a question about machine events, maintenance manuals, parts, or database history. The multi-agent orchestrator will route tasks accordingly.</p>
              <div className="suggested-queries">
                <button onClick={() => setInput('Why did Machine X fail three times this month?')}>
                  "Why did Machine X fail three times this month?"
                </button>
                <button onClick={() => setInput('Find all critical events for Robotic Welding Arm A')}>
                  "Find all critical events for Robotic Welding Arm A"
                </button>
              </div>
            </div>
          ) : (
            messages.map((msg) => (
              <div key={msg.id} className={`message-row ${msg.role}`}>
                <div className="message-bubble glass">
                  <div className="message-content">{msg.content}</div>

                  {msg.role === 'assistant' && (
                    <div className="assistant-meta mt-4 flex items-center justify-between border-t border-slate-700/50 pt-2">
                      <div className="flex gap-4">
                        <span className="confidence flex items-center gap-1 text-xs">
                          <Sparkles size={12} className="text-amber-400" />
                          Confidence: {msg.confidence_score ? (msg.confidence_score * 100).toFixed(0) : 0}%
                        </span>
                        <span className="latency text-xs text-slate-400">
                          {msg.latency_ms ? `${(msg.latency_ms / 1000).toFixed(2)}s` : ''}
                        </span>
                      </div>
                      
                      <div className="flex gap-2">
                        {msg.agent_trace && msg.agent_trace.length > 0 && (
                          <button 
                            className="btn-text-icon flex items-center gap-1 text-xs text-cyan hover:underline"
                            onClick={() => setActiveTrace(msg.agent_trace)}
                          >
                            <Info size={12} />
                            <span>View Agent Path</span>
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
          {loading && (
            <div className="message-row assistant">
              <div className="message-bubble glass loading flex items-center gap-3">
                <div className="typing-dot"></div>
                <div className="typing-dot"></div>
                <div className="typing-dot"></div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <form className="chat-input-bar-container" onSubmit={handleSend}>
          <input 
            type="text"
            placeholder="Type your enterprise system query..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
          />
          <button type="submit" className="chat-send-btn" disabled={loading || !input.trim()}>
            <Send size={18} />
          </button>
        </form>
      </div>

      {/* Right Side Agent Trace Visualizer Panel */}
      {activeTrace && (
        <div className="agent-trace-sidebar-panel glass animate-slideLeft">
          <div className="panel-header border-b border-slate-700/50 pb-2 mb-4 flex justify-between items-center">
            <h3>Orchestration Trace</h3>
            <button className="btn-close" onClick={() => setActiveTrace(null)}>X</button>
          </div>
          <div className="trace-path-flow">
            {activeTrace.map((step, index) => (
              <div key={index} className="trace-step flex items-start gap-3 relative pb-4">
                {index < activeTrace.length - 1 && (
                  <div className="connector-line"></div>
                )}
                <div className="step-badge-indicator flex items-center justify-center bg-cyan text-slate-900 font-bold rounded-full w-6 h-6 text-xs">
                  {index + 1}
                </div>
                <div className="step-details flex-1">
                  <h4 className="text-cyan font-bold text-sm uppercase">{step.agent}</h4>
                  <p className="text-xs text-slate-300 mt-1">{step.action || step.task || 'Processed execution step'}</p>
                  {step.status && (
                    <span className={`status-badge text-[10px] ${step.status}`}>{step.status}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default Chat;
