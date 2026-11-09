import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { BackendProvider } from '@/api/BackendProvider';
import { TEST_CONNECTION } from '@/test/render';

describe('BackendProvider', () => {
  it('shows the startup screen until the backend is ready, then the app', async () => {
    let resolve: (value: typeof TEST_CONNECTION) => void = () => {};
    const connect = () => new Promise<typeof TEST_CONNECTION>((r) => (resolve = r));

    render(
      <BackendProvider connect={connect}>
        <p>App content</p>
      </BackendProvider>,
    );

    expect(screen.getByText('Starting PowerShift')).toBeInTheDocument();
    expect(screen.queryByText('App content')).not.toBeInTheDocument();

    resolve(TEST_CONNECTION);
    expect(await screen.findByText('App content')).toBeInTheDocument();
  });

  it('shows the failure message and retries when asked', async () => {
    const connect = vi
      .fn()
      .mockRejectedValueOnce(new Error('Backend exited with code 1'))
      .mockResolvedValueOnce(TEST_CONNECTION);

    render(
      <BackendProvider connect={connect}>
        <p>App content</p>
      </BackendProvider>,
    );

    expect(await screen.findByRole('alert')).toHaveTextContent('Backend exited with code 1');

    await userEvent.click(screen.getByRole('button', { name: 'Try again' }));

    expect(await screen.findByText('App content')).toBeInTheDocument();
    expect(connect).toHaveBeenCalledTimes(2);
  });
});
