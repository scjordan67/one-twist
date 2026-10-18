import katex from 'katex';
import 'katex/dist/katex.min.css';

interface MathProps {
  latex: string;
  display?: boolean;
}

export function Math({ latex, display = false }: MathProps) {
  try {
    const html = katex.renderToString(latex, {
      displayMode: display,
      throwOnError: true,
      trust: false,
      strict: 'error',
      maxExpand: 200,
    });
    return <span className="math" dangerouslySetInnerHTML={{ __html: html }} />;
  } catch {
    return <span role="alert">This formula could not be rendered.</span>;
  }
}
