'use client';

import { useState } from 'react';
import toast from 'react-hot-toast';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { PriceListForm } from '@/components/pricing/PriceListForm';
import { useDefaultPrices, useSetDefaultPrices } from '@/hooks/useNodes';
import { errorMessage } from '@/lib/errors';

/** The prices every machine a provider enrolls starts with. */
export function DefaultPricesCard() {
  const { data, isLoading, error } = useDefaultPrices();
  const save = useSetDefaultPrices();
  const [applyToExisting, setApplyToExisting] = useState(false);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Default machine prices</CardTitle>
        <CardDescription>
          Each machine you enroll starts with these prices; change any machine&apos;s prices later on its own page.
          Without defaults, new machines are free until you price them.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : error ? (
          <p role="alert" className="text-sm text-destructive">
            {errorMessage(error)}
          </p>
        ) : (
          <PriceListForm
            idPrefix="default"
            initial={data?.prices ?? null}
            submitLabel="Save defaults"
            pending={save.isPending}
            onSubmit={(prices) =>
              save
                .mutateAsync({ ...prices, apply_to_existing: applyToExisting })
                .then((r) =>
                  toast.success(
                    applyToExisting ? `Defaults saved and published on ${r.updated_machines} machine(s)` : 'Defaults saved',
                  ),
                )
                .catch((e) => toast.error(errorMessage(e)))
            }
          >
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={applyToExisting} onChange={(e) => setApplyToExisting(e.target.checked)} />
              Also publish these prices on all my active machines now
            </label>
          </PriceListForm>
        )}
      </CardContent>
    </Card>
  );
}
