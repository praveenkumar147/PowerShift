/**
 * In-memory stand-in for the Python backend, installed as `fetch` in tests.
 * It understands just enough of the API for UI tests; the real rules are
 * tested in backend/tests.
 */
import { vi } from 'vitest';
import type { HealthResponse } from '@/api/health';
import type { Appliance, ApplianceInput } from '@/features/appliances/types';
import type { BillEstimate, EnergyReport, HourlyProfile, MonthlyProjection } from '@/features/energy/types';
import type { Household } from '@/features/household/api';
import type { PeakLoadAnalysis } from '@/features/peak-load/types';
import type { OptimizationRequest, OptimizationRun } from '@/features/scheduler/types';
import type { Tariff, TariffInput } from '@/features/tariffs/types';

export const HEALTH: HealthResponse = {
  status: 'ok',
  version: '0.1.0',
  schema_revision: '0002',
  database_path: 'C:\\data\\powershift.db',
};

export const ZERO_ESTIMATES: Appliance['estimates'] = {
  max_power_kw: 0,
  average_power_kw: 0,
  on_hours_per_day: 0,
  energy_per_operating_day_kwh: 0,
  energy_per_week_kwh: 0,
};

interface Override {
  method: string;
  path: string;
  status: number;
  body: unknown;
}

/** Canned energy responses; the real calculations are tested in the backend. */
export interface EnergyFixtures {
  report?: EnergyReport;
  hourly?: HourlyProfile;
  monthly?: MonthlyProjection;
  bill?: BillEstimate;
  /** A fixed analysis, or one computed from the requested weekday (null = not given). */
  peak?: PeakLoadAnalysis | ((weekday: number | null) => PeakLoadAnalysis);
}

export interface FakeBackend {
  household: Household | null;
  appliances: Appliance[];
  tariffs: Tariff[];
  energy: EnergyFixtures;
  /** Stored optimization runs, oldest first. */
  runs: OptimizationRun[];
  /** Builds the result of the next POST /api/optimization/run (id is assigned by the fake). */
  solve?: (request: OptimizationRequest) => OptimizationRun;
  requests: Array<{ method: string; path: string; body: unknown }>;
  /** Make the next matching request fail (or return a custom body). */
  respondOnce: (method: string, path: string, status: number, body: unknown) => void;
}

