import { AlertCircle, Loader2 } from "lucide-react";

export function LoadingState({ label = "Cargando datos…" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-24 text-gray-500 dark:text-gray-400">
      <Loader2 className="animate-spin" size={28} aria-hidden />
      <p className="text-sm">{label}</p>
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-red-200 bg-red-50 py-16 px-6 text-center dark:border-red-900 dark:bg-red-950/40">
      <AlertCircle className="text-red-600 dark:text-red-400" size={28} aria-hidden />
      <p className="max-w-md text-sm text-red-800 dark:text-red-300">{message}</p>
    </div>
  );
}
