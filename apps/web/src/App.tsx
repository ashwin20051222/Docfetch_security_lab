import { Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { DashboardPage } from "./pages/DashboardPage";
import { FindingsPage } from "./pages/FindingsPage";
import { LabPage } from "./pages/LabPage";
import { RetrievePage } from "./pages/RetrievePage";
import { SettingsPage } from "./pages/SettingsPage";
import { TargetsPage } from "./pages/TargetsPage";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="retrieve" element={<RetrievePage />} />
        <Route path="lab" element={<LabPage />} />
        <Route path="targets" element={<TargetsPage />} />
        <Route path="findings" element={<FindingsPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}