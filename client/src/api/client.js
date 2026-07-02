import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:3000/api",
  headers: { "Content-Type": "application/json" }
});

export const reviewPR = async (prUrl, token) => {
  const res = await api.post("/review", { pr_url: prUrl, token });
  return res.data;
}