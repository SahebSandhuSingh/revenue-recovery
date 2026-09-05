import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

export const getRecoverySummary = async () => {
  const res = await api.get("/metrics/recovery-summary");
  return res.data;
};

export const getCaseDetail = async (eventId) => {
  const res = await api.get(`/events/${eventId}/case`);
  return res.data;
};

export const getCases = async (params = {}) => {
  const res = await api.get("/cases", { params });
  return res.data;
};

export const getComplianceRecords = async (escalationFlag = true) => {
  const res = await api.get(`/compliance`, {
    params: { escalation_flag: escalationFlag },
  });
  return res.data;
};

export const markPromiseKept = async (promiseId) => {
  const res = await api.post(`/promises/${promiseId}/mark-kept`);
  return res.data;
};

export const simulateCase = async (payload) => {
  const res = await api.post("/cases/simulate", payload);
  return res.data;
};

export default api;

