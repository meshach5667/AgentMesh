import React from 'react';
import { render, screen } from '@testing-library/react';
import { Sidebar } from './Sidebar';

// Mock Next.js hooks
jest.mock('next/navigation', () => ({
  usePathname: () => '/',
}));

// Mock Auth hook
jest.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ user: { role: 'provider' } }),
}));

// Mock utils
jest.mock('../../lib/utils', () => ({
  cn: (...args: unknown[]) => args.filter(Boolean).join(' '),
}), { virtual: true });

describe('Sidebar', () => {
  it('renders provider links', () => {
    render(<Sidebar />);
    expect(screen.getByText('Overview')).toBeInTheDocument();
    expect(screen.getByText('My Nodes')).toBeInTheDocument();
  });
});
