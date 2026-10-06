import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Subscriptions from "./pages/Subscriptions";
import SubscriptionDetail from "./pages/SubscriptionDetail";
import Invoices from "./pages/Invoices";
import Dunning from "./pages/Dunning";

const link = ({ isActive }) =>
  `rounded-lg px-3 py-1.5 text-sm font-medium ${
    isActive ? "bg-indigo-50 text-indigo-700" : "text-gray-600 hover:bg-gray-100"
  }`;

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        <header className="border-b bg-white px-8 py-3">
          <div className="mx-auto flex max-w-6xl items-center gap-6">
            <h1 className="text-lg font-bold text-gray-900">Billing</h1>
            <nav className="flex gap-1">
              <NavLink to="/" end className={link}>Dashboard</NavLink>
              <NavLink to="/subscriptions" className={link}>Subscriptions</NavLink>
              <NavLink to="/invoices" className={link}>Invoices</NavLink>
              <NavLink to="/dunning" className={link}>Dunning</NavLink>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-6xl p-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/subscriptions" element={<Subscriptions />} />
            <Route path="/subscriptions/:id" element={<SubscriptionDetail />} />
            <Route path="/invoices" element={<Invoices />} />
            <Route path="/dunning" element={<Dunning />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}