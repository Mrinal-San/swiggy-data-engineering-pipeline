import { Link } from 'react-router-dom';
export default function NotFoundPage() { return <section className="empty-page"><span>404</span><h1>Page not found</h1><p>The page you requested is not available.</p><Link className="primary-button" to="/">Back to dashboard</Link></section>; }
