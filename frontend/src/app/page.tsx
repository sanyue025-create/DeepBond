'use client';

import { useState, useEffect, useRef } from 'react';
import dynamic from 'next/dynamic';

const AtomicCore = dynamic(() => import('../components/AtomicCore'), { ssr: false });
import Typewriter from '../components/Typewriter';

interface Message {
  id: string; // Required for reliable state updates and key-based rendering
  role: 'user' | 'ai' | 'proactive';
  content: string;
  timestamp: string;
  animate?: boolean;
}

interface LogEntry {
  type: string;
  content: any;
  timestamp: string;
}

interface Task {
  id: string;
  content: string;
  status: 'active' | 'completed' | 'pending';
  schedule: string;
  next_run?: number;
  max_repetitions?: number;
}

export default function Home() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [sessions, setSessions] = useState<any[]>([]); // New: Session List
  const [showSessions, setShowSessions] = useState(false); // New: Toggle Right Column

  // [New] Tab System
  const [activeTab, setActiveTab] = useState<'history' | 'care'>('history');
  const [careItems, setCareItems] = useState<any[]>([]);

  const [isConnected, setIsConnected] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [phase, setPhase] = useState('idle'); // New: AI Phase State

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, logs]);

  // WebSocket Connection with Auto-Reconnect
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimeout: NodeJS.Timeout;
    let isMounted = true;

    const connect = () => {
      if (!isMounted) return;

      ws = new WebSocket('ws://localhost:8000/ws');

      ws.onopen = () => {
        if (!isMounted) return;
        setIsConnected(true);
        addLog('SYS', 'LINK ESTABLISHED');
      };

      ws.onclose = () => {
        if (!isMounted) return;
        setIsConnected(false);
        // addLog('SYS', 'LINK LOST - RETRYING...'); // Optional: Reduce noise
        reconnectTimeout = setTimeout(connect, 3000); // Retry every 3s
      };

      ws.onmessage = (event) => {
        if (!isMounted) return;
        try {
          const data = JSON.parse(event.data);

          if (data.type === 'proactive') {
            setMessages(prev => [...prev, {
              id: `proactive-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
              role: 'proactive',
              content: data.content,
              timestamp: new Date().toLocaleTimeString(),
              animate: true
            }]);
          }
          else if (data.type === 'thought') {
            setIsThinking(true);
            setTimeout(() => setIsThinking(false), 2000);
            addLog(data.category || 'THOUGHT', data.content);
          }
          else if (data.type === 'state') {
            setPhase(data.phase);
            setIsThinking(data.phase !== 'idle');
          }
        } catch (e) {
          console.error('WS Parse Error', e);
        }
      };
    };

    connect();

    return () => {
      isMounted = false;
      if (ws) ws.close();
      clearTimeout(reconnectTimeout);
    };
  }, []);

  // Fetch Logic
  const fetchHistory = async () => {
    try {
      const res = await fetch('http://localhost:8000/history');
      const data = await res.json();
      const formattedMessages = data.map((msg: any, idx: number) => ({
        id: msg.id || `hist-${idx}-${Date.now()}`, // [Fix] Use Backend ID if available
        role: msg.role === 'model' ? 'ai' : msg.role === 'assistant' ? 'ai' : 'user',
        content: msg.content,
        timestamp: new Date().toLocaleTimeString(),
        animate: false
      }));
      setMessages(formattedMessages); // Reset/Load messages
      scrollToBottom();
      addLog('SYS', `LOADED ${formattedMessages.length} MSGS`);
    } catch (e) {
      console.error('Failed to load history', e);
    }
  };

  const fetchSessions = async () => {
    try {
      const res = await fetch('http://localhost:8000/sessions');
      const data = await res.json();
      setSessions(data);
    } catch (e) {
      console.error('Failed to load sessions', e);
    }
  };

  const fetchCareList = async () => {
    try {
      const res = await fetch('http://localhost:8000/care-list');
      const data = await res.json();
      setCareItems(data);
    } catch (e) {
      console.error("Failed to fetch care list", e);
    }
  };

  useEffect(() => {
    if (activeTab === 'care') {
      fetchCareList();
      const interval = setInterval(fetchCareList, 2000);
      return () => clearInterval(interval);
    }
  }, [activeTab]);

  // Initial Load & Auto-Restore
  const hasLoadedRef = useRef(false);

  useEffect(() => {
    fetchSessions(); // First, get the list
  }, []);

  // Once sessions are loaded, automatically open the latest one ONCE
  useEffect(() => {
    if (sessions.length > 0 && !hasLoadedRef.current) {
      console.log('Auto-loading latest session...');
      const latestId = sessions[0].id;
      handleLoadSession(latestId);
      hasLoadedRef.current = true;
    }
  }, [sessions]);



  const addLog = (type: string, content: any) => {
    setLogs(prev => [...prev.slice(-49), {
      type,
      content: typeof content === 'object' ? JSON.stringify(content, null, 2) : content,
      timestamp: new Date().toLocaleTimeString()
    }]);
  };

  const handleSend = async () => {
    if (!input.trim()) return;
    const userMsg = input;
    setInput('');
    const userMsgId = `user-${Date.now()}`;
    setMessages(prev => [...prev, {
      id: userMsgId,
      role: 'user',
      content: userMsg,
      timestamp: new Date().toLocaleTimeString()
    }]);

    setIsThinking(true);

    try {
      // Create empty message for AI response with fixed ID
      const aiMsgId = `ai-${Date.now()}`;
      setMessages(prev => [...prev, {
        id: aiMsgId,
        role: 'ai',
        content: '',
        timestamp: new Date().toLocaleTimeString(),
        animate: false // Stream naturally feels like typing, no typewriter needed
      }]);

      const res = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg, id: userMsgId }), // [Link] Send ID
      });

      if (!res.body) throw new Error("No response body");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let done = false;

      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        const chunkValue = decoder.decode(value, { stream: !done });

        setMessages(prev => {
          return prev.map(msg => {
            if (msg.id === aiMsgId) {
              return { ...msg, content: msg.content + chunkValue };
            }
            return msg;
          });
        });
      }

    } catch (e) {
      addLog('ERR', 'TX FAILED');
    } finally {
      setIsThinking(false);
    }
  };

  const handleNewSession = async () => {
    // 移除确认弹窗，实现"即点即毁"的畅快感（且修复自动化测试阻塞）
    try {
      const res = await fetch('http://localhost:8000/sessions/new', { method: 'POST' });
      const data = await res.json();

      // Force UI sync from Backend Source of Truth
      if (data.chat_history) {
        setMessages(data.chat_history.map((msg: any, idx: number) => ({
          id: `new-session-${idx}-${Date.now()}`,
          role: msg.role === 'model' ? 'ai' : msg.role === 'assistant' ? 'ai' : 'user',
          content: msg.content,
          timestamp: new Date().toLocaleTimeString(),
          animate: false
        })));
      } else {
        setMessages([]);
      }

      // Verify via Session List update only
      await fetchSessions();
      setLogs([]); // [Fix] Clear logs for new session
      addLog('SYS', 'NEW SESSION STARTED');
    } catch (e) {
      addLog('ERR', 'NEW SESSION FAILED');
    }
  };

  const handleLoadSession = async (sessionId: string) => {
    try {
      const res = await fetch(`http://localhost:8000/sessions/${sessionId}/load`, { method: 'POST' });
      const data = await res.json();

      // Load Logs from backend
      if (data.logs) {
        // Normalize logs to match frontend expectations (uppercase type, stringified content)
        const normalized = data.logs.map((L: any) => ({
          ...L,
          type: L.type.toUpperCase(),
          content: typeof L.content === 'object' ? JSON.stringify(L.content) : L.content
        }));
        setLogs(normalized);
      } else {
        setLogs([]);
      }


      // Load Active Tasks from backend - DELETED

      await fetchHistory();
      addLog('SYS', `SESSION ${sessionId} LOADED`);
    } catch (e) {
      addLog('ERR', 'LOAD SESSION FAILED');
    }
  };

  const handleDelete = async (msgId: string) => {
    try {
      addLog('SYS', `DELETING MSG...`);
      await fetch(`http://localhost:8000/messages/${msgId}`, { method: 'DELETE' });
      setMessages(prev => prev.filter(m => m.id !== msgId));
      addLog('SYS', `DELETED MSG`);
    } catch (e) {
      addLog('ERR', 'DELETE FAILED');
    }
  };

  return (
    <main className="grid grid-cols-[1fr_600px_350px] h-screen w-screen bg-white text-black font-sans overflow-hidden fixed inset-0">

      {/* COLUMN 1: VISUALIZER (Left) */}
      <section className="border-r border-white flex flex-col bg-white h-full min-h-0 overflow-hidden">
        <header className="p-4 border-b border-white">
          <h1 className="text-[10px] font-mono tracking-widest text-gray-500">CORE VISUALIZER</h1>
        </header>

        <div className="flex-1 flex items-center justify-center relative p-10">
          <div className="w-full h-full max-w-[600px] max-h-[600px] aspect-square">
            <AtomicCore isThinking={isThinking} phase={phase} />
          </div>
          {/* Status Text Overlay */}
          <div className="absolute bottom-10 left-0 w-full text-center">
            <span className={`text-[10px] font-mono tracking-widest ${isConnected ? 'text-black' : 'text-gray-400'}`}>
              {isConnected ? 'SYSTEM ONLINE' : 'OFFLINE'}
            </span>
          </div>
        </div>
      </section>

      {/* COLUMN 2: INTERACTION (Center) */}
      <section className="flex flex-col relative bg-white h-full min-h-0 overflow-hidden">
        <div className="flex-1 overflow-y-auto p-8 pt-12 custom-scrollbar space-y-8 min-h-0">
          {messages.length === 0 && (
            <div className="h-full flex items-center justify-center">
              <span className="text-gray-300 text-sm font-light tracking-wide">Ready for input...</span>
            </div>
          )}

          {messages.map((msg) => (
            <div key={msg.id} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'} animate-in fade-in duration-500 group`}>
              <div className={`flex items-center gap-2 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>

                {/* Message Bubble */}
                <div className={`max-w-[75%] bg-transparent`}>
                  <p className={`text-sm leading-relaxed whitespace-pre-wrap ${msg.role === 'user' ? 'font-medium text-black text-right' :
                    msg.role === 'proactive' ? 'text-gray-500 italic' :
                      'font-light text-black'
                    }`}>
                    {msg.animate && msg.role !== 'user' ? (
                      <Typewriter text={msg.content} />
                    ) : (
                      msg.content
                    )}
                  </p>
                </div>

                {/* Delete Button (Hover) */}
                <button
                  onClick={() => handleDelete(msg.id)}
                  title="Delete Message & Memory"
                  className="opacity-0 group-hover:opacity-100 bg-gray-100 hover:bg-black hover:text-white text-gray-400 text-[10px] w-5 h-5 flex items-center justify-center rounded-full transition-all"
                >
                  ×
                </button>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="p-8 pb-10 flex gap-4">
          {/* New Chat Button */}
          <button
            onClick={handleNewSession}
            className="px-4 py-3 bg-white hover:bg-black hover:text-white transition-colors border-b border-white font-mono text-xs tracking-widest whitespace-nowrap"
          >
            [NEW]
          </button>

          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Type command..."
            className="flex-1 bg-transparent border-b border-gray-200 py-3 text-lg font-light focus:outline-none focus:border-black transition-colors placeholder-gray-200"
          />
        </div>
      </section>

      {/* COLUMN 3: DATA STREAM (Right) */}
      <section className="border-l border-white flex flex-col bg-white font-mono text-[10px] h-full min-h-0 overflow-hidden">
        {/* Top: Tabs (Sessions / Care) */}
        <div className="h-1/2 flex flex-col border-b border-white">
          <header className="flex border-b border-white">
            <button
              onClick={() => setActiveTab('history')}
              className={`flex-1 p-3 text-center tracking-widest font-bold transition-colors ${activeTab === 'history' ? 'bg-black text-white' : 'text-gray-400 hover:bg-gray-100'}`}
            >
              ARCHIVES
            </button>
            <button
              onClick={() => { setActiveTab('care'); fetchCareList(); }}
              className={`flex-1 p-3 text-center tracking-widest font-bold transition-colors ${activeTab === 'care' ? 'bg-black text-white' : 'text-gray-400 hover:bg-gray-100'}`}
            >
              CARE LIST
            </button>
          </header>

          <div className="flex-1 overflow-y-auto p-4 space-y-2">
            {activeTab === 'history' ? (
              /* Session List */
              sessions.map((session, i) => (
                <div key={i}
                  onClick={() => handleLoadSession(session.id)}
                  className="group flex flex-col gap-1 cursor-pointer p-2 hover:bg-gray-200 transition-colors border text-gray-600 border-transparent hover:border-gray-300"
                >
                  <div className="flex justify-between font-bold text-gray-900">
                    <span>ID: {session.id}</span>
                    <span>{new Date(session.updated_at * 1000).toLocaleDateString()}</span>
                  </div>
                  <div className="line-clamp-2 text-[9px] opacity-70 group-hover:opacity-100">
                    {session.preview || 'No preview available'}
                  </div>
                </div>
              ))
            ) : (
              /* Care List */
              careItems.length === 0 ? (
                <div className="text-gray-400 italic text-center p-4">No pending care items.</div>
              ) : (
                careItems.map((item, i) => {
                  const now = Date.now() / 1000;
                  const delta = item.trigger_time - now;
                  let timeDisplay = "";
                  if (delta < 0) timeDisplay = "READY";
                  else if (delta < 3600) timeDisplay = `in ${Math.ceil(delta / 60)}m`;
                  else timeDisplay = `in ${(delta / 3600).toFixed(1)}h`;

                  return (
                    <div key={i} className="flex flex-col gap-1 p-2 border border-gray-200 bg-gray-50 border-l-4 border-l-black">
                      <div className="flex justify-between items-center font-bold text-black">
                        <span className="uppercase">{item.category}</span>
                        <span className={`text-[9px] px-1 py-0.5 rounded ${delta < 0 ? 'bg-red-500 text-white' : 'bg-gray-200 text-gray-600'}`}>
                          {timeDisplay}
                        </span>
                      </div>
                      <div className="text-gray-600 text-[10px] leading-tight mt-1">
                        {item.content}
                      </div>
                    </div>
                  )
                })
              )
            )}
          </div>
        </div>

        {/* Bottom: Logs */}
        <div className="h-1/2 flex flex-col bg-white">
          <header className="p-4 border-b border-white">
            <h2 className="tracking-widest text-gray-500">NEURAL LOGS</h2>
          </header>
          <div className="flex-1 overflow-y-auto p-4 space-y-1.5 text-gray-500">
            {logs.map((log, i) => {
              let parsedContent = log.content;
              let isThought = log.type === 'THOUGHT';

              // 尝试解析 JSON 思考过程
              if (isThought && typeof parsedContent === 'string') {
                try {
                  parsedContent = JSON.parse(parsedContent);
                } catch (e) { }
              }

              return (
                <div key={i} className={`flex flex-col gap-1 border-b border-gray-50 pb-2 last:border-0 hover:text-black transition-colors cursor-default ${isThought ? 'bg-white p-2 rounded border border-gray-100' : ''}`}>
                  <div className="flex gap-2 items-center">
                    <span className={`shrink-0 w-8 font-bold ${isThought ? 'text-blue-600' : 'text-gray-900'}`}>{log.type}</span>
                    <span className="text-[9px] opacity-50">{log.timestamp}</span>
                  </div>

                  {isThought ? (
                    // Thought (Structured or Raw)
                    typeof parsedContent === 'object' && parsedContent !== null ? (
                      <div className="flex flex-col gap-1 text-[9px] text-gray-600 mt-1 pl-1 border-l-2 border-blue-200">
                        <div><span className="font-bold">OBS:</span> {parsedContent.observation}</div>
                        <div><span className="font-bold">ANA:</span> {parsedContent.analysis}</div>
                        <div><span className="font-bold">DEC:</span> {parsedContent.decision}</div>
                        {parsedContent.schedule && (
                          <div>
                            <span className="font-bold">WAIT:</span>{' '}
                            {(() => {
                              const sec = parseInt(parsedContent.schedule);
                              if (isNaN(sec)) return parsedContent.schedule;
                              if (sec < 60) return `${sec}s`;
                              if (sec < 3600) return `${Math.ceil(sec / 60)}m`;
                              const h = (sec / 3600).toFixed(1);
                              return h.endsWith('.0') ? `${h.slice(0, -2)}h` : `${h}h`;
                            })()}
                          </div>
                        )}
                      </div>
                    ) : (
                      // Fallback for Thought (String content)
                      <div className="text-[9px] text-gray-400 mt-1 pl-1 border-l-2 border-gray-200 italic">
                        {String(parsedContent)}
                      </div>
                    )
                  ) : (
                    // Regular Log
                    <span className={`break-all ${isThought ? '' : 'line-clamp-2'}`}>{String(parsedContent)}</span>
                  )}
                </div>
              );
            })}
            <div ref={logsEndRef} />
          </div>
        </div>
      </section>

    </main>
  );
}
