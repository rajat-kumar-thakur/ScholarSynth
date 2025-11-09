/**
 * API client for ScholarSynth backend.
 */
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL;

export interface Citation {
  id: string;
  title: string;
  url: string;
  authors?: string;
  date?: string;
  snippet: string;
}

export interface SubQuestion {
  question: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  summary?: string;
  sources: Citation[];
}

export interface Report {
  title: string;
  content: string;
  word_count: number;
  citations: Citation[];
  generated_at: string;
}

export interface TaskState {
  task_id: string;
  query: string;
  status: 'planning' | 'executing' | 'publishing' | 'done' | 'failed';
  sub_questions: SubQuestion[];
  report?: Report;
  error?: string;
  created_at: string;
  updated_at: string;
  current_step: string;
  progress_percentage: number;
}

export interface StatusResponse {
  task_id: string;
  status: string;
  current_step: string;
  progress_percentage: number;
  sub_questions_count: number;
  completed_questions: number;
}

export interface CreateReportRequest {
  query: string;
}

export interface CreateReportResponse {
  task_id: string;
  status: string;
  message: string;
}

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const scholarApi = {
  /**
   * Create a new research report task.
   */
  createReport: async (query: string): Promise<CreateReportResponse> => {
    const response = await api.post<CreateReportResponse>('/api/report', { query });
    return response.data;
  },

  /**
   * Get status of a research task.
   */
  getStatus: async (taskId: string): Promise<StatusResponse> => {
    const response = await api.get<StatusResponse>(`/api/report/${taskId}/status`);
    return response.data;
  },

  /**
   * Get the complete task state including the final report.
   */
  getReport: async (taskId: string): Promise<TaskState> => {
    const response = await api.get<TaskState>(`/api/report/${taskId}`);
    return response.data;
  },

  /**
   * Create an EventSource for streaming progress updates.
   */
  streamProgress: (taskId: string): EventSource => {
    return new EventSource(`${API_BASE_URL}/api/report/${taskId}/stream`);
  },

  /**
   * Delete a report task.
   */
  deleteReport: async (taskId: string): Promise<void> => {
    await api.delete(`/api/report/${taskId}`);
  },
};
