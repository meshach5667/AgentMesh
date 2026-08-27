"use client";
import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../../hooks/useAuth';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';

export function RegisterForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<'provider' | 'customer'>('provider');
  const { login } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login(role);
      router.push(role === 'provider' ? '/provider' : '/customer');
    } catch (error) {
      console.error(error);
    }
  };

  return (
    <Card className="w-full max-w-md mx-auto border-border bg-background shadow-lg">
      <CardHeader>
        <CardTitle className="text-2xl text-center">Join AgentMesh</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm text-muted-foreground">Email</label>
            <Input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required className="bg-secondary/20" />
          </div>
          <div className="space-y-2">
             <label className="text-sm text-muted-foreground">Password</label>
            <Input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required className="bg-secondary/20" />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-muted-foreground">Join As</label>
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

          <Button type="submit" className="w-full bg-blue-600 hover:bg-blue-700 text-white mt-4">Register</Button>
        </form>
      </CardContent>
    </Card>
  );
}
