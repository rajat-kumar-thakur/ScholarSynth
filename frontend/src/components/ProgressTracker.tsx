/**
 * Progress tracker component for research workflow.
 */
import React from 'react';
import { StatusResponse, SubQuestion } from '../api/client';
import { CheckCircle2, Circle, Loader2, AlertCircle } from 'lucide-react';

interface ProgressTrackerProps {
  status?: StatusResponse;
  subQuestions?: SubQuestion[];
}

export const ProgressTracker: React.FC<ProgressTrackerProps> = ({ status, subQuestions }) => {
  if (!status) return null;

  const getStatusIcon = (questionStatus: string) => {
    switch (questionStatus) {
      case 'completed':
        return <CheckCircle2 className="w-5 h-5 text-green-500" />;
      case 'processing':
        return <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />;
      case 'failed':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      default:
        return <Circle className="w-5 h-5 text-gray-300" />;
    }
  };

  const getStageColor = (stage: string) => {
    switch (stage) {
      case 'planning':
        return 'bg-blue-500';
      case 'executing':
        return 'bg-purple-500';
      case 'publishing':
        return 'bg-green-500';
      case 'done':
        return 'bg-emerald-500';
      case 'failed':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };

  return (
    <div className="space-y-6">
      {/* Progress Bar */}
      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <h3 className="text-lg font-semibold text-gray-900">Research Progress</h3>
          <span className="text-sm font-medium text-gray-600">
            {status.progress_percentage}%
          </span>
        </div>
        
        <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
          <div
            className={`h-full transition-all duration-500 ease-out ${getStageColor(status.status)}`}
            style={{ width: `${status.progress_percentage}%` }}
          />
        </div>
        
        <p className="text-sm text-gray-600">{status.current_step}</p>
      </div>

      {/* Stage Indicators */}
      <div className="flex items-center justify-between">
        {['planning', 'executing', 'publishing', 'done'].map((stage, index) => (
          <div key={stage} className="flex items-center">
            <div className="flex flex-col items-center">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center ${
                  status.status === stage || 
                  (stage === 'done' && status.status === 'done')
                    ? getStageColor(stage)
                    : 'bg-gray-200'
                }`}
              >
                {status.status === stage && status.status !== 'done' ? (
                  <Loader2 className="w-5 h-5 text-white animate-spin" />
                ) : (
                  <span className="text-white font-semibold">{index + 1}</span>
                )}
              </div>
              <span className="text-xs mt-2 capitalize">{stage}</span>
            </div>
            {index < 3 && (
              <div className="w-12 h-1 bg-gray-200 mx-2" />
            )}
          </div>
        ))}
      </div>

      {/* Sub-questions List */}
      {subQuestions && subQuestions.length > 0 && (
        <div className="space-y-3">
          <h4 className="font-semibold text-gray-900">Research Questions</h4>
          <div className="space-y-2">
            {subQuestions.map((q, index) => (
              <div
                key={index}
                className="flex items-start gap-3 p-3 rounded-lg bg-gray-50 border border-gray-200"
              >
                <div className="mt-0.5">{getStatusIcon(q.status)}</div>
                <div className="flex-1">
                  <p className="text-sm text-gray-800">{q.question}</p>
                  {q.status === 'completed' && q.sources.length > 0 && (
                    <p className="text-xs text-gray-500 mt-1">
                      {q.sources.length} sources found
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
