let pending: ReturnType<typeof setTimeout> | undefined;

/** Scrolls to the element with this id once it has rendered (data may still be loading), then briefly highlights it. */
export function scrollToSection(id: string, tries = 30): void {
  clearTimeout(pending);
  const el = document.getElementById(id);
  if (!el) {
    if (tries > 0) pending = setTimeout(() => scrollToSection(id, tries - 1), 100);
    return;
  }
  const smooth = !matchMedia('(prefers-reduced-motion: reduce)').matches;
  el.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'start' });
  el.classList.remove('cn-flash');
  void el.offsetWidth; // restart the animation if it is already running
  el.classList.add('cn-flash');
  setTimeout(() => el.classList.remove('cn-flash'), 1900);
}
