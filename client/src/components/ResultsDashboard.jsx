import { motion } from "motion/react";
import { ShieldAlert, Lightbulb, TestTube2, AlertTriangle } from "lucide-react";

const riskColors = {
  HIGH: "bg-red-500/15 text-red-400 border-red-500/30",
  MEDIUM: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  LOW: "bg-green-500/15 text-gree-400 border-green-500/30"
};

const severityColors = {
  HIGH: "text-rd-400",
  MEDIUM: "text-yellow-400",
  LOW: "text-blue-400"
}

export default function ResultsDashboard ({ data }) {
  if(!data) return null;

  const {risk_level, summary, issues = [], test_cases_missing = [], suggestions = []} = data;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20}}
      animate={{ opacity: 1, y: 0}}
      transition={{ duration: 0.4 }}
      className="w-full max-w-3xl mx-auto mt-8 space-y-5"
    >
      {/* Risk + Summary */}
      <div className="bg-neutral-900/60 backdrop-blur border border-neutral-800 rounded-2xl p-6">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-neutral-100 font-semibold text-lg font-sans">Review Summary</h3>
          <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${riskColors[risk_level] || riskColors.LOW}`}>
            {risk_level || "UNKNOWN"} RISK
          </span>
        </div>
        <p className="text-neutral-400 text-sm leading-relaxed">{summary}</p>
      </div>

      {/* Issues */}
      <Section icon={<ShieldAlert size={18} className="text-red-400" />} title={`Issues Found (${issues.length})`}>
        {issues.length === 0 ? (
          <EmptyState text="No major issues found!" />
        ) : (
          issues.map((issue, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="border border-neutral-800 rounded-lg p-3 bg-neutral-950/40"
            >
              <div className="flex items-center gap-2 mb-1">
                <AlertTriangle size={14} className={severityColors[issue.severity] || "text-neutral-400"} />
                <span className="font-medium text-neutral-200 text-sm">{issue.type}</span>
                <span className="text-xs text-neutral-500">· {issue.file}</span>
              </div>
              <p className="text-neutral-400 text-sm">{issue.description}</p>
            </motion.div>
          ))
        )}
      </Section>

      {/* Suggestions */}
      <Section icon={<Lightbulb size={18} className="text-yellow-400"/>} title="Suggestions">
        {suggestions.length === 0 ? (
          <EmptyState text="No suggestions."/>
        ) : (
          <ul className="list-disc list-inside space-y-1 text-neutral-400 text-sm">
            {suggestions.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        )}
      </Section>

      {/* Mising Tests */}
      <Section icon={<TestTube2 size={18} className="text-indigo-400"/>} title="Missing Test Cases">
        {test_cases_missing.length === 0 ? (
          <EmptyState text="Test coverage looks good." />
        ) : (
          <ul className="list-disc list-inside space-y-1 text-neutral-400 text-sm">
            {test_cases_missing.map((t,i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        )}

      </Section>

    </motion.div>
  );
}

function Section({icon, title, children }) {
  return (
    <div className="bg-neutral-900/60 backdrop-blur border border-neutral-800 rounded-2xl p-6">
      <div className="flex items-center gap-2 mb-3 ">
        {icon}
        <h3 className="text-neutral-100 font-semibold">{title}</h3>
      </div>
      <div className="space-y-2">{children}</div>
    </div>
  )
}

function EmptyState({ text }) {
  return <p className="text-neutral-500 text-sm italic">{text}</p>
}