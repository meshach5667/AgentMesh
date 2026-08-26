import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card';
import { formatCurrency } from '../../lib/utils';

export function WalletBalance({ balance, currency }: { balance: number, currency: string }) {
  return (
    <Card className="bg-gradient-to-br from-blue-900/40 to-gray-900 border-blue-500/20">
      <CardHeader>
        <CardTitle className="text-gray-400 text-sm uppercase">Available Balance</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-4xl font-bold">{formatCurrency(balance, currency)}</div>
      </CardContent>
    </Card>
  );
}
