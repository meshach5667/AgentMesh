'use client';
import React, { useState } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';

export function DepositForm({ onDeposit }: { onDeposit: (amount: number) => void }) {
  const [amount, setAmount] = useState('');
  return (
    <div className="flex gap-2">
      <Input type="number" placeholder="Amount" value={amount} onChange={e => setAmount(e.target.value)} />
      <Button onClick={() => onDeposit(Number(amount))}>Deposit</Button>
    </div>
  );
}
