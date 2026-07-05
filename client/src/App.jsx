import { useState } from "react";
import ReviewForm from "./components/ReviewForm";
import ResultsDashboard from "./components/ResultsDashboard";
import { Bot } from "lucide-react";

export default function App() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [status, setStatus] = useState("");  // ← new

  const handleSubmit = async (prUrl, token) => {
    setLoading(true);
    setError(null);
    setResult(null);
    setStatus("");

    try {
      const response = await fetch("http://localhost:8000/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pr_url: prUrl, token: token })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.status === "complete") {
                setResult(data.result);
                setLoading(false);
                setStatus("");
              } else if (data.status === "error") {
                setError(data.message);
                setLoading(false);
              } else {
                setStatus(data.message);  // live status update
              }
            } catch {
              // incomplete chunk — ignore
            }
          }
        }
      }
    } catch (err) {
      setError("Something went wrong.", err);
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 px-4 py-12">
      <div className="flex items-center justify-center gap-2 mb-8">
        <Bot className="text-indigo-400" size={26} />
        <h1 className="text-2xl font-bold">BugBeGone</h1>
      </div>

      <ReviewForm onSubmit={handleSubmit} loading={loading} />

      {/* Live status — streaming messages */}
      {loading && status && (
        <p className="text-center text-indigo-400 text-sm mt-4 max-w-2xl mx-auto animate-pulse">
          {status}
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