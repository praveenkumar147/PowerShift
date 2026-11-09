import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { ThemeProvider } from '@/app/theme/ThemeProvider';
import { ThemeSwitcher } from '@/app/theme/ThemeSwitcher';

function renderSwitcher() {
  return render(
    <ThemeProvider>
      <ThemeSwitcher />
    </ThemeProvider>,
  );
}

describe('ThemeSwitcher', () => {
  it('defaults to the system theme', () => {
    renderSwitcher();
    expect(screen.getByRole('radio', { name: 'System' })).toHaveAttribute('aria-checked', 'true');
  });

  it('applies dark mode to the document and remembers the choice', async () => {
    renderSwitcher();

    await userEvent.click(screen.getByRole('radio', { name: 'Dark' }));

    expect(document.documentElement).toHaveClass('dark');
    expect(localStorage.getItem('powershift.theme')).toBe('dark');
  });

  it('restores a stored preference on startup', () => {
    localStorage.setItem('powershift.theme', 'light');
    renderSwitcher();

    expect(screen.getByRole('radio', { name: 'Light' })).toHaveAttribute('aria-checked', 'true');
    expect(document.documentElement).not.toHaveClass('dark');
  });
});
