interface StatusBadgeProps {
  status: string;
}

const statusConfig: Record<string, { color: string; label: string }> = {
  uploaded: { color: 'badge-info', label: 'Uploaded' },
  queued: { color: 'badge-neutral', label: 'Queued' },
  normalizing: { color: 'badge-info', label: 'Normalizing' },
  normalized: { color: 'badge-info', label: 'Normalized' },
  ocr_processing: { color: 'badge-warning', label: 'OCR Processing' },
  ocr_complete: { color: 'badge-info', label: 'OCR Complete' },
  ocr_failed: { color: 'badge-error', label: 'OCR Failed' },
  skipped: { color: 'badge-neutral', label: "Can't Process Photos" },
  classifying: { color: 'badge-warning', label: 'Classifying' },
  classified: { color: 'badge-info', label: 'Classified' },
  classification_failed: { color: 'badge-error', label: 'Classification Failed' },
  validating: { color: 'badge-warning', label: 'Validating' },
  validated: { color: 'badge-info', label: 'Validated' },
  validation_failed: { color: 'badge-error', label: 'Validation Failed' },
  completed: { color: 'badge-success', label: 'Completed' },
  partial: { color: 'badge-warning', label: 'Partial' },
  awaiting_required_documents: { color: 'badge-warning', label: 'Awaiting Documents' },
  failed: { color: 'badge-error', label: 'Failed' },
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  const config = statusConfig[status] || { color: 'badge-neutral', label: status };
  return <span className={config.color}>{config.label}</span>;
}
