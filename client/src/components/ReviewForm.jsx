import { useState } from "react";
import { motion } from "motion/react"
import { GitPullRequest, Loader2 } from "lucide-react"

export default function ReviewForm({ onSubmit, loading }) {
  const [prUrl, setPrUrl] = useState("");
  const [token, setToken] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!prUrl.trim()) return;
    onSubmit(prUrl, token);
  };

  return (
    <motion.form
      onSubmit={handleSubmit}
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="w-full max-w-2xl mx-auto bg-neutral-900/60 backdrop-blur border border-neutral-800 rounded-2xl p-6 shadow-xl"
    >
      <div className="flex items-center gap-2 mb-4">
        <GitPullRequest className="text-indigo-400" size={20} />
        <h2 className="text-lg font-semibold text-neutral-100 font-sans">Analyze a Pull Request</h2>
      </div>

      <input type="text"
        placeholder="https://github.com/owner/repo/pull/123"
        value={prUrl}
        onChange={(e) => setPrUrl(e.target.value)}
        className="w-full mb-3 px-4 py-2.5 rounded-lg bg-neutral-800 border border-neutral-700 text-neutral-100 placeholder-neutral-500 focus:ring-2 focus:ring-indigo-500 font-serif"
      />

      <input type="password"
        placeholder="Github token (optional)"
        value={token}
        onChange={(e) => setToken(e.target.value)}
        className="w-full mb-4 px-4 py-2.5 rounded-lg bg-neutral-800 border border-neutral-700 text-neutral-100 placeholder-neutral-500 focus:outline-none focus:ring-indigo-500 font-serif"
       />

       <button type="submit"
        disabled={loading}
        className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-indigo-600 disabled:opacity-60 text-white font-medium transition font-serif"
       >
        {loading ? (
          <>
          <Loader2 className="animate-spin" size={18}/> Analyzing...
          </>
        ) : (
          "Run Review"
        )}
       </button>
    </motion.form>
  )
}