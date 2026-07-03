import { useState } from "react";
import ReviewForm from "./components/ReviewForm";
import ResultsDashboard from "./components/ResultsDashboard";
import { Bot } from "lucide-react";
import { reviewPR } from "./api/client";

export default function App() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleSubmit = async (prUrl, token) => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await reviewPR(prUrl, token);
      setResult(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 px-4 py-12">
      <div className="flex items-center justify-center gap-2 mb-8">
        <Bot className="text-indigo-400" size={26} />
        <h1 className="text-2xl font-bold">PR Review Intelligence Agent</h1>
      </div>

      <ReviewForm onSubmit={handleSubmit} loading={loading} />

      {error && (
        <p className="text-center text-red-400 text-sm mt-4 max-w-2xl mx-auto">{error}</p>
      )}

      <ResultsDashboard data={result} />
    </div>
  );
}