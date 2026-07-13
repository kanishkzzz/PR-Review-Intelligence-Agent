import { useState } from "react";
import ReviewForm from "./components/ReviewForm";
import ResultsDashboard from "./components/ResultsDashboard";
import { Bot } from "lucide-react";

export default function App() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleSubmit = async (prUrl, token) => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pr_url: prUrl, token: token })
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Request failed: ${response.status}`);
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 px-4 py-12">
      <div className="flex items-center justify-center gap-2 mb-8">
        <Bot className="text-indigo-400" size={26} />
        <h1 className="text-2xl font-bold ">BugBeGone</h1>
      </div>

      <ReviewForm onSubmit={handleSubmit} loading={loading} />

      {loading && (
        <p className="text-center text-indigo-400 text-sm mt-4 max-w-2xl mx-auto animate-pulse">
          Analyzing PR — running security, logic, and test coverage agents...
        </p>
      )}

      {error && (
        <p className="text-center text-red-400 text-sm mt-4 max-w-2xl mx-auto">
          {error}
        </p>
      )}

      <ResultsDashboard data={result} />
    </div>
  );
}