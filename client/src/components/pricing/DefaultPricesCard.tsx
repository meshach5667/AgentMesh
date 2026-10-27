'use client';

import { useState } from 'react';
import toast from 'react-hot-toast';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { PriceListForm } from '@/components/pricing/PriceListForm';
import { usePricing } from '@/hooks/useBilling';
import { useDefaultPrices, useSetDefaultPrices } from '@/hooks/useNodes';
import { errorMessage } from '@/lib/errors';

/** The prices every machine a provider enrolls starts with. */
export function DefaultPricesCard() {
  const { data, isLoading } = useDefaultPrices();
  const pricing = usePricing();
  const save = useSetDefaultPrices();
  const [applyToExisting, setApplyToExisting] = useState(false);
  const network = pricing.data?.current ?? null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Default machine prices</CardTitle>
        <CardDescription>
          Each machine you enroll starts with these prices; change any machine&apos;s prices later on its own page.
          Without defaults, a new machine charges the network prices until you set its own.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading || pricing.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : (
          <PriceListForm
            idPrefix="default"
            initial={data?.prices ?? network}
            currency={data?.currency ?? pricing.data?.currency ?? 'NGN'}
            commissionRate={network?.platform_fee_rate ?? pricing.data?.default_platform_fee_rate ?? null}
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
