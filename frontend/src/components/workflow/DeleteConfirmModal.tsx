"use client";

import { Loader2, AlertTriangle, X } from "lucide-react";

export interface DeleteConfirmModalProps {
  workflowName: string;
  deleting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function DeleteConfirmModal({
  workflowName,
  deleting,
  onConfirm,
  onCancel,
}: DeleteConfirmModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-sm mx-4 shadow-2xl">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex items-center justify-center w-10 h-10 rounded-full bg-red-900/40 text-red-400">
            <AlertTriangle size={20} />
          </div>
          <div>
            <h3 className="text-white font-semibold text-sm">
              Delete Workflow
            </h3>
            <p className="text-gray-400 text-xs mt-0.5">
              This action cannot be undone.
            </p>
          </div>
          <button
            onClick={onCancel}
            disabled={deleting}
            className="ml-auto text-gray-500 hover:text-gray-300 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        <p className="text-gray-300 text-sm mb-6">
          Are you sure you want to delete{" "}
          <span className="text-white font-medium">{workflowName}</span>?
          All associated runs will also be removed.
        </p>

        <div className="flex gap-2 justify-end">
          <button
            onClick={onCancel}
            disabled={deleting}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-gray-300 text-sm rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={deleting}
            className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white text-sm rounded-lg transition-colors"
          >
            {deleting && <Loader2 size={14} className="animate-spin" />}
            {deleting ? "Deleting…" : "Delete"}
          </button>
        </div>
      </div>
    </div>
  );
}
