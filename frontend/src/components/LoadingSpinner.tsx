interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  message?: string;
}

export default function LoadingSpinner({ size = 'md', message }: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-8 h-8',
    lg: 'w-12 h-12',
  };

  return (
    <div className="flex flex-col items-center justify-center py-16">
      <div
        className={`${sizeClasses[size]} border-4 border-gray-100 border-t-primary-600 rounded-full animate-spin`}
      />
      {message && <p className="mt-4 text-sm text-gray-500 font-medium">{message}</p>}
    </div>
  );
}
