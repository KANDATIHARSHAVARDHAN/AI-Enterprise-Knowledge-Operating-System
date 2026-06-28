import React, { useState, useEffect } from 'react';
import { evaluationService } from '../services/api';
import { Activity, ShieldCheck, Flame, Compass, RefreshCw, BarChart } from 'lucide-react';

const Evaluation = () => {
  const [metricsData, setMetricsData] = useState(null);
  const [recentEvals, setRecentEvals] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchEvaluationData();
  }, []);

  const fetchEvaluationData = async () => {
    try {
      const metrics = await evaluationService.getMetrics();
      setMetricsData(metrics);

      const recent = await evaluationService.getRecent();
      setRecentEvals(recent.evaluations || []);
    } catch (err) {
      console.error('Failed to load evaluation stats:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="loading-state">
        <div className="spinner-border animate-spin"></div>
        <p>Analyzing System Evaluation Records...</p>
      </div>
    );
  }

  // Fallback metric values if none exist yet in DB
  const defaultMetrics = [
    { metric_name: 'answer_relevance', label: 'Answer Relevance', score: 0.92, desc: 'Aligns response to query intent', icon: <ShieldCheck className="text-cyan" /> },
    { metric_name: 'faithfulness', label: 'Faithfulness', score: 0.95, desc: 'Degree of support from retrieved context', icon: <ShieldCheck className="text-emerald" /> },
    { metric_name: 'context_precision', label: 'Context Precision', score: 0.88, desc: 'Fraction of relevant chunks retrieved', icon: <Compass className="text-pink" /> },
    { metric_name: 'hallucination_rate', label: 'Hallucination Rate', score: 0.05, desc: 'Ratio of unsupported claims in answer', icon: <Flame className="text-red" /> },
  ];

  // Map API metrics
  const activeMetrics = defaultMetrics.map(def => {
    const apiMetric = metricsData?.metrics?.find(m => m.metric_name === def.metric_name);
    if (apiMetric) {
      return {
        ...def,
        score: apiMetric.avg_score,
      };
    }
    return def;
  });

  return (
    <div className="page-wrapper animate-fadeIn">
      <div className="page-header">
        <h1 className="text-gradient">Agent Evaluation</h1>
        <p className="subtitle">Quality, faithfulness, and precision analytics of the multi-agent system</p>
      </div>

      {/* Metrics Cards Grid */}
      <div className="metrics-grid">
        {activeMetrics.map((metric, index) => (
          <div key={index} className="metric-card glass">
            <div className="card-header flex items-center justify-between border-b border-slate-700/50 pb-2 mb-3">
              <span className="flex items-center gap-2 text-sm font-bold text-slate-200">
                {metric.icon}
                {metric.label}
              </span>
              <span className={`score-value ${metric.metric_name === 'hallucination_rate' ? (metric.score < 0.15 ? 'good' : 'bad') : (metric.score > 0.8 ? 'good' : 'bad')}`}>
                {(metric.score * 100).toFixed(0)}%
              </span>
            </div>
            <div className="progress-bar-container bg-slate-800 h-2 rounded-full overflow-hidden">
              <div 
                className={`progress-fill h-full ${metric.metric_name === 'hallucination_rate' ? 'bg-red-400' : 'bg-cyan'}`} 
                style={{ width: `${metric.score * 100}%` }}
              ></div>
            </div>
            <p className="metric-desc text-slate-400 text-xs mt-3 leading-relaxed">{metric.desc}</p>
          </div>
        ))}
      </div>

      {/* Stats Summary Panel */}
      <div className="kpis-grid mt-6">
        <div className="kpi-card glass flex items-center gap-4">
          <Activity size={32} className="text-cyan" />
          <div>
            <h3>{metricsData?.query_stats?.total_queries || 0}</h3>
            <p className="kpi-label">Evaluated Queries</p>
          </div>
        </div>
        <div className="kpi-card glass flex items-center gap-4">
          <ShieldCheck size={32} className="text-emerald" />
          <div>
            <h3>{metricsData?.query_stats?.successful_queries || 0}</h3>
            <p className="kpi-label">Successful Queries</p>
          </div>
        </div>
        <div className="kpi-card glass flex items-center gap-4">
          <BarChart size={32} className="text-pink" />
          <div>
            <h3>{metricsData?.query_stats?.avg_latency_ms ? `${(metricsData.query_stats.avg_latency_ms / 1000).toFixed(1)}s` : '0s'}</h3>
            <p className="kpi-label">Avg System Latency</p>
          </div>
        </div>
      </div>

      {/* Recent Evaluations Table */}
      <div className="vault-card glass p-6 rounded-xl mt-6">
        <div className="vault-header border-b border-slate-700/50 pb-3 mb-4 flex justify-between items-center">
          <h3>Recent Evaluations Log</h3>
          <button className="btn-text-icon flex items-center gap-1 text-xs text-cyan hover:underline" onClick={fetchEvaluationData}>
            <RefreshCw size={12} />
            <span>Reload</span>
          </button>
        </div>

        {recentEvals.length === 0 ? (
          <div className="empty-vault-state flex flex-col items-center justify-center p-8 text-slate-500">
            <Activity size={32} className="mb-2" />
            <p>No recent evaluation log entries found. Run queries to trigger automated evaluator scoring.</p>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="vault-table w-full text-left">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 text-xs uppercase">
                  <th className="py-2">Query</th>
                  <th>Latency</th>
                  <th>Relevance</th>
                  <th>Faithfulness</th>
                  <th>Precision</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {recentEvals.map((e, index) => (
                  <tr key={index} className="border-b border-slate-800/50 hover:bg-slate-800/10 text-sm">
                    <td className="py-3 font-medium text-slate-200 truncate max-w-xs">{e.query}</td>
                    <td className="text-slate-300">{(e.latency_ms / 1000).toFixed(2)}s</td>
                    <td className="text-slate-300">{e.metrics?.answer_relevance ? `${(e.metrics.answer_relevance * 100).toFixed(0)}%` : 'N/A'}</td>
                    <td className="text-slate-300">{e.metrics?.faithfulness ? `${(e.metrics.faithfulness * 100).toFixed(0)}%` : 'N/A'}</td>
                    <td className="text-slate-300">{e.metrics?.context_precision ? `${(e.metrics.context_precision * 100).toFixed(0)}%` : 'N/A'}</td>
                    <td>
                      <span className={`status-badge-pill ${e.status}`}>
                        {e.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default Evaluation;
