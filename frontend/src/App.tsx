import { Link, NavLink, Route, Routes } from 'react-router-dom';
import { Math } from './components/Math';
import { ExplorerProvider } from './explorer/ExplorerContext';
import { BoundaryExplorer, MethodInspector, ProblemExplorer } from './explorer/Pages';
import { ChallengeInterface } from './challenges/ChallengeInterface';

const navigation = [
  ['/', 'Home'], ['/problems', 'Problem Explorer'], ['/methods', 'Method Inspector'],
  ['/boundaries', 'Boundary Explorer'], ['/challenges', 'Challenge Interface'],
] as const;

function Home() {
  return <section className="hero">
    <p className="eyebrow">MATHEMATICAL METHOD BOUNDARY EXPLORER</p>
    <h1>Change one condition.<br />Discover why it matters.</h1>
    <p className="lead">Explore the assumptions that make a mathematical method work, one condition at a time.</p>
    <Link className="button" to="/problems">Explore the example problems <span aria-hidden="true">→</span></Link>
    <div className="formula-card"><span className="eyebrow">A BOUNDARY TO EXPLORE</span>
      <Math latex={String.raw`\int_0^b \frac{1}{1-x}\,\mathrm{d}x`} display />
      <p>What changes when the upper endpoint reaches a singularity?</p>
    </div>
    <div className="mode-grid">
      <article><span>01 / FIND THE FLAW</span><h2>Inspect a step</h2><p>Locate the first unsupported transformation.</p></article>
      <article><span>02 / BREAK THE METHOD</span><h2>Change a condition</h2><p>Explore the boundary of an assumption.</p></article>
      <article><span>03 / JUDGE THE AI</span><h2>Review a derivation</h2><p>Check the reasoning behind an answer.</p></article>
    </div>
    <p className="phase-note"><Link to="/challenges">Practice with Find the Flaw, Break the Method and Judge the AI →</Link></p>
  </section>;
}
function Placeholder({ title, description }: { title: string; description: string }) {
  return <section><p className="eyebrow">COMING IN A LATER PHASE</p><h1>{title}</h1><p className="lead">{description}</p>
    <Link to="/problems">Browse the current examples →</Link></section>;
}
export function App() {
  return <ExplorerProvider><div className="app-shell">
    <header><Link className="brand" to="/">One<span>↝</span>Twist</Link><span className="badge">INTERACTIVE EXPLORER</span></header>
    <nav aria-label="Main navigation">{navigation.map(([path, label]) =>
      <NavLink key={path} to={path} end={path === '/'}>{label}</NavLink>,
    )}</nav>
    <main><Routes>
      <Route path="/" element={<Home />} />
      <Route path="/problems" element={<ProblemExplorer />} />
      <Route path="/methods" element={<MethodInspector />} />
      <Route path="/boundaries" element={<BoundaryExplorer />} />
      <Route path="/challenges" element={<ChallengeInterface />} />
      <Route path="*" element={<Placeholder title="Page not found" description="Choose a page from the navigation to continue." />} />
    </Routes></main>
    <footer>One condition. One assumption. A clearer understanding.</footer>
  </div></ExplorerProvider>;
}
