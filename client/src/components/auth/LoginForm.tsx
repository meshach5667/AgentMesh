'use client';

import React, { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '../ui/card';
import { useRouter } from 'next/navigation';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';

export function LoginForm() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<'provider' | 'customer'>('provider');
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    login(role); // mocked
    router.push(role === 'provider' ? '/provider' : '/customer');
  };

  return (
    <Card className="w-full max-w-md mx-auto mt-20 border-border bg-background shadow-lg">
      <CardHeader>
        <CardTitle className="text-2xl text-center">Login to AgentMesh</CardTitle>
      </CardHeader>
      <form onSubmit={handleSubmit}>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm text-muted-foreground">Email</label>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className="bg-secondary/20" />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-muted-foreground">Password</label>
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required className="bg-secondary/20" />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-muted-foreground">Login As</label>
            <Select value={role} onValueChange={(value) => setRole(value as 'provider' | 'customer')}>
              <SelectTrigger className="bg-secondary/20">
                <SelectValue placeholder="Select Role" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="provider">Compute Provider</SelectItem>
                <SelectItem value="customer">Model Customer</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
        <CardFooter>
          <Button type="submit" className="w-full bg-blue-600 hover:bg-blue-700 text-white">Sign In</Button>
        </CardFooter>
      </form>
    </Card>
  );
}
