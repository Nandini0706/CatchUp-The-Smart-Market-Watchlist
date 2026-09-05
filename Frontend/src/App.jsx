import { SignedIn, SignedOut, SignIn, UserButton, useAuth } from "@clerk/clerk-react";
import { useState, useEffect } from 'react';
import axios from 'axios';
import {
  TrendingUp, TrendingDown, Sparkles, Activity,
  Trash2, RefreshCw, Plus, BarChart2, Moon, Sun
} from 'lucide-react';

const API_BASE = 'http://localhost:8000/api';

function App() {
  const { getToken } = useAuth();
  const [feed, setFeed] = useState({ meaningful_changes: [], noise: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [newTicker, setNewTicker] = useState("");
  const [adding, setAdding] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [deletingTicker, setDeletingTicker] = useState(null);

  // --- NEW: Theme State ---
  // Default to true (dark mode) for the cool fintech vibe
  const [isDark, setIsDark] = useState(true);

  // Sync the theme state to the HTML document root
  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDark]);

  const fetchFeed = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();

      const response = await axios.get(`${API_BASE}/catchup`, {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
      setFeed(response.data);
    } catch (err) {
      setError("Failed to load market data. Is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFeed();
  }, []);

  const handleAddTicker = async (e) => {
    e.preventDefault();
    if (!newTicker.trim()) return;
    setAdding(true);
    setError(null);
    try {
      const token = await getToken();

      await axios.post(
        `${API_BASE}/watchlist`,
        { ticker: newTicker },
        {
          headers: {
            Authorization: `Bearer ${token}`
          }
        }
      );

      setNewTicker("");
      await fetchFeed();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to add ticker.");
    } finally {
      setAdding(false);
    }
  };

  const handleAcknowledge = async () => {
    setSyncing(true);
    try {
      const token = await getToken();
      await axios.post(`${API_BASE}/acknowledge`, {}, {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
      await fetchFeed();
    } catch (err) {
      alert("Failed to sync.");
    } finally {
      setSyncing(false);
    }
  };

  const handleDeleteTicker = async (ticker) => {
    if (!window.confirm(`Are you sure you want to remove ${ticker}?`)) return;
    setDeletingTicker(ticker);
    try {
      const token = await getToken();
      await axios.delete(`${API_BASE}/watchlist/${ticker}`, {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
      await fetchFeed();
    } catch (err) {
      alert("Failed to delete ticker.");
    } finally {
      setDeletingTicker(null);
    }
  };

  const formatPrice = (price) => price ? `$${price.toFixed(2)}` : 'N/A';

  return (
    <div className="min-h-screen transition-colors duration-300 bg-[#F8FAFC] dark:bg-slate-950 text-slate-800 dark:text-slate-200 font-sans selection:bg-indigo-100 dark:selection:bg-cyan-900 selection:text-indigo-900 dark:selection:text-cyan-100">
      {/* If logged out, show the beautiful Clerk Login box centered on the screen */}
      <SignedOut>
        <div className="flex items-center justify-center min-h-screen">
          <SignIn />
        </div>
      </SignedOut>

      {/* If logged in, show our Dashboard */}
      <SignedIn>

        {/* Top Navigation Bar */}
        <nav className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-6 md:px-12 py-4 flex items-center justify-between sticky top-0 z-10 shadow-sm dark:shadow-lg dark:shadow-black/20 transition-colors duration-300">
          <div className="flex items-center gap-3">
            <div className="bg-indigo-600 dark:bg-cyan-500/10 p-2 rounded-lg dark:border dark:border-cyan-500/20 transition-colors">
              <BarChart2 className="text-white dark:text-cyan-400 w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-white tracking-tight">Smart Watchlist</h1>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* THEME TOGGLE BUTTON */}
            <button
              onClick={() => setIsDark(!isDark)}
              className="p-2 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 transition-colors"
              title="Toggle Theme"
            >
              {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>

            <button
              onClick={handleAcknowledge}
              disabled={syncing || loading}
              className="bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 px-4 py-2 rounded-lg text-sm font-medium transition disabled:opacity-50 shadow-sm flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin text-indigo-600 dark:text-cyan-400' : 'text-slate-500 dark:text-slate-400'}`} />
              <span className="hidden sm:inline">{syncing ? 'Syncing...' : 'Mark as Read'}</span>
            </button>

            <UserButton />
          </div>
        </nav>



        <div className="max-w-5xl mx-auto p-6 md:p-12">

          {/* Header & Add Action */}
          <header className="mb-10 flex flex-col md:flex-row justify-between items-start md:items-end gap-6">
            <div>
              <h2 className="text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">Your Catch-Up Feed</h2>
              <p className="text-slate-500 dark:text-slate-400 mt-2 text-lg">Filtered signal, minus the market noise.</p>
            </div>

            <form onSubmit={handleAddTicker} className="flex gap-0 w-full md:w-auto shadow-sm">
              <input
                type="text"
                value={newTicker}
                onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
                placeholder="e.g. AAPL"
                className="bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-l-lg px-4 py-3 w-full md:w-40 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:focus:ring-cyan-500 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 uppercase transition-colors"
                maxLength={5}
              />
              <button
                type="submit"
                disabled={adding}
                className="bg-indigo-600 dark:bg-cyan-600 hover:bg-indigo-700 dark:hover:bg-cyan-500 text-white px-5 py-3 rounded-r-lg font-medium transition disabled:opacity-50 flex items-center gap-2"
              >
                {adding ? <RefreshCw className="w-5 h-5 animate-spin" /> : <Plus className="w-5 h-5" />}
                <span className="hidden md:inline">{adding ? 'Adding' : 'Add'}</span>
              </button>
            </form>
          </header>

          {/* UI SKELETON LOADER */}
          {loading ? (
            <div className="space-y-6 animate-pulse">
              <div className="h-8 bg-slate-200 dark:bg-slate-800 rounded w-48 mb-6"></div>
              {[1, 2].map(i => (
                <div key={i} className="bg-white dark:bg-slate-900 rounded-2xl h-40 border border-slate-200 dark:border-slate-800"></div>
              ))}
            </div>
          ) : (
            <div className="space-y-12">

              {/* The Signal: Meaningful Changes */}
              <section>
                <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-6 flex items-center gap-2">
                  <Activity className="w-6 h-6 text-indigo-600 dark:text-cyan-400" />
                  Meaningful Changes
                  <span className="text-sm font-medium text-indigo-700 dark:text-cyan-300 bg-indigo-100 dark:bg-cyan-900/40 px-2.5 py-0.5 rounded-full ml-2 dark:border dark:border-cyan-800">
                    {feed.meaningful_changes.length}
                  </span>
                </h3>

                {feed.meaningful_changes.length === 0 ? (
                  <div className="bg-white dark:bg-slate-900/50 p-12 rounded-2xl border border-dashed border-slate-300 dark:border-slate-700 text-center shadow-sm">
                    <Activity className="w-10 h-10 mx-auto text-slate-300 dark:text-slate-600 mb-3" />
                    <p className="font-medium text-lg text-slate-500 dark:text-slate-300">You're all caught up!</p>
                  </div>
                ) : (
                  <div className="grid gap-6">
                    {feed.meaningful_changes.map((item) => (
                      <div key={item.ticker} className="group relative bg-white dark:bg-slate-900 rounded-2xl shadow-sm dark:shadow-lg border border-slate-200 dark:border-slate-800 p-6 flex flex-col md:flex-row gap-6 items-start md:items-center transition duration-300 hover:shadow-md hover:border-indigo-200 dark:hover:border-slate-600 overflow-hidden">

                        {/* Edge accent (Solid in light, Neon glow in dark) */}
                        <div className={`absolute top-0 left-0 w-1 h-full ${item.percent_change >= 0 ? 'bg-emerald-400 dark:bg-emerald-500 dark:shadow-[0_0_10px_rgba(16,185,129,0.8)]' : 'bg-rose-400 dark:bg-rose-500 dark:shadow-[0_0_10px_rgba(244,63,94,0.8)]'}`}></div>

                        <button
                          onClick={() => handleDeleteTicker(item.ticker)}
                          disabled={deletingTicker === item.ticker}
                          className="absolute top-4 right-4 text-slate-300 dark:text-slate-500 hover:text-rose-500 dark:hover:text-rose-400 transition p-2 rounded-full hover:bg-rose-50 dark:hover:bg-slate-800"
                        >
                          {deletingTicker === item.ticker ? <RefreshCw className="w-4 h-4 animate-spin text-rose-500" /> : <Trash2 className="w-4 h-4" />}
                        </button>

                        {/* Price Data */}
                        <div className="flex-shrink-0 min-w-[140px] pl-4 md:pl-2">
                          <h4 className="text-3xl font-black text-slate-900 dark:text-white tracking-tight">{item.ticker}</h4>
                          <div className="flex items-center gap-2 mt-1">
                            <p className="text-slate-900 dark:text-slate-200 font-bold text-xl">{formatPrice(item.current_price)}</p>
                          </div>
                          <p className="text-slate-400 dark:text-slate-500 text-xs mt-1">Was {formatPrice(item.last_seen_price)}</p>

                          <div className={`inline-flex items-center gap-1 px-2.5 py-1 mt-3 rounded-md text-sm font-bold ${item.percent_change >= 0 ? 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/20' : 'bg-rose-50 dark:bg-rose-500/10 text-rose-700 dark:text-rose-400 border border-rose-200 dark:border-rose-500/20'}`}>
                            {item.percent_change >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                            {Math.abs(item.percent_change)}%
                          </div>
                        </div>

                        {/* AI Context Box */}
                        <div className="flex-grow w-full bg-gradient-to-br from-indigo-50/50 to-purple-50/50 dark:from-indigo-900/30 dark:via-purple-900/10 rounded-xl p-5 border border-indigo-100 dark:border-indigo-500/20 relative transition-colors">
                          <div className="flex items-center gap-2 mb-2">
                            <Sparkles className="w-4 h-4 text-indigo-500 dark:text-indigo-400" />
                            <p className="text-xs font-bold text-indigo-700 dark:text-indigo-300 uppercase tracking-widest">AI Insight</p>
                          </div>
                          <p className="text-slate-700 dark:text-slate-300 leading-relaxed text-[15px] font-medium">
                            {item.ai_context || "Analyzing market sentiment..."}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* The Noise: Minor Movements */}
              <section>
                <h3 className="text-lg font-bold text-slate-400 dark:text-slate-500 mb-4 flex items-center gap-2">
                  No Major Action
                  <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 bg-slate-200 dark:bg-slate-800 px-2 py-0.5 rounded-full dark:border dark:border-slate-700">
                    {feed.noise.length}
                  </span>
                </h3>

                {feed.noise.length > 0 && (
                  <div className="bg-white dark:bg-slate-900/50 rounded-2xl p-5 flex flex-wrap gap-3 border border-slate-200 dark:border-slate-800 shadow-sm transition-colors">
                    {feed.noise.map((item) => (
                      <div key={item.ticker} className="bg-slate-50 dark:bg-slate-800/80 px-4 py-2 rounded-lg text-sm border border-slate-200 dark:border-slate-700 flex items-center gap-3 group/pill hover:bg-slate-100 dark:hover:bg-slate-700 transition cursor-default">
                        <span className="font-bold text-slate-700 dark:text-slate-300">{item.ticker}</span>
                        <span className="text-slate-400 dark:text-slate-500">{formatPrice(item.current_price)}</span>
                        <span className={`font-semibold ${item.percent_change >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-500 dark:text-rose-400'}`}>
                          {item.percent_change > 0 ? '+' : ''}{item.percent_change}%
                        </span>

                        <button
                          onClick={() => handleDeleteTicker(item.ticker)}
                          className="ml-1 text-slate-300 dark:text-slate-600 hover:text-rose-500 dark:hover:text-rose-400 opacity-0 group-hover/pill:opacity-100 transition"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </section>

            </div>
          )}
        </div>
      </SignedIn>
    </div>
  );
}

export default App;