import React from 'react';
import { render, screen } from '@testing-library/react';
import fs from 'fs';
import path from 'path';
import { Sidebar, customerSections, operatorSections, providerSections } from './Sidebar';

let pathname = '/provider/nodes/register';
let role = 'provider';
jest.mock('next/navigation', () => ({ usePathname: () => pathname }));
jest.mock('../../hooks/useAuth', () => ({ useAuth: () => ({ user: { role, email: 'p@example.com' }, logout: jest.fn() }) }));
jest.mock('@/providers/ThemeProvider', () => ({ useTheme: () => ({ theme: 'dark', toggleTheme: jest.fn() }) }));

describe('Sidebar', () => {
  it('shows provider links and marks only the most specific match as current', () => {
    render(<Sidebar />);
    expect(screen.getByText('My Nodes')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Add a Machine' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: 'My Nodes' })).not.toHaveAttribute('aria-current');
  });

  it('shows operator links for admins, grouped, and only pages that exist', () => {
    role = 'admin';
    pathname = '/operator';
    render(<Sidebar />);
    expect(screen.getByText('Audit Log')).toBeInTheDocument();
    expect(screen.getByText('Partners')).toBeInTheDocument();
    expect(screen.queryByText('Finance')).toBeNull();
    expect(screen.getByText('Admin')).toBeInTheDocument();
    expect(screen.queryByText('Network Map')).toBeNull();
  });

  it('shows AI Deploy to customers without a coming-soon badge', () => {
    role = 'customer';
    pathname = '/customer';
    render(<Sidebar />);
    expect(screen.getByRole('link', { name: /AI Deploy/ })).not.toHaveTextContent('Soon');
  });

  it('links only to pages that exist, and never to retired payment pages', () => {
    const hrefs = [...customerSections, ...providerSections, ...operatorSections].flatMap((sec) => sec.links.map((l) => l.href));
    for (const href of hrefs) {
      expect(fs.existsSync(path.join(__dirname, '../../app', href, 'page.tsx'))).toBe(true);
      expect(href).not.toMatch(/transactions|earnings|payouts|refunds|revenue|reconciliation|subscription|pricing/);
      expect(href).not.toMatch(/commission|checkout/);
    }
  });
});
