import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import WelcomePage from './pages/WelcomePage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import ApiSettingsPage from './pages/ApiSettingsPage';
import CreditsPage from './pages/CreditsPage';
import ProfilePage from './pages/ProfilePage';
import WorkspacePage from './pages/WorkspacePage';
import SessionDetailPage from './pages/SessionDetailPage';
import AdminDashboard from './pages/AdminDashboard';
import WordFormatterPage from './pages/WordFormatterPage';
import SpecGeneratorPage from './pages/SpecGeneratorPage';
import ArticlePreprocessorPage from './pages/ArticlePreprocessorPage';
import FormatCheckerPage from './pages/FormatCheckerPage';
import AuthGuard from './components/AuthGuard';
import './index.css';

function App() {
  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 3000,
          style: {
            background: '#363636',
            color: '#fff',
          },
          success: {
            duration: 3000,
            iconTheme: {
              primary: '#10B981',
              secondary: '#fff',
            },
          },
          error: {
            duration: 4000,
            iconTheme: {
              primary: '#EF4444',
              secondary: '#fff',
            },
          },
        }}
      />
      
      <Routes>
        <Route path="/" element={<WelcomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/admin" element={<AdminDashboard />} />
        
        <Route
          path="/workspace"
          element={
            <AuthGuard>
              <WorkspacePage />
            </AuthGuard>
          }
        />

        <Route
          path="/profile"
          element={
            <AuthGuard>
              <ProfilePage />
            </AuthGuard>
          }
        />

        <Route
          path="/api-settings"
          element={
            <AuthGuard>
              <ApiSettingsPage />
            </AuthGuard>
          }
        />

        <Route
          path="/credits"
          element={
            <AuthGuard>
              <CreditsPage />
            </AuthGuard>
          }
        />
        
        <Route
          path="/session/:sessionId"
          element={
            <AuthGuard>
              <SessionDetailPage />
            </AuthGuard>
          }
        />

        <Route
          path="/word-formatter"
          element={
            <AuthGuard>
              <WordFormatterPage />
            </AuthGuard>
          }
        />

        <Route
          path="/spec-generator"
          element={
            <AuthGuard>
              <SpecGeneratorPage />
            </AuthGuard>
          }
        />

        <Route
          path="/article-preprocessor"
          element={
            <AuthGuard>
              <ArticlePreprocessorPage />
            </AuthGuard>
          }
        />

        <Route
          path="/format-checker"
          element={
            <AuthGuard>
              <FormatCheckerPage />
            </AuthGuard>
          }
        />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
