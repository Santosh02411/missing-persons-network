import { Route, BrowserRouter as Router, Routes } from "react-router-dom";
import Masthead from "./components/Masthead";
import ProtectedRoute from "./components/ProtectedRoute";
import { AuthProvider } from "./context/AuthContext";
import CaseCreate from "./pages/CaseCreate";
import CaseDetail from "./pages/CaseDetail";
import CaseList from "./pages/CaseList";
import Login from "./pages/Login";
import NotFound from "./pages/NotFound";
import Register from "./pages/Register";

export default function App() {
  return (
    <Router>
      <AuthProvider>
        <div className="app-shell">
          <Masthead />
          <main>
            <Routes>
              <Route path="/" element={<CaseList />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/cases/:caseId" element={<CaseDetail />} />
              <Route
                path="/cases/new"
                element={
                  <ProtectedRoute>
                    <CaseCreate />
                  </ProtectedRoute>
                }
              />
              {/* Authority/admin dashboards land in the next frontend pass --
                  see docs/FEATURE_TICKET_LIST.md TICKET-606/607. Claiming a
                  case and changing its status already work from the case
                  detail page itself in the meantime. */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </main>
        </div>
      </AuthProvider>
    </Router>
  );
}
