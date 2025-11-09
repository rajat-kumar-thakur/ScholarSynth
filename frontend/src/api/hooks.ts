/**
 * React Query hooks for API interactions.
 */
import { useQuery, useMutation, useQueryClient } from 'react-query';
import { scholarApi, TaskState, StatusResponse } from './client';

/**
 * Hook to create a new research report.
 */
export const useCreateReport = () => {
  const queryClient = useQueryClient();
  
  return useMutation(
    (query: string) => scholarApi.createReport(query),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('reports');
      },
    }
  );
};

/**
 * Hook to fetch report status with polling.
 */
export const useReportStatus = (taskId: string | null, enabled = true) => {
  return useQuery<StatusResponse>(
    ['reportStatus', taskId],
    () => scholarApi.getStatus(taskId!),
    {
      enabled: enabled && !!taskId,
      refetchInterval: (data) => {
        // Poll every 1 second if not done
        if (!data || (data.status !== 'done' && data.status !== 'failed')) {
          return 1000;
        }
        return false;
      },
    }
  );
};

/**
 * Hook to fetch the complete report.
 */
export const useReport = (taskId: string | null, enabled = true) => {
  return useQuery<TaskState>(
    ['report', taskId],
    () => scholarApi.getReport(taskId!),
    {
      enabled: enabled && !!taskId,
      refetchInterval: (data) => {
        // Poll every 1 second if not done
        if (!data || (data.status !== 'done' && data.status !== 'failed')) {
          return 1000;
        }
        return false;
      },
      refetchOnWindowFocus: false,
    }
  );
};

/**
 * Hook to delete a report.
 */
export const useDeleteReport = () => {
  const queryClient = useQueryClient();
  
  return useMutation(
    (taskId: string) => scholarApi.deleteReport(taskId),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('reports');
      },
    }
  );
};
