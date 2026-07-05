import axios from "axios";

const api = axios.create({
  baseURL: "https://pr-review-intelligence-agent.onrender.com",
  headers: { "Content-Type": "application/json" },
});

export const reviewPR = async (prUrl, token) => {
  const res = await api.post("/review", { pr_url: prUrl, token });
  return res.data;
};