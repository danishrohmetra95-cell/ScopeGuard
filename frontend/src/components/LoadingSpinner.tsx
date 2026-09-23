export function LoadingSpinner({ message = 'Analyzing...' }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16">
      <div className="sg-spinner w-8 h-8 mb-4" />
      <p className="text-sm text-[#8b8d98]">{message}</p>
    </div>
  );
}
