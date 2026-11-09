import { Construction } from 'lucide-react';
import type { NavItem } from '@/app/navigation';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageHeader } from '@/components/ui/PageHeader';

/**
 * Honest placeholder for a module that is not built yet. It shows no fake data
 * and no buttons; each one is replaced by the real page in its stage.
 */
export function ModulePendingPage({ item }: { item: NavItem }) {
  return (
    <>
      <PageHeader title={item.label} description={item.description} />
      <EmptyState
        icon={Construction}
        title="Not built yet"
        message={`This module is planned for development Stage ${item.stage}.`}
      />
    </>
  );
}