function json(body: unknown, status = 200): Response {
  if (status === 204) return new Response(null, { status });
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

const notFound = () => json({ error: { code: 'not_found', message: 'Not Found', fields: {} } }, 404);

type Initial = Partial<Pick<FakeBackend, 'household' | 'appliances' | 'tariffs' | 'energy' | 'runs' | 'solve'>>;

export function installFakeBackend(initial: Initial = {}): FakeBackend {
  const overrides: Override[] = [];
  let nextId = 100;
  const backend: FakeBackend = {
    household: initial.household ?? null,
    appliances: initial.appliances ?? [],
    tariffs: initial.tariffs ?? [],
    energy: initial.energy ?? {},
    runs: initial.runs ?? [],
    ...(initial.solve ? { solve: initial.solve } : {}),
    requests: [],
    respondOnce: (method, path, status, body) => overrides.push({ method, path, status, body }),
  };

  function handle(method: string, url: URL, body: unknown): Response {
    const path = url.pathname;
    const overrideIndex = overrides.findIndex((o) => o.method === method && o.path === path);
    if (overrideIndex >= 0) {
      const [override] = overrides.splice(overrideIndex, 1);
      return json(override?.body, override?.status);
    }

    if (path === '/api/health') return json(HEALTH);
    if (path === '/api/household') {
      if (method === 'PUT') backend.household = body as Household;
      return json(backend.household);
    }
    if (path === '/api/appliances' && method === 'GET') {
      const q = url.searchParams.get('q')?.toLowerCase() ?? '';
      const category = url.searchParams.get('category');
      const mode = url.searchParams.get('mode');
      return json(
        backend.appliances.filter(
          (a) => a.name.toLowerCase().includes(q) && (!category || a.category === category) && (!mode || a.mode === mode),
        ),
      );
    }
    if (path === '/api/appliances' && method === 'POST') {
      const created: Appliance = { ...(body as ApplianceInput), id: nextId++, estimates: ZERO_ESTIMATES, warnings: [] };
      backend.appliances.push(created);
      return json(created, 201);
    }
    const tariffResponse = handleTariffs(method, path, body);
    if (tariffResponse) return tariffResponse;
    const energyResponse = handleEnergy(url);
    if (energyResponse) return energyResponse;
    const optimizationResponse = handleOptimization(method, path, body);
    if (optimizationResponse) return optimizationResponse;
    if (path === '/api/demo' && method === 'POST') return json({ appliances: 9, tariffs: 1 }, 201);

    const match = /^\/api\/appliances\/(\d+)$/.exec(path);
    if (match) {
      const id = Number(match[1]);
      const index = backend.appliances.findIndex((a) => a.id === id);
      const existing = backend.appliances[index];
      if (!existing) return notFound();
      if (method === 'DELETE') {
        backend.appliances.splice(index, 1);
        return json(null, 204);
      }
      if (method === 'PUT') {
        const updated: Appliance = { ...existing, ...(body as ApplianceInput) };
        backend.appliances[index] = updated;
        return json(updated);
      }
      return json(existing);
    }
    return notFound();
  }

  function handleTariffs(method: string, path: string, body: unknown): Response | null {
    if (path === '/api/tariffs' && method === 'GET') return json(backend.tariffs);
    if (path === '/api/tariffs' && method === 'POST') {
      const created: Tariff = { ...(body as TariffInput), id: nextId++, is_active: backend.tariffs.length === 0 };
      backend.tariffs.push(created);
      return json(created, 201);
    }
    const match = /^\/api\/tariffs\/(\d+)(\/activate)?$/.exec(path);
    if (!match) return null;
    const id = Number(match[1]);
    const existing = backend.tariffs.find((t) => t.id === id);
    if (!existing) return notFound();
    if (match[2] && method === 'POST') {
      backend.tariffs = backend.tariffs.map((t) => ({ ...t, is_active: t.id === id }));
      return json({ ...existing, is_active: true });
    }
    if (method === 'DELETE') {
      backend.tariffs = backend.tariffs.filter((t) => t.id !== id);
      return json(null, 204);
    }
    if (method === 'PUT') {
      const updated = { ...existing, ...(body as TariffInput) };
      backend.tariffs = backend.tariffs.map((t) => (t.id === id ? updated : t));
      return json(updated);
    }
    return json(existing);
  }

  function handleOptimization(method: string, path: string, body: unknown): Response | null {
    if (path === '/api/optimization/run' && method === 'POST') {
      if (!backend.solve) return notFound();
      const run = { ...backend.solve(body as OptimizationRequest), id: nextId++ };
      backend.runs.push(run);
      return json(run, 201);
    }
    if (path === '/api/optimization/history') {
      return json(
        [...backend.runs].reverse().map((r) => ({
          id: r.id,
          created_at: r.created_at,
          priority: r.priority,
          status: r.status,
          schedule_valid: r.schedule_valid,
          solve_time_ms: r.solve_time_ms,
          moved_count: r.items.filter((i) => i.moved).length,
          baseline_bill: r.baseline.monthly_bill,
          optimized_bill: r.optimized?.monthly_bill ?? null,
          baseline_peak_kw: r.baseline.peak_kw,
          optimized_peak_kw: r.optimized?.peak_kw ?? null,
        })),
      );
    }
    const match = /^\/api\/optimization\/(\d+)$/.exec(path);
    if (!match) return null;
    const run = backend.runs.find((r) => r.id === Number(match[1]));
    return run ? json(run) : notFound();
  }

  function handleEnergy(url: URL): Response | null {
    const path = url.pathname;
    if (path === '/api/peak-load/analysis') {
      const peak = backend.energy.peak;
      if (!peak) return notFound();
      const weekday = url.searchParams.get('weekday');
      return json(typeof peak === 'function' ? peak(weekday === null ? null : Number(weekday)) : peak);
    }
    const fixtures: Record<string, unknown> = {
      '/api/energy/report': backend.energy.report,
      '/api/energy/hourly-profile': backend.energy.hourly,
      '/api/energy/monthly': backend.energy.monthly,
      '/api/energy/bill': backend.energy.bill,
    };
    if (!(path in fixtures)) return null;
    return fixtures[path] === undefined ? notFound() : json(fixtures[path]);
  }

  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET';
      const body: unknown = init?.body ? JSON.parse(init.body as string) : undefined;
      const url = new URL(input);
      backend.requests.push({ method, path: url.pathname + url.search, body });
      return handle(method, url, body);
    }),
  );
  return backend;
}
