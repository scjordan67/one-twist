import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { Math } from './Math';

afterEach(cleanup);

describe('Math', () => {
  it('renders a real integral using KaTeX HTML and accessible MathML', () => {
    const { container } = render(<Math latex={String.raw`\int_0^{1/2}\frac{1}{1-x}\,\mathrm{d}x`} display />);
    expect(container.querySelector('.katex-html')).not.toBeNull();
    expect(container.querySelector('math')).not.toBeNull();
    expect(container.querySelector('annotation')?.textContent).toContain(String.raw`\int_0`);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('reports invalid formulas instead of pretending plain text is rendered math', () => {
    render(<Math latex={String.raw`\notARealCommand{x}`} />);
    expect(screen.getByRole('alert').textContent).toContain('could not be rendered');
  });
});
