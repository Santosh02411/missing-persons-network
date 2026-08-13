import { Route, BrowserRouter as Router, Routes, useLocation } from "react-router-dom";
import EmailVerificationBanner from "./components/EmailVerificationBanner";
import Masthead from "./components/Masthead";
import ProtectedRoute from "./components/ProtectedRoute";
import { AuthProvider } from "./context/AuthContext";
import AccountSecurity from "./pages/AccountSecurity";
import AdminAnalytics from "./pages/AdminAnalytics";
import AdminDashboard from "./pages/AdminDashboard";
import AuthorityDashboard from "./pages/AuthorityDashboard";
import CaseCreate from "./pages/CaseCreate";
import CaseDetail from "./pages/CaseDetail";
import CaseList from "./pages/CaseList";
import CitizenDashboard from "./pages/CitizenDashboard";
import ForgotPassword from "./pages/ForgotPassword";
import Login from "./pages/Login";
import NotFound from "./pages/NotFound";
import Profile from "./pages/Profile";
import Register from "./pages/Register";
import ResetPassword from "./pages/ResetPassword";
import SuccessStories from "./pages/SuccessStories";
import VerifyEmail from "./pages/VerifyEmail";

function AnimatedRoutes() {
  const location = useLocation();
  return (
    <div key={location.pathname} className="page-enter">
      <Routes location={location}>
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <CaseList />
            </ProtectedRoute>
          }
        />
        <Route
          path="/reunited"
          element={
            <ProtectedRoute>
              <SuccessStories />
            </ProtectedRoute>
          }
        />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route
          path="/cases/:caseId"
          element={
            <ProtectedRoute>
              <CaseDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/cases/new"
          element={
            <ProtectedRoute>
              <CaseCreate />
            </ProtectedRoute>
          }
        />
        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <Profile />
            </ProtectedRoute>
          }
        />
        <Route
          path="/account/security"
          element={
            <ProtectedRoute>
              <AccountSecurity />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/citizen"
          element={
            <ProtectedRoute allowedRoles={["reporter"]}>
              <CitizenDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/authority"
          element={
            <ProtectedRoute allowedRoles={["authority", "admin"]}>
              <AuthorityDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/admin"
          element={
            <ProtectedRoute allowedRoles={["admin"]}>
              <AdminDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/admin/analytics"
          element={
            <ProtectedRoute allowedRoles={["admin"]}>
              <AdminAnalytics />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </div>
  );
}

export default function App() {
  return (
    <Router>
      <AuthProvider>
        <div className="app-shell">
          <Masthead />
          <EmailVerificationBanner />
          <main>
            <AnimatedRoutes />
          </main>
        </div>
      </AuthProvider>
    </Router>
  );
}
