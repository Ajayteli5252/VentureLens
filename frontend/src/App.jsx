import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Header from './components/Header';
import LandingPage from './pages/LandingPage';
import LiveValidationPage from './pages/LiveValidationPage';
import FinalResultPage from './pages/FinalResultPage';
import FullReportPage from './pages/FullReportPage';
import FollowUpChatPage from './pages/FollowUpChatPage';
import AgentDetailPage from './pages/AgentDetailPage';
import './index.css';

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <Header />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/validate/:sessionId" element={<LiveValidationPage />} />
            <Route path="/result/:sessionId" element={<FinalResultPage />} />
            <Route path="/report/:sessionId" element={<FullReportPage />} />
            <Route path="/chat/:sessionId" element={<FollowUpChatPage />} />
            <Route path="/agent/:sessionId/:agent" element={<AgentDetailPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
