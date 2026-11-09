import { AlertTriangle, Zap } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';

interface StartupScreenProps {
  error: string | null;
  onRetry: () => void;
}

export function StartupScreen({ error, onRetry }: StartupScreenProps) {
  return (
    <main className="flex h-full items-center justify-center p-8">
      <div className="w-full max-w-md rounded-xl border border-border bg-surface p-8 text-center shadow-sm">
        <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-lg bg-accent-soft text-accent">
          {error ? <AlertTriangle aria-hidden className="size-6" /> : <Zap aria-hidden className="size-6" />}
        </div>
        {error ? (
          <>
            <h1 className="text-lg font-semibold">PowerShift could not start its local engine</h1>
            <p className="mt-2 text-sm text-muted" role="alert">
              {error}
            </p>
            <p className="mt-2 text-xs text-muted">Details are in the backend log file in the app data folder.</p>
            <Button className="mt-6" onClick={onRetry}>
              Try again
            </Button>
          </>
        ) : (
          <>
            <h1 className="text-lg font-semibold">Starting PowerShift</h1>
            <p className="mt-2 text-sm text-muted">Preparing the local calculation engine and database…</p>
            <Spinner className="mx-auto mt-6" label="Starting" />
          </>
        )}
      </div>
    </main>
  );
}
