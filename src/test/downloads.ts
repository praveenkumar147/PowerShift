import { vi } from 'vitest';

/**
 * jsdom cannot download files. This replaces the object-URL and anchor-click steps of
 * `saveFile` and records what would have been saved, so tests can assert on it.
 */
export function captureDownloads(): { filenames: string[]; blobs: Blob[] } {
  const captured = { filenames: [] as string[], blobs: [] as Blob[] };
  URL.createObjectURL = vi.fn((blob: Blob | MediaSource) => {
    captured.blobs.push(blob as Blob);
    return 'blob:powershift-test';
  });
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
    captured.filenames.push(this.download);
  });
  return captured;
}
