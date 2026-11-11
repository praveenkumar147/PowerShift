/**
 * The atmosphere behind every page: two soft lime glows drifting very slowly and a faint grid.
 * It is decoration only: hidden from assistive technology, never intercepts the mouse, and sits
 * behind the content. All the styling lives in index.css (.ps-backdrop).
 */
export function AppBackdrop() {
  return (
    <div aria-hidden className="ps-backdrop">
      <div className="ps-glow ps-glow-a" />
      <div className="ps-glow ps-glow-b" />
    </div>
  );
}
