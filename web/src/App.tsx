import { useEffect } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import AiReadiness from './pages/AiReadiness';

// The copied components link to /contact, which lived on the main Codenix
// site. Send those clicks there instead of showing a blank page.
const CONTACT_URL = import.meta.env.VITE_CONTACT_URL || 'https://www.codenixlabs.com/contact';

function ExternalRedirect({ to }: { to: string }) {
  useEffect(() => {
    window.location.replace(to);
  }, [to]);
  return null;
}

function App() {
  return (
    <div className="min-h-screen text-white bg-background">
      <main id="main-content">
        <Routes>
          <Route path="/" element={<AiReadiness />} />
          <Route path="/ai-readiness" element={<AiReadiness />} />
          <Route path="/contact" element={<ExternalRedirect to={CONTACT_URL} />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
